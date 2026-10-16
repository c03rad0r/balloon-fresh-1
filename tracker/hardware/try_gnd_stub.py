#!/usr/bin/env python3
"""Can each J_W* GND pad reach the F.Cu GND plane with a SHORT STUB instead of a zone island?

WHY NOT THE ISLAND. The approved zone-island fix was proven geometrically impossible: J_W* pad 2 is a
4.00 x 1.20 mm land whose /W<n>_SOLAR_* neighbours sit 1.80 mm away centre-to-centre, i.e. 0.60 mm
edge-to-edge, so an island wide enough to be useful cannot also clear them.

WHY A STUB IS DIFFERENT. pad 2 is an SMD land on F.Cu with NO drill. The F.Cu GND plane is on the SAME
layer and already surrounds the socket area -- it simply does not touch this pad because of the 0.20 mm
clearance to the neighbouring solar/cut-sense copper. A copper STUB from the pad edge outward to the
nearest plane copper needs no via and no island, only a clear corridor of a few tenths of a mm.

This script, for each J_W socket, samples directions around pad 2 and reports the shortest direction
in which a stub of the given width reaches the F.Cu GND fill while keeping the clearance floor to
every foreign pad and track.

Read-only.

Usage: try_gnd_stub.py <board.kicad_pcb> [--width-mm 0.30]
"""
import math
import sys

import pcbnew

CLEAR = 0.20
STUB_W = 0.30
MAX_LEN = 6.0
STEP = 0.05


def mm(v):
    return pcbnew.ToMM(v)


def gnd_fill(board, layer):
    for z in board.Zones():
        if z.GetNetname() == "GND" and z.GetLayer() == layer:
            return z.GetFilledPolysList(layer)
    return None


def pad_boxes(board):
    out = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            r = p.GetBoundingBox()
            out.append((fp.GetReference(), str(p.GetNumber()), p.GetNetname(),
                        mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom())))
    return out


def seg_clear(seg, width, own_net, obs, clearance, ignore_ref=None):
    half = width / 2.0
    (ax, ay), (bx, by) = seg
    vx, vy = bx - ax, by - ay
    worst = None
    for ref, num, net, x0, y0, x1, y1 in obs:
        if net == own_net:
            continue
        if ignore_ref and ref == ignore_ref:
            continue
        for i in range(31):
            t = i / 30.0
            px, py = ax + t * vx, ay + t * vy
            dx = max(0.0, max(x0 - px, px - x1))
            dy = max(0.0, max(y0 - py, py - y1))
            d = math.hypot(dx, dy)
            need = clearance + half
            if d < need:
                pen = need - d
                if worst is None or pen > worst[0]:
                    worst = (pen, f"{ref}.{num} {net}")
    return worst


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"
    width = STUB_W
    if "--width-mm" in sys.argv:
        width = float(sys.argv[sys.argv.index("--width-mm") + 1])
    b = pcbnew.LoadBoard(path)
    fill = gnd_fill(b, pcbnew.F_Cu)
    if fill is None:
        print("no F.Cu GND zone")
        return 1
    obs = pad_boxes(b)
    print(f"board: {path}\nstub width {width} mm, clearance {CLEAR} mm, search out to {MAX_LEN} mm\n")

    results = {}
    for ref in ("J_W1", "J_W2", "J_W3", "J_W4"):
        fp = b.FindFootprintByReference(ref)
        if fp is None:
            continue
        pad2 = None
        for p in fp.Pads():
            if p.GetNetname() == "GND":
                pad2 = p
                break
        if pad2 is None:
            print(f"  {ref}: no GND pad")
            continue
        c = pad2.GetPosition()
        cx, cy = mm(c.x), mm(c.y)
        s = pad2.GetSize()
        hw, hh = mm(s.x) / 2.0, mm(s.y) / 2.0
        best = None
        for deg in range(0, 360, 5):
            r = math.radians(deg)
            ux, uy = math.cos(r), math.sin(r)
            # leave from the pad EDGE in that direction
            t_edge = min(abs(hw / ux) if abs(ux) > 1e-9 else 1e9,
                         abs(hh / uy) if abs(uy) > 1e-9 else 1e9)
            sx, sy = cx + ux * t_edge, cy + uy * t_edge
            t = 0.0
            while t < MAX_LEN:
                t += STEP
                ex, ey = sx + ux * t, sy + uy * t
                if not (0.5 < ex < 69.5 and 0.5 < ey < 69.5):
                    break
                worst = seg_clear(((sx, sy), (ex, ey)), width, "GND", obs, CLEAR, ignore_ref=ref)
                if worst:
                    break
                inside = fill.Contains(pcbnew.VECTOR2I(int(ex * 1e6), int(ey * 1e6)))
                if inside:
                    if best is None or t < best[0]:
                        best = (t, deg, (sx, sy), (ex, ey))
                    break
        if best:
            t, deg, sp, ep = best
            results[ref] = (t, deg, sp, ep)
            print(f"  {ref}: STUB OK  length {t:.2f} mm at {deg} deg   "
                  f"from ({sp[0]:.2f},{sp[1]:.2f}) to ({ep[0]:.2f},{ep[1]:.2f})")
        else:
            print(f"  {ref}: NO STUB FOUND within {MAX_LEN} mm of the pad edge at {width} mm width")
    print()
    if len(results) == 4:
        print("ALL FOUR sockets can be stitched with a short stub, no via, no island.")
        print("STUBS FOR A BUILD STEP:")
        for ref, (t, deg, sp, ep) in results.items():
            print(f'    {ref}: ({sp[0]:.2f},{sp[1]:.2f}) -> ({ep[0]:.2f},{ep[1]:.2f})  '
                  f'w={width} mm  ({t:.2f} mm, {deg} deg)')
    else:
        print(f"stubs found for {len(results)}/4 sockets; the rest need their own treatment.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

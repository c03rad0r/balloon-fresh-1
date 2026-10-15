#!/usr/bin/env python3
"""Route /SX1280_RF as a 50-ohm controlled-impedance trace, plus an RF net class to carry the width.

WHY A NET CLASS AND NOT JUST A TRACK. The board declares exactly one net class ("Default", clearance
0.2, track 0.2). If this trace is laid at 0.2 mm the router will reproduce it at 0.2 mm on any future
pass, which on this stackup is 69 ohms -- a 38% error at 2.4 GHz. So the width has to be expressed as
a RULE (an RF net class), consistent with build_hub_board_v9.py's rule R2: no hand-typed geometry.

COMPUTED WIDTH. rf_impedance.py, Wheeler microstrip on the JLCPCB 4-layer stackup
(H=0.21 mm, T=0.035 mm, eps_r=4.1 -- the project file carries NO stackup, so this is the fab default
and is stated as an assumption, not a measurement):
    0.20 mm -> 69.03 ohm      (what every net on this board currently is)
    0.364 mm -> 50.00 ohm     <- target
    0.35 mm -> 51.26 ohm

GEOMETRY CHECK (measured): pad22 is 0.30 x 0.80 mm and its GND neighbours pad21/pad23 sit 0.50 mm
away, so a 0.364 mm trace centred on pad22 leaves 0.318 mm edge clearance against a 0.20 mm floor.
It fits. No via, no layer change.

WHAT THIS DOES NOT DO: it does not move anything, and it does not touch any other net. The three RF
pads are 1.62 mm and 2.96 mm from U4.pad22, so the whole connection is under ~3 mm.

Usage: route_rf_match.py <in.kicad_pcb> <out.kicad_pcb> [--width-mm 0.364]
"""
import math
import sys

import pcbnew

RF_NET = "/SX1280_RF"
RF_CLASS = "RF"
WIDTH_MM = 0.364
VIA_MM, VIA_DRILL_MM = 0.6, 0.3


def mm(v):
    return pcbnew.ToMM(v)


def find_net(board, name):
    for c in range(1, board.GetNetCount()):
        n = board.FindNet(c)
        if n and n.GetNetname() == name:
            return n
    return None


def rf_pads(board):
    out = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == RF_NET:
                c = p.GetPosition()
                out.append((fp.GetReference(), p, mm(c.x), mm(c.y)))
    return out


def add_track(board, net, a_xy, b_xy, width, layer=pcbnew.F_Cu):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I(int(round(a_xy[0] * 1e6)), int(round(a_xy[1] * 1e6))))
    t.SetEnd(pcbnew.VECTOR2I(int(round(b_xy[0] * 1e6)), int(round(b_xy[1] * 1e6))))
    t.SetWidth(int(round(width * 1e6)))
    t.SetLayer(layer)
    t.SetNet(net)
    board.Add(t)
    return t


def segment_clear(board, a_xy, b_xy, width, own_net, clearance):
    """Does a segment of this width clear every foreign pad and track?"""
    half = width / 2.0
    bad = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == own_net:
                continue
            r = p.GetBoundingBox()
            x0, y0, x1, y1 = mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom())
            # sample the segment; a rectangle-vs-segment test via sampling is adequate at this size
            n = 24
            for i in range(n + 1):
                px = a_xy[0] + (b_xy[0] - a_xy[0]) * i / n
                py = a_xy[1] + (b_xy[1] - a_xy[1]) * i / n
                dx = max(0.0, max(x0 - px, px - x1))
                dy = max(0.0, max(y0 - py, py - y1))
                if math.hypot(dx, dy) < clearance + half:
                    bad.append((fp.GetReference(), str(p.GetNumber()), p.GetNetname(),
                                round(math.hypot(dx, dy), 3)))
                    break
    for t in board.GetTracks():
        if t.GetNetname() == own_net:
            continue
        for pt in (t.GetStart(), t.GetEnd()):
            dx = 0.0
            dy = 0.0
            px, py = mm(pt.x), mm(pt.y)
            ax, ay = a_xy
            bx, by = b_xy
            # point to segment distance
            vx, vy = bx - ax, by - ay
            wx, wy = px - ax, py - ay
            L2 = vx * vx + vy * vy
            tt = 0.0 if L2 == 0 else max(0.0, min(1.0, (wx * vx + wy * vy) / L2))
            dx = px - (ax + tt * vx)
            dy = py - (ay + tt * vy)
            if math.hypot(dx, dy) < clearance + half:
                bad.append(("trk", t.GetNetname(), "", round(math.hypot(dx, dy), 3)))
                break
    return bad


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    width = WIDTH_MM
    if "--width-mm" in sys.argv:
        width = float(sys.argv[sys.argv.index("--width-mm") + 1])

    b = pcbnew.LoadBoard(src)
    net = find_net(b, RF_NET)
    if net is None:
        print(f"{RF_NET} not on the board")
        return 1
    pads = rf_pads(b)
    print(f"board: {src}")
    print(f"{RF_NET}: {len(pads)} pads, width target {width} mm")
    for ref, _p, x, y in sorted(pads):
        print(f"  {ref:4} ({x:6.2f},{y:6.2f})")

    # 1. remove any pre-existing tracks on this net so the route is deterministic
    old = [t for t in b.GetTracks() if t.GetNetname() == RF_NET]
    for t in old:
        b.Remove(t)
    print(f"\npre-existing tracks on this net removed: {len(old)}")

    # 2. route every pair. U4's RFIO pad is the hub; connect it to each match element.
    u4 = [(r, p, x, y) for r, p, x, y in pads if r == "U4"]
    others = [(r, p, x, y) for r, p, x, y in pads if r != "U4"]
    if not u4:
        print("no U4 pad on the RF net")
        return 1
    hub = u4[0]
    clear = 0.20     # board minimum
    placed = []
    for ref, _p, x, y in sorted(others):
        seg = ((hub[2], hub[3]), (x, y))
        bad = segment_clear(b, seg[0], seg[1], width, RF_NET, clear)
        if bad:
            print(f"\n  {ref}: direct segment BLOCKED -- first obstruction {bad[0]}")
            # fall back to a two-segment L route via a point offset below the pad row
            mid = ((hub[2] + x) / 2, max(hub[3], y) + 1.0)
            bad2 = (segment_clear(b, seg[0], mid, width, RF_NET, clear)
                    + segment_clear(b, mid, seg[1], width, RF_NET, clear))
            if bad2:
                print(f"     L-route via {mid} also blocked: {bad2[0]}")
                return 1
            print(f"     L-route via {mid} is clear")
            placed.append((seg[0], mid))
            placed.append((mid, seg[1]))
        else:
            print(f"\n  {ref}: direct segment CLEAR at {width} mm")
            placed.append(seg)

    # 3. lay the tracks
    n = 0
    for a, c in placed:
        add_track(b, net, a, c, width, pcbnew.F_Cu)
        n += 1
    print(f"\ntracks added: {n}  (all on F.Cu, {width} mm, no vias)")

    # 4. verify by reading back
    rbt = [t for t in b.GetTracks() if t.GetNetname() == RF_NET]
    tot = sum(math.hypot(mm(t.GetEnd().x) - mm(t.GetStart().x),
                         mm(t.GetEnd().y) - mm(t.GetStart().y)) for t in rbt)
    widths = sorted({round(mm(t.GetWidth()), 3) for t in rbt})
    print(f"read back: {len(rbt)} tracks, total length {tot:.2f} mm, widths {widths}")
    print(f"vias on the net: {sum(1 for t in rbt if t.Type() == pcbnew.PCB_VIA_T)}")

    pcbnew.SaveBoard(dst, b)
    print(f"\nwrote {dst}")
    print(f"\nNOTE: the RF net class was NOT yet added to the project file -- track width is set on the")
    print(f"      tracks themselves. See the commit message for the net-class follow-up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

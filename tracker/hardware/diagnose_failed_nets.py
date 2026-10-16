#!/usr/bin/env python3
"""What blocks /SX1280_MOSI and /SX1280_SCK on the routed board?

THE ROUTER'S OWN REPORT: failed_single = ['/SX1280_MOSI', '/SX1280_SCK'], escalations 0,
min_clearance_used 0.20. Both are U1 <-> U4 SPI lines, and each already carries ONE partial track.

GEOMETRY, which is the thing to look at before any sweep:
    U1.8  /SX1280_MOSI  (49.95, 11.84)   <- U1's WEST edge (U1 spans x 48.9..68.5)
    U4.17 /SX1280_MOSI  (55.15, 25.25)   <- U4's EAST edge  (U4 spans x 49.7..55.8)
    U1.22 /SX1280_SCK   (60.60, 20.71)   <- U1's EAST/south edge
    U4.18 /SX1280_SCK   (55.15, 24.75)   <- U4's EAST edge

So MOSI must leave U1 at the far WEST, run ~14 mm south, and re-enter U4 at the far EAST -- the long way
round both footprints. That is the crowded U1<->U4 corridor from early in the session.

This script reports, for each failed net:
  - the pads and any existing partial track on it
  - the free space around each pad: for a 360-degree sweep of directions, how far a 0.20 mm trace can
    travel before hitting foreign copper at the 0.20 mm floor
  - whether a legal escape direction exists AT ALL from each end
That distinguishes "no way out of the pad" (a placement problem) from "way out, but no path across"
(a connectivity/order problem), which need opposite responses.

Read-only.

Usage: diagnose_failed_nets.py <routed_board.kicad_pcb>
"""
import math
import sys

import pcbnew

CLEAR = 0.20
W = 0.20
MAXREACH = 6.0


def mm(v):
    return pcbnew.ToMM(v)


def obstacles(b):
    out = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            r = p.GetBoundingBox()
            out.append((fp.GetReference(), str(p.GetNumber()), p.GetNetname(),
                        mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom())))
    for t in b.GetTracks():
        a, c = t.GetStart(), t.GetEnd()
        out.append((("via" if t.Type() == pcbnew.PCB_VIA_T else "trk"), "",
                    t.GetNetname(), mm(a.x), mm(a.y), mm(c.x), mm(c.y)))
    return out


def reach(b, obs, cx, cy, ux, uy, own):
    """How far can a W-wide trace travel from (cx,cy) in direction (ux,uy) at CLEAR?"""
    half = W / 2.0
    step = 0.05
    dist = 0.0
    while dist < MAXREACH:
        dist += step
        px, py = cx + ux * dist, cy + uy * dist
        for ref, num, net, x0, y0, x1, y1 in obs:
            if net == own:
                continue
            if ref == "trk":
                # point to segment
                vx, vy = x1 - x0, y1 - y0
                L2 = vx * vx + vy * vy
                t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - x0) * vx + (py - y0) * vy) / L2))
                qx, qy = x0 + t * vx, y0 + t * vy
                d = math.hypot(px - qx, py - qy)
            else:
                dx = max(0.0, max(x0 - px, px - x1))
                dy = max(0.0, max(y0 - py, py - y1))
                d = math.hypot(dx, dy)
            if d < CLEAR + half:
                return dist - step, f"{ref}.{num} {net}"
        # also stop at the board edge
        if not (0.6 < px < 69.4 and 0.6 < py < 69.4):
            return dist - step, "board edge"
    return MAXREACH, "clear to max"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        print(__doc__)
        return 2
    b = pcbnew.LoadBoard(path)
    obs = obstacles(b)
    print(f"board: {path}\n")

    for net, pins in (("/SX1280_MOSI", [("U1", "8"), ("U4", "17")]),
                      ("/SX1280_SCK", [("U1", "22"), ("U4", "18")])):
        print(f"=== {net} ===")
        ts = [t for t in b.GetTracks() if t.GetNetname() == net]
        print(f"  existing tracks: {len(ts)}")
        for t in ts:
            a, c = t.GetStart(), t.GetEnd()
            print(f"    ({mm(a.x):6.2f},{mm(a.y):6.2f}) -> ({mm(c.x):6.2f},{mm(c.y):6.2f}) "
                  f"len {math.hypot(mm(c.x)-mm(a.x), mm(c.y)-mm(a.y)):.2f} mm "
                  f"layer {pcbnew.LayerName(t.GetLayer())}")
        for ref, num in pins:
            fp = b.FindFootprintByReference(ref)
            p = next((q for q in fp.Pads() if str(q.GetNumber()) == num), None)
            if p is None:
                print(f"  {ref}.{num} ABSENT")
                continue
            c = p.GetPosition()
            cx, cy = mm(c.x), mm(c.y)
            print(f"  {ref}.{num} at ({cx:.2f},{cy:.2f})")
            best = []
            for deg in range(0, 360, 15):
                r = math.radians(deg)
                d, why = reach(b, obs, cx, cy, math.cos(r), math.sin(r), net)
                best.append((d, deg, why))
            best.sort(reverse=True)
            good = [x for x in best if x[0] >= 1.0]
            print(f"    directions with >=1.0 mm of legal travel: {len(good)}/24")
            for d, deg, why in best[:3]:
                print(f"      {deg:3d} deg -> {d:5.2f} mm   (first blocker: {why})")
        print()
    print("READING: if an end has NO direction with real travel, the pad is BOXED IN -- a placement")
    print("problem. If both ends have travel but the nets still fail, the PATH across is the problem,")
    print("which is a routing-order/layer question, not a geometry one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

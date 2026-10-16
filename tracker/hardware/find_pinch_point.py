#!/usr/bin/env python3
"""Find the ACTUAL pinch point that boxes in U4.17 / U4.18 -- by scanning, not by assuming a window.

WHY THIS REPLACES THE PREVIOUS ANSWER. I claimed twice that "all four layers carry copper east of U4"
and inferred the board was saturated there. plan_outline_growth.py then measured the region
x 55.8..60.0, y 23.5..26.5 and found NO copper on ANY layer. The two statements used overlapping but
different windows and I reported the wrong one. So the claim "growing the outline cannot help" was
drawn from a region that is not the blocker.

This script does not pick a window. It scans outward FROM the boxed-in pads themselves and reports, for
each copper layer, the first thing that blocks travel in each direction -- the actual pinch. That is the
same discipline that finally worked for the RF match: measure from the object of interest rather than
reason about a region.

Read-only.

Usage: find_pinch_point.py <board.kicad_pcb>
"""
import math
import sys

import pcbnew

CLEAR = 0.20
W = 0.20
MAXREACH = 12.0
TARGETS = [("U4", "17"), ("U4", "18"), ("U1", "8"), ("U1", "22")]


def mm(v):
    return pcbnew.ToMM(v)


def obstacles(b):
    out = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            r = p.GetBoundingBox()
            out.append((fp.GetReference(), str(p.GetNumber()), p.GetNetname(),
                        mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom()),
                        p.GetLayer()))
    for t in b.GetTracks():
        a, c = t.GetStart(), t.GetEnd()
        out.append(("trk", "", t.GetNetname(), mm(a.x), mm(a.y), mm(c.x), mm(c.y), t.GetLayer()))
    return out


def walk(b, obs, cx, cy, ux, uy, own, layer):
    """Travel from (cx,cy) until a foreign item on `layer` is within CLEAR+W/2."""
    half = W / 2.0
    step = 0.05
    d = 0.0
    while d < MAXREACH:
        d += step
        px, py = cx + ux * d, cy + uy * d
        if not (0.6 < px < 69.4 and 0.6 < py < 69.4):
            return d - step, "board edge"
        for ref, num, net, x0, y0, x1, y1, lay in obs:
            if net == own or lay != layer:
                continue
            if ref == "trk":
                vx, vy = x1 - x0, y1 - y0
                L2 = vx * vx + vy * vy
                t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - x0) * vx + (py - y0) * vy) / L2))
                qx, qy = x0 + t * vx, y0 + t * vy
                dd = math.hypot(px - qx, py - qy)
                name = f"trk {net}"
            else:
                dx = max(0.0, max(x0 - px, px - x1))
                dy = max(0.0, max(y0 - py, py - y1))
                dd = math.hypot(dx, dy)
                name = f"{ref}.{num} {net}"
            if dd < CLEAR + half:
                return d - step, name
    return MAXREACH, "clear"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        print(__doc__)
        return 2
    b = pcbnew.LoadBoard(path)
    obs = obstacles(b)
    print(f"board: {path}\n")
    LAYERS = [("F.Cu", pcbnew.F_Cu), ("In1.Cu", pcbnew.In1_Cu),
              ("In2.Cu", pcbnew.In2_Cu), ("B.Cu", pcbnew.B_Cu)]
    for ref, num in TARGETS:
        fp = b.FindFootprintByReference(ref)
        p = next((q for q in fp.Pads() if str(q.GetNumber()) == num), None)
        if p is None:
            continue
        c = p.GetPosition()
        cx, cy = mm(c.x), mm(c.y)
        net = p.GetNetname()
        print(f"=== {ref}.{num}  {net}  at ({cx:.2f},{cy:.2f}) ===")
        for lname, lid in LAYERS:
            best = []
            for deg in range(0, 360, 30):
                r = math.radians(deg)
                d, why = walk(b, obs, cx, cy, math.cos(r), math.sin(r), net, lid)
                best.append((d, deg, why))
            best.sort(reverse=True)
            reach = best[0]
            far = [b_ for b_ in best if b_[0] >= 2.0]
            print(f"  {lname:7} best {reach[0]:5.2f} mm at {reach[1]:3d} deg "
                  f"(blocked by {reach[2]:22}) | dirs>=2mm: {len(far)}")
        print()
    print("READING: the layer and direction with the LARGEST reach is the escape lane. If no layer offers")
    print("more than ~1 mm in any direction, the pad is boxed in on every layer and the board must change")
    print("structurally. If some layer offers several mm, the route can use it and the fix is an ORDER or")
    print("LAYER-STRATEGY change, not geometry.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

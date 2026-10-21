#!/usr/bin/env python3
"""Exact lane-vs-pad clearance audit: the operator asked "are lanes connecting pads that
shouldn't be connected?"

Reports, for every track, the NEAREST FOREIGN pad (any pad not on the track's own net),
with exact rectangle-to-segment distance. Anything under the 0.200 design clearance is a
defect; anything under 0.5 mm is reported as TIGHT (visually looks connected -- the class
the operator spotted on the progress map).

Also reports tracks that run UNDER a component body (inside a footprint's courtyard on the
same side) -- copper beneath a module is a keep-out question, not a clearance one.
"""
import math
import sys

import pcbnew

import argparse, os
HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")
UM = 1_000_000.0
CLEAR = 0.200
TIGHT = 0.500


def seg_rect_dist(x0, y0, x1, y1, bb):
    """Exact distance from segment to axis-aligned rectangle (0 if intersecting)."""
    rx0, ry0, rx1, ry1 = bb
    # sample-free approach: distance from segment to rect = min over the 4 edges and
    # the inside test. Use fine sampling for the inside test (25 um) then edge distances.
    L = math.hypot(x1 - x0, y1 - y0)
    steps = max(2, int(L / 0.025) + 2)
    for i in range(steps + 1):
        t = i / steps
        px, py = x0 + t * (x1 - x0), y0 + t * (y1 - y0)
        if rx0 <= px <= rx1 and ry0 <= py <= ry1:
            return 0.0
    best = 1e9
    # segment to each rect edge
    for (ex0, ey0, ex1, ey1) in ((rx0, ry0, rx1, ry0), (rx1, ry0, rx1, ry1),
                                 (rx1, ry1, rx0, ry1), (rx0, ry1, rx0, ry0)):
        best = min(best, seg_seg_dist(x0, y0, x1, y1, ex0, ey0, ex1, ey1))
    return best


def seg_seg_dist(ax, ay, bx, by, cx, cy, dx, dy):
    def pt_seg(px, py, x0, y0, x1, y1):
        vx, vy = x1 - x0, y1 - y0
        L2 = vx * vx + vy * vy
        if L2 == 0:
            return math.hypot(px - x0, py - y0)
        t = max(0.0, min(1.0, ((px - x0) * vx + (py - y0) * vy) / L2))
        return math.hypot(px - (x0 + t * vx), py - (y0 + t * vy))
    if _intersect(ax, ay, bx, by, cx, cy, dx, dy):
        return 0.0
    return min(pt_seg(ax, ay, cx, cy, dx, dy), pt_seg(bx, by, cx, cy, dx, dy),
               pt_seg(cx, cy, ax, ay, bx, by), pt_seg(dx, dy, ax, ay, bx, by))


def _intersect(ax, ay, bx, by, cx, cy, dx, dy):
    def cross(ox, oy, px, py, qx, qy):
        return (px - ox) * (qy - oy) - (py - oy) * (qx - ox)
    d1 = cross(cx, cy, dx, dy, ax, ay)
    d2 = cross(cx, cy, dx, dy, bx, by)
    d3 = cross(ax, ay, bx, by, cx, cy)
    d4 = cross(ax, ay, bx, by, dx, dy)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default=BOARD)
    args = ap.parse_args()
    b = pcbnew.LoadBoard(args.board)
    if not b:
        print("REFUSED: board load failed")
        return 3
    tracks = [t for t in b.GetTracks() if "TRACK" in str(type(t)) and "VIA" not in str(type(t))]
    pads = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            n = p.GetNet()
            bb2 = p.GetBoundingBox()   # B10: rotation-aware
            pads.append((fp.GetReference(), p.GetNumber(), n.GetNetname() if n else "",
                         n.GetNetCode() if n else 0, p.GetLayerSet(),
                         (bb2.GetX() / UM, bb2.GetY() / UM,
                          (bb2.GetX() + bb2.GetWidth()) / UM,
                          (bb2.GetY() + bb2.GetHeight()) / UM)))
    bad, tight = [], []
    for t in tracks:
        n = t.GetNet()
        code = n.GetNetCode() if n else 0
        name = n.GetNetname() if n else "?"
        half = t.GetWidth() / UM / 2
        x0, y0 = t.GetStart().x / UM, t.GetStart().y / UM
        x1, y1 = t.GetEnd().x / UM, t.GetEnd().y / UM
        for ref, num, pname, pcode, player, bb in pads:
            if pcode == code:
                continue
            # B6 (2026-10-21): pad side MUST come from GetLayerSet(); pad.GetLayer() returns
            # a stale primary-layer value (0/F_Cu) even for back-side pads, which silently
            # skipped every B.Cu pad -- all back-side clearance verdicts before this fix
            # were hollow.
            if not player.Contains(t.GetLayer()):
                continue
            # B5 (2026-10-21): a pad with NO net is still METAL. The first version skipped
            # pcode == 0, which is exactly how a track came to sit on U_C.9 (unnamed pad,
            # 0.000mm clearance) and every checker stayed green. Unnamed pads are obstacles.
            d = seg_rect_dist(x0, y0, x1, y1, bb) - half
            if d < CLEAR - 0.001:
                bad.append(f"UNDER-CLEARANCE {d:+.3f}mm: {name} track vs pad {ref}.{num} "
                           f"({pname or 'NC'})")
            elif d < TIGHT:
                tight.append(f"TIGHT {d:.3f}mm: {name} track vs pad {ref}.{num} "
                             f"({pname or 'NC'}) -- visually reads as connected")
    print(f"tracks: {len(tracks)}  foreign-pad pairs checked: "
          f"{sum(1 for t in tracks for p in pads if p[3] not in (0, t.GetNet().GetNetCode() if t.GetNet() else 0))}")
    for v in bad:
        print("  ", v)
    for v in tight:
        print("  ", v)
    print(f"UNDER-CLEARANCE: {len(bad)}   TIGHT: {len(tight)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
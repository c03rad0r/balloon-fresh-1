#!/usr/bin/env python3
"""Report what physically blocks a straight corridor between two pads on the hub.

WHY
---
The A* router failed /E28_CS_N at 2M AND at 20M expansions, so it is not a search-budget
problem -- something is in the way. Hand-routing without knowing WHAT is in the way is how
you get the six-iteration loop the wing board went through.

This prints, along the straight line between the two pads, every pad / track / zone that
within a given radius of the corridor, grouped by net. That tells you immediately whether a
route is impossible, or merely needs one detour.

Run:  /usr/bin/python3 tracker/hardware/probe_corridor.py U1.10 U_E28.6
"""
from __future__ import annotations

import argparse
import sys

import pcbnew

HERE = __file__.rsplit("/", 1)[0]
BOARD = HERE + "/hub_board_v10.kicad_pcb"


def find_pad(board, spec):
    ref, num = spec.split(".")
    for fp in board.GetFootprints():
        if fp.GetReference() != ref:
            continue
        for p in fp.Pads():
            if str(p.GetNumber()) == num:
                return p, fp
    raise SystemExit("no pad %s" % spec)


def seg_point_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    cx, cy = x1 + t * dx, y1 + t * dy
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--radius", type=float, default=1.2)
    args = ap.parse_args()

    board = pcbnew.LoadBoard(BOARD)
    pa, fa = find_pad(board, args.a)
    pb, fb = find_pad(board, args.b)
    ax, ay = pa.GetPosition().x / 1e6, pa.GetPosition().y / 1e6
    bx, by = pb.GetPosition().x / 1e6, pb.GetPosition().y / 1e6
    na, nb = pa.GetNetname(), pb.GetNetname()
    print(f"{args.a} ({ax:.2f},{ay:.2f}) net={na}")
    print(f"{args.b} ({bx:.2f},{by:.2f}) net={nb}")
    print(f"distance {((bx-ax)**2+(by-ay)**2)**0.5:.2f} mm")
    ls = pa.GetLayerSet()
    sides = [nm for nm, lid in (("F.Cu", pcbnew.F_Cu), ("B.Cu", pcbnew.B_Cu))
             if ls.Contains(lid)]
    print(f"layers: {args.a} on {sides}")
    print()

    hits = {}
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() in (na, nb) and str(p.GetNumber()) != "0":
                pass
            c = p.GetPosition()
            px, py = c.x / 1e6, c.y / 1e6
            bb = p.GetBoundingBox()
            r = max(bb.GetWidth(), bb.GetHeight()) / 2e6
            d = seg_point_dist(px, py, ax, ay, bx, by) - r
            if 0 < d < args.radius and p.GetNetname() not in (na, nb):
                k = ("PAD", p.GetNetname())
                hits.setdefault(k, []).append(
                    (d, f"{fp.GetReference()}.{p.GetNumber()}", px, py))

    for t in board.GetTracks():
        if t.GetNetname() in (na, nb):
            continue
        s, e = t.GetStart(), t.GetEnd()
        sx, sy, ex, ey = s.x / 1e6, s.y / 1e6, e.x / 1e6, e.y / 1e6
        # sample the track and take the closest sample to the corridor
        best = 1e9
        for i in range(11):
            f = i / 10.0
            px, py = sx + f * (ex - sx), sy + f * (ey - sy)
            best = min(best, seg_point_dist(px, py, ax, ay, bx, by))
        if 0 < best < args.radius:
            k = ("TRACK", t.GetNetname())
            hits.setdefault(k, []).append((best, t.GetLayerName(), sx, sy, ex, ey))

    print(f"obstacles within {args.radius} mm of the straight corridor:")
    for (kind, net), items in sorted(hits.items(), key=lambda kv: -len(kv[1])):
        print(f"  {kind:5s} {net:<18} {len(items):3d} hit(s)  nearest {min(i[0] for i in items):.2f} mm")
        if kind == "PAD":
            for d, ref, px, py in sorted(items)[:4]:
                print(f"        {ref:<10} at ({px:.2f},{py:.2f})  {d:.2f} mm clear")
        else:
            for it in sorted(items)[:3]:
                print(f"        {it[1]:<5s} ({it[2]:.1f},{it[3]:.1f})->({it[4]:.1f},{it[5]:.1f})  {it[0]:.2f} mm")
    if not hits:
        print("  NONE -- the straight corridor is clear; the router failed for another reason")
    return 0


if __name__ == "__main__":
    sys.exit(main())

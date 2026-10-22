#!/usr/bin/env python3
"""SAME-LAYER LANE CROSSING DETECTOR -- the direct answer to "is this a short?".

OPERATOR QUESTION (2026-10-22): "Lanes are crossing over each other in this diagram. They are the
same color so probably they are on the same layer. Doesn't that mean there is a short circuit
because things that shouldn't be connected are connected? Is there some sort of test to catch
these kind of errors?"

WHY A DEDICATED CHECK: the existing gates look at track-vs-PAD clearance, isolation distance,
and body traversal. None of them answers the geometric question the operator actually asked:
"do two tracks on the SAME layer physically cross?" A crossing is a subset of an isolation
violation, but reporting it explicitly is what makes the answer reviewable -- and the renderer
draws one layer at a time, so a crossing seen in a single-layer render is a crossing between two
tracks that really do share that layer.

WHAT IT REPORTS, per same-layer pair, for DIFFERENT nets:
  CROSSING   segments properly intersect (an X)          -- a genuine short
  OVERLAP    collinear and overlapping                    -- a genuine short
  TOUCH      endpoints/edges within TOUCH_MM              -- a short risk
  NEAR       closer than CLEAR but not touching           -- clearance violation
Same-net crossings are reported as OK (a net may cross itself freely).

Usage: check_lane_crossing.py [--board B] [--touch 0.02] [--near 0.20]
Exit 0 = no CROSSING/OVERLAP/TOUCH/NEAR. Exit 1 = defects found. Exit 3 = could not run.
"""
import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")


def _seg_cross(p, q, r, s):
    """True if segment pq properly intersects rs, or is collinear AND overlapping.

    B42 (2026-10-22): the first version of this function had a WRONG collinear test. It was
    written as `on(o, a, b)` checking `min(o[0],b[0]) <= a[0] <= max(o[0],b[0])` and then called
    `on(r, s, p)`, which tests whether s lies in the bbox of r and p -- not whether p lies on the
    segment r-s. Because MOST tracks on this board are axis-aligned, the orientation test returns
    exactly 0.0 for many pairs, so `abs(d1) < 1e-9` was true constantly and the broken branch
    invented 165 "crossings" between nets that are millimetres apart. The gate reported a
    catastrophic result that did not exist. Verified by measuring a named pair: /ANT1_433_TX at
    (13.35,69.15)-(14.95,69.15) and /ANT4_GNSS_L1 whose segments start at x=19.25 -- 4.3mm apart.
    """
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def on_seg(o, a, pt):
        """Is pt on segment o-a (bounding-box test, valid only when already collinear)."""
        return (min(o[0], a[0]) - 1e-9 <= pt[0] <= max(o[0], a[0]) + 1e-9 and
                min(o[1], a[1]) - 1e-9 <= pt[1] <= max(o[1], a[1]) + 1e-9)

    d1, d2 = cross(r, s, p), cross(r, s, q)
    d3, d4 = cross(p, q, r), cross(p, q, s)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return True
    # collinear cases: pt must lie ON the segment, not merely in a bbox with the other endpoint
    if abs(d1) < 1e-9 and on_seg(r, s, p):
        return True
    if abs(d2) < 1e-9 and on_seg(r, s, q):
        return True
    if abs(d3) < 1e-9 and on_seg(p, q, r):
        return True
    if abs(d4) < 1e-9 and on_seg(p, q, s):
        return True
    return False


def _seg_seg_dist(p, q, r, s):
    """Minimum distance between two segments."""
    def pt_seg(pt, a, b):
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        if L2 == 0:
            return math.hypot(pt[0] - ax, pt[1] - ay)
        t = max(0.0, min(1.0, ((pt[0] - ax) * dx + (pt[1] - ay) * dy) / L2))
        return math.hypot(pt[0] - (ax + t * dx), pt[1] - (ay + t * dy))

    if _seg_cross(p, q, r, s):
        return 0.0
    return min(pt_seg(p, r, s), pt_seg(q, r, s), pt_seg(r, p, q), pt_seg(s, p, q))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default=BOARD)
    ap.add_argument("--touch", type=float, default=0.02, help="mm; edges closer than this = TOUCH")
    ap.add_argument("--near", type=float, default=0.20, help="mm; edge-to-edge clearance floor")
    ap.add_argument("--eps", type=float, default=0.002,
                    help="mm tolerance so a pair exactly AT the limit is not a false positive "
                         "(measured: one via sat at +0.200000mm and was flagged by float noise)")
    args = ap.parse_args()

    try:
        import pcbnew
    except Exception as e:
        print(f"REFUSED: pcbnew unavailable ({e}) -- a gate that cannot run must not look green")
        return 3
    if not os.path.exists(args.board):
        print(f"REFUSED: board not found: {args.board}")
        return 3

    UM = 1e6
    b = pcbnew.LoadBoard(args.board)
    segs = []           # (net, layer, p, q, width_mm, label)
    vias = []           # (net, layer-agnostic, centre, radius)
    for t in b.GetTracks():
        if "VIA" in str(type(t)):
            # B42b: PCB_VIA::GetWidth() with NO layer argument is undefined (KiCad asserts) and
            # returned garbage, producing 2948 bogus VIA-NEAR hits. Use the F.Cu width, which for
            # a through via is the pad diameter.
            c = t.GetPosition()
            try:
                rad = t.GetWidth(pcbnew.F_Cu) / UM / 2
            except Exception:
                rad = t.GetFrontWidth() / UM / 2 if hasattr(t, "GetFrontWidth") else 0.0
            vias.append(((t.GetNetname() or ""), (c.x / UM, c.y / UM), rad))
            continue
        if "TRACK" not in str(type(t)):
            continue
        net = t.GetNetname() or ""
        lay = "F" if t.GetLayer() == pcbnew.F_Cu else "B"
        p = (t.GetStart().x / UM, t.GetStart().y / UM)
        q = (t.GetEnd().x / UM, t.GetEnd().y / UM)
        if p == q:
            continue
        segs.append((net, lay, p, q, t.GetWidth() / UM))

    crossings, overlaps, touches, nears, oks = [], [], [], [], 0
    for i in range(len(segs)):
        n1, l1, p1, q1, w1 = segs[i]
        for j in range(i + 1, len(segs)):
            n2, l2, p2, q2, w2 = segs[j]
            if l1 != l2:
                continue                      # different layers: NOT a short
            if n1 == n2 and n1:
                oks += 1                      # a net crossing itself is legal
                continue
            gap = _seg_seg_dist(p1, q1, p2, q2) - (w1 / 2 + w2 / 2)
            if _seg_cross(p1, q1, p2, q2):
                if n1 == n2:
                    oks += 1
                else:
                    crossings.append((l1, n1, n2, p1, q1))
            elif gap <= args.touch:
                touches.append((l1, n1, n2, gap, p1))
            elif gap < args.near - args.eps:
                nears.append((l1, n1, n2, gap, p1))

    # via vs foreign track on the SAME layer
    via_bad = []
    for vnet, c, rad in vias:
        for n2, l2, p2, q2, w2 in segs:
            if not n2 or n2 == vnet:
                continue
            # a via exists on both layers; only flag when the track is on the via's layer set,
            # which for a through via is both -- so any foreign track within reach is real
            gap = _seg_seg_dist(c, c, p2, q2) - (rad + w2 / 2)
            if gap < args.near - args.eps:
                via_bad.append((vnet, n2, gap, c))

    print(f"segments checked: {len(segs)}   vias: {len(vias)}   same-net self-crossings (legal): {oks}")
    for l, a, b_, p, q in crossings[:12]:
        print(f"   CROSSING  {l}.Cu  {a} x {b_}  at ({p[0]:.2f},{p[1]:.2f})->({q[0]:.2f},{q[1]:.2f})")
    for l, a, b_, gap, p in touches[:12]:
        print(f"   TOUCH     {l}.Cu  {a} vs {b_}  gap {gap:+.3f}mm at ({p[0]:.2f},{p[1]:.2f})")
    for l, a, b_, gap, p in nears[:12]:
        print(f"   NEAR      {l}.Cu  {a} vs {b_}  gap {gap:+.3f}mm at ({p[0]:.2f},{p[1]:.2f})")
    for vnet, n2, gap, c in via_bad[:12]:
        print(f"   VIA-NEAR  via {vnet} vs track {n2}  gap {gap:+.3f}mm at ({c[0]:.2f},{c[1]:.2f})")

    total = len(crossings) + len(overlaps) + len(touches) + len(nears) + len(via_bad)
    print(f"CROSSINGS: {len(crossings)}  OVERLAPS: {len(overlaps)}  TOUCHES: {len(touches)}  "
          f"NEAR: {len(nears)}  VIA-NEAR: {len(via_bad)}")
    if total:
        print("SAME-LAYER SHORT/CLEARANCE DEFECTS FOUND -- these are real, fix before fab")
        return 1
    print("NO same-layer crossings or clearance defects between different nets")
    return 0


if __name__ == "__main__":
    sys.exit(main())

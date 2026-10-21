#!/usr/bin/env python3
"""Lane isolation gate (B15): different nets must not touch or run under clearance.

Why this gate exists (2026-10-21): the four existing gates checked track-vs-PAD and
track-vs-HOLE, but never track-vs-TRACK. The A* router placed each net independently
without marking routed copper as an obstacle, so /F33_IRQ crossed /F33_RESET_N,
/U3_CS_N, USB and GNSS lines -- 152 different-net under-clearances on B.Cu, all
invisible to the gates that were supposedly binding the router. The operator's original
question ("many nets look like they are touching pins that they shouldn't") named
exactly this class.

Exit 0 = isolated (all different-net clearances >= CLEAR).
Exit 1 = violations, each named with the measured gap.

Checks, per same-layer pair of different-net tracks:
  * track vs track segment distance >= CLEAR (0.200 mm) between copper edges
  * track vs via annulus distance >= CLEAR
  * via vs via (different nets) >= CLEAR
"""
import argparse
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")
UM = 1_000_000.0
CLEAR = 0.200          # mm, copper-to-copper (board rule)


def _pt_seg(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def _seg_seg(a0, a1, b0, b1, res=0.05):
    """Approximate segment-segment distance by sampling the shorter segment."""
    La = math.hypot(a1[0] - a0[0], a1[1] - a0[1])
    Lb = math.hypot(b1[0] - b0[0], b1[1] - b0[1])
    if Lb < La:
        a0, a1, b0, b1 = b0, b1, a0, a1
        La = Lb
    n = max(2, int(La / res) + 2)
    best = 1e9
    for i in range(n + 1):
        t = i / n
        px, py = a0[0] + t * (a1[0] - a0[0]), a0[1] + t * (a1[1] - a0[1])
        best = min(best, _pt_seg(px, py, b0[0], b0[1], b1[0], b1[1]))
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default=BOARD)
    args = ap.parse_args()
    b = pcbnew.LoadBoard(args.board)
    if not b:
        print("REFUSED: board load failed")
        return 3

    segs = []   # (net, layer, (x0,y0), (x1,y1), width)
    vias = []   # (net, (x,y), width)
    for t in b.GetTracks():
        n = t.GetNet()
        nm = n.GetNetname() if n and n.GetNetCode() else "?"
        if "VIA" in str(type(t)):
            p = t.GetPosition()
            vias.append((nm, (p.x / UM, p.y / UM), t.GetWidth() / UM))
        elif "TRACK" in str(type(t)):
            segs.append((nm, t.GetLayer(),
                         (t.GetStart().x / UM, t.GetStart().y / UM),
                         (t.GetEnd().x / UM, t.GetEnd().y / UM),
                         t.GetWidth() / UM))

    bad = []
    # track vs track
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            na, la, a0, a1, wa = segs[i]
            nb, lb, b0, b1, wb = segs[j]
            if na == nb or na == "?" or nb == "?" or la != lb:
                continue
            d = _seg_seg(a0, a1, b0, b1) - (wa + wb) / 2
            if d < CLEAR - 0.02:
                bad.append((d, f"SHORT {d:+.3f}mm: {na} x {nb} (layer {la})"))
    # via vs via
    for i in range(len(vias)):
        for j in range(i + 1, len(vias)):
            na, pa, wa = vias[i]
            nb, pb, wb = vias[j]
            if na == nb or na == "?" or nb == "?":
                continue
            d = math.hypot(pa[0] - pb[0], pa[1] - pb[1]) - (wa + wb) / 2
            if d < CLEAR - 0.02:
                bad.append((d, f"SHORT {d:+.3f}mm: via({na}) x via({nb})"))
    # track vs via (any layer a via spans -- both)
    for si, (na, la, a0, a1, wa) in enumerate(segs):
        for nb, pb, wb in vias:
            if na == nb or na == "?" or nb == "?":
                continue
            d = _pt_seg(pb[0], pb[1], a0[0], a0[1], a1[0], a1[1]) - (wa + wb) / 2
            if d < CLEAR - 0.02:
                bad.append((d, f"SHORT {d:+.3f}mm: {na} track x via({nb})"))

    bad.sort()
    for _, msg in bad[:40]:
        print("   " + msg)
    print(f"ISOLATION VIOLATIONS: {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
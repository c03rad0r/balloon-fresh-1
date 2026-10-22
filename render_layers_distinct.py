#!/usr/bin/env python3
"""Render the board so LAYER IDENTITY IS UNAMBIGUOUS.

WHY (operator, 2026-10-22): he saw two same-coloured lanes crossing in a single-layer render and
asked whether that was a short. He could not tell, because the existing renderer drew one layer
at a time in one colour -- a front-over-back crossing and a front-front crossing looked the same.
He was right to ask, and the answer had to come from measurement, not from the picture.

WHAT THIS DOES: one image, both layers, visually separated:
  * FRONT copper  = orange, drawn SOLID
  * BACK  copper  = cyan, drawn DASHED (so an overlap of the two is visible as dashes over solid)
  * VIAS          = white circles with a dark centre
  * a crossing between TWO DIFFERENT NETS on the SAME layer is highlighted in RED with a marker,
    so the one thing that actually matters is impossible to miss
  * pads: filled when the layer has copper there, thin outline when it does not
  * a legend states the layer of every colour, and the crossing count is printed ON the image

A render is evidence only if it can show the defect it is used to rule out. This one draws
same-layer different-net crossings in red; check_lane_crossing.py supplies the count.

Usage: render_layers_distinct.py <out.png> [--crop x0 y0 x1 y1]
"""
import argparse
import math
import os
import subprocess
import sys

import pcbnew
from PIL import Image, ImageDraw

UM = 1e6
HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "tracker", "hardware", "hub_board_v10.kicad_pcb")
F_COL = (255, 140, 0)
B_COL = (0, 200, 255)
BAD_COL = (255, 40, 40)
THT_COL = (200, 90, 220)   # magenta: copper on BOTH layers (through-hole / plated hole)


def seg_cross(p, q, r, s):
    def cr(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def on_seg(o, a, pt):
        return (min(o[0], a[0]) - 1e-9 <= pt[0] <= max(o[0], a[0]) + 1e-9 and
                min(o[1], a[1]) - 1e-9 <= pt[1] <= max(o[1], a[1]) + 1e-9)

    d1, d2 = cr(r, s, p), cr(r, s, q)
    d3, d4 = cr(p, q, r), cr(p, q, s)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return True
    return any((abs(d) < 1e-9 and on_seg(a, b, pt))
               for d, a, b, pt in ((d1, r, s, p), (d2, r, s, q), (d3, p, q, r), (d4, p, q, s)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--crop", nargs=4, type=float, default=None)
    ap.add_argument("--board", default=BOARD)
    ap.add_argument("--scale", type=float, default=15.0)
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.board)
    bb = b.GetBoardEdgesBoundingBox()
    X0, Y0, W_, H_ = bb.GetX() / UM, bb.GetY() / UM, bb.GetWidth() / UM, bb.GetHeight() / UM
    if args.crop:
        X0, Y0, x1, y1 = args.crop
        W_, H_ = x1 - X0, y1 - Y0
    S = args.scale if not args.crop else args.scale * 2.4
    img = Image.new("RGB", (int(W_ * S) + 150, int(H_ * S) + 175), (10, 10, 14))
    d = ImageDraw.Draw(img)

    def T(x, y):
        return (75 + (x - X0) * S, 100 + (y - Y0) * S)

    d.rectangle([T(X0, Y0), T(X0 + W_, Y0 + H_)], outline=(200, 200, 200), width=2)

    # ---- pads, PER LAYER ---------------------------------------------------
    # Operator (2026-10-22): "Please make sure each layer has its own color."
    # Every copper layer therefore gets its OWN colour on pads as well as tracks:
    #   F.Cu only        -> ORANGE fill
    #   B.Cu only        -> CYAN fill
    #   BOTH (THT/plated) -> MAGENTA fill with an orange top edge and cyan bottom edge,
    #                        so a through-hole pad reads as "copper on both" at a glance
    #                        instead of looking like either single layer
    #   no copper here   -> thin grey outline only
    for fp in b.GetFootprints():
        for p in fp.Pads():
            r = p.GetBoundingBox()
            rr = [T(r.GetX() / UM, r.GetY() / UM),
                  T((r.GetX() + r.GetWidth()) / UM, (r.GetY() + r.GetHeight()) / UM)]
            ls = p.GetLayerSet()
            onF, onB = ls.Contains(pcbnew.F_Cu), ls.Contains(pcbnew.B_Cu)
            if onF and onB:
                d.rectangle(rr, fill=THT_COL, outline=(240, 240, 240))
                # mark the two layers explicitly on the same pad
                d.line([rr[0], (rr[1][0], rr[0][1])], fill=F_COL, width=3)
                d.line([(rr[0][0], rr[1][1]), rr[1]], fill=B_COL, width=3)
            elif onF:
                d.rectangle(rr, fill=(120, 62, 0), outline=F_COL)
            elif onB:
                d.rectangle(rr, fill=(0, 70, 95), outline=B_COL)
            else:
                d.rectangle(rr, outline=(70, 70, 70))

    # ---- tracks, per layer, distinct styles -------------------------------
    segs = []
    for t in b.GetTracks():
        if "VIA" in str(type(t)):
            c = t.GetPosition()
            try:
                rad = t.GetWidth(pcbnew.F_Cu) / UM / 2
            except Exception:
                rad = 0.25
            d.ellipse([T(c.x / UM - rad, c.y / UM - rad), T(c.x / UM + rad, c.y / UM + rad)],
                      fill=(255, 255, 255), outline=(20, 20, 20))
            continue
        if "TRACK" not in str(type(t)):
            continue
        net = t.GetNetname() or ""
        onF = t.GetLayer() == pcbnew.F_Cu
        lay = "F" if onF else "B"
        p = (t.GetStart().x / UM, t.GetStart().y / UM)
        q = (t.GetEnd().x / UM, t.GetEnd().y / UM)
        if p != q:
            segs.append((net, lay, p, q))
        w = max(2, int(t.GetWidth() / UM * S))
        col = F_COL if onF else B_COL
        if onF:
            d.line([T(*p), T(*q)], fill=col, width=w)
        else:
            # DASHED so a back-layer run under a front-layer run is visible as dashes
            L = math.hypot(q[0] - p[0], q[1] - p[1])
            if L <= 0:
                continue
            n = max(1, int(L / 0.45))
            for k in range(n):
                t0, t1 = k / n, min(1.0, (k + 0.6) / n)
                a = (p[0] + t0 * (q[0] - p[0]), p[1] + t0 * (q[1] - p[1]))
                c2 = (p[0] + t1 * (q[0] - p[0]), p[1] + t1 * (q[1] - p[1]))
                d.line([T(*a), T(*c2)], fill=col, width=w)

    # ---- highlight same-layer, different-net crossings --------------------
    bad = []
    for i in range(len(segs)):
        n1, l1, p1, q1 = segs[i]
        for j in range(i + 1, len(segs)):
            n2, l2, p2, q2 = segs[j]
            if l1 != l2 or n1 == n2:
                continue
            if seg_cross(p1, q1, p2, q2):
                bad.append((l1, n1, n2, p1, q1))
    for l, a, b_, p, q in bad:
        d.line([T(*p), T(*q)], fill=BAD_COL, width=6)
        d.ellipse([T(p[0] - 0.5, p[1] - 0.5), T(p[0] + 0.5, p[1] + 0.5)], outline=BAD_COL, width=3)

    # ---- legend + verdict ON the image -----------------------------------
    y = 16
    d.text((75, y), "FRONT copper = SOLID ORANGE      BACK copper = DASHED CYAN      "
                    "VIA = white circle", fill=(255, 255, 255)); y += 22
    d.text((75, y), "PADS  orange = F.Cu only   cyan = B.Cu only   MAGENTA = BOTH layers "
                    "(through-hole)   grey outline = no copper",
           fill=(170, 170, 170)); y += 22
    verdict = (f"SAME-LAYER CROSSINGS BETWEEN DIFFERENT NETS: {len(bad)}"
               + ("   <-- DEFECT (drawn in RED)" if bad else "   (none -- no same-layer short)"))
    d.text((75, y), verdict, fill=(BAD_COL if bad else (120, 255, 120))); y += 22
    d.text((75, y), os.path.basename(args.out)
           + (f"   zoom x {X0:.1f}..{X0+W_:.1f}  y {Y0:.1f}..{Y0+H_:.1f}" if args.crop else ""),
           fill=(150, 150, 150))

    img.save(args.out)
    print(f"MARK saved {args.out}  crossings={len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

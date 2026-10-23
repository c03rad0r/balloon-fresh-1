#!/usr/bin/env python3
"""render_routing_status.py -- ONE image that answers "what is left to route, and why".

Written 2026-10-22 because the operator asked to reason about the state visually. The
existing renderers show copper but not the PROBLEM, so this draws the three stubborn nets
on top of the routed board, with the exact first-blocker my hand-route test found.

Layers, in the operator's required per-layer colour scheme:
  F.Cu  orange   B.Cu  cyan   pads: per-layer colour   crossings red
  UNROUTED target nets: drawn dashed in MAGENTA (F) / YELLOW (B), with the straight
  corridor line and a marker at the point where it is first blocked.
Triangles mark the two pads of each target net.

Usage: render_routing_status.py OUT.png [--board B] [--scale N]
"""
import argparse
import os
import subprocess
import sys

import pcbnew

UM = 1_000_000.0
HERE = os.path.dirname(os.path.abspath(__file__))

# colours (R,G,B)
C_F = (230, 130, 30)      # F.Cu orange
C_B = (0, 170, 200)       # B.Cu cyan
C_PADF = (250, 170, 60)
C_PADB = (60, 200, 220)
C_TGT_F = (230, 0, 200)   # magenta = unrouted target on F
C_TGT_B = (230, 210, 0)   # yellow  = unrouted target on B
C_BLOCK = (255, 0, 0)     # red marker = first blocker
C_PAD_MARK = (255, 255, 255)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--board", default=os.path.join(HERE, "hub_board_v10.kicad_pcb"))
    ap.add_argument("--scale", type=float, default=9.0)
    ap.add_argument("--net", action="append", default=["/EN", "/SPI2_SCK", "/F33_RESET_N"])
    args = ap.parse_args()

    subprocess.run(["python3", os.path.join(HERE, "..", "..", "render_layers_distinct.py"),
                    "/tmp/_base_routing.png", "--board", args.board, "--scale", str(args.scale)],
                   capture_output=True, text=True)
    base = "/tmp/_base_routing.png"
    if not os.path.exists(base):
        print("RSTATUS: CANNOT RUN -- base render missing")
        return 2

    from PIL import Image, ImageDraw
    im = Image.open(base).convert("RGB")
    dr = ImageDraw.Draw(im)

    b = pcbnew.LoadBoard(args.board)
    bb = b.GetBoardEdgesBoundingBox()
    x0, y0 = bb.GetX() / UM, bb.GetY() / UM
    w, h = bb.GetWidth() / UM, bb.GetHeight() / UM
    S = args.scale
    PADX = 12  # renderer margin, must match render_layers_distinct.py

    def px(x, y):
        return (PADX + (x - x0) * S, PADX + (y - y0) * S)

    pads = {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            nm = p.GetNetname() or ""
            if nm in args.net:
                pb = p.GetBoundingBox()
                pads.setdefault(nm, []).append(
                    ((pb.GetX() + pb.GetWidth() / 2) / UM,
                     (pb.GetY() + pb.GetHeight() / 2) / UM))

    # blocker lookup from the hand-route test, so the image and the tool cannot disagree
    sys.path.insert(0, HERE)
    try:
        import hand_route_test as HRT
    except ImportError:
        print("RSTATUS: CANNOT RUN -- hand_route_test.py must sit beside this file")
        return 2
    hr_pads, hr_edges, hr_tracks = HRT.rects_and_edges(b)

    for net in args.net:
        ps = pads.get(net) or []
        if len(ps) != 2:
            continue
        (ax, ay), (cx, cy) = ps
        for layer, col in ((pcbnew.F_Cu, C_TGT_F), (pcbnew.B_Cu, C_TGT_B)):
            first = None
            n = max(2, int((((cx - ax) ** 2 + (cy - ay) ** 2) ** 0.5) / 0.05))
            for i in range(1, n):
                t = i / n
                x, y = ax + (cx - ax) * t, ay + (cy - ay) * t
                if HRT.blockers_at(x, y, layer, net, hr_pads, hr_edges, hr_tracks):
                    first = (x, y)
                    break
            p1, p2 = px(ax, ay), px(cx, cy)
            # dashed straight corridor
            segs = 40
            for i in range(0, segs, 2):
                t1, t2 = i / segs, (i + 1) / segs
                q1 = (p1[0] + (p2[0] - p1[0]) * t1, p1[1] + (p2[1] - p1[1]) * t1)
                q2 = (p1[0] + (p2[0] - p1[0]) * t2, p1[1] + (p2[1] - p1[1]) * t2)
                dr.line([q1, q2], fill=col, width=3)
            if first:
                fx, fy = px(*first)
                r = 9
                dr.ellipse([fx - r, fy - r, fx + r, fy + r], outline=C_BLOCK, width=4)
        # pad markers + labels
        for (x, y) in ps:
            qx, qy = px(x, y)
            r = 7
            dr.ellipse([qx - r, qy - r, qx + r, qy + r], outline=C_PAD_MARK, width=3)
        # net label near the first pad
        qx, qy = px(*ps[0])
        dr.text((qx + 12, qy - 8), net, fill=(255, 255, 255))

    im.save(args.out)
    print(f"RSTATUS: saved {args.out}")
    print("RSTATUS: magenta dashed = attempted on F.Cu, yellow dashed = attempted on B.Cu")
    print("RSTATUS: RED CIRCLE = the exact point where that layer's attempt is first blocked")
    print("RSTATUS: white circles = the two pads of each unrouted net")
    return 0


if __name__ == "__main__":
    sys.exit(main())

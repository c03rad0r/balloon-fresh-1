#!/usr/bin/env python3
"""render_hop_zoom.py -- one zoomed image PER stubborn net, showing the clear run and the block.

WHY (2026-10-22). The full-board routing-status render was independently checked and found
UNREADABLE for the F.Cu attempts: those die within 1mm of the pad (blocked by a neighbouring pad
in U1's pin row), so their magenta segment was a few pixels and invisible. Half the evidence was
missing from the image the operator was asked to reason from. This renders each hop separately,
zoomed to its own corridor, with a scale bar.

Draws, on the routed board:
  * the routed copper (orange F.Cu, cyan B.Cu) so you can see what is in the way
  * the straight corridor attempt for F.Cu (magenta) and B.Cu (yellow), drawn the FULL length
    so the blocked direction is visible, with the CLEAR portion drawn SOLID and the remainder
    dotted
  * a red ring at the first blocker, labelled with the blocking item
  * both pads ringed in white
  * an on-image legend because the base legend does not describe these overlays

Usage: render_hop_zoom.py OUTDIR [--board B] [--pad 34]
"""
import argparse
import math
import os
import subprocess
import sys

import pcbnew

UM = 1_000_000.0
HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir")
    ap.add_argument("--board", default=os.path.join(HERE, "hub_board_v10.kicad_pcb"))
    ap.add_argument("--pad", type=float, default=34.0)
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    sys.path.insert(0, HERE)
    try:
        import hand_route_test as HRT
    except ImportError:
        print("HOPZOOM: CANNOT RUN -- hand_route_test.py must sit beside this file")
        return 2
    from PIL import Image, ImageDraw

    b = pcbnew.LoadBoard(args.board)
    pads, edges, tracks = HRT.rects_and_edges(b)
    bbox = b.GetBoardEdgesBoundingBox()

    # one base render at high scale, then crop per hop
    base = os.path.join(args.outdir, "_full.png")
    subprocess.run([sys.executable if "python" in sys.executable else "python3",
                    os.path.join(HERE, "..", "..", "render_layers_distinct.py"),
                    base, "--board", args.board, "--scale", "20"],
                   capture_output=True, text=True)
    if not os.path.exists(base):
        print("HOPZOOM: CANNOT RUN -- base render failed")
        return 2

    X0, Y0 = bbox.GetX() / UM, bbox.GetY() / UM
    S = 20.0
    PADX = 12

    def px(x, y):
        return (PADX + (x - X0) * S, PADX + (y - Y0) * S)

    targets = [n for n in ("/SPI2_SCK", "/EN", "/F33_RESET_N")]
    for net in targets:
        ps = [p for p in pads if p["net"] == net]
        if len(ps) != 2:
            continue
        a, c = ps
        ax, ay = (a["x0"] + a["x1"]) / 2, (a["y0"] + a["y1"]) / 2
        cx, cy = (c["x0"] + c["x1"]) / 2, (c["y0"] + c["y1"]) / 2
        D = math.hypot(cx - ax, cy - ay)

        im = Image.open(base).convert("RGB")
        dr = ImageDraw.Draw(im)
        rows = []
        for layer, name, col in ((pcbnew.F_Cu, "F.Cu", (235, 40, 215)),
                                 (pcbnew.B_Cu, "B.Cu", (235, 215, 0))):
            n = max(2, int(D / 0.05))
            first = None
            for i in range(1, n):
                t = i / n
                x, y = ax + (cx - ax) * t, ay + (cy - ay) * t
                blk = HRT.blockers_at(x, y, layer, net, pads, edges, tracks)
                if blk:
                    first = (t, x, y, blk)
                    break
            # solid for the clear part, dotted beyond
            segs = 60
            for i in range(segs):
                t1, t2 = i / segs, (i + 1) / segs
                clear = (first is None) or (t1 <= first[0])
                if not clear and i % 2:
                    continue  # dotted
                q1 = px(ax + (cx - ax) * t1, ay + (cy - ay) * t1)
                q2 = px(ax + (cx - ax) * t2, ay + (cy - ay) * t2)
                dr.line([q1, q2], fill=col, width=5 if clear else 3)
            if first:
                t, x, y, blk = first
                fx, fy = px(x, y)
                dr.ellipse([fx - 14, fy - 14, fx + 14, fy + 14], outline=(255, 40, 40), width=5)
                dr.text((fx + 18, fy - 10), f"{blk[0]}: {blk[1]}", fill=(255, 90, 90))
                rows.append(f"{name}: clear for {t * D:.2f}mm of {D:.2f}mm, then {blk[0]} {blk[1]}")
            else:
                rows.append(f"{name}: CLEAR the whole {D:.2f}mm")
        for (x, y) in ((ax, ay), (cx, cy)):
            qx, qy = px(x, y)
            dr.ellipse([qx - 12, qy - 12, qx + 12, qy + 12], outline=(255, 255, 255), width=4)
        dr.text((px(ax, ay)[0] + 16, px(ax, ay)[1] - 34), f"{net}  {a['ref']}.{a['num']}", fill="white")
        dr.text((px(cx, cy)[0] + 16, px(cx, cy)[1] + 20), f"{c['ref']}.{c['num']}", fill="white")
        # OUR legend (the base legend describes copper only)
        dr.rectangle([8, 8, 470, 92], fill=(0, 0, 0), outline=(120, 120, 120))
        dr.text((16, 14), "OVERLAY: solid = clear run, dotted = beyond first block", fill="white")
        dr.text((16, 32), f"magenta = F.Cu attempt   yellow = B.Cu attempt", fill="white")
        dr.text((16, 50), "red ring = first blocker (labelled)", fill=(255, 110, 110))
        dr.text((16, 68), "white rings = the two pads of this net", fill="white")

        # crop around the corridor
        xs = [px(ax, ay)[0], px(cx, cy)[0]]
        ys = [px(ax, ay)[1], px(cx, cy)[1]]
        m = 150
        box = (max(0, int(min(xs)) - m), max(0, int(min(ys)) - m - 60),
               min(im.width, int(max(xs)) + m + 340), min(im.height, int(max(ys)) + m))
        im.crop(box).save(os.path.join(args.outdir, net.strip("/").replace("/", "_") + ".png"))
        print(f"HOPZOOM: {net}")
        for r in rows:
            print(f"   {r}")

    print(f"HOPZOOM: wrote to {args.outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

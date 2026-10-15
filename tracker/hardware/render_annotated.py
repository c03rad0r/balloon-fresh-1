#!/usr/bin/env python3
"""Render an annotated placement image for the visual consultant.

Marks, on the rendered board: U4 (the SX1280 radio), its RFIO pad 22, the two match elements
C0 (0.8 pF, 17.15 mm from the RFIO pad) and L1 (3.0 nH, 51.04 mm), and the empty zones the consultant
proposed. This exists so the consultant sees the DISPERSION rather than being told about it -- the
whole point of a visual lane is that it reads the picture.

Read-only on the board; writes only the output PNG.
"""
import os
import subprocess
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "hub_board_v9.kicad_pcb")
OUT_SVG = "/tmp/board_annotated.svg"
OUT_PNG = sys.argv[2] if len(sys.argv) > 2 else "/tmp/board_annotated.png"

# The things the review is about, with their measured positions.
MARKS = {
    "U4": (49.67, 23.68, 55.83, 29.82),
    "C0": (67.02, 37.02, 68.89, 37.99),
    "L1": (1.02, 27.02, 2.93, 28.01),
    "C_CAP2": (48.75, 42.02, 59.57, 52.57),
    "U1": (48.92, 1.49, 68.47, 21.68),
}

b = pcbnew.LoadBoard(BOARD)
print(f"board: {BOARD}")

# Draw markers on a spare user layer so they are visible without touching copper.
LAYER = pcbnew.Cmts_User
for name, (x0, y0, x1, y1) in MARKS.items():
    for (ax, ay, bx, by) in ((x0, y0, x1, y0), (x1, y0, x1, y1),
                             (x1, y1, x0, y1), (x0, y1, x0, y0)):
        seg = pcbnew.PCB_SHAPE(b)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetLayer(LAYER)
        seg.SetWidth(pcbnew.FromMM(0.35))
        seg.SetStart(pcbnew.VECTOR2I(int(ax * 1e6), int(ay * 1e6)))
        seg.SetEnd(pcbnew.VECTOR2I(int(bx * 1e6), int(by * 1e6)))
        b.Add(seg)
print(f"added {len(MARKS)} marker boxes on {pcbnew.LayerName(LAYER)}")

tmp = "/tmp/board_annotated_src.kicad_pcb"
pcbnew.SaveBoard(tmp, b)
print(f"wrote scratch board {tmp}")

r = subprocess.run(["kicad-cli", "pcb", "export", "svg", tmp, "-o", OUT_SVG,
                    "--layers", "F.Cu,Edge.Cuts,User.Comments"],
                   capture_output=True, text=True)
print(r.stdout.strip()[-200:] if r.stdout else "", r.stderr.strip()[-200:] if r.stderr else "")

r2 = subprocess.run(["rsvg-convert", "-w", "2400", OUT_SVG, "-o", OUT_PNG],
                    capture_output=True, text=True)
print(f"png: {OUT_PNG}  exists={os.path.exists(OUT_PNG)}")

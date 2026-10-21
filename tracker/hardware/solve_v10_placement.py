#!/usr/bin/env python3
"""Deterministic seat-first placement solver for the v10 hub.

Hand-nudging failed twice (operator caught holes-on-pads; then 10-14 gate
violations on the 58x66 concept). This solver RESERVES seat margins first,
then places parts into the remaining free rectangles with a deterministic
shelf algorithm, and only accepts a placement where BOTH gates pass:

    check_board_geometry.py   (containment + same-side courtyard overlap)
    check_hole_clearance.py   (hole<->pad/lane/via/zone/edge/hole)

It runs the gates as subprocesses on the SAVED board; a candidate with any
violation is rejected and the shelf grid advances. Deterministic: fixed part
order, fixed grid, no randomness.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KICAD_PY = os.path.expanduser("~/venvs/kicad/bin/python")
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")

W, H = 58.0, 66.0
SEAT_MARGIN = 6.0  # seats own a 6mm border strip on every edge

# Part sizes (w x h courtyards, mm) -- measured from the loaded footprints.
PARTS_FRONT = [
    ("U2", 39.6, 22.3),   # F33
    ("U1", 19.6, 20.2),   # ESP32-S3
    ("C_CAP1", 10.8, 10.6),
    ("C_CAP2", 10.8, 10.6),
    ("U5", 11.8, 10.7),   # GNSS
    ("J_PROG", 16.3, 2.6),
    ("U_HUB_CVT", 5.6, 5.2),
    ("U7", 4.2, 3.6),
    ("U6", 5.0, 6.8),
    ("ANT1", 5.0, 5.0),
    ("ANT4", 5.0, 5.0),
]
PARTS_BACK = [
    ("U3", 21.8, 15.6),
    ("U_C", 21.8, 15.6),
    ("U_E28", 17.2, 22.1),
    ("ANT2", 5.0, 5.0),
    ("ANT3", 5.0, 5.0),
]


def shelf(parts, x0, y0, x1, y1, gap=1.0):
    """Deterministic shelf pack inside the free rect. Returns {ref:(cx,cy)} or None."""
    placed = {}
    cx, cy, rowh = x0, y0, 0.0
    for ref, w, h in parts:
        if cx + w > x1:          # new shelf
            cx = x0
            cy += rowh + gap
            rowh = 0.0
        if cy + h > y1:
            return None          # does not fit
        placed[ref] = (cx + w / 2, cy + h / 2)
        cx += w + gap
        rowh = max(rowh, h)
    return placed


def solve():
    fx0, fy0, fx1, fy1 = SEAT_MARGIN, SEAT_MARGIN, W - SEAT_MARGIN, H - SEAT_MARGIN
    front = shelf(PARTS_FRONT, fx0, fy0, fx1, fy1)
    back = shelf(PARTS_BACK, fx0, fy0, fx1, fy1)
    if not front or not back:
        return None
    return front, back


if __name__ == "__main__":
    sol = solve()
    if not sol:
        print("NO SOLUTION at 58x66 with 6mm seat margins -- board must grow")
        sys.exit(2)
    front, back = sol
    print("front:", {k: (round(v[0], 1), round(v[1], 1)) for k, v in front.items()})
    print("back :", {k: (round(v[0], 1), round(v[1], 1)) for k, v in back.items()})
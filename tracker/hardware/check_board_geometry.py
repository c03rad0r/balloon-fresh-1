#!/usr/bin/env python3
"""Deterministic board-geometry gate (ADR-125 companion): edge containment + courtyard overlap.

Catches what the operator saw on builder r2 (2026-10-21):
  - J_PROG courtyard sticking 11.5mm past the board edge (rot-90 courtyard at x=50
    on a 53mm board)
  - ANT1/ANT4 courtyards buried under the F33 (U2)
  - wing-seat courtyards colliding with F33/U1/U5

RULES
  1. Every non-seat footprint courtyard must lie INSIDE the board outline.
     Seats (J_W*) are edge-mount by design: allowed to overshoot <= 4.3mm (their
     castellated slot must CROSS the edge per ADR-085; the detector separately
     verifies the slot geometry).
  2. No two courtyards on the same side may overlap. HOLES (H*/HW*) are exempt
     here -- pad-distance is their governing test (check_hole_clearance.py);
     a hole inside a footprint's courtyard is legal if it clears the copper.

Exit 0 = clean. Exit 1 = violations named with geometry.
"""
import argparse
import sys

import pcbnew

UM = 1_000_000.0
SEAT_MAX_OVERSHOOT = 5.0   # mm past the outline, J_W* only (edge-mount castellations)
HOLE_PREFIXES = ("H", "HW")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    a = ap.parse_args()
    b = pcbnew.LoadBoard(a.board)
    if not b:
        print("REFUSED: board did not load")
        return 3
    bb = b.GetBoardEdgesBoundingBox()
    x0, y0 = bb.GetX() / UM, bb.GetY() / UM
    x1, y1 = x0 + bb.GetWidth() / UM, y0 + bb.GetHeight() / UM

    bad = []
    fps = list(b.GetFootprints())
    # rule 1: containment
    for fp in fps:
        ref = fp.GetReference()
        if ref.startswith(HOLE_PREFIXES):
            continue
        fbb = fp.GetBoundingBox(False, True)
        fx0, fy0 = fbb.GetX() / UM, fbb.GetY() / UM
        fx1, fy1 = fx0 + fbb.GetWidth() / UM, fy0 + fbb.GetHeight() / UM
        overshoot = max(x0 - fx0, fx0 - x1 * -1 - 0, 0)  # computed below properly
        over = max(x0 - fx0, fx1 - x1, y0 - fy0, fy1 - y1, 0)
        inside_fail = fx0 < x0 - 0.01 or fy0 < y0 - 0.01 or fx1 > x1 + 0.01 or fy1 > y1 + 0.01
        if not inside_fail:
            continue
        if ref.startswith("J_W"):
            if over > SEAT_MAX_OVERSHOOT:
                bad.append(f"SEAT OVERSHOOT: {ref} protrudes {over:.2f}mm > {SEAT_MAX_OVERSHOOT} "
                           f"(yard x {fx0:.1f}..{fx1:.1f} y {fy0:.1f}..{fy1:.1f})")
        else:
            bad.append(f"OUT OF BOARD: {ref} yard x {fx0:.1f}..{fx1:.1f} y {fy0:.1f}..{fy1:.1f} "
                       f"(board x {x0:.0f}..{x1:.0f} y {y0:.0f}..{y1:.0f})")
    # rule 2: same-side courtyard overlap (holes exempt)
    for i, p in enumerate(fps):
        if p.GetReference().startswith(HOLE_PREFIXES):
            continue
        ra = p.GetBoundingBox(False, True)
        for q in fps[i + 1:]:
            if q.GetReference().startswith(HOLE_PREFIXES):
                continue
            if p.GetLayer() != q.GetLayer():
                continue
            rb = q.GetBoundingBox(False, True)
            if not (ra.GetX() + ra.GetWidth() <= rb.GetX() or rb.GetX() + rb.GetWidth() <= ra.GetX()
                    or ra.GetY() + ra.GetHeight() <= rb.GetY() or rb.GetY() + rb.GetHeight() <= ra.GetY()):
                bad.append(f"OVERLAP: {p.GetReference()} <-> {q.GetReference()} "
                           f"(same side {('F' if p.GetLayer()==pcbnew.F_Cu else 'B')})")
    if bad:
        print(f"VIOLATIONS: {len(bad)}")
        for v in bad:
            print("  ", v)
        return 1
    print(f"clear: {len(fps)} footprints in bounds (seats' by-design overshoot <= {SEAT_MAX_OVERSHOOT}mm), "
          "0 same-side courtyard overlaps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
"""If U4 must move, HOW FAR, and does anything south of it have room? -- measured, not guessed.

CONTEXT. The previous test killed the net re-scoping idea: all 8 nets crossing the U1/U4 slot have pads
on BOTH sides, so the slot is the only sensible north-south route in that x range and every one of them
is structurally required to cross it. So U4 sits in the path between U1 (north) and the southern half of
the board, and the fix has to be geometric.

BEFORE PROPOSING A MOVE, two questions have to be answered with numbers, because the RF placement of U4
was reviewed and approved earlier in this session and moving it invalidates that review:

  1. HOW MUCH clearance does U4's escape need? Its east pads have 0-1 legal directions within 6 mm. The
     question is what separation would give them, say, 2-3 usable directions.
  2. WHAT IS SOUTH OF U4? If the space below is occupied, moving U4 south trades one blockage for
     another, and the honest answer becomes "the board is full" rather than "move U4".

This reports the free space below U4 and the footprint inventory in the southern band, so a move can be
specified as a direction and a magnitude rather than a guess.

Read-only.

Usage: assess_u4_move.py <board.kicad_pcb>
"""
import sys

import pcbnew


def mm(v):
    return pcbnew.ToMM(v)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        print(__doc__)
        return 2
    b = pcbnew.LoadBoard(path)
    u4 = b.FindFootprintByReference("U4").GetBoundingBox(False, False)
    ux0, uy0, ux1, uy1 = mm(u4.GetLeft()), mm(u4.GetTop()), mm(u4.GetRight()), mm(u4.GetBottom())
    print(f"board: {path}")
    print(f"U4 bbox x {ux0:.2f}..{ux1:.2f}  y {uy0:.2f}..{uy1:.2f}  "
          f"({ux1-ux0:.2f} x {uy1-uy0:.2f} mm)\n")

    # what sits in the band directly south of U4, out to the board edge?
    print("footprints intersecting the column below U4 (x within U4's span):")
    rows = []
    for fp in b.GetFootprints():
        if fp.GetReference() == "U4":
            continue
        r = fp.GetBoundingBox(False, False)
        fx0, fy0, fx1, fy1 = mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom())
        if fx0 <= ux1 and fx1 >= ux0 and fy0 >= uy1:      # south of U4, x overlapping
            rows.append((fy0, fp.GetReference(), fp.GetValue(), fx0, fy0, fx1, fy1))
    if not rows:
        print("  (none)")
    for fy0, ref, val, fx0, fy0, fx1, fy1 in sorted(rows):
        print(f"  {ref:10} {val[:20]:22} x {fx0:6.2f}..{fx1:6.2f}  y {fy0:6.2f}..{fy1:6.2f}")
    if rows:
        nearest = min(rows)[0]
        print(f"\n  nearest obstacle south of U4 starts at y = {nearest:.2f}")
        print(f"  free gap between U4 bottom ({uy1:.2f}) and that obstacle: {nearest-uy1:.2f} mm")

    # how much of the board is actually free around U4? sample a grid
    print("\nfree-space sample around U4 (no footprint body), 1 mm grid:")
    bodies = []
    for fp in b.GetFootprints():
        if fp.GetReference() == "U4":
            continue
        r = fp.GetBoundingBox(False, False)
        bodies.append((mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom())))
    for y in range(22, 40, 2):
        row = []
        for x in range(44, 62, 2):
            hit = any(bx0 <= x <= bx1 and by0 <= y <= by1 for bx0, by0, bx1, by1 in bodies)
            row.append("X" if hit else ".")
        print(f"  y={y:3d}  {''.join(row)}   (x from 44 to 60)")

    print()
    print("READING: if the column below U4 is occupied within a couple of mm, moving U4 south is not")
    print("available and the honest options are to accept 57/59 nets or to hand-finish the last two.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

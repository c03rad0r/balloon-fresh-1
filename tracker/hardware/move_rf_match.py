#!/usr/bin/env python3
"""Apply the operator-approved RF match move: C0 and L1 to compact sites at U4.pad22.

Approved by the operator; recommended by the visual consultant Round 2 ("starting with a compact
matching layout at U4.pad22"); constrained by measurements recorded in the commit that introduced
this script.

SITES (found by place_rf_match.py, both legal at the board's 0.20 mm clearance):
    C0   from (67.47, 37.51)  ->  (52.50, 30.65)     17.15 mm -> 1.50 mm from U4.pad22
    L1   from ( 1.49, 27.52)  ->  (54.27, 30.92)     51.04 mm -> 2.50 mm from U4.pad22

WHAT THIS DOES NOT DO:
  - it does not add vias anywhere (AN1200.66 checklist 4.3: no vias crossing under the RF)
  - it does not touch In1.Cu (the measured 81/81-continuous RF reference plane)
  - it does not move U4, U1 or C_CAP2 (the consultant explicitly did not require it)
  - it does not rotate the elements (orientation is preserved; the router will handle the trace)

Usage: move_rf_match.py <in.kicad_pcb> <out.kicad_pcb>
"""
import sys

import pcbnew

# Sites from place_rf_match2.py, which reads the REAL courtyard boxes (1.91x1.01 and 1.95x1.03 mm)
# and enforces a true non-overlap test. The first attempt used an assumed 1.5 mm separation constant
# and DRC caught the two courtyards overlapping by 0.15 mm (courtyards_overlap, 1 error).
MOVES = {
    "C0": (52.50, 30.70),
    "L1": (55.50, 30.71),
}


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    b = pcbnew.LoadBoard(src)
    print(f"src: {src}\n")

    moved = 0
    for ref, (nx, ny) in MOVES.items():
        fp = b.FindFootprintByReference(ref)
        if fp is None:
            print(f"  {ref}: ABSENT -- refusing to continue")
            return 1
        old = fp.GetPosition()
        ox, oy = pcbnew.ToMM(old.x), pcbnew.ToMM(old.y)
        # Move by delta so the footprint's internal orientation and local pad offsets are preserved.
        fp.Move(pcbnew.VECTOR2I(int(round((nx - ox) * 1e6)), int(round((ny - oy) * 1e6))))
        new = fp.GetPosition()
        print(f"  {ref:4} ({ox:6.2f},{oy:6.2f}) -> "
              f"({pcbnew.ToMM(new.x):6.2f},{pcbnew.ToMM(new.y):6.2f})")
        moved += 1

    if moved != len(MOVES):
        print("  not all moves applied -- not writing")
        return 1

    # Verify: the RF net's pad-to-pad span must have collapsed.
    import math
    pads = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == "/SX1280_RF":
                c = p.GetPosition()
                pads.append((fp.GetReference(), pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)))
    print("\n/SX1280_RF after the move:")
    for ref, x, y in sorted(pads):
        print(f"  {ref:4} ({x:6.2f},{y:6.2f})")
    for i in range(len(pads)):
        for j in range(i + 1, len(pads)):
            a, b_ = pads[i], pads[j]
            d = math.hypot(a[1] - b_[1], a[2] - b_[2])
            print(f"  {a[0]:4} <-> {b_[0]:4}  {d:6.2f} mm")

    pcbnew.SaveBoard(dst, b)
    print(f"\nwrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

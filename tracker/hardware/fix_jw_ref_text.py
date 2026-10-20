#!/usr/bin/env python3
"""Move J_W1/J_W3 reference text to the outboard pattern J_W2/J_W4 already use.

WHY THIS EXISTS (measured 2026-10-20, DRC at master 717bc927d):
`Wing_Tab_4P` places its Reference property at local (8.0, -7.0). The socket datum has
+x pointing INBOARD (ADR-048), so for the two sockets whose local +x maps into the board
(J_W1 rot 0, J_W3 rot 180) the ref text lands 8mm INSIDE the board:

  J_W1 ref at (13.20, 28.00)  -- inside, over U3/U2 silk
  J_W3 ref at (56.80, 42.00)  -- inside, over C_CAP2's silk (35 of the 77 silk_overlap items)

J_W2 and J_W4's refs sit at local (-8, +7) -- OUTBOARD, off the board edge -- and produce
ZERO violations (they appear nowhere in the DRC output). That pattern is therefore
proven-safe on this very board. This script moves J_W1/J_W3's refs to the same local
offset, mirrored:

  J_W1 (rot   0): world (-2.80, 42.00)   off-board west
  J_W3 (rot 180): world (72.80, 28.00)   off-board east

Silk outside the board outline is simply not printed by the fabricator; both J_W2/J_W4
refs have lived off-board through every DRC run without a single violation.

NOT TOUCHED: the functional orientation marks (fp_text 'W', '1', '4', '90') -- they are
documented interface geometry (WING-TO-HUB-SOCKET-SPEC s6) and stay where the spec puts
them. Their residual silk overlaps are cosmetic and counted separately.

Self-verifying: refuses (exit 3) unless both refs are found at the measured default
positions; prints before/after; the caller re-runs DRC.
"""
import argparse
import sys

import pcbnew

UM = 1_000_000.0

# measured default positions (footprint property (8.0,-7.0) under each rotation)
EXPECT = {
    "J_W1": (13.20, 28.00),
    "J_W3": (56.80, 42.00),
}
# the outboard pattern (local (-8, +7) under each rotation) -- J_W2/J_W4's proven offset
TARGET = {
    "J_W1": (-2.80, 42.00),
    "J_W3": (72.80, 28.00),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.inp)
    if not b:
        print("REFUSED: board did not load")
        return 3

    for ref, (ex, ey) in EXPECT.items():
        fp = b.FindFootprintByReference(ref)
        if fp is None:
            print(f"REFUSED: {ref} not found")
            return 3
        rt = fp.Reference()
        px, py = rt.GetPosition().x / UM, rt.GetPosition().y / UM
        if abs(px - ex) > 0.05 or abs(py - ey) > 0.05:
            print(f"REFUSED: {ref} ref at ({px:.2f},{py:.2f}) != measured default ({ex},{ey}) -- board state changed")
            return 3
        tx, ty = TARGET[ref]
        rt.SetPosition(pcbnew.VECTOR2I(int(tx * UM), int(ty * UM)))
        print(f"  {ref} ref text: ({px:.2f},{py:.2f}) -> ({tx:.2f},{ty:.2f})  [outboard, J_W2/J_W4 pattern]")

    # The interface marks ('W','1','4','90'): J_W2/J_W4 place ALL FOUR at local x=-8.00
    # (outboard, zero violations); J_W1/J_W3 place them at local x=+8.00 (inboard, overlapping
    # C_CAP2/TH_NTC1/U3 silk). Mirror them to the proven outboard row. Local y unchanged,
    # so the mark ORDER along the socket edge is preserved.
    import math
    MARK_MIRROR = {"J_W1": 0, "J_W3": 180}
    for ref, rot in MARK_MIRROR.items():
        fp = b.FindFootprintByReference(ref)
        pos = fp.GetPosition()
        c_, s_ = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        for gi in fp.GraphicalItems():
            if gi.GetClass() != "PCB_TEXT":
                continue
            q = gi.GetPosition()
            dx, dy = q.x / UM - pos.x / UM, q.y / UM - pos.y / UM
            lx = dx * c_ + dy * s_
            ly = -dx * s_ + dy * c_
            if abs(lx - 8.00) < 0.06:      # the inboard row
                nwx = pos.x / UM + (-8.00) * c_ - ly * s_
                nwy = pos.y / UM + (-8.00) * s_ + ly * c_
                gi.SetPosition(pcbnew.VECTOR2I(int(nwx * UM), int(nwy * UM)))
                print(f"  {ref} mark '{gi.GetText()}': ({q.x/UM:.2f},{q.y/UM:.2f}) -> ({nwx:.2f},{nwy:.2f})  [outboard]")

    b.Save(args.out)
    print(f"saved {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

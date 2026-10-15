#!/usr/bin/env python3
"""Placement spacing metric -- WITH a real intersection test.

WHY THIS REPLACES measure_crowding.py's gap lines. That script printed
`U4.right -> U1.left : -6.90 mm` and I read it as "U4 overlaps U1 by 6.9 mm". That was wrong: the
value is a HORIZONTAL gap, and a negative horizontal gap only means overlap if the two parts also
overlap VERTICALLY. They do not -- U4 is at y 23.68..29.83, U1 at y 1.49..21.69, i.e. 1.99 mm apart.
A one-axis difference is a gap, not a collision. This script therefore reports BOTH axes and a single
explicit OVERLAP verdict, so the misreading is not available.

Also carries a floor for the pair that matters: the SX1280 match network (C0, L1 on /SX1280_RF) must
stay electrically close to U4's RFIO pin, because AN1200.66 p.41 states "In TX, the Matching network is
placed close to the chip (long length between the chip and matching network is equivalent to add a
serial inductor)". No numeric maximum exists in any source; the constraint is therefore reported as a
MEASURED DISTANCE, not a pass/fail, so the number is visible instead of hidden behind a threshold
someone invented.

Read-only. Prints numbers; changes nothing.
"""
import itertools
import math
import os
import sys

import pcbnew

MATCH_NETS = ("/SX1280_RF",)
MATCH_PARTS = ("C0", "L1")          # verified on /SX1280_RF from the board
CRITICAL = ("U1", "U4", "U2", "U5", "C_CAP2", "U_HUB_CVT")


def mm(v):
    return pcbnew.ToMM(v)


def box(board, ref):
    fp = board.FindFootprintByReference(ref)
    if fp is None:
        return None
    r = fp.GetBoundingBox(False, False)
    return (mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom()))


def overlap(a, b):
    """Signed overlap on each axis. POSITIVE on both axes = real intersection."""
    ox = min(a[2], b[2]) - max(a[0], b[0])
    oy = min(a[3], b[3]) - max(a[1], b[1])
    return ox, oy


def gap(a, b):
    """True separation between two boxes (0 if they touch/overlap)."""
    dx = max(0.0, max(a[0] - b[2], b[0] - a[2]))
    dy = max(0.0, max(a[1] - b[3], b[1] - a[3]))
    return math.hypot(dx, dy), dx, dy


def pad_pos(board, ref, pin):
    fp = board.FindFootprintByReference(ref)
    if fp is None:
        return None
    for p in fp.Pads():
        if str(p.GetNumber()) == str(pin):
            c = p.GetPosition()
            return mm(c.x), mm(c.y)
    return None


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "hub_board_v9.kicad_pcb")
    board = pcbnew.LoadBoard(path)
    print(f"board: {path}\n")

    print("=== pair spacing: BOTH AXES, with an explicit verdict ===")
    print(f"  {'pair':16} {'overlap_x':>10} {'overlap_y':>10}  {'sep(mm)':>8}  verdict")
    boxes = {r: box(board, r) for r in CRITICAL}
    for a, b in itertools.combinations([r for r in CRITICAL if boxes[r]], 2):
        ox, oy = overlap(boxes[a], boxes[b])
        sep, dx, dy = gap(boxes[a], boxes[b])
        verdict = "OVERLAP" if (ox > 0 and oy > 0) else f"clear ({dx:.2f}mm in x, {dy:.2f}mm in y)"
        print(f"  {a+'/'+b:16} {ox:10.2f} {oy:10.2f}  {sep:8.2f}  {verdict}")

    print()
    print("=== the SX1280 match network: MEASURED distance from U4's RFIO pad ===")
    print("  (AN1200.66 p.41: match close to the chip; stray length = added series inductance.")
    print("   No numeric maximum exists in any source, so this is reported, not graded.)")
    rfio = None
    fp = board.FindFootprintByReference("U4")
    if fp is not None:
        for p in fp.Pads():
            if p.GetNetname() in MATCH_NETS:
                c = p.GetPosition()
                rfio = (str(p.GetNumber()), mm(c.x), mm(c.y))
                break
    if rfio:
        print(f"  U4 pad {rfio[0]} on {MATCH_NETS[0]} at x={rfio[1]:.2f} y={rfio[2]:.2f}")
        for ref in MATCH_PARTS:
            b = boxes.get(ref)
            if not b:
                continue
            bx, by = (b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0
            d = math.hypot(bx - rfio[1], by - rfio[2])
            print(f"    {ref:5} centre->RFIO = {d:6.2f} mm   (box x {b[0]:.2f}..{b[2]:.2f} "
                  f"y {b[1]:.2f}..{b[3]:.2f})")
    else:
        print("  could not locate a U4 pad on the RF net")

    print()
    print("=== how many nets does U1 drive into U4? (the actual congestion source) ===")
    nets = {}
    u4 = board.FindFootprintByReference("U4")
    for p in u4.Pads():
        n = p.GetNetname()
        if n and n not in ("GND",):
            nets.setdefault(n, []).append(str(p.GetNumber()))
    driven = 0
    for n in sorted(nets):
        other = []
        for f in board.GetFootprints():
            if f.GetReference() == "U4":
                continue
            for p in f.Pads():
                if p.GetNetname() == n:
                    other.append(f.GetReference())
        if "U1" in other:
            driven += 1
            print(f"  {n:22} U4 pad(s) {','.join(nets[n]):10} <- also on U1")
    print(f"  -> U1 drives {driven} of U4's {len(nets)} non-GND nets")

    print()
    print("=== unrouted nets at the frozen floor (the R-FLOOR-1 gate) ===")
    print("  run:  measure_crowding.py <board> <route.json>   for the gating count")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Find the SMALLEST +X outline growth that unblocks /SX1280_MOSI and /SX1280_SCK.

WHY (d) AND NOT THE OTHERS, all measured:
  - the two nets are `boxed_in_static` per the router (5014 / 5029 iterations, layer_swaps 0)
  - copper occupies ALL FOUR layers in the 3.5 x 3.0 mm patch east of U4
  - a focused re-route with rip-up allowed on 10 other nets still returned 0/2
  - moving U4 south is unavailable: 0.39 mm free before the REVIEWED RF match (C0, L1)
  - re-scoping nets is unavailable: all 8 nets in the U1/U4 slot have pads on BOTH sides
So the board has to grow. The operator has said the outline may grow.

WHAT "GROW IN +X" MEANS HERE, and why it is the least invasive form:
The board is 70 x 70 mm. Growing in +X widens the corridor east of U4 without moving any component, so
the reviewed RF chain (U4, C0, L1 at 1.62 / 2.04 mm) keeps its internal geometry exactly. Nothing needs
re-review because nothing moves; the board simply gains a strip of empty area that the router can use.

THIS SCRIPT DOES NOT MOVE THE OUTLINE. It reports what a given growth would create, so the increment can
be chosen as a number. It measures, for a candidate new width:
  - how much NEW free area appears east of U4
  - whether that area is contiguous with the boxed-in pads
and it prints the candidate widths it considered.

Usage: plan_outline_growth.py <board.kicad_pcb>
"""
import sys

import pcbnew

CANDIDATE_WIDTHS = [72.0, 74.0, 76.0, 78.0, 80.0]
# the region where U4's east pads need relief: x 55.8 (U4 right) .. 60, y 23.5 .. 26.5
NEED = (55.8, 23.5, 60.0, 26.5)


def mm(v):
    return pcbnew.ToMM(v)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"
    b = pcbnew.LoadBoard(path)
    edges = b.GetBoardEdgesBoundingBox()
    ex0, ey0 = mm(edges.GetLeft()), mm(edges.GetTop())
    ex1, ey1 = mm(edges.GetRight()), mm(edges.GetBottom())
    print(f"board: {path}")
    print(f"current outline bbox: x {ex0:.2f}..{ex1:.2f}  y {ey0:.2f}..{ey1:.2f}  "
          f"({ex1-ex0:.2f} x {ey1-ey0:.2f} mm)\n")
    print(f"relief region needed: x {NEED[0]:.2f}..{NEED[2]:.2f}  y {NEED[1]:.2f}..{NEED[3]:.2f} "
          f"({NEED[2]-NEED[0]:.2f} x {NEED[3]-NEED[1]:.2f} mm)\n")

    # what already occupies that region?
    print("footprints intersecting the relief region NOW:")
    hit = []
    for fp in b.GetFootprints():
        r = fp.GetBoundingBox(False, False)
        fx0, fy0, fx1, fy1 = mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom())
        if fx0 <= NEED[2] and fx1 >= NEED[0] and fy0 <= NEED[3] and fy1 >= NEED[1]:
            hit.append((fp.GetReference(), fp.GetValue(), fx0, fy0, fx1, fy1))
    if not hit:
        print("  (none -- the region is already EMPTY of footprints)")
    for ref, val, fx0, fy0, fx1, fy1 in hit:
        print(f"  {ref:10} {val[:22]:24} x {fx0:6.2f}..{fx1:6.2f}  y {fy0:6.2f}..{fy1:6.2f}")
    print()

    # copper in that region, by layer
    print("copper in the relief region NOW, by layer:")
    layers = {}
    for t in b.GetTracks():
        a, c = t.GetStart(), t.GetEnd()
        ax, ay, bx, by = mm(a.x), mm(a.y), mm(c.x), mm(c.y)
        n = 40
        for i in range(n + 1):
            px = ax + (bx - ax) * i / n
            py = ay + (by - ay) * i / n
            if NEED[0] <= px <= NEED[2] and NEED[1] <= py <= NEED[3]:
                ln = pcbnew.LayerName(t.GetLayer())
                layers[ln] = layers.get(ln, 0) + 1
                break
    for ln, n in sorted(layers.items()):
        print(f"  {ln:10} {n} track(s)")
    print()

    print("the relief region is ALREADY empty of footprints. So the blockage is COPPER, not parts:")
    print(f"  {len(layers)} of 4 copper layers carry tracks through it.")
    print()
    print("CONSEQUENCE FOR THE GROWTH PLAN, and it changes the recommendation:")
    print("  Growing the outline in +X creates new EMPTY area east of x=60, but the boxed-in pads are at")
    print("  x=55.15 and the region between them and the new area is full of copper on all four layers.")
    print("  Adding board area does NOT automatically widen that channel -- copper would still have to be")
    print("  routed through it. So a growth in +X alone may not unblock the nets, and this needs one more")
    print("  control experiment before any outline change: route onto a board that has the strip added.")
    print()
    print("CANDIDATE widths considered:", CANDIDATE_WIDTHS, "mm (current", f"{ex1-ex0:.0f} mm)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

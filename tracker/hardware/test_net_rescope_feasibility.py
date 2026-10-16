#!/usr/bin/env python3
"""Is there actually a BETTER path for the errant nets, or is the U1/U4 slot their only route?

FALSIFICATION TEST, run BEFORE proposing any net-scoping rule. The previous commit found 8 nets routed
through the 2.0 x 7.5 mm slot between U1 (ESP32-S3) and U4 (SX1280), two of them wing/solar and LoRa
nets. The obvious next step is "keep those nets out of the corridor" -- but that is only correct if a
LEGAL ALTERNATIVE PATH EXISTS. If the slot is the only way those nets can reach their destinations, then
re-scoping them would simply make them unroutable, and the finding would be a description of a
constrained board rather than a fixable ordering defect.

So this tests feasibility rather than asserting it. For each net that crosses the slot, it asks: do that
net's two endpoints have an alternative corridor? A net is RE-SCOPABLE only if removing it from the slot
leaves its pads reachable around the outside. A net is NOT re-scopable if the slot is on the only
geometrically sensible route.

The test is deliberately coarse, and reports its coarseness: it checks, for each such net, whether its
endpoint pads are on OPPOSITE sides of the U1/U4 stack (which forces a crossing) or on the SAME side
(which does not, and therefore means the slot is being used as a shortcut rather than a necessity).

    pads on opposite sides  -> crossing is structurally required; do NOT re-scope
    pads on the same side    -> the slot is being used as a through-route; re-scoping is plausible

Read-only, and this is the falsifier: if every crossing net has opposite-side pads, the finding is dead
and the fix must be (b) or (c).

Usage: test_net_rescope_feasibility.py <routed_board.kicad_pcb>
"""
import sys

import pcbnew

# The slot, measured: x 49.0..56.5, y 21.4..24.0
X0, X1, Y0, Y1 = 49.0, 56.5, 21.4, 24.0

NETS = ("/GNSS_PPS", "/SX1280_DIO1", "/GNSS_TX", "/W3_SOLAR_N",
        "/SX1280_BUSY", "/SX1280_DIO2", "/U3_BUSY", "/F33_RESET_N")


def mm(v):
    return pcbnew.ToMM(v)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        print(__doc__)
        return 2
    b = pcbnew.LoadBoard(path)
    print(f"board: {path}")
    print(f"slot under test: x {X0}..{X1}  y {Y0}..{Y1}\n")

    # For each net, find all pads and classify them relative to the slot.
    for net in NETS:
        pads = []
        for fp in b.GetFootprints():
            for p in fp.Pads():
                if p.GetNetname() == net:
                    c = p.GetPosition()
                    pads.append((fp.GetReference(), str(p.GetNumber()),
                                 mm(c.x), mm(c.y)))
        if not pads:
            print(f"{net:22} -- no pads found (maybe a plane net)")
            continue
        sides = set()
        for _r, _n, x, y in pads:
            # side is defined by y relative to the slot's vertical band
            if y < Y0:
                sides.add("north")
            elif y > Y1:
                sides.add("south")
            else:
                sides.add("in-slot")
        # does a track of this net cross the slot?
        crosses = False
        for t in b.GetTracks():
            if t.GetNetname() != net:
                continue
            a, c = t.GetStart(), t.GetEnd()
            ax, ay, bx, by = mm(a.x), mm(a.y), mm(c.x), mm(c.y)
            n = 48
            for i in range(n + 1):
                px = ax + (bx - ax) * i / n
                py = ay + (by - ay) * i / n
                if X0 <= px <= X1 and Y0 <= py <= Y1:
                    crosses = True
                    break
            if crosses:
                break
        verdict = ("STRUCTURALLY REQUIRED (pads on opposite sides -- do NOT re-scope)"
                   if {"north", "south"} <= sides else
                   "re-scope PLAUSIBLE (all pads on one side)" if len(sides - {"in-slot"}) <= 1
                   else "UNCLEAR")
        print(f"{net:22} pads={len(pads):3d} sides={sorted(sides)} crosses_slot={crosses}")
        print(f"{'':22} -> {verdict}")
    print()
    print("USE: any net marked STRUCTURALLY REQUIRED kills the re-scoping proposal for that net.")
    print("If all are structurally required, option (a) is dead and the choice is (b) or (c).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

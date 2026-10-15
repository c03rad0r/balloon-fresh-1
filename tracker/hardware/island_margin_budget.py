#!/usr/bin/env python3
"""How much margin can a GND island over J_W* pad 2 actually have before it shorts a neighbour?

Establishes the geometric budget for the approved fix. J_W* pad 2 is a 4.00 x 1.20 mm GND land.
Its neighbours on the SAME footprint are pad 1 and pad 3, both 1.20 mm tall, on a pitch of one pad
height plus one gap.

Required clearance (the zone's own setting, and the board's frozen floor): 0.20 mm.
So the island may extend past pad 2's edge by at most  (gap_between_pads - clearance) mm, i.e. only if
the pads are further apart than one clearance. This prints the actual budget.

Read-only.
"""
import sys

import pcbnew

BOARD = sys.argv[1] if len(sys.argv) > 1 else "/tmp/stitch_v5_filled.kicad_pcb"
CLEARANCE_MM = float(sys.argv[2]) if len(sys.argv) > 2 else 0.20

b = pcbnew.LoadBoard(BOARD)
print(f"board: {BOARD}   required clearance: {CLEARANCE_MM} mm\n")

for ref in ("J_W1", "J_W2", "J_W3", "J_W4"):
    fp = b.FindFootprintByReference(ref)
    if fp is None:
        continue
    print(f"{ref}:")
    pads = []
    for p in fp.Pads():
        c = p.GetPosition()
        s = p.GetSize()
        pads.append((str(p.GetNumber()), p.GetNetname(), pcbnew.ToMM(c.y),
                     pcbnew.ToMM(s.x), pcbnew.ToMM(s.y)))
    # unique by pad number (the land set carries two copies per number)
    seen = {}
    for num, net, y, sx, sy in pads:
        seen[num] = (net, y, sx, sy)
    for num in sorted(seen):
        net, y, sx, sy = seen[num]
        print(f"  pad {num:3} net {net:14} y={y:6.2f}  land {sx:.2f} x {sy:.2f}")

    # If pad 2 is GND, work out the gap to its vertical neighbours.
    if "2" in seen and seen["2"][0] == "GND":
        gnd_y = seen["2"][1]
        gnd_h = seen["2"][3]
        for num, (net, y, _sx, _sy) in sorted(seen.items()):
            if num == "2":
                continue
            edge_gap = abs(y - gnd_y) - gnd_h / 2.0 - _sy / 2.0
            budget = edge_gap - CLEARANCE_MM
            verdict = (f"island margin may be up to {budget:.2f} mm"
                       if budget > 0 else "NO margin available -- an island here cannot clear "
                                         f"{num} ({net})")
            print(f"      vs pad {num} ({net}): edge gap {edge_gap:.2f} mm -> {verdict}")
    print()

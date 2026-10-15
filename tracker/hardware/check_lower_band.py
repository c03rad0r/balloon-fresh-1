#!/usr/bin/env python3
"""Is the consultant's proposed free band actually consumed by the U2/U3 MODULE BODIES?

The consultant twice warned: "the large apparently empty rectangle inside U2 is not evidence of free
component-placement area. Its body envelope matters even if routing underneath is permitted." and
flagged the limiting assumption "that band is not reserved for mechanical hardware, cable access,
antenna keepouts, or opposite-side components."

Pad occupancy was already checked (only C_CAP1, C_CAP2, ANT3 intersect y 51..64). This checks the
BODY ENVELOPE instead: the courtyard/fab outline of each large module, plus antenna keepouts, which is
a different and larger region than the pads.

Read-only.
"""
import os
import sys

import pcbnew

BOARD = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"
BAND = (51.0, 64.0)          # y range the consultant proposed
MODULES = ("U2", "U3", "U5", "U1")

b = pcbnew.LoadBoard(BOARD)
print(f"board: {BOARD}")
print(f"proposed free band: y {BAND[0]:.1f}..{BAND[1]:.1f}\n")


def mm(v):
    return pcbnew.ToMM(v)


print("=== module BODY envelopes (courtyard where present, else bbox) ===")
for ref in MODULES:
    fp = b.FindFootprintByReference(ref)
    if fp is None:
        print(f"  {ref}: absent")
        continue
    # courtyard is the placement-relevant envelope; bbox is the fallback
    try:
        cy = fp.GetCourtyard(pcbnew.F_CrtYd)
        if cy.OutlineCount():
            bb = cy.BBox()
            src = "courtyard F.CrtYd"
        else:
            raise ValueError("empty courtyard")
    except Exception:
        bb = fp.GetBoundingBox(False, False)
        src = "bbox (no courtyard)"
    x0, y0, x1, y1 = mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())
    inband = not (y1 < BAND[0] or y0 > BAND[1])
    print(f"  {ref:4} {fp.GetValue()[:20]:22} x {x0:6.2f}..{x1:6.2f} y {y0:6.2f}..{y1:6.2f}"
          f"   {'<-- INTERSECTS THE BAND' if inband else ''}   [{src}]")

print()
print("=== every footprint whose BODY intersects the band ===")
hits = []
for fp in b.GetFootprints():
    bb = fp.GetBoundingBox(False, False)
    x0, y0, x1, y1 = mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())
    if not (y1 < BAND[0] or y0 > BAND[1]):
        hits.append((fp.GetReference(), fp.GetValue(), x0, y0, x1, y1))
for ref, val, x0, y0, x1, y1 in sorted(hits, key=lambda t: (t[2], t[3])):
    w = x1 - x0
    print(f"  {ref:10} {val[:20]:22} x {x0:6.2f}..{x1:6.2f}  y {y0:6.2f}..{y1:6.2f}  w={w:5.2f}")
print(f"  -> {len(hits)} footprint(s)")

print()
print("=== antenna / connector keepouts from the board's own courtyard layer ===")
for fp in b.GetFootprints():
    ref = fp.GetReference()
    val = str(fp.GetValue())
    if not (ref.startswith("ANT") or ref.startswith("J_W") or "U.FL" in val):
        continue
    bb = fp.GetBoundingBox(False, False)
    x0, y0, x1, y1 = mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())
    inband = not (y1 < BAND[0] or y0 > BAND[1])
    print(f"  {ref:10} {val[:20]:22} x {x0:6.2f}..{x1:6.2f}  y {y0:6.2f}..{y1:6.2f}"
          f"   {'IN BAND' if inband else ''}")

print()
print("=== usable width left in the band, per x slice (no footprint body) ===")
for xa in range(0, 70, 5):
    xb = xa + 5
    occupied = False
    for ref, val, x0, y0, x1, y1 in hits:
        if x0 < xb and x1 > xa:
            occupied = True
            break
    print(f"  x {xa:2d}..{xb:2d}: {'occupied' if occupied else 'FREE'}")

#!/usr/bin/env python3
"""Why is J_W1 pad 2 not stitched? Report the pad geometry and its neighbours.

J_W1 pad 2 is the last GND holdout (DRC: "Pad 2 [GND] of J_W1 on F.Cu" vs the GND zone AND vs its own
B.Cu pad). The pad is a WING SOCKET land -- a duplicate pad number on two layers by design. The
stitcher's corrected predicate now REFUSES a stitch when either the via site OR the stub lacks
clearance, so it declined rather than making an illegal one. This prints what is actually in the way.

Read-only.
"""
import os
import sys

import pcbnew

BOARD = sys.argv[1] if len(sys.argv) > 1 else "/tmp/stitch_v5_filled.kicad_pcb"
b = pcbnew.LoadBoard(BOARD)
print(f"board: {BOARD}\n")

fp = b.FindFootprintByReference("J_W1")
if fp is None:
    print("J_W1 absent")
    sys.exit(1)

bb = fp.GetBoundingBox(False, False)
x0, y0 = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())
x1, y1 = pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())
print(f"J_W1 courtyard box: x {x0:.2f}..{x1:.2f}  y {y0:.2f}..{y1:.2f}")
print(f"  ({x1-x0:.2f} x {y1-y0:.2f} mm)\n")

print("pads:")
for p in fp.Pads():
    c = p.GetPosition()
    s = p.GetSize()
    d = p.GetDrillSize()
    try:
        ln = pcbnew.LayerName(p.GetLayer())
    except Exception:
        ln = "multi"
    print(f"  pad {str(p.GetNumber()):4} net {p.GetNetname():12} layer {ln:8} "
          f"at ({pcbnew.ToMM(c.x):6.2f},{pcbnew.ToMM(c.y):6.2f}) "
          f"size {pcbnew.ToMM(s.x):.2f}x{pcbnew.ToMM(s.y):.2f} "
          f"drill {pcbnew.ToMM(d.x):.2f}")

# What is physically near the pad centre, on the layers that matter?
cx, cy = None, None
for p in fp.Pads():
    if str(p.GetNumber()) == "2":
        c = p.GetPosition()
        cx, cy = pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)
        break
if cx is None:
    print("\nno pad 2")
    sys.exit(0)

print(f"\nneighbours within 3.0 mm of pad 2 centre ({cx:.2f},{cy:.2f}):")
R = 3.0
print("  -- pads --")
for f in b.GetFootprints():
    for p in f.Pads():
        c = p.GetPosition()
        px, py = pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)
        d = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
        if 0 < d <= R and not (f.GetReference() == "J_W1" and str(p.GetNumber()) == "2"):
            print(f"    {f.GetReference():8} pad {str(p.GetNumber()):4} net {p.GetNetname():14} "
                  f"d={d:5.2f}mm")
print("  -- tracks/vias --")
for t in b.GetTracks():
    for pt in (t.GetStart(), t.GetEnd()):
        px, py = pcbnew.ToMM(pt.x), pcbnew.ToMM(pt.y)
        d = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
        if 0 < d <= R:
            kind = "VIA" if t.Type() == pcbnew.PCB_VIA_T else "trk"
            print(f"    {kind} {t.GetNetname():14} layer {pcbnew.LayerName(t.GetLayer()):8} "
                  f"d={d:5.2f}mm at ({px:.2f},{py:.2f})")
            break

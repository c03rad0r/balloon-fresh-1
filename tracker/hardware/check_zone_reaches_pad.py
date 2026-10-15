#!/usr/bin/env python3
"""Does the F.Cu GND zone actually cover J_W1 pad 2? Sample the FILLED polygon.

The DRC item is "Zone 'GND_PLANE_F.Cu' [GND] on F.Cu  <->  Pad 2 [GND] of J_W1 on F.Cu". Both are on
F.Cu, so no via is needed: either the fill reaches the pad or it does not. This samples the zone's
FILLED polygon at the pad centre and at points inside the pad body, which distinguishes:

  - fill reaches the pad centre            -> pad is connected, DRC item is about something else
  - fill reaches the pad but not the centre-> thermal spokes, i.e. a connection setting
  - fill nowhere near the pad              -> the zone was clipped away there (a keepout, a clearance
                                              to something, or the pad sits outside the zone outline)

Read-only.
"""
import os
import sys

import pcbnew

BOARD = sys.argv[1] if len(sys.argv) > 1 else "/tmp/stitch_v5_filled.kicad_pcb"
b = pcbnew.LoadBoard(BOARD)
print(f"board: {BOARD}\n")

zones = [z for z in b.Zones() if z.GetNetname() == "GND"]
print(f"GND zones: {len(zones)}")
for z in zones:
    layers = [pcbnew.LayerName(l) for l in z.GetLayerSet().Seq()]
    print(f"  '{z.GetZoneName()}' layers={layers} filled={z.IsFilled()} "
          f"pad_conn={z.GetPadConnection()} clearance={pcbnew.ToMM(z.GetLocalClearance()):.2f}")

fzone = None
for z in zones:
    if z.GetLayer() == pcbnew.F_Cu:
        fzone = z
        break
if fzone is None:
    print("\nNO F.Cu GND zone found")
    sys.exit(1)

print()
fp = b.FindFootprintByReference("J_W1")
pad2 = None
for p in fp.Pads():
    if str(p.GetNumber()) == "2":
        pad2 = p
        break
if pad2 is None:
    print("J_W1 pad 2 absent")
    sys.exit(1)

c = pad2.GetPosition()
s = pad2.GetSize()
print(f"J_W1 pad 2 centre ({pcbnew.ToMM(c.x):.2f},{pcbnew.ToMM(c.y):.2f}) "
      f"size {pcbnew.ToMM(s.x):.2f}x{pcbnew.ToMM(s.y):.2f}")

filled = fzone.GetFilledPolysList(fzone.GetLayer())
print(f"F.Cu fill: {filled.OutlineCount()} outline(s)")

pts = {
    "pad centre": (c.x, c.y),
    "pad left edge": (c.x - s.x // 2 + 100000, c.y),
    "pad right edge": (c.x + s.x // 2 - 100000, c.y),
    "1mm above": (c.x, c.y - 1000000),
    "1mm below": (c.x, c.y + 1000000),
    "3mm above": (c.x, c.y - 3000000),
    "3mm left": (c.x - 3000000, c.y),
}
for label, (px, py) in pts.items():
    inside = filled.Contains(pcbnew.VECTOR2I(int(px), int(py)))
    print(f"  {label:16} ({pcbnew.ToMM(int(px)):6.2f},{pcbnew.ToMM(int(py)):6.2f})  "
          f"inside F.Cu fill: {inside}")

# Is there a keepout / rule area covering the pad?
print()
print("keepouts / rule areas covering the pad:")
found = False
for z in b.Zones():
    if z.GetIsRuleArea():
        for l in z.GetLayerSet().Seq():
            try:
                poly = z.GetFilledPolysList(l)
                if poly.OutlineCount() and poly.Contains(pcbnew.VECTOR2I(c.x, c.y)):
                    print(f"  RULE AREA '{z.GetZoneName()}' on {pcbnew.LayerName(l)} covers pad 2")
                    found = True
            except Exception:
                pass
if not found:
    print("  (none)")

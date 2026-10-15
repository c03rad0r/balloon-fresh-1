#!/usr/bin/env python3
"""Is J_W1.2's GND failure a THERMAL-RELIEF problem (pad isolated by spokes) or a real gap?

The DRC says: Zone 'GND_PLANE_F.Cu' [GND] on F.Cu  <->  Pad 2 [GND] of J_W1 on F.Cu.
Both are on F.Cu, so NO VIA IS REQUIRED -- the zone just has to reach the pad. The likely cause is
that the pad is a 4.00 x 1.20 mm land which cannot host the default thermal spokes across its short
(1.2 mm) axis, so the fill leaves it isolated. That is the same class the builder already fixes for
U4's QFN land by switching the pad to a SOLID zone connection.

This checks the pad's zone-connection setting, which is the thing that would have to change.

Read-only.
"""
import sys

import pcbnew

BOARD = sys.argv[1] if len(sys.argv) > 1 else "/tmp/stitch_v5_filled.kicad_pcb"
b = pcbnew.LoadBoard(BOARD)

PAD_ZONE_CONN = {}
for name in dir(pcbnew):
    if name.startswith("ZONE_CONNECTION"):
        PAD_ZONE_CONN[getattr(pcbnew, name)] = name
ZONE_CONN = {}
for name in dir(pcbnew):
    if name.startswith("ZONE_CONNECTION_") or name in ("PAD_ZONE_CONN_INHERITED",):
        ZONE_CONN[getattr(pcbnew, name)] = name

print(f"board: {BOARD}\n")
print("zone-connection constants available:")
for v, n in sorted(ZONE_CONN.items(), key=lambda kv: str(kv[1])):
    print(f"  {n} = {v}")
print()

targets = sys.argv[2].split(",") if len(sys.argv) > 2 else ["J_W1", "J_W2", "J_W3", "J_W4", "U4"]
for ref in targets:
    fp = b.FindFootprintByReference(ref)
    if fp is None:
        print(f"{ref}: absent")
        continue
    print(f"{ref}:")
    for p in fp.Pads():
        if p.GetNetname() != "GND":
            continue
        try:
            zc = p.GetZoneConnection()
            zn = ZONE_CONN.get(zc, str(zc))
        except Exception as e:
            zn = f"(unreadable: {e})"
        s = p.GetSize()
        print(f"  pad {str(p.GetNumber()):4} size {pcbnew.ToMM(s.x):.2f}x{pcbnew.ToMM(s.y):.2f} "
              f"drill {pcbnew.ToMM(p.GetDrillSize().x):.2f}  zone_connection={zn}  "
              f"spoke_angle={p.GetThermalSpokeAngle()}")

print()
print("GND zones on the board:")
for z in b.Zones():
    if z.GetNetname() != "GND":
        continue
    layers = [pcbnew.LayerName(l) for l in z.GetLayerSet().Seq()]
    print(f"  zone '{z.GetZoneName()}'  layers={layers}  "
          f"pad_conn={ZONE_CONN.get(z.GetPadConnection(), z.GetPadConnection())}  "
          f"clearance={pcbnew.ToMM(z.GetLocalClearance()):.2f}  "
          f"min_thickness={pcbnew.ToMM(z.GetMinThickness()):.2f}")

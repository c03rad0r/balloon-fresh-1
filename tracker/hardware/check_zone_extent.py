#!/usr/bin/env python3
"""Where is the F.Cu GND zone OUTLINE, and why is the wing area outside the fill?

Follow-up to check_zone_reaches_pad.py, which found J_W1 pad 2 is NOT covered by the F.Cu GND fill
for at least 3 mm in every direction, with no rule area over it. That rules out thermal relief and
rules out a keepout. The remaining possibilities are:

  (a) the zone OUTLINE does not extend over the wing pads (the fill is correct, the outline is small)
  (b) the outline covers them, but the fill is clipped out locally by copper clearance to the many
      other nets that converge there (J_W1.1 /W1_SOLAR_P, J_W1.3 /CUT_SENSE_W1, and the
      /SX1280_VBAT_IO tracks on In2.Cu seen at 1.7-2.0 mm)

This prints the zone outline bbox vs the board edge bbox, then samples a grid across the wing area to
show the shape of the unfilled region. Read-only.
"""
import sys

import pcbnew

BOARD = sys.argv[1] if len(sys.argv) > 1 else "/tmp/stitch_v5_filled.kicad_pcb"
b = pcbnew.LoadBoard(BOARD)
print(f"board: {BOARD}\n")

be = b.GetBoardEdgesBoundingBox()
print(f"board edge bbox: x {pcbnew.ToMM(be.GetLeft()):7.2f}..{pcbnew.ToMM(be.GetRight()):7.2f}"
      f"  y {pcbnew.ToMM(be.GetTop()):7.2f}..{pcbnew.ToMM(be.GetBottom()):7.2f}")

for z in b.Zones():
    if z.GetNetname() != "GND":
        continue
    # NOTE: ZONE has no GetOutline() in this build; the outline is the filled polys list, and the
    # declared boundary is available via GetFilledPolysList only after a fill. Use the raw outline
    # polygon count from the zone's own poly set accessor that does exist.
    n_out = None
    for acc in ("OutlineCount", "GetOutlineArea"):
        try:
            n_out = getattr(z, acc)()
            break
        except Exception:
            continue
    print(f"\nzone '{z.GetZoneName()}'  layer={pcbnew.LayerName(z.GetLayer())}  "
          f"pad_conn={z.GetPadConnection()}  min_thickness={pcbnew.ToMM(z.GetMinThickness()):.3f}"
          f"  (outline-count accessor: {n_out})")

# The wing region: J_W1 is at x 4.67..12.88, y 30.18..39.83.
print("\nsampling the F.Cu FILL over the J_W1 region (x 3..15, y 28..42):")
fz = None
for z in b.Zones():
    if z.GetNetname() == "GND" and z.GetLayer() == pcbnew.F_Cu:
        fz = z
        break
if fz is None:
    print("  no F.Cu GND zone")
    sys.exit(1)
filled = fz.GetFilledPolysList(fz.GetLayer())
print(f"  fill outlines: {filled.OutlineCount()}")
for i in range(filled.OutlineCount()):
    bb = filled.Outline(i).BBox()
    a = pcbnew.ToMM((bb.GetRight() - bb.GetLeft()) * (bb.GetBottom() - bb.GetTop())) / 1e6
    print(f"    fill {i}: x {pcbnew.ToMM(bb.GetLeft()):7.2f}..{pcbnew.ToMM(bb.GetRight()):7.2f}"
          f"  y {pcbnew.ToMM(bb.GetTop()):7.2f}..{pcbnew.ToMM(bb.GetBottom()):7.2f}"
          f"  pts={filled.Outline(i).PointCount()}")

print("\ngrid sample ('.' = inside fill, 'x' = outside):")
ys = [28 + 2 * k for k in range(8)]
xs = [3 + 1.5 * k for k in range(9)]
print("        " + "".join(f"{x:6.1f}" for x in xs))
for y in ys:
    row = []
    for x in xs:
        inside = filled.Contains(pcbnew.VECTOR2I(int(x * 1e6), int(y * 1e6)))
        row.append("     ." if inside else "     x")
    print(f"  y={y:5.1f}" + "".join(row))

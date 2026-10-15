#!/usr/bin/env python3
"""Is the RF-match corridor at U4.pad22 clear of C_CAP2 and U1 on ALL layers?

Closes the visual consultant's assumption 3: "Leave C_CAP2 and U1 provisionally unchanged -- neither
footprint nor its required routing/clearances intersects the selected RF corridor. Measure that
corridor against their all-layer geometry."

The corridor is the region the compact 2.4 GHz match would occupy: a rectangle around U4's RFIO pad
(U4.pad22 at 52.50, 29.15) large enough for two 0402-class match elements and their traces, plus the
ground reference beneath. This reports, for each copper layer, which foreign nets occupy that region,
so "clear" is a read number and not an assertion.

Read-only.
"""
import sys

import pcbnew

BOARD = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"
# RFIO pad coordinate, read earlier from the board.
RFIO = (52.50, 29.15)
# A compact match needs only a few mm; take a deliberately generous 4 mm box so the answer is
# conservative -- if 4 mm is clear, a tighter layout certainly is.
HALF = 4.0

b = pcbnew.LoadBoard(BOARD)
x0, y0 = RFIO[0] - HALF, RFIO[1] - HALF
x1, y1 = RFIO[0] + HALF, RFIO[1] + HALF
print(f"board: {BOARD}")
print(f"RF corridor tested: x {x0:.2f}..{x1:.2f}  y {y0:.2f}..{y1:.2f}  "
      f"({2*HALF:.1f} x {2*HALF:.1f} mm around U4.pad22)\n")


def inside(px, py):
    return x0 <= px <= x1 and y0 <= py <= y1


def box_corners(box):
    return ((box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3]))


print("=== footprints whose BBox intersects the corridor ===")
hits = []
for fp in b.GetFootprints():
    r = fp.GetBoundingBox(False, False)
    bb = (pcbnew.ToMM(r.GetLeft()), pcbnew.ToMM(r.GetTop()),
          pcbnew.ToMM(r.GetRight()), pcbnew.ToMM(r.GetBottom()))
    # rectangle overlap test
    if bb[0] <= x1 and bb[2] >= x0 and bb[1] <= y1 and bb[3] >= y0:
        hits.append((fp.GetReference(), fp.GetValue(), bb))
if not hits:
    print("  (none)")
for ref, val, bb in sorted(hits):
    print(f"  {ref:8} {val[:22]:24} x {bb[0]:6.2f}..{bb[2]:6.2f}  y {bb[1]:6.2f}..{bb[3]:6.2f}")

print()
print("=== copper (tracks/vias) inside the corridor, by layer and net ===")
occ = {}
for t in b.GetTracks():
    for pt in (t.GetStart(), t.GetEnd()):
        px, py = pcbnew.ToMM(pt.x), pcbnew.ToMM(pt.y)
        if inside(px, py):
            ln = pcbnew.LayerName(t.GetLayer())
            kind = "via" if t.Type() == pcbnew.PCB_VIA_T else "track"
            key = (ln, t.GetNetname(), kind)
            occ[key] = occ.get(key, 0) + 1
if not occ:
    print("  (no track or via vertices inside the corridor)")
for (ln, net, kind), n in sorted(occ.items()):
    print(f"  {ln:8} {kind:5} {net:22} {n} vertex/vertices")

print()
print("=== pads whose centre lies inside the corridor ===")
padnets = {}
for fp in b.GetFootprints():
    for p in fp.Pads():
        c = p.GetPosition()
        px, py = pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)
        if inside(px, py):
            key = (fp.GetReference(), str(p.GetNumber()), p.GetNetname())
            padnets[key] = True
if not padnets:
    print("  (none)")
for (ref, num, net) in sorted(padnets):
    print(f"  {ref:8} pad {num:4} net {net}")

print()
print("=== GND reference continuity inside the corridor, per layer ===")
for name, layer in (("F.Cu", pcbnew.F_Cu), ("In1.Cu", pcbnew.In1_Cu),
                    ("In2.Cu", pcbnew.In2_Cu), ("B.Cu", pcbnew.B_Cu)):
    z = None
    for zz in b.Zones():
        if zz.GetNetname() == "GND" and zz.GetLayer() == layer:
            z = zz
            break
    if z is None:
        print(f"  {name:8} no GND zone")
        continue
    f = z.GetFilledPolysList(layer)
    tot = okc = 0
    steps = 9
    for i in range(steps):
        for j in range(steps):
            px = x0 + (x1 - x0) * i / (steps - 1)
            py = y0 + (y1 - y0) * j / (steps - 1)
            tot += 1
            if f.Contains(pcbnew.VECTOR2I(int(px * 1e6), int(py * 1e6))):
                okc += 1
    print(f"  {name:8} {okc}/{tot} sample points inside the GND fill")

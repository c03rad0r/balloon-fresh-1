#!/usr/bin/env python3
"""Add a bounded GND zone island over the J_W* wing GND pads.

THE DEFECT (measured, 2026-10-15). The F.Cu GND plane spans the whole board (fill outline 3:
x 0.50..69.50, y 0.50..69.50) but carries a ~7 x 8 mm HOLE over the J_W1..J_W4 wing socket lands.
Sampled from the FILLED polygon, J_W1 pad 2 at (8.20, 34.10) is OUTSIDE the fill, with fill on both
sides, and NO rule area covers it. Cause: the pad's neighbours sit 1.80 mm away
(J_W1.1 /W1_SOLAR_P, J_W1.3 /CUT_SENSE_W1) and /SX1280_VBAT_IO runs at 1.70 mm, so the parent zone's
0.20 mm clearance plus 0.25 mm minimum thickness carves the copper back to nothing there.

WHY A ZONE ISLAND AND NOT A VIA. A stitch via connects a pad to copper on another layer. There is no
copper to connect to -- the void is on F.Cu itself, and the stitcher's own corrected predicate
therefore and correctly refused. The repair is to put copper THERE.

WHAT THIS ADDS. For each J_W* footprint with a GND pad, a small rectangular GND zone on F.Cu with:
  - HIGHER PRIORITY than the parent plane, so it is poured first / wins the local area
  - the SAME net (GND), so it is not a separate net and cannot create a false connection
  - a boundary drawn around the pad plus a margin, so the island is bounded and does not try to pour
    the whole board
  - solid pad connection, matching what the builder already does for pads that cannot host spokes

The island is bounded to the pad's own neighbourhood on purpose: a wide island would be clipped by
the same neighbour clearances and reproduce the hole.

Usage: add_gnd_island.py <in.kicad_pcb> <out.kicad_pcb> [--margin-mm M] [--dry-run]
"""
import os
import sys

import pcbnew

MARGIN_MM = 1.2          # how far the island extends past the pad body
ISLAND_PRIORITY = 5      # above the parent plane so it wins the local area


def mm(v):
    return pcbnew.ToMM(v)


def vec(x_mm, y_mm):
    return pcbnew.VECTOR2I(int(round(x_mm * 1e6)), int(round(y_mm * 1e6)))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    margin = MARGIN_MM
    if "--margin-mm" in sys.argv:
        margin = float(sys.argv[sys.argv.index("--margin-mm") + 1])
    dry = "--dry-run" in sys.argv

    board = pcbnew.LoadBoard(src)
    print(f"src: {src}  margin={margin} mm  dry_run={dry}\n")

    made = 0
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if not ref.startswith("J_W"):
            continue
        gnd_pads = [p for p in fp.Pads() if p.GetNetname() == "GND"]
        if not gnd_pads:
            continue
        for pad in gnd_pads:
            c = pad.GetPosition()
            s = pad.GetSize()
            cx, cy = mm(c.x), mm(c.y)
            halfw, halfh = mm(s.x) / 2.0, mm(s.y) / 2.0
            x0, y0 = cx - halfw - margin, cy - halfh - margin
            x1, y1 = cx + halfw + margin, cy + halfh + margin

            print(f"  {ref} pad {pad.GetNumber()}: pad centre ({cx:.2f},{cy:.2f}) "
                  f"size {mm(s.x):.2f}x{mm(s.y):.2f}")
            print(f"      island extent x {x0:.2f}..{x1:.2f}  y {y0:.2f}..{y1:.2f}"
                  f"  ({x1-x0:.2f} x {y1-y0:.2f} mm)")

            if dry:
                made += 1
                continue

            z = pcbnew.ZONE(board)
            z.SetLayer(pcbnew.F_Cu)
            z.SetNetCode(pad.GetNetCode())
            z.SetZoneName(f"GND_ISLAND_{ref}_{pad.GetNumber()}")
            z.SetLocalClearance(pcbnew.FromMM(0.2))
            z.SetMinThickness(pcbnew.FromMM(0.25))
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)   # solid: the pad is the point
            z.SetAssignedPriority(ISLAND_PRIORITY)
            # Isolate islands: without this a zone island that connects to nothing is dropped by
            # KiCad's fill as a "remove islands" candidate, which would silently undo the fix.
            z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
            z.SetDoNotAllowCopperPour(False)

            out = pcbnew.SHAPE_POLY_SET()
            out.NewOutline()
            for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
                out.Append(vec(x, y))
            z.SetOutline(out)
            board.Add(z)
            made += 1

    print(f"\nislands {'would be' if dry else ''} added: {made}")
    if dry:
        print("--dry-run: nothing written")
        return 0
    if made == 0:
        print("NOTHING TO DO: no J_W* GND pads found. Refusing to write an unchanged board.")
        return 1
    pcbnew.SaveBoard(dst, board)
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

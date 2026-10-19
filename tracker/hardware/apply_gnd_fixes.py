"""Apply the GND fixes that are MEASURED AND LEGAL, and refuse the ones that are not.

STATE OF PLAY (all measured on the filled canonical board, see docs/fab/D12-*):

  B) In1.Cu island 1 stitching  -- LEGAL, being applied.
     3 x 0.60/0.30 GND vias at (35.00,43.00) clearance 0.390, (33.00,44.00) 0.200, (34.00,44.00) 0.223.
     Each lands inside In1 island1 AND B.Cu main, so it ties the 29.2 mm2 island down with redundancy
     instead of the single via at U3.18. Astra's ruling: "add 2-3 well-placed GND stitching vias from
     the island to B.Cu main", and do NOT reroute +3V3.

  A) U_HUB_CVT.2 GND stub -- NOT applied here. The direct vertical is blocked at y=3.2..3.3 by pad
     U_HUB_CVT.3 and by U_HUB_CVT.17 (the GND thermal pad, which is itself UNASSIGNED in the netlist,
     so it is not a valid GND target). Needs an escape around the pad ring; separate work.

  C) U4.13 GND -- NOT applied. Measured dead ends:
       - no via fits inside its 0.298 mm-tall fragment
       - east: /SX1280_VDD blocks every x in 55.70..56.60
       - west: /SX1280_DCC_SW vertical at x=54.40; the thermal pad's east edge is x=54.100, so a
         0.200 track needs 0.300 clearance and the minimum legal x IS 54.400 -- it cannot nudge west
       - replacing VDD's diagonal: 0 legal corridors found
     So it needs DCC_SW (or VDD) moved to an INNER LAYER. That is a bigger change and is not attempted
     unattended.

WHY A SCRIPT THAT REFUSES: the two earlier attempts at U4.13 produced (1) a via that would have shorted
GND to VDD at -0.2411 mm, and (2) a planned VDD leg overlapping a planned GND via at -0.250 mm. Both were
caught before touching the board. This tool only writes what it has proven.

Run:
    ~/venvs/kicad/bin/python tracker/hardware/apply_gnd_fixes.py \\
        --in <board> --out <out> [--apply]
"""
from __future__ import annotations

import argparse
import math
import sys

import pcbnew

UM = 1_000_000.0
VIA_D = 0.600
VIA_DRILL = 0.300
CLR = 0.200

# Measured legal stitching vias for In1 island 1 (see module docstring).
STITCH = [(35.00, 43.00, 0.390, "In1 island1 <-> B.Cu main"),
          (33.00, 44.00, 0.200, "In1 island1 <-> B.Cu main"),
          (34.00, 44.00, 0.223, "In1 island1 <-> B.Cu main")]


def segd(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def recheck(board, x, y, radius):
    """Re-verify a via site against the board AS LOADED, all four layers, no net exclusions."""
    gnd = board.FindNet("GND").GetNetCode()
    worst = (1e9, None)
    for t in board.GetTracks():
        if t.GetNetCode() == gnd:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            p = t.GetPosition()
            d = math.hypot(x - p.x / UM, y - p.y / UM) - t.GetWidth(pcbnew.F_Cu) / 2 / UM - radius
            if d < worst[0]:
                worst = (d, "via " + str(t.GetNetname()))
        elif t.Type() == pcbnew.PCB_TRACE_T:
            s, e = t.GetStart(), t.GetEnd()
            d = segd(x, y, s.x / UM, s.y / UM, e.x / UM, e.y / UM) - t.GetWidth() / 2 / UM - radius
            if d < worst[0]:
                worst = (d, board.GetLayerName(t.GetLayer()) + " trk " + str(t.GetNetname()))
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetCode() == gnd:
                continue
            pos = p.GetPosition()
            ww, hh = p.GetSize().x / UM, p.GetSize().y / UM
            px, py = pos.x / UM, pos.y / UM
            dx = max(px - ww / 2 - x, 0.0, x - (px + ww / 2))
            dy = max(py - hh / 2 - y, 0.0, y - (py + hh / 2))
            d = math.hypot(dx, dy) - radius
            if d < worst[0]:
                worst = (d, "pad " + fp.GetReference() + "." + str(p.GetNumber()))
    # via-to-via spacing against existing GND vias
    for t in board.GetTracks():
        if t.GetNetCode() == gnd and t.Type() == pcbnew.PCB_VIA_T:
            p = t.GetPosition()
            d = math.hypot(x - p.x / UM, y - p.y / UM) - 0.800
            if d < worst[0]:
                worst = (d, "existing GND via")
    return worst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    board = pcbnew.LoadBoard(args.inp)
    gnd = board.FindNet("GND")

    print("=== B) In1 island 1 stitching vias ===")
    accept = []
    for x, y, recorded, note in STITCH:
        c = recheck(board, x, y, VIA_D / 2)
        flag = "OK " if c[0] >= CLR else "REJECT"
        print(f"  {flag} ({x:.2f},{y:.2f}) recorded {recorded:.3f} -> re-measured {c[0]:+.3f} vs {c[1]}")
        if c[0] >= CLR:
            accept.append((x, y))

    print(f"\n  {len(accept)}/{len(STITCH)} sites pass re-verification")
    if len(accept) < 2:
        print("  REFUSING: fewer than 2 stitching vias would not add redundancy")
        return 1

    if not args.apply:
        print("\n(dry run -- pass --apply to write)")
        return 0

    for x, y in accept:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(int(round(x * UM)), int(round(y * UM))))
        v.SetWidth(int(round(VIA_D * UM)))
        v.SetDrill(int(round(VIA_DRILL * UM)))
        v.SetNet(gnd)
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        board.Add(v)
        print(f"  added stitching via ({x:.2f},{y:.2f})")

    print("  refilling zones")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(args.out, board)
    print(f"  saved {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

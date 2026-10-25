#!/usr/bin/env python3
"""Add the GND / +3V3 / VSCAP pours to hub_board_v10.kicad_pcb, IN PLACE.

WHY
---
The hub reports 147 unrouted items. MEASURED split of that number:

    82  GND       <- pour net
    16  +3V3      <- pour net
    11  /VSCAP    <- pour net
   ~38  signal    <- real track work

and `b.Zones()` returns **0**. The board has no copper pours at all, so every GND/+3V3/VSCAP
pad shows as unrouted no matter how much signal routing is done. The router deliberately skips
rails (`RAILS = ("GND", "+3V3")` in route_v10_astar.py: "Rails are POUR territory, ADR-118
two-sided planes; v9 practice").

So ~109 of the 147 are not track work. They are missing planes.

APPROACH IS COPIED FROM build_hub_board_v9.py, which is the proven in-repo pattern:
  * one zone per layer, inset from the outline by a margin
  * thermal relief by default, SOLID for pads too small to take two spokes
  * ZONE_FILLER afterwards
v10 is 2-layer (F.Cu / B.Cu), so two GND zones. +3V3 and VSCAP get zones on B.Cu INSIDE the
GND zone's keepout (a zone of a different net carves itself out of the GND fill automatically;
KiCad resolves the priority), which keeps three rails from fighting over the same copper.

NOT a fabrication release. After this, DRC must be re-run and the remaining signal nets routed.

Run:  /usr/bin/python3 tracker/hardware/add_hub_planes.py [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")

EDGE_MARGIN_MM = 0.5    # keep the plane off the routed edge
CLEARANCE_MM = 0.25
MIN_THICK_MM = 0.25
# THERMAL vs SOLID THRESHOLD — measured, not guessed.
# First attempt used "min dimension < 2*SPOKE (0.6 mm) -> SOLID" and produced 9
# `starved_thermal` violations: pads of 2.0x0.7, 1.8x0.8 and even 4.0x1.2 could not fit two
# 0.3 mm spokes at 0.25 mm clearance. The pad is too NARROW for the relief, not too small in
# area, so the test must be on the minimum dimension with headroom for spokes + clearance.
SOLID_BELOW_MM = 1.5    # 2 spokes (0.6) + 2 clearances (0.5) + margin

# order matters: GND first (largest), then the smaller rails carve inside it
RAILS = [("GND", ["F.Cu", "B.Cu"]), ("+3V3", ["B.Cu"]), ("/VSCAP", ["B.Cu"])]


def net_by_name(board, name):
    for code in range(board.GetNetCount()):
        n = board.FindNet(code)
        if n and n.GetNetname() == name:
            return n
    return None


def board_rect_mm(board):
    bb = board.GetBoardEdgesBoundingBox()
    return (bb.GetX() / 1e6, bb.GetY() / 1e6,
            bb.GetWidth() / 1e6, bb.GetHeight() / 1e6)


def layer_id(name):
    return {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu,
            "In1.Cu": pcbnew.In1_Cu}[name]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    board = pcbnew.LoadBoard(BOARD)
    ox, oy, w, h = board_rect_mm(board)
    print(f"board {w:.2f} x {h:.2f} mm at ({ox:.2f}, {oy:.2f})")
    print(f"existing zones: {len(board.Zones())}")

    if args.dry_run:
        for name, layers in RAILS:
            n = net_by_name(board, name)
            print(f"  would pour {name!r} on {layers}"
                  f" -> net {'found code %d' % n.GetNetCode() if n else 'MISSING'}")
        return 0

    added = []
    for name, layers in RAILS:
        net = net_by_name(board, name)
        if net is None:
            print(f"SKIP {name}: net not on the board")
            continue
        for lname in layers:
            # A pad too small to take two spokes gets a SOLID tie: thermal relief on a
            # 0.4 mm pad is how a plane looks connected and is not.
            for fp in board.GetFootprints():
                for pad in fp.Pads():
                    if pad.GetNetname() != name:
                        continue
                    sz = pad.GetSize()
                    if min(sz.x, sz.y) / 1e6 < SOLID_BELOW_MM:
                        pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
            z = pcbnew.ZONE(board)
            z.SetLayer(layer_id(lname))
            z.SetNet(net)
            z.SetZoneName(f"{name.strip('/').replace('+', 'P')}_{lname.replace('.', '')}")
            z.SetLocalClearance(pcbnew.FromMM(CLEARANCE_MM))
            z.SetMinThickness(pcbnew.FromMM(MIN_THICK_MM))
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
            z.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.3))
            poly = z.Outline()
            poly.NewOutline()
            m = EDGE_MARGIN_MM
            for x, y in ((ox + m, oy + m), (ox + w - m, oy + m),
                         (ox + w - m, oy + h - m), (ox + m, oy + h - m)):
                poly.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
            board.Add(z)
            added.append(f"{name}@{lname}")

    print(f"added {len(added)} zone(s): {added}")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(BOARD, board)
    print("filled and saved")

    b2 = pcbnew.LoadBoard(BOARD)
    b2.BuildConnectivity()
    print(f"zones now: {len(b2.Zones())}")
    print(f"unrouted now: {b2.GetConnectivity().GetUnconnectedCount(False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

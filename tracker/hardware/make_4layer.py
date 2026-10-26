#!/usr/bin/env python3
"""Convert hub_board_v10 from 2 copper layers to 4 (operator decision, 2026-10-25).

WHY 4 LAYERS -- AND WHY IT ADDRESSES THE MEASURED BLOCKER
--------------------------------------------------------
The radio link is blocked because the space a U1 net must cross is already occupied by nets that
were routed EARLIER. Measured facts:

  * U1 pad pitch 1.27 mm, copper-to-copper gap 0.370 mm.
  * Rules 0.2 mm clearance + 0.2 mm track => a track between pads needs 0.600 mm. Deficit 0.230 mm,
    so no track passes BETWEEN adjacent pads at any legal width.
  * Therefore every escape must go AROUND the module, and the corridors around it are full
    (/I2C_SCL, /I2C_SDA, /USB_DN, J_PROG pads, and the GNSS/USB/U3 tracks below U1).
  * The board was 2-layer: F.Cu and B.Cu only. No layer existed on which the earlier nets could
    move aside.

**The 4th/3rd layer does NOT let a track squeeze between pads** -- no layer can, because the gap is
in the pad ROW, not in the layer stack. What it does is give the nets that currently own the
corridors somewhere else to go. That is the whole mechanism, stated plainly so it is not
over-claimed.

STACKUP CHOSEN
--------------
    F.Cu    signal (existing routing, untouched)
    In1.Cu  GND plane  -- solid, no routing
    In2.Cu  signal escape layer  <-- the new capability
    B.Cu    signal (existing routing, untouched)

In1 is a full GND plane so that both outer layers get a continuous reference; In2 is the escape
layer. Components are NOT moved (operator: "try to avoid moving the components").

Safe by construction: adding layers cannot break an existing connection. Through-vias already span
all layers, and every existing track stays on the layer it was on.

Run:  /usr/bin/python3 tracker/hardware/make_4layer.py [--write]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")
PRO = os.path.join(HERE, "hub_board_v10.kicad_pro")

F_SIG, GND_L, ESC_L, B_SIG = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)
GND_PLANE_LAYER = GND_L
ESC_LAYER = ESC_L


def counts(board):
    board.BuildConnectivity()
    return dict(
        layers=board.GetCopperLayerCount(),
        tracks=len(board.GetTracks()),
        footprints=len(board.GetFootprints()),
        zones=len(board.Zones()),
        unconnected=board.GetConnectivity().GetUnconnectedCount(False),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    board = pcbnew.LoadBoard(BOARD)
    before = counts(board)
    print("current board")
    for k, v in before.items():
        print(f"  {k:<12} {v}")

    if before["layers"] != 2:
        print(f"\nboard already has {before['layers']} copper layers -- nothing to convert")
        return 0

    print("\nplanned stackup")
    print("  F.Cu    signal (unchanged)")
    print("  In1.Cu  GND plane, solid")
    print("  In2.Cu  signal escape layer  <-- new capability")
    print("  B.Cu    signal (unchanged)")
    print("\nno footprint is moved; no existing track changes layer")

    if not args.write:
        print("\n(dry run -- pass --write to convert)")
        return 0

    # back up both files: a layer-count change is structural and must be reversible
    for p in (BOARD, PRO):
        if os.path.exists(p):
            shutil.copy2(p, p + ".2layer.bak")
    print("\nbacked up board + project as *.2layer.bak")

    # 1. enable the two inner layers and set the count
    board.SetCopperLayerCount(4)
    for lid in (GND_L, ESC_L):
        board.SetLayerName(lid, "In1.Cu" if lid == GND_L else "In2.Cu")
        board.SetLayerType(lid, pcbnew.LT_SIGNAL)

    # 2. full-board GND plane on In1
    bb = board.GetBoardEdgesBoundingBox()
    gx1, gy1 = bb.GetX() / 1e6, bb.GetY() / 1e6
    gx2, gy2 = (bb.GetX() + bb.GetWidth()) / 1e6, (bb.GetY() + bb.GetHeight()) / 1e6
    inset = 0.3
    gnd_net = None
    for code in range(board.GetNetCount()):
        n = board.FindNet(code)
        if n and n.GetNetname() == "GND":
            gnd_net = n
    if gnd_net is None:
        sys.exit("no GND net -- refusing to build a plane without a net")

    z = pcbnew.ZONE(board)
    z.SetLayer(GND_L)
    z.SetNet(gnd_net)
    z.SetZoneName("GND_In1")
    z.SetLocalClearance(pcbnew.FromMM(0.25))
    z.SetMinThickness(pcbnew.FromMM(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    poly = z.Outline()
    poly.NewOutline()
    for x, y in ((gx1 + inset, gy1 + inset), (gx2 - inset, gy1 + inset),
                 (gx2 - inset, gy2 - inset), (gx1 + inset, gy2 - inset)):
        poly.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
    board.Add(z)
    print(f"added In1 GND plane over {gx2-gx1:.1f} x {gy2-gy1:.1f} mm")

    pcbnew.SaveBoard(BOARD, board)
    print("saved board")

    # 3. project file must agree on the copper layer count, or KiCad reopens it as 2-layer
    if os.path.exists(PRO):
        d = json.load(open(PRO))
        bs = d.setdefault("board", {}).setdefault("design_settings", {})
        bs["copper_layer_count"] = 4
        # declare the stackup so fab sees an explicit 4-layer build
        stack = bs.setdefault("stackup", {})
        stack["layers"] = [
            {"type": "copper", "thickness": 0.035},
            {"type": "dielectric", "thickness": 0.2, "material": "FR4"},
            {"type": "copper", "thickness": 0.035},
            {"type": "dielectric", "thickness": 1.065, "material": "FR4 core"},
            {"type": "copper", "thickness": 0.035},
            {"type": "dielectric", "thickness": 0.2, "material": "FR4"},
            {"type": "copper", "thickness": 0.035},
        ]
        with open(PRO, "w") as fh:
            json.dump(d, fh, indent=2)
        print("updated .kicad_pro: copper_layer_count=4 + explicit stackup")

    # 4. refill (mandatory after ANY structural change -- stale fill produced phantom DRC twice)
    b2 = pcbnew.LoadBoard(BOARD)
    pcbnew.ZONE_FILLER(b2).Fill(b2.Zones())
    pcbnew.SaveBoard(BOARD, b2)

    b3 = pcbnew.LoadBoard(BOARD)
    after = counts(b3)
    print("\nafter conversion")
    for k, v in after.items():
        print(f"  {k:<12} {v}")
    print("\nlayer names now:")
    for lid in (F_SIG, GND_L, ESC_L, B_SIG):
        print(f"  {board.GetLayerName(lid)}")
    assert after["layers"] == 4, "layer count did not stick"
    assert after["tracks"] == before["tracks"], "track count changed -- conversion must not touch routing"
    assert after["footprints"] == before["footprints"], "footprint count changed -- no component may move"
    assert after["unconnected"] <= before["unconnected"], (
        f"unconnected ROSE {before['unconnected']} -> {after['unconnected']}: adding layers must "
        "not disconnect anything")
    if after["unconnected"] < before["unconnected"]:
        print(f"\nbonus: the In1 GND plane closed {before['unconnected']-after['unconnected']} "
              "previously-floating connection(s)")
    print("\nOK: 4 layers, nothing moved, nothing disconnected")
    return 0


if __name__ == "__main__":
    sys.exit(main())

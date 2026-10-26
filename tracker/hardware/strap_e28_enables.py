#!/usr/bin/env python3
"""Strap U_E28's PA/LNA enables (RX_EN, TX_EN) to +3V3 — ADR-108's existing pattern.

THE DEFECT THIS FIXES (measured 2026-10-25)
-------------------------------------------
`docs/modules/e28-2g4m27sx/E28-2G4M27SX_UserManual_v1.0.pdf` (pdftotext, lines 253-254):

    pin 8  RX_EN  Input  LNA control pin, active high
    pin 9  TX_EN  Input  PA control pin, active high

On the board both were **(NC)** — floating. The manual documents a built-in 50 K pull-up for
`NRESET` (pin 11) only, and states no default for these two. The radio link is routed 9/9, but with
the low-noise and power amplifiers not enabled it may still not work — and it would present as an RF
or firmware fault, which is the worst possible thing to chase during a flight campaign.

WHY STRAP RATHER THAN DRIVE FROM FIRMWARE
-----------------------------------------
ADR-108 R1 records: "after R1 **no free ESP32-S3 GPIO remains**". There is nothing to drive them
with. ADR-108 already straps the F33's `CE` to `+3V3` for exactly this reason ("do not drive from
firmware; strap to 3V3"). This follows that precedent.

TRADE-OFF, STATED
-----------------
Strapped high means the PA and LNA are permanently enabled: no ability to power down the LNA for
current savings. Accepted for first flight — a working link outranks a few mA.

HOW IT IS IMPLEMENTED (and why not with tracks alone)
----------------------------------------------------
Both pads are on **F.Cu**; the `+3V3` pour (`P3V3_BCu`) is on **B.Cu** and covers the whole board
(measured bbox 0.5..71.5 x 0.5..79.5). So each pad gets:

    pad --0.2 mm F.Cu stub--> via (0.5/0.25) --> B.Cu +3V3 pour

Two vias, two short stubs. Both via sites were measured CLEAR on F.Cu and B.Cu before placing:
    pad 8 (RX_EN) at (57.45, 59.10) -> via at (59.80, 59.10)
    pad 9 (TX_EN) at (48.55, 74.10) -> via at (46.20, 74.10)

Routeing a track around the module was rejected: pads 1-8 sit on a 1.27 mm pitch with a 0.370 mm
copper gap, so a 0.2/0.2 track cannot pass between them (the same arithmetic that blocked the radio
link on 2 layers) and any path would have to go the long way around three module edges.

Run:  /usr/bin/python3 tracker/hardware/strap_e28_enables.py [--write]
"""
from __future__ import annotations

import argparse
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")
REF = "U_E28"
PINS = {"8": "RX_EN", "9": "TX_EN"}
VIA_MM = {"dia": 0.5, "drill": 0.25}
TRACK_MM = 0.2
# measured-clear via sites, offset outward from each pad so the stub leaves the module body
VIA_SITES = {"8": (59.80, 59.10), "9": (46.20, 74.10)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    board = pcbnew.LoadBoard(BOARD)

    net3 = None
    for code in range(board.GetNetCount()):
        n = board.FindNet(code)
        if n and n.GetNetname() == "+3V3":
            net3 = n
    if net3 is None:
        sys.exit("no +3V3 net on the board -- refusing to guess")

    fp = next((f for f in board.GetFootprints() if f.GetReference() == REF), None)
    if fp is None:
        sys.exit(f"{REF} not found")

    pads = {str(p.GetNumber()): p for p in fp.Pads()}
    plan = []
    for pin, name in PINS.items():
        p = pads.get(pin)
        if p is None:
            sys.exit(f"{REF} has no pad {pin}")
        cur = p.GetNetname()
        pos = p.GetPosition()
        vx, vy = VIA_SITES[pin]
        plan.append((pin, name, cur or "(NC)", pos.x / 1e6, pos.y / 1e6, vx, vy))

    print(f"strap {REF} enables to +3V3 (net code {net3.GetNetCode()})")
    print(f"  via {VIA_MM['dia']}/{VIA_MM['drill']} mm, track {TRACK_MM} mm, tapping the B.Cu pour")
    for pin, name, cur, px, py, vx, vy in plan:
        print(f"  pad {pin} {name:<6} now {cur:<6} at ({px:.2f},{py:.2f}) -> via ({vx:.2f},{vy:.2f})")

    if all(cur == "+3V3" for _p, _n, cur, *_ in plan):
        print("\nalready strapped -- nothing to do")
        return 0

    if not args.write:
        print("\n(dry run -- pass --write to apply)")
        return 0

    for pin, name, _cur, px, py, vx, vy in plan:
        pads[pin].SetNet(net3)

        via = pcbnew.PCB_VIA(board)
        via.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(vx), pcbnew.FromMM(vy)))
        via.SetWidth(pcbnew.FromMM(VIA_MM["dia"]))
        via.SetDrill(pcbnew.FromMM(VIA_MM["drill"]))
        via.SetNet(net3)
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        board.Add(via)

        tr = pcbnew.PCB_TRACK(board)
        tr.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(px), pcbnew.FromMM(py)))
        tr.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(vx), pcbnew.FromMM(vy)))
        tr.SetWidth(pcbnew.FromMM(TRACK_MM))
        tr.SetLayer(pcbnew.F_Cu)
        tr.SetNet(net3)
        board.Add(tr)
        print(f"  strapped {name} (pad {pin})")

    pcbnew.SaveBoard(BOARD, board)

    # refill is MANDATORY: the vias must pick up the B.Cu pour, and any move invalidates fill
    b2 = pcbnew.LoadBoard(BOARD)
    pcbnew.ZONE_FILLER(b2).Fill(b2.Zones())
    pcbnew.SaveBoard(BOARD, b2)

    b3 = pcbnew.LoadBoard(BOARD)
    b3.BuildConnectivity()
    print(f"\nunconnected now: {b3.GetConnectivity().GetUnconnectedCount(False)}")
    fp3 = next(f for f in b3.GetFootprints() if f.GetReference() == REF)
    for p in fp3.Pads():
        if str(p.GetNumber()) in PINS:
            print(f"  pad {p.GetNumber()} net = {p.GetNetname() or '(NC)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

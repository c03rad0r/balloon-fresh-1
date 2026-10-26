#!/usr/bin/env python3
"""Apply ADR-137: delete the board-level RF provision (ANT* nets + their U.FL connectors).

WHY THIS COMES FIRST
--------------------
ADR-137 (merged 1aaf132b) says the hub carries NO RF design: the antenna attaches at the radio
module, never on our PCB. It also unblocks ADR-136 option A -- measured: the destination box for
the U_E28 move was obstructed by /ANT1_433_TX, i.e. by the very copper this script removes.

WHAT IS REMOVED
---------------
* every track segment whose net starts with /ANT
* every footprint whose reference is ANT1..ANTn (the board's U.FL connectors)
* the now-empty ANT nets are left for KiCad to drop on save

WHAT IS *NOT* REMOVED, AND WHY
------------------------------
The antenna provision itself is not deleted -- it MOVES to the module:
  U2  LoRa2021F33-2G4 : pins 9 (ANT, sub-GHz) / 10 (ANT-2G4) per docs/F33-MODULE-PLAN.md
  U_E28 SX1280 module : its own IPEX/U.FL on the module board
  U3/U_C              : castellated RF pin
  U5  MAX-M10S        : its own antenna pin
The operator's rule is that a pigtail/antenna attaches there. This script deletes OUR copper and
OUR connector(s); it does not delete the radio's antenna port.

Run:  /usr/bin/python3 tracker/hardware/apply_adr137_remove_rf.py [--write]
"""
from __future__ import annotations

import argparse
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")


def ant_stats(board):
    segs = [t for t in board.GetTracks() if t.GetNetname().startswith("/ANT")]
    length = sum(
        math.dist((t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y)) / 1e6
        for t in segs
    )
    fps = [f for f in board.GetFootprints() if f.GetReference().startswith("ANT")]
    return segs, length, fps


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    board = pcbnew.LoadBoard(BOARD)
    before_unc = None
    board.BuildConnectivity()
    before_unc = board.GetConnectivity().GetUnconnectedCount(False)

    segs, length, fps = ant_stats(board)
    print("ADR-137 removal plan")
    print(f"  RF track segments : {len(segs)}")
    print(f"  RF copper length  : {length:.1f} mm")
    print(f"  connectors        : {len(fps)}  -> {', '.join(sorted(f.GetReference() for f in fps)) or '(none)'}")
    print(f"  unconnected before: {before_unc}")

    if not segs and not fps:
        print("\nnothing to remove -- already applied")
        return 0

    for f in fps:
        c = f.GetPosition()
        print(f"    {f.GetReference():<6} at ({c.x/1e6:.1f}, {c.y/1e6:.1f})")

    if not args.write:
        print("\n(dry run -- pass --write to remove)")
        return 0

    for t in segs:
        board.Remove(t)
    for f in fps:
        board.Remove(f)

    pcbnew.SaveBoard(BOARD, board)

    b2 = pcbnew.LoadBoard(BOARD)
    b2.BuildConnectivity()
    s2, l2, f2 = ant_stats(b2)
    print(f"\nremoved. remaining ANT segments: {len(s2)}, ANT connectors: {len(f2)}")
    print(f"unconnected after: {b2.GetConnectivity().GetUnconnectedCount(False)}  (was {before_unc})")
    print(f"footprints now: {len(b2.GetFootprints())}   tracks now: {len(b2.GetTracks())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

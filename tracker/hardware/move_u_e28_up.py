#!/usr/bin/env python3
"""OPTION A (ADR-136 sec 5): move U_E28 up so its top pad row lands on the clear F.Cu channel.

MEASURED BASIS
--------------
U_E28 sits at (53.00, 69.00) with pad rows at y=61.50 and y=76.50. The clear F.Cu routing channel
is at y~56.8 (verified clear across x 12-48, and B.Cu at x 47-48.6 / y 56-62 is empty).
Moving the part UP by DIST_MM puts its top pad row at 61.50 - DIST_MM.

DIST_MM is chosen so the top row lands just below the channel rather than through it: the channel
band spans y 56.05-57.55, and a pad row at 59.10 leaves 1.55 mm of clearance, which is more than
the 0.2 mm track + 0.2 mm clearance the router needs.

WHAT THIS DOES AND DOES NOT FIX -- stated up front, because ADR-136 sec 5 is explicit
------------------------------------------------------------------------------
It frees the LONG VERTICAL LEG from the channel down to the module. It does **not** create a
downward escape from U1's bottom pads, which is the actual blocker. Measured after the move the
12 radio nets are still blocked at U1. This script is honest about that and does not claim a
routing win.

Run:  /usr/bin/python3 tracker/hardware/move_u_e28_up.py [--write]
"""
from __future__ import annotations

import argparse
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")
REF = "U_E28"
DIST_MM = 2.4          # 61.50 -> 59.10, i.e. 1.55 mm clear of the channel band


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    board = pcbnew.LoadBoard(BOARD)
    target = None
    for fp in board.GetFootprints():
        if fp.GetReference() == REF:
            target = fp
            break
    if target is None:
        sys.exit(f"{REF} not found")

    before = target.GetPosition()
    bx, by = before.x / 1e6, before.y / 1e6
    nb = pcbnew.VECTOR2I(before.x, before.y - int(DIST_MM * 1e6))

    # Would the move short anything? Test the DESTINATION region directly: shift the part's own
    # pad bounding box and look for other-net copper inside it. Simpler and stricter than an
    # inflated envelope, and it uses only calls this pcbnew exposes.
    xs, ys = [], []
    for p in target.Pads():
        bb = p.GetBoundingBox()
        xs += [bb.GetX() / 1e6, (bb.GetX() + bb.GetWidth()) / 1e6]
        ys += [bb.GetY() / 1e6, (bb.GetY() + bb.GetHeight()) / 1e6]
    move = DIST_MM
    dx1, dy1, dx2, dy2 = min(xs), min(ys) - move, max(xs), max(ys) - move
    moved_nets = {p.GetNetname() for p in target.Pads() if p.GetNetname()}

    clashes = []
    for t in board.GetTracks():
        s, e = t.GetStart(), t.GetEnd()
        tx1, tx2 = sorted((s.x / 1e6, e.x / 1e6))
        ty1, ty2 = sorted((s.y / 1e6, e.y / 1e6))
        if tx2 >= dx1 and tx1 <= dx2 and ty2 >= dy1 and ty1 <= dy2:
            if t.GetNetname() not in moved_nets:
                clashes.append((t.GetNetname(), t.GetLayerName(),
                                round(tx1, 1), round(ty1, 1)))
    for fp in board.GetFootprints():
        if fp.GetReference() == REF:
            continue
        for p in fp.Pads():
            c = p.GetPosition()
            px, py = c.x / 1e6, c.y / 1e6
            if dx1 <= px <= dx2 and dy1 <= py <= dy2 and p.GetNetname() not in moved_nets:
                clashes.append(("PAD:" + fp.GetReference(), str(p.GetNumber()),
                                round(px, 1), round(py, 1)))

    print(f"{REF} at ({bx:.2f}, {by:.2f}) -> y {by - DIST_MM:.2f}  (up {DIST_MM} mm)")
    print(f"destination pad box: x {dx1:.1f}..{dx2:.1f}  y {dy1:.1f}..{dy2:.1f}")
    print(f"foreign-net items inside the destination: {len(clashes)}")
    for c in clashes[:12]:
        print("   ", c)
    if clashes:
        print("\nREFUSING: the destination is not clear. Inspect the points above.")
        return 1

    if not args.write:
        print("\n(dry run -- pass --write to move)")
        return 0

    target.SetPosition(nb)
    pcbnew.SaveBoard(BOARD, board)
    print(f"\nmoved {REF}; saved")

    b2 = pcbnew.LoadBoard(BOARD)
    b2.BuildConnectivity()
    print(f"unrouted now: {b2.GetConnectivity().GetUnconnectedCount(False)}")
    print("NOTE: expect this number to be UNCHANGED. The move frees the vertical leg but does not")
    print("      create a downward escape from U1 -- that is Option B, blocked separately.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

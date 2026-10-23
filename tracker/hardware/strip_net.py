#!/usr/bin/env python3
"""strip_net.py -- remove ALL copper (tracks + vias) belonging to one net.

Used by route_ripup.py to implement rip-up-and-reroute: a net that blocks another is
temporarily torn up so the blocked net can take its corridor, then re-routed.

Deliberately minimal: it touches ONLY tracks and vias of the named net. Pads, zones,
footprints, silk and the outline are untouched -- a rip-up must not disturb the board.

Usage:
    strip_net.py --board B.kicad_pcb --net /EN [--net /SPI2_SCK ...] [--dry-run]

Exit: 0 = stripped (or nothing to strip); 2 = could not run.
"""
import argparse
import os
import shutil
import sys

import pcbnew


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    ap.add_argument("--net", action="append", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.board):
        print(f"STRIP: CANNOT RUN -- no board at {args.board}")
        return 2

    targets = set(args.net)
    b = pcbnew.LoadBoard(args.board)
    victims = []
    for t in b.GetTracks():
        nm = t.GetNetname() or ""
        if nm in targets:
            victims.append((nm, "VIA" if "VIA" in str(type(t)) else "TRACK", t))

    if args.dry_run:
        for nm, kind, _ in victims:
            print(f"STRIP-WOULD: {kind} of {nm}")
        print(f"STRIP: {len(victims)} item(s) would be removed")
        return 0

    for _, _, t in victims:
        b.Remove(t)

    pcbnew.SaveBoard(args.board, b)
    by_net = {}
    for nm, kind, _ in victims:
        by_net.setdefault(nm, [0, 0])
        by_net[nm][0 if kind == "TRACK" else 1] += 1
    for nm, (tr, vi) in sorted(by_net.items()):
        print(f"STRIP: removed {tr} track(s), {vi} via(s) from {nm}")
    if not victims:
        print("STRIP: nothing to remove")
    return 0


if __name__ == "__main__":
    sys.exit(main())

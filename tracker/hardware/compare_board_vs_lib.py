#!/usr/bin/env python3
"""Does the BOARD's copy of a custom footprint differ from the LIBRARY's?

`lib_footprint_issues` in KiCad means "the footprint on the board differs from the library's copy",
NOT "library missing" (all five libraries resolve, verified). This matters because a stale board copy
means the plotted board is not the part the library/BOM describes.

TWO MEASUREMENT TRAPS, both hit while building this and both fixed here:

  1. RELATIVE vs ABSOLUTE. `pad.GetPosition()` on a board footprint returns BOARD coordinates; on a
     library footprint it returns footprint-LOCAL coordinates. Comparing them directly reports "25 of
     25 pads differ" for a footprint that is in fact correct. Compare (position - footprint origin).
  2. `pcbnew.FootprintLoad()` returned None for every footprint even though the .kicad_mod files
     exist. Parsing the footprint's own S-expression for pad geometry is deterministic and avoids
     that API entirely, so that is what is used below.
"""
import os
import re
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "hub_board_v9.kicad_pcb")

LIBS = {
    "balloon_flight_v9": os.path.join(HERE, "schematics", "flight_board", "v9_lib",
                                      "balloon_flight_v9.pretty"),
    "Tracker_Mechanical": os.path.join(HERE, "footprints", "tracker_mechanical.pretty"),
}

TARGETS = [("U4", "balloon_flight_v9", "SX1280_QFN24"),
           ("U2", "balloon_flight_v9", "LoRa2021F33_2G4"),
           ("U3", "balloon_flight_v9", "LoRa2021_Castellated"),
           ("J_W1", "Tracker_Mechanical", "Wing_Tab_4P")]

PAD_RE = re.compile(
    r'\(pad\s+"([^"]*)"\s+\S+\s+\S+\s+\(at\s+([-\d.]+)\s+([-\d.]+)(?:\s+([-\d.]+))?\)'
    r'\s+\(size\s+([-\d.]+)\s+([-\d.]+)\)', re.S)


def lib_pads(path):
    txt = open(path, errors="replace").read()
    return sorted((n, round(float(x), 4), round(float(y), 4),
                   round(float(w), 4), round(float(h), 4))
                  for n, x, y, _r, w, h in PAD_RE.findall(txt))


def board_pads(fp):
    ox, oy = fp.GetPosition().x, fp.GetPosition().y
    out = []
    for p in fp.Pads():
        pos = p.GetPosition()
        sz = p.GetSize()
        out.append((str(p.GetNumber()),
                    round(pcbnew.ToMM(pos.x - ox), 4), round(pcbnew.ToMM(pos.y - oy), 4),
                    round(pcbnew.ToMM(sz.x), 4), round(pcbnew.ToMM(sz.y), 4)))
    return sorted(out)


def main():
    board = pcbnew.LoadBoard(BOARD)
    print(f"{'ref':6} {'board':>6} {'lib':>5}  verdict")
    print("-" * 78)
    for ref, nickname, item in TARGETS:
        fp = board.FindFootprintByReference(ref)
        if fp is None:
            print(f"{ref:6} NOT ON BOARD")
            continue
        src = os.path.join(LIBS[nickname], item + ".kicad_mod")
        if not os.path.exists(src):
            print(f"{ref:6} {fp.GetPadCount():>6} {'--':>5}  library file MISSING")
            continue
        bp, lp = board_pads(fp), lib_pads(src)
        if len(bp) != len(lp):
            print(f"{ref:6} {len(bp):>6} {len(lp):>5}  DIFFERS: pad count")
            continue
        # Compare geometry only; pad NAME forms can differ legitimately (e.g. "41" vs "41_1").
        bg = sorted(t[1:] for t in bp)
        lg = sorted(t[1:] for t in lp)
        if bg == lg:
            print(f"{ref:6} {len(bp):>6} {len(lp):>5}  IDENTICAL geometry (rel. to origin)")
        else:
            diffs = [(a, b) for a, b in zip(bg, lg) if a != b]
            print(f"{ref:6} {len(bp):>6} {len(lp):>5}  DIFFERS: {len(diffs)}/{len(bp)} pads; "
                  f"e.g. board {diffs[0][0]} vs lib {diffs[0][1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

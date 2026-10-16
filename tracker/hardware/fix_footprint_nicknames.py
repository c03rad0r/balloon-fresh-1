#!/usr/bin/env python3
"""Restore the library nickname on footprint IDs that lost it -- measured, not guessed.

THE DEFECT. The hub board's canonical file stores U4's footprint as a bare `SX1280_QFN24` with no library
nickname, while the netlist names `balloon_flight_v9:SX1280_QFN24` and every other part on the board
carries a nickname. pad_audit.py flags this.

WHERE IT COMES FROM -- MEASURED, by counting nicknameless footprints in every board the toolchain
produces:

    output/hub_board_v9_seed.kicad_pcb        44 footprints, 44 with nickname, 0 without
    output/v9_routed.kicad_pcb                39 footprints, 39 with nickname, 0 without
    hub_board_v9.kicad_pcb  (SHIPPED)         59 footprints, 58 with nickname, 1 WITHOUT  <- U4

So the BUILDER and the ROUTER both produce a correct nickname -- `FootprintLoad` strips it on read but
`SetFPID(LIB_ID(lib, name))` restores it, and every part comes out named. The defect appears ONLY in the
board that was promoted to canonical by the H1 fix, which is a save path that did not go through the
builder. That is the real finding: a fab artifact carries a footprint the builder did not write.

WHAT THIS DOES. It sets the missing nickname to the value the SOURCE LIBRARY already carries
(`(footprint "balloon_flight_v9:SX1280_QFN24"` in
schematics/flight_board/v9_lib/balloon_flight_v9.pretty/SX1280_QFN24.kicad_mod) and the netlist names. It
does NOT touch geometry, positions, nets or tracks -- only the LIB_ID nickname string, and only where it
is empty. Verified to survive a save+reload.

This is not a hand-typed geometry edit: no coordinate is written. It is a metadata repair, and rule R2 is
about geometry. The alternative -- a full builder re-run -- is strictly larger and would risk the 57/59
routing on the canonical board, so the narrow repair is the conservative choice; it is recorded here so
the decision is visible.

Run:  ~/venvs/kicad/bin/python fix_footprint_nicknames.py [--write] [board.kicad_pcb]
      (without --write it only reports; with --write it saves in place and re-reads to confirm)
"""
from __future__ import annotations

import os
import sys

import pcbnew

DEFAULT_BOARD = "tracker/hardware/hub_board_v9.kicad_pcb"

# Designator -> the LIB_ID the source library and the netlist agree on. Kept explicit rather than derived,
# so a future empty nickname is REPORTED and not silently invented.
KNOWN_IDS = {
    "U4": ("balloon_flight_v9", "SX1280_QFN24"),
}


def nicknameless(board):
    out = []
    for fp in board.GetFootprints():
        if not str(fp.GetFPID().GetLibNickname()).strip():
            out.append(fp)
    return out


def main(argv):
    args = [a for a in argv[1:] if a != "--write"]
    write = "--write" in argv
    board_path = args[0] if args else DEFAULT_BOARD

    if not os.path.exists(board_path):
        print(f"ABSENT: {board_path}")
        return 2
    board = pcbnew.LoadBoard(board_path)
    if board is None:
        print(f"CANNOT READ: {board_path}")
        return 2

    bad = nicknameless(board)
    print(f"board: {board_path}")
    print(f"footprints: {len(list(board.GetFootprints()))}")
    print(f"nicknameless: {len(bad)}")
    if not bad:
        print("\nRESULT: nothing to repair.")
        return 0

    fixed, unknown = 0, []
    for fp in bad:
        ref = fp.GetReference()
        if ref in KNOWN_IDS:
            lib, item = KNOWN_IDS[ref]
            fp.SetFPID(pcbnew.LIB_ID(lib, item))
            print(f"  set  {ref:8} -> {lib}:{item}")
            fixed += 1
        else:
            unknown.append((ref, str(fp.GetFPID().GetLibItemName())))
            print(f"  SKIP {ref:8} -- no known LIB_ID; report, do not invent")

    if unknown:
        print(f"\nRESULT: {len(unknown)} footprint(s) have NO nickname and no recorded source:")
        for ref, item in unknown:
            print(f"  {ref}: {item}")
        print("  Add them to KNOWN_IDS from the netlist or the source library. Not guessing.")

    if not write:
        print(f"\nDRY RUN -- {fixed} repairable. Re-run with --write to apply.")
        return 0

    pcbnew.SaveBoard(board_path, board)
    check = pcbnew.LoadBoard(board_path)
    remaining = nicknameless(check)
    print(f"\nwrote {board_path}")
    print(f"re-read: nicknameless now {len(remaining)}")
    if remaining:
        print("RESULT: FAIL -- some nicknames did not persist")
        return 1
    print("RESULT: PASS -- every footprint carries a library nickname")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

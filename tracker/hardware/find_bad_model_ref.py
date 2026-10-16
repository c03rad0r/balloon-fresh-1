#!/usr/bin/env python3
"""Locate the ONE footprint whose model reference does not resolve, using KiCad's own parser.

WHY THIS REPLACES MY LAST ATTEMPT. My regex split the file on '\\n  (footprint ' and reported garbage
(R_0402, U.FL, D_SMA...) because '(footprint' also appears INSIDE model paths and library names. The
census module -- which uses pcbnew -- reported exactly one unresolved reference. So: use pcbnew, which
parses the file the way KiCad does, instead of pattern-matching text.

Run: ~/venvs/kicad/bin/python find_bad_model_ref.py
"""
import os
import sys

import pcbnew

BOARD = "tracker/hardware/hub_board_v9.kicad_pcb"
PKG = "/usr/share/kicad/3dmodels"


def main():
    b = pcbnew.LoadBoard(BOARD)
    print(f"board: {BOARD}")
    print(f"footprints: {len(list(b.GetFootprints()))}\n")
    bad = []
    for fp in b.GetFootprints():
        for m in fp.Models():
            fn = str(m.m_Filename)
            if "3DMODEL_DIR" not in fn:
                continue
            rel = fn.split("}/", 1)[-1]
            full = os.path.join(PKG, rel)
            if not os.path.exists(full):
                bad.append((str(fp.GetReference()), str(fp.GetFPID().GetLibItemName()),
                            str(fp.GetValue()), fn, rel))
    print(f"UNRESOLVED package model refs: {len(bad)}")
    for ref, fpn, val, fn, rel in bad:
        print(f"\n  reference : {ref}")
        print(f"  footprint : {fpn}")
        print(f"  value     : {val}")
        print(f"  wants     : {rel}")
        d = os.path.join(PKG, os.path.dirname(rel))
        base = os.path.basename(rel)
        if os.path.isdir(d):
            stem = base.split("_EP")[0].rstrip("_")
            print(f"  library HAS (same dir):")
            for f in sorted(os.listdir(d)):
                if stem[:9].lower() in f.lower():
                    print(f"      {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

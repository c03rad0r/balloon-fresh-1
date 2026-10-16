#!/usr/bin/env python3
"""Which footprints on hub_board_v9 lack a 3D model block, and where does the footprint file live?

REGRESSION CONTEXT. CI's tests/test_model_resolution_census.py fails on this branch with
'no model block: [U4]'. Measured against master, master's board has U4 with 1 model and ours has 0 --
so this is a real regression introduced by the placement work, not a pre-existing red test.

U4 is the SX1280. The census test treats a set of references as MUST-BE-VISIBLE, so a missing model
block means the part cannot be seen in a 3D review of the assembly -- which matters for exactly the
kind of visual check this project keeps relying on.

Run with an interpreter that has pcbnew: ~/venvs/kicad/bin/python inspect_missing_models.py
"""
import os
import re
import sys

import pcbnew

BOARD = "tracker/hardware/hub_board_v9.kicad_pcb"


def main():
    b = pcbnew.LoadBoard(BOARD)
    missing = []
    for f in b.GetFootprints():
        if len(list(f.Models())) == 0:
            missing.append((str(f.GetReference()), str(f.GetFPID().GetLibItemName()),
                            str(f.GetValue())))
    print(f"board: {BOARD}")
    print(f"footprints: {len(list(b.GetFootprints()))}")
    print(f"WITHOUT a model block: {len(missing)}")
    for ref, name, val in sorted(missing):
        print(f"   {ref:8} footprint={name:26} value={val}")

    print("\n--- footprint files in the project library ---")
    lib = "tracker/hardware/schematics/flight_board/v9_lib/balloon_flight_v9.pretty"
    if os.path.isdir(lib):
        for fn in sorted(os.listdir(lib)):
            if not fn.endswith(".kicad_mod"):
                continue
            p = os.path.join(lib, fn)
            txt = open(p, encoding="utf-8", errors="replace").read()
            n = len(re.findall(r'\(model\s+"', txt))
            n2 = len(re.findall(r'\(model\s', txt))
            print(f"   {fn:34} model blocks: {max(n, n2)}")
    else:
        print(f"   {lib} is not a directory")

    print("\n--- how does the builder attach models? ---")
    for cand in ("tracker/hardware/build_hub_board_v9.py",):
        txt = open(cand, encoding="utf-8", errors="replace").read()
        hits = [ln.strip() for ln in txt.splitlines()
                if re.search(r'model|3d|step|wrl|SetModel|AddModel', ln, re.I)]
        print(f"   {cand}: {len(hits)} lines mentioning a model")
        for h in hits[:14]:
            print(f"     {h[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

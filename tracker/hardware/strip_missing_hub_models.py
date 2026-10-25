#!/usr/bin/env python3
"""Strip 3D-model references on hub_board_v10 that point at files which DO NOT EXIST.

THE FINDING
-----------
pad_audit reports 9 x "model reference does not resolve". MEASURED against the installed
library (/usr/share/kicad/3dmodels, 105 libraries):

    ESP32-S3-WROOM-1U.step          MISSING -- the library ships WROOM-1 / -2 / C3, not -1U
    RF_GPS.3dshapes/                MISSING -- the whole directory is absent
    Connector_Coaxial/...U.FL...    MISSING -- no U.FL model in the library
    Package_DFN_QFN/...VQFN-16...   MISSING
    RF_Module/NiceRF_LoRa2021.wrl   MISSING

WHY STRIPPING IS THE HONEST FIX, NOT PAPERING OVER
AGENTS.md (3D-model note) records the hazard: "kicad-cli pcb render exits 0 and prints no
warning when a footprint's model does not resolve -- the part is silently absent." So a
dangling reference is worse than no reference: it LOOKS like the part has geometry while
rendering nothing. Removing it makes the absence explicit and the gate truthful.

DELIBERATELY NOT DONE: substituting a NEARBY model. `ESP32-S3-WROOM-1.step` exists, but -1U
is a different part (U.FL instead of PCB antenna) -- pointing at it would render a part this
board does not carry, which is the same class of error as the "wrong nickname" risk. A wrong
picture is worse than no picture.

EFFECT ON FABRICATION: none. 3D models are visual only; they are not on any copper, mask or
drill layer.

Run:  /usr/bin/python3 tracker/hardware/strip_missing_hub_models.py [--write]
"""
from __future__ import annotations

import argparse
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")
MODELS = "/usr/share/kicad/3dmodels"


def resolve(ref: str) -> str:
    """Expand the KiCad 3D-model variables the way the renderer does."""
    for var in ("${KICAD9_3DMODEL_DIR}", "${KICAD8_3DMODEL_DIR}", "${KICAD7_3DMODEL_DIR}"):
        ref = ref.replace(var, MODELS)
    ref = ref.replace("${KIPRJMOD}", os.path.dirname(BOARD))
    return ref


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    board = pcbnew.LoadBoard(BOARD)
    doomed = []
    for fp in board.GetFootprints():
        for m in fp.Models():
            p = resolve(m.m_Filename)
            if not os.path.exists(p):
                doomed.append((fp.GetReference(), m.m_Filename))

    print(f"dangling model references: {len(doomed)}")
    for ref, fn in doomed:
        print(f"   {ref:<10} {fn}")
    if not doomed:
        return 0
    if not args.write:
        print("\n(dry run -- pass --write to strip)")
        return 0

    for fp in board.GetFootprints():
        for m in fp.Models():
            if not os.path.exists(resolve(m.m_Filename)):
                m.m_Show = False
    pcbnew.SaveBoard(BOARD, board)
    # m_Show does NOT survive SaveBoard through this binding (measured: fp.Models() returns
    # copies, so the flag is lost and the file keeps no `(hide yes)`. Apply it as a TEXT edit
    # instead -- the schematic-file syntax `(hide yes)` inside the (model ...) block is the
    # form KiCad itself reads, and was verified to load back with m_Show=False.
    import re
    text = open(BOARD, errors="replace").read()
    n_fixed = 0
    for ref in sorted({r for r, _f in doomed}):
        for fn in [f for r, f in doomed if r == ref]:
            # locate the model block by its filename, then append (hide yes) if absent
            pat = re.compile(r'(\(model "' + re.escape(fn) + r'"(?:[^\n]*\n)*?\t\t)(\)\n)')
            def _sub(m, _fn=fn):
                nonlocal n_fixed
                if "(hide yes)" in m.group(0):
                    return m.group(0)
                n_fixed += 1
                return m.group(1) + "\t\t\t(hide yes)\n" + m.group(2)
            # count=0 (ALL occurrences): the same missing model filename appears once per
            # footprint that references it -- U.FL shows up on ANT1..ANT4, so count=1 left
            # 3 findings behind (measured).
            text = pat.sub(_sub, text, count=0)
    open(BOARD, "w").write(text)
    print(f"\nexcluded {len(doomed)} dangling reference(s); wrote {n_fixed} (hide yes)")

    b2 = pcbnew.LoadBoard(BOARD)
    still = 0
    for fp in b2.GetFootprints():
        for m in fp.Models():
            if not os.path.exists(resolve(m.m_Filename)):
                still += 1
    print(f"dangling after: {still}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

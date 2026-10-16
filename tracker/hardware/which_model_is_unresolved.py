#!/usr/bin/env python3
"""Which footprint references a KiCad system 3D model that is NOT installed?

The model census test asserts, when the local kicad-packages3d directory exists, that every
${KICAD9_3DMODEL_DIR} reference resolves. One does not:

    ${KICAD9_3DMODEL_DIR}/Package_DFN_QFN.3dshapes/VQFN-16-1EP_3x3mm_P0.5mm_EP1.1x1.1mm.step

This is a REAL, checkable fact about the board -- a reference to a library part KiCad does not ship under
that name -- as distinct from the host-dependent class the test deliberately tolerates. The installed
library has `Texas_RSA_VQFN-16-1EP_4x4mm_P0.65mm_EP2.7x2.7mm.step` instead: a different part.

Run: ~/venvs/kicad/bin/python which_model_is_unresolved.py
"""
import os
import re
import sys

BOARD = "tracker/hardware/hub_board_v9.kicad_pcb"
KICAD_DIR = os.environ.get("KICAD9_3DMODEL_DIR") or "/usr/share/kicad/3dmodels"


def main():
    txt = open(BOARD, encoding="utf-8", errors="replace").read()

    # each footprint block: (footprint "lib:name" ... (model "path" ...))
    blocks = re.split(r'\n  \(footprint ', txt)
    print(f"board: {BOARD}")
    print(f"package dir: {KICAD_DIR}  exists={os.path.isdir(KICAD_DIR)}\n")

    unresolved = []
    for blk in blocks[1:]:
        m = re.match(r'"([^"]+)"', blk)
        fpname = m.group(1) if m else "?"
        ref_m = re.search(r'\(fp_text reference "([^"]+)"', blk)
        ref = ref_m.group(1) if ref_m else "?"
        for mm in re.finditer(r'\(model\s+"([^"]+)"', blk):
            path = mm.group(1)
            if "3DMODEL_DIR" not in path:
                continue
            rel = re.sub(r'^\$\{[^}]+\}/', '', path)
            full = os.path.join(KICAD_DIR, rel)
            if not os.path.exists(full):
                unresolved.append((ref, fpname, path, os.path.basename(rel)))

    print(f"UNRESOLVED package references: {len(unresolved)}")
    for ref, fpname, path, base in unresolved:
        print(f"  {ref:8} {fpname}")
        print(f"           wants: {base}")
        # is there a near-name neighbour in the same .3dshapes dir?
        d = os.path.join(KICAD_DIR, os.path.dirname(re.sub(r'^\$\{[^}]+\}/', '', path)))
        if os.path.isdir(d):
            stem = base.split("_EP")[0]
            near = [f for f in sorted(os.listdir(d)) if stem.split("-")[0] in f][:6]
            if near:
                print(f"           the dir HAS: {near}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

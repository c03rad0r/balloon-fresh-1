#!/usr/bin/env python3
"""Measure U_HUB_CVT's real geometry so an honest envelope model can be generated for it.

WHY. U_HUB_CVT (BQ25504RGTR, the solar harvester) references
    ${KICAD9_3DMODEL_DIR}/Package_DFN_QFN.3dshapes/VQFN-16-1EP_3x3mm_P0.5mm_EP1.1x1.1mm.step
which the installed KiCad library does not ship -- it has a 4 x 4 mm, 0.65 mm-pitch Texas part instead.
Repointing at that would be a wrong-sized model, i.e. a fabricated-green fix.

The project's established answer for a part with no usable system model is an IN-REPO ENVELOPE generated
by scripts/gen_3d_models_hub.py and attached by the builder (as done for U2, U4, U5). To build one I need
the part's real X/Y and a defensible Z. This script measures X/Y from the board and reports what Z could
be sourced from -- it does NOT invent a height.

Run: ~/venvs/kicad/bin/python measure_uhubcvt.py
"""
import sys

import pcbnew

BOARD = "tracker/hardware/hub_board_v9.kicad_pcb"


def main():
    b = pcbnew.LoadBoard(BOARD)
    fp = b.FindFootprintByReference("U_HUB_CVT")
    if fp is None:
        print("U_HUB_CVT absent")
        return 1
    print(f"reference : U_HUB_CVT")
    print(f"value     : {fp.GetValue()}")
    print(f"fpid      : {fp.GetFPID().GetLibItemName()}")

    # pad extents include pad SIZE, which is what an envelope must cover
    xs, ys = [], []
    for p in fp.Pads():
        c = p.GetPosition()
        s = p.GetSize()
        xs += [pcbnew.ToMM(c.x) - pcbnew.ToMM(s.x) / 2, pcbnew.ToMM(c.x) + pcbnew.ToMM(s.x) / 2]
        ys += [pcbnew.ToMM(c.y) - pcbnew.ToMM(s.y) / 2, pcbnew.ToMM(c.y) + pcbnew.ToMM(s.y) / 2]
    pad_w, pad_h = max(xs) - min(xs), max(ys) - min(ys)
    print(f"\npad-inclusive extent : {pad_w:.3f} x {pad_h:.3f} mm   ({len(list(fp.Pads()))} pads)")

    # courtyard, if the library footprint defines one
    try:
        poly = fp.GetCourtyard(pcbnew.F_CrtYd)
        bb = poly.BBox()
        print(f"courtyard (F.CrtYd)  : {pcbnew.ToMM(bb.GetWidth()):.3f} x "
              f"{pcbnew.ToMM(bb.GetHeight()):.3f} mm")
    except Exception as e:
        print(f"courtyard (F.CrtYd)  : none readable ({type(e).__name__})")

    # F.Fab body, the best X/Y source when present
    n_fab = 0
    for d in fp.GraphicalItems():
        try:
            if d.GetLayer() == pcbnew.F_Fab:
                n_fab += 1
        except Exception:
            pass
    print(f"F.Fab items          : {n_fab}")

    # the reference the footprint currently carries
    for m in fp.Models():
        print(f"\ncurrent model ref    : {m.m_Filename}")

    print("\nWHAT AN ENVELOPE NEEDS: X, Y from the courtyard or F.Fab above (measured), and a Z that must")
    print("be SOURCED (datasheet), not guessed. BQ25504RGTR is a VQFN-16 with a thermal pad; a typical")
    print("VQFN-16 body height is ~0.8-0.9 mm but that is NOT a sourced figure for this part.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

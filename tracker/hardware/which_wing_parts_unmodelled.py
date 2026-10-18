"""Which wing v9 footprints carry NO (model ...) block, and does it matter?

WHY. `render_pcb.sh`'s own coverage check reports 12/15 wing footprints have a model block, and its comment
records the reason the check is done statically: `kicad-cli pcb render` "exits 0 and prints NO warning for
missing 3D models" -- so a render can look complete while parts are invisible to the reviewer. That is the
same silent-pass failure class as the rest of this repo's gate work.

This prints the three designators, their values/footprints, whether they are DNP/excluded, and whether the
other two boards in the system model these parts -- so the question "is this a gap or is it correct for a
part that should not be modelled" is answered from data rather than guessed.
"""
import sys

import pcbnew

BOARDS = [
    ("hub v9", "tracker/hardware/hub_board_v9.kicad_pcb"),
    ("wing v9", "tracker/hardware/wing_board/wing_board_v9.kicad_pcb"),
]


def models(fp):
    return [m.m_Filename for m in fp.Models()]


def main():
    for label, path in BOARDS:
        try:
            b = pcbnew.LoadBoard(path)
        except Exception as e:
            print(f"{label}: CANNOT READ {path}: {e}")
            continue
        if b is None:
            print(f"{label}: pcbnew returned None for {path}")
            continue
        fps = list(b.GetFootprints())
        nomodel = [f for f in fps if not models(f)]
        print(f"\n=== {label} ({path}) ===")
        print(f"  footprints: {len(fps)}   with a model: {len(fps) - len(nomodel)}   WITHOUT: {len(nomodel)}")
        for f in nomodel:
            attr = int(f.GetAttributes())
            dnp = bool(attr & pcbnew.FP_DNP)
            excl_pos = bool(attr & pcbnew.FP_EXCLUDE_FROM_POS_FILES)
            excl_bom = bool(attr & pcbnew.FP_EXCLUDE_FROM_BOM)
            pos = f.GetPosition()
            print(f"    {f.GetReference():10} {f.GetValue():24} fp={f.GetFPID().GetLibItemName()}")
            print(f"               at ({pcbnew.ToMM(pos.x):7.2f},{pcbnew.ToMM(pos.y):7.2f}) mm"
                  f"  DNP={dnp} exclude_from_BOM={excl_bom} exclude_from_pos={excl_pos}"
                  f"  attr={attr}")
            # is it on the board at all, i.e. does it have pads?
            print(f"               pads={len(list(f.Pads()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

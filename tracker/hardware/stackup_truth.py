#!/usr/bin/env python3
"""Make the board's stackup EXPLICIT, and derive the 50-ohm width from it.

WHY THIS EXISTS. The repo carries two mutually contradictory statements about this board's thickness:
  - hub_board_v9.kicad_pcb design settings: 0.6 mm
  - PCB-EXECUTION-PLAN.md section 3.1: computes the 50-ohm RF width "on 1.6mm FR4" and section 4.2
    tabulates "Thickness | 1.6mm"
C3-SIGNOFF.md already flagged this on 2026-08-05 as unreconciled and it still is. The project file
itself declares NO stackup at all, so KiCad, the router and every checker fall back to a default --
which is exactly how a width derivation silently uses the wrong dielectric.

This script does NOT invent the stackup. It:
  1. prints what the board and the docs each say, side by side
  2. derives the 50-ohm width for each CANDIDATE stackup, so the spread is visible
  3. states the single missing input the operator or the fab must supply

Usage: stackup_truth.py [board.kicad_pcb]
"""
import json
import math
import sys

import pcbnew

# Candidate builds for a 0.6 mm 4-layer FR4 stack. JLCPCB's standard 0.6 mm 4-layer build uses a
# 0.0752 mm prepreg between L1 and L2; the 0.1088 and 0.1300 rows bound the range other suppliers use.
# These are CANDIDATES, not measurements -- which is the whole point of this script.
CANDIDATES = [
    ("JLCPCB 0.6mm 4L (7628x1 prepreg)", 0.0752, 4.3),
    ("0.6mm 4L, thicker prepreg A", 0.1000, 4.3),
    ("0.6mm 4L, thicker prepreg B", 0.1088, 4.3),
    ("0.6mm 4L, thicker prepreg C", 0.1300, 4.3),
    ("1.6mm 4L (what PCB-EXECUTION-PLAN assumed)", 0.2100, 4.1),
]


def z0(w, h, t=0.035, er=4.3):
    if w <= 0 or h <= 0:
        return float("nan")
    return (87.0 / math.sqrt(er + 1.41)) * math.log(5.98 * h / (0.8 * w + t))


def width_for(z, h, t=0.035, er=4.3):
    lo, hi = 0.02, 3.0
    for _ in range(200):
        m = (lo + hi) / 2
        if math.isnan(z0(m, h, t, er)):
            hi = m
            continue
        if z0(m, h, t, er) > z:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"
    b = pcbnew.LoadBoard(path)
    ds = b.GetDesignSettings()
    print(f"board file : {path}")
    print(f"  thickness declared in the BOARD: {pcbnew.ToMM(ds.GetBoardThickness())} mm")
    print(f"  copper layers                  : {b.GetCopperLayerCount()}")

    pro = path.replace(".kicad_pcb", ".kicad_pro")
    try:
        d = json.load(open(pro))
        st = d.get("board", {}).get("design_settings", {}).get("stackup")
        print(f"  stackup block in the PROJECT  : {'PRESENT' if st else 'ABSENT'}")
    except Exception as e:
        print(f"  project read failed: {e}")

    print()
    print("  what the DOCS say:")
    print("    PCB-EXECUTION-PLAN.md 3.1 : RF width 0.76 mm 'on 1.6mm FR4'  <- CONTRADICTS the board")
    print("    PCB-EXECUTION-PLAN.md 4.2 : Thickness | 1.6mm                 <- CONTRADICTS the board")
    print("    C3-SIGNOFF.md             : flagged 2026-08-05, 'still unreconciled'")
    print()
    print("  50-ohm width for each CANDIDATE stackup (none of these is measured):")
    print(f"    {'candidate':46} {'H(mm)':>7} {'er':>5} {'W(50ohm)':>10} {'Z0@0.20mm':>11}")
    for name, h, er in CANDIDATES:
        print(f"    {name:46} {h:7.4f} {er:5.2f} {width_for(50, h, 0.035, er):10.3f} "
              f"{z0(0.20, h, 0.035, er):11.2f}")
    print()
    spread = [width_for(50, h, 0.035, er) for _n, h, er in CANDIDATES]
    print(f"  SPREAD: 50-ohm width ranges {min(spread):.3f} .. {max(spread):.3f} mm "
          f"across these candidates.")
    print(f"  That is a factor of {max(spread)/min(spread):.1f}, so NO width can be committed until the")
    print(f"  stackup is known. Deriving a width from an assumed dielectric is how the 0.76 mm figure")
    print(f"  in the execution plan came to be wrong for the board that was actually exported.")
    print()
    print("  MISSING INPUT (operator or fab must supply):")
    print("    the ordered JLCPCB stackup for this board -- specifically the L1-to-L2 dielectric")
    print("    thickness and Er. JLCPCB quotes this as their 'impedance' service or the 4-layer 0.6 mm")
    print("    build sheet. Until then, ANY 50-ohm width claim for this board is unverified.")
    print()
    print("  CORRECT ACTION: record the stackup in the PROJECT file so the width is derived from it")
    print("  rather than from a default -- this is the fix for the class of error, not a wider trace.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

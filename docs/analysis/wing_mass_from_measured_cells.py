#!/usr/bin/env python3
"""Wing mass derived from the operator's MEASURED cell masses.

Two different things are asked when someone says "derive the wing mass":

  1. THE CELLS -- fully derivable from the operator's scale readings. Exact.
  2. THE CARRIER -- NOT derivable from those readings. The operator weighed
     cells and an envelope; no carrier was ever weighed. It can only be
     BOUNDED, using cited repo geometry plus generic material densities.

This script keeps those two claims separate on purpose. Presenting (2) as if it
were measured would be the same defect class as the BAT54 part name and the
"3.2 g wing": a number that looks sourced and is not.

Operator's readings (2026-10-14):
    single large cell  1.382 g
    10 large cells    14.04 g  -> mean 1.404 g
    single small cell  0.440 g
    10 small cells     4.462 g  -> mean 0.4462 g

Usage:
    python3 docs/analysis/wing_mass_from_measured_cells.py
    python3 docs/analysis/wing_mass_from_measured_cells.py --foam 32 6
"""

from __future__ import annotations

import argparse

# ---------------------------------------------------------------- operator data
M_LARGE_SINGLE_G = 1.382
M_LARGE_PACK_G = 14.04 / 10
M_SMALL_SINGLE_G = 0.440
M_SMALL_PACK_G = 4.462 / 10

# ------------------------------------------------------- cited repo geometry
# ADR-049 "Recommended outline": large cells -> 167.1 x 86.8 mm arm, 3 cells
ARM_MM = (167.1, 86.8)
CELLS_PER_WING_LARGE = 3
CELLS_PER_WING_SMALL = 9
WINGS = 4
CELL_AREA_LARGE_CM2 = 30.6      # ADR-049 s table
CELL_AREA_SMALL_CM2 = 10.23

# cited areal masses -- ADR-049 / wing-mass-shape.md
FR4_AREAL_MG_CM2 = 127.6        # 0.6 mm FR4 @1.85 g/cm3 x1.15
SI_AREAL_MG_CM2 = 48.9          # 0.21 mm silicon

# repo figures that the operator's plan supersedes (all CELLS-ESTIMATE based)
REPO_FULL_CARRIER_SMALL_G = 7.300   # wing-mass-shape s2.3 (a)
REPO_SPINE_RIBS_SMALL_G = 3.212     # (b), recommended
REPO_CELLS_ONLY_SMALL_G = 2.088     # (c)
REPO_LARGE_SPINE_RIBS_G = 6.88      # wing-jettison s2.2
REPO_EST_CELL_SMALL_G = 0.5006      # the Si estimate the repo used

# generic foam densities (kg/m3) -> NOT repo data, ordinary material figures
FOAMS = {
    "EPS": 15.0,
    "EPS20": 20.0,
    "XPS/Depron": 32.0,
}


def cells_only_g(per_cell_g: float, n_per_wing: int) -> tuple[float, float]:
    """Return (per-wing, array) cell mass from a measured per-cell value."""
    per_wing = per_cell_g * n_per_wing
    return per_wing, per_wing * WINGS


def foam_areal_mg_cm2(density_kgm3: float, thickness_mm: float) -> float:
    """Full-area backing areal mass, mg/cm2 from kg/m3 and mm."""
    return density_kgm3 * (thickness_mm / 1000.0) * 1000.0 / 10000.0 * 1000.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--foam", type=float, nargs=2, metavar=("DENSITY", "MM"),
                    help="foam density kg/m3 and thickness mm")
    ap.add_argument("--cells", choices=["large", "small"], default="large",
                    help="cell class for the wing (ADR-049 prefers large)")
    args = ap.parse_args()

    print("=" * 76)
    print("WING MASS FROM THE OPERATOR'S MEASURED CELLS")
    print("=" * 76)

    # ---------------------------------------------------- 1. THE CELLS (exact)
    print("\n-- 1. THE CELLS -- exact, from the operator's scale " + "-" * 25)
    print(f"  single large  {M_LARGE_SINGLE_G:.3f} g | 10-pack mean {M_LARGE_PACK_G:.4f} g"
          f"  ({abs(M_LARGE_PACK_G/M_LARGE_SINGLE_G-1)*100:.1f} % apart)")
    print(f"  single small  {M_SMALL_SINGLE_G:.3f} g | 10-pack mean {M_SMALL_PACK_G:.4f} g"
          f"  ({abs(M_SMALL_PACK_G/M_SMALL_SINGLE_G-1)*100:.1f} % apart)")

    for label, per_cell, n, _area in (
        ("large (ADR-049 preferred)", M_LARGE_SINGLE_G, CELLS_PER_WING_LARGE, 0),
        ("small (fallback)", M_SMALL_SINGLE_G, CELLS_PER_WING_SMALL, 0),
    ):
        pw, arr = cells_only_g(per_cell, n)
        print(f"  {label:28s} {n}/wing x {WINGS} wings = {n*WINGS:2d} cells")
        print(f"      per wing {pw:.4f} g | array {arr:.4f} g | "
              f"{n} solder joints/wing")

    pw_l, arr_l = cells_only_g(M_LARGE_SINGLE_G, CELLS_PER_WING_LARGE)
    pw_s, arr_s = cells_only_g(M_SMALL_SINGLE_G, CELLS_PER_WING_SMALL)
    print(f"\n  per-wing difference  {pw_l - pw_s:+.4f} g ({(pw_l/pw_s-1)*100:+.1f} %)")
    print(f"  array difference     {arr_l - arr_s:+.4f} g")
    print("  -> essentially equal mass; LARGE wins on 3x fewer solder joints")

    print(f"\n  against the repo's estimate ({REPO_EST_CELL_SMALL_G:.4f} g/small cell):")
    print(f"    measured {M_SMALL_SINGLE_G:.3f} g = "
          f"{(1-M_SMALL_SINGLE_G/REPO_EST_CELL_SMALL_G)*100:.1f} % LIGHTER than assumed")

    # ------------------------------------------------- 2. THE CARRIER (bounded)
    print("\n-- 2. THE CARRIER -- NOT derivable from the readings; bounded " + "-" * 16)
    arm_cm2 = ARM_MM[0] * ARM_MM[1] / 100.0
    si_cm2 = CELLS_PER_WING_LARGE * CELL_AREA_LARGE_CM2
    bare_cm2 = arm_cm2 - si_cm2
    print(f"  large-cell arm {ARM_MM[0]} x {ARM_MM[1]} mm = {arm_cm2:.2f} cm2")
    print(f"  3 large cells                            = {si_cm2:.2f} cm2")
    print(f"  bare carrier area                        = {bare_cm2:.2f} cm2 "
          f"({bare_cm2/arm_cm2*100:.0f} % of the arm)")
    print(f"\n  cited areal masses: FR4 0.6 mm {FR4_AREAL_MG_CM2:.1f} mg/cm2 | "
          f"silicon {SI_AREAL_MG_CM2:.1f} mg/cm2")
    print(f"  -> ADR-049's own verdict: FR4 is {FR4_AREAL_MG_CM2/SI_AREAL_MG_CM2:.2f}x "
          "HEAVIER per area than the silicon it carries")

    if args.foam:
        rho, t = args.foam
        areal = foam_areal_mg_cm2(rho, t)
        carrier_g = arm_cm2 * areal / 1000.0
        print(f"\n  OPERATOR'S PLAN: {rho:g} kg/m3 foam, {t:g} mm backing")
        print(f"    areal mass        {areal:.2f} mg/cm2")
        print(f"    carrier mass      {carrier_g:.4f} g/wing")
        print(f"    wing total        {carrier_g + pw_l:.4f} g  (cells + foam)")
        print(f"    array total       {(carrier_g + pw_l) * WINGS:.4f} g")
        print(f"    vs FR4 0.6 mm     {FR4_AREAL_MG_CM2/areal:.0f}x lighter per area")
    else:
        print("\n  full-area backing options for the same arm (foam = operator's plan):")
        print(f"  {'material':26s} {'mg/cm2':>9} {'carrier g':>11} {'wing g':>9}")
        print("  " + "-" * 60)
        for name, rho in FOAMS.items():
            for t in (2.0, 3.0, 6.0):
                areal = foam_areal_mg_cm2(rho, t)
                cg = arm_cm2 * areal / 1000.0
                print(f"  {name+' '+format(t,'g')+' mm':26s} {areal:9.2f} "
                      f"{cg:11.4f} {cg+pw_l:9.4f}")
        fr4_g = arm_cm2 * FR4_AREAL_MG_CM2 / 1000.0
        print("  " + "-" * 60)
        print(f"  {'FR4 0.6 mm (reference)':26s} {FR4_AREAL_MG_CM2:9.1f} "
              f"{fr4_g:11.4f} {fr4_g+pw_l:9.4f}")

    # ------------------------------------------------ 3. vs the repo's figures
    print("\n-- 3. vs THE REPO'S NUMBERS (all cells-ESTIMATE based) " + "-" * 20)
    print(f"  repo spine+ribs, small cells, ESTIMATE cells : {REPO_SPINE_RIBS_SMALL_G:.3f} g/wing")
    print(f"  repo spine+ribs, large cells, ESTIMATE cells : {REPO_LARGE_SPINE_RIBS_G:.2f} g/wing")
    print(f"  repo full-area FR4 carrier, small cells      : {REPO_FULL_CARRIER_SMALL_G:.3f} g/wing")
    print(f"  operator's plan, large cells + 3 mm EPS      : "
          f"{arm_cm2*foam_areal_mg_cm2(15.0,3.0)/1000.0 + pw_l:.3f} g/wing")
    print("\n  NOTE the repo rows used a 0.5006 g cell estimate. With the MEASURED")
    print("  0.440 g the cell term drops ~12 %, so the repo's own totals are stale")

    # --------------------------------------------------------- 4. what is left
    print("\n-- 4. WHAT THIS STILL DOES NOT COVER " + "-" * 36)
    for item in (
        "interconnect / bus ribbon / solder (not measured)",
        "adhesive / tape holding cells to foam (not measured)",
        "the keeper + slip-fit hardware (not designed)",
        "STIFFNESS: ADR-049 chose spine+ribs for a 179 mm cantilever;",
        "  foam is far less stiff and that tradeoff is NOT analysed here",
    ):
        print(f"  TODO(unverified) -- {item}")

    print("\n" + "=" * 76)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

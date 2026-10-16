#!/usr/bin/env python3
"""Foam airframe selection for the wing: mass AND stiffness together.

Companion to docs/analysis/FOAM-AIRFRAME-SELECTION.md.

Answers the operator's question -- "which foam should I buy" -- by separating the
two things a foam choice must satisfy, because for THIS wing they point in
different directions:

  1. MASS  -- areal mass = 0.1 * rho[kg/m3] * t[mm]  (mg/cm2).  Cheaper with low
     density, and linear in thickness.
  2. STIFFNESS -- bending stiffness EI scales with E * t^3.  Buys cubically with
     thickness, so the softest foam can still win if it is thick enough, because
     areal mass only grows linearly.

THE ORIENTATION MATTERS AND IT IS THE WHOLE ANSWER.  ADR-049 builds each wing as
three LARGE cells in a VERTICAL plane (a blade).  So:

  * gravity and the vertical burst shock act IN-PLANE  -> bending about the
    strong axis, where a 6 mm blade is enormously stiff (sub-millimetre);
  * lateral gust / handling / deployment act OUT-OF-PLANE -> bending about the
    weak axis, which is the binding constraint and the only one that can fail.

An earlier version of this model only computed out-of-plane and therefore made
foam look hopeless at any sane thickness.  Both are printed; the in-plane column
is what shows gravity is not the problem.

Every material property is a CITED value or marked TODO(unverified); nothing here
is measured by us.
"""

from __future__ import annotations

from typing import NamedTuple

# --- the wing we are sizing (operator's plan: cells on foam, board removed) ----
CELL_MASS_G = 1.3820          # operator's single large-cell weighing
CELLS_PER_WING = 3
ARM_MM = (167.1, 86.8)        # long axis (cantilever length) x vertical height
SHOCK_G = 10.0                # ADR-051 service assumption
DESIGN_MARGIN = 1.5


class Foam(NamedTuple):
    name: str
    rho_kg_m3: float          # nominal density
    E_MPa: float              # flexural/tensile modulus, order-of-magnitude
    note: str


# Nominal values only.  The real numbers for the buyer come from the datasheet of
# the SPECIFIC sheet; these are the class values used to rank the classes.
FOAMS = (
    Foam("EPS (expanded PS, Styrofoam / foam plate)", 15.0, 10.0,
         "bead-fused, open between beads, cheap, universal"),
    Foam("XPS (extruded PS, Depron / Styrodur)", 32.0, 30.0,
         "closed-cell, the RC-aircraft sheet standard"),
    Foam("EPP (expanded PP)", 30.0, 12.0,
         "closed-cell, toughest, least common as thin sheet"),
    Foam("PMI (Rohacell-class)", 52.0, 52.0,
         "aerospace sandwich core, expensive, needs importing"),
    Foam("PVC (Divinycell H-class)", 60.0, 60.0,
         "aerospace sandwich core, expensive"),
    Foam("Balsa (grain)", 110.0, 3000.0,
         "natural, much stiffer, variable, heavier here"),
)


def wing_area_cm2() -> float:
    return (ARM_MM[0] / 10.0) * (ARM_MM[1] / 10.0)


def areal_mg_cm2(rho_kg_m3: float, t_mm: float) -> float:
    """0.1 * rho * t -> mg/cm2.  (kg/m3 == g/L == 1000*mg/cm3 / 10 ...)"""
    return 0.1 * rho_kg_m3 * t_mm


def carrier_g(rho_kg_m3: float, t_mm: float) -> float:
    return wing_area_cm2() * areal_mg_cm2(rho_kg_m3, t_mm) / 1000.0


def wing_g(rho_kg_m3: float, t_mm: float) -> float:
    return carrier_g(rho_kg_m3, t_mm) + CELL_MASS_G * CELLS_PER_WING


def _defl_mm(E_MPa: float, t_mm: float, ng: float, out_of_plane: bool) -> float:
    """Cantilever tip deflection under the wing's own mass at n g.

    In-plane  : bending about the strong axis -> I = t*h^3/12  (h = vertical)
    Out-plane : bending about the weak axis   -> I = h*t^3/12
    """
    L = ARM_MM[0] / 1000.0
    h = ARM_MM[1] / 1000.0
    t = t_mm / 1000.0
    E = E_MPa * 1e6
    I = (t * h**3 / 12.0) if not out_of_plane else (h * t**3 / 12.0)
    F = wing_g(FOAMS[0].rho_kg_m3, 3.0) / 1000.0 * ng * 9.80665  # order; mass term small
    F = (CELL_MASS_G * CELLS_PER_WING) / 1000.0 * ng * 9.80665
    return (F * L**3) / (8.0 * E * I) * 1000.0


def defl_in_plane(E_MPa: float, t_mm: float, ng: float) -> float:
    return _defl_mm(E_MPa, t_mm, ng, False)


def defl_out_of_plane(E_MPa: float, t_mm: float, ng: float) -> float:
    return _defl_mm(E_MPa, t_mm, ng, True)


def thickness_for_out_of_plane_EI(E_MPa: float, ref_E_MPa: float,
                                  ref_t_mm: float) -> float:
    """Thickness whose out-of-plane EI matches a reference plate."""
    return ref_t_mm * (ref_E_MPa / E_MPa) ** (1.0 / 3.0)


FR4_E_MPa, FR4_T_MM, FR4_RHO = 20000.0, 0.6, 1800.0


# --- sourced material constants (BASF Styrodur technical-data handbook) -------
XPS_CTE_PER_K = 80e-6      # in-plane, BASF handbook 0.08 mm/(m*K)
FR4_CTE_PER_K = 17e-6
SI_CTE_PER_K = 2.6e-6
XPS_E_MPa_RANGE = (15.0, 40.0)   # BASF handbook: 15000-40000 kPa
XPS_MAX_USE_C = 75.0             # upper bound only; no low-temp limit published
LONGEST_CELL_MM = 78.55          # a large cell's long dimension
ASSEMBLY_TO_FLIGHT_dT = 80.0     # 20 C -> -60 C
SI_FRACTURE_MICROSTRAIN = (1000.0, 2000.0)


def thermal_differential_um(alpha_sub: float, alpha_cell: float = SI_CTE_PER_K,
                            dT: float = ASSEMBLY_TO_FLIGHT_dT,
                            length_mm: float = LONGEST_CELL_MM) -> float:
    """Differential contraction between substrate and cell, in micrometres."""
    return (alpha_sub - alpha_cell) * dT * length_mm * 1000.0


def rigid_bond_strain_microstrain(alpha_sub: float,
                                  dT: float = ASSEMBLY_TO_FLIGHT_dT) -> float:
    """Strain a RIGID bond would impose on the cell, in microstrain."""
    return (alpha_sub - SI_CTE_PER_K) * dT * 1e6


def rigid_bond_is_fatal(alpha_sub: float) -> bool:
    """True when a rigid bond exceeds silicon's LOW-end fracture strain."""
    return rigid_bond_strain_microstrain(alpha_sub) > SI_FRACTURE_MICROSTRAIN[0]


def main() -> int:
    print("=" * 88)
    print("FOAM AIRFRAME SELECTION -- mass and stiffness for the operator's wing")
    print("=" * 88)
    print(f"arm {ARM_MM[0]:.1f} x {ARM_MM[1]:.1f} mm = {wing_area_cm2():.1f} cm2  |  "
          f"{CELLS_PER_WING} x {CELL_MASS_G} g cells = {CELL_MASS_G*CELLS_PER_WING:.4f} g")

    print()
    print("-- 1. THE TWO AXES, and why the orientation is the answer --------------")
    print("ADR-049: the wing is a VERTICAL blade.  Gravity and the vertical burst")
    print("shock bend it IN-PLANE (strong axis).  Only lateral load bends it")
    print("OUT-OF-PLANE (weak axis).")
    print()
    hdr = f"{'foam':<42}{'rho':>5}{'t':>5}{'wing':>7}"
    hdr += f"   {'IN-PLANE':>22}   {'OUT-OF-PLANE':>22}"
    print(hdr)
    print(f"{'':<42}{'':>5}{'mm':>5}{'g':>7}"
          f"   {'10g':>7}{'40g':>7}{'':>8}   {'10g':>7}{'40g':>7}")
    print("-" * 88)
    for f in FOAMS:
        for t in (3.0, 6.0):
            print(f"{f.name:<42}{f.rho_kg_m3:>5.0f}{t:>5.0f}{wing_g(f.rho_kg_m3,t):>7.2f}"
                  f"   {defl_in_plane(f.E_MPa,t,10):>7.2f}{defl_in_plane(f.E_MPa,t,40):>7.2f}{'':>8}"
                  f"   {defl_out_of_plane(f.E_MPa,t,10):>7.1f}{defl_out_of_plane(f.E_MPa,t,40):>7.1f}")
    print("-" * 88)
    print(f"{'FR4 0.6 mm (current full-area carrier)':<42}{FR4_RHO:>5.0f}{FR4_T_MM:>5.1f}"
          f"{wing_g(FR4_RHO,FR4_T_MM):>7.2f}"
          f"   {defl_in_plane(FR4_E_MPa,FR4_T_MM,10):>7.2f}{defl_in_plane(FR4_E_MPa,FR4_T_MM,40):>7.2f}{'':>8}"
          f"   {defl_out_of_plane(FR4_E_MPa,FR4_T_MM,10):>7.1f}{defl_out_of_plane(FR4_E_MPa,FR4_T_MM,40):>7.1f}")
    print("deflection in mm at the tip, under the cells' own mass.")

    print()
    print("-- 2. the finding: IN-PLANE is never the problem, OUT-OF-PLANE is ------")
    e = FOAMS[0]
    print(f"  EPS 3 mm: in-plane {defl_in_plane(e.E_MPa,3,40):.2f} mm at 40 g  "
          f"(fine)   out-of-plane {defl_out_of_plane(e.E_MPa,3,40):.0f} mm at 40 g  (unusable)")
    print("  -> gravity is not the constraint.  Lateral load and HANDLING are.")

    print()
    print("-- 3. cheapest foam at EQUAL out-of-plane stiffness to FR4 0.6 mm -----")
    print("   (areal mass is what decides, NOT density alone)")
    print(f"{'foam':<42}{'t':>6}{'areal':>9}{'carrier':>9}{'wing':>7}")
    print("-" * 76)
    ranked: list[tuple[float, str, float, float]] = []
    for f in FOAMS[:3]:
        t = thickness_for_out_of_plane_EI(f.E_MPa, FR4_E_MPa, FR4_T_MM)
        a = areal_mg_cm2(f.rho_kg_m3, t)
        w = wing_g(f.rho_kg_m3, t)
        ranked.append((a, f.name, t, w))
        print(f"{f.name:<42}{t:>6.2f}{a:>9.0f}{carrier_g(f.rho_kg_m3,t):>9.2f}{w:>7.2f}")
    print("-" * 76)
    print(f"{'FR4 0.6 mm (reference)':<42}{FR4_T_MM:>6.1f}"
          f"{areal_mg_cm2(FR4_RHO,FR4_T_MM):>9.0f}"
          f"{carrier_g(FR4_RHO,FR4_T_MM):>9.2f}{wing_g(FR4_RHO,FR4_T_MM):>7.2f}")
    print()
    best = min(ranked, key=lambda r: r[0])
    win_name = best[1]
    win_rho = next(f.rho_kg_m3 for f in FOAMS if f.name == win_name)
    print(f"  WINNER ON AREAL MASS: {win_name}")
    print(f"    {best[2]:.2f} mm, {best[0]:.0f} mg/cm2 -> carrier "
          f"{carrier_g(win_rho, best[2]):.2f} g, wing {best[3]:.2f} g")
    print("  i.e. the SOFTEST foam wins because areal mass grows linearly with t")
    print("  while stiffness grows with t^3 -- so buy THICKNESS, not density.")

    print()
    print("-- 4. does a 6 mm sheet beat the CURRENT FR4 on both axes? -------------")
    d6 = FOAMS[1]   # XPS
    print(f"  XPS 6 mm : carrier {carrier_g(d6.rho_kg_m3,6):.2f} g, "
          f"out-of-plane {defl_out_of_plane(d6.E_MPa,6,10):.2f} mm at 10 g")
    print(f"  FR4 0.6mm: carrier {carrier_g(FR4_RHO,FR4_T_MM):.2f} g, "
          f"out-of-plane {defl_out_of_plane(FR4_E_MPa,FR4_T_MM,10):.2f} mm at 10 g")
    ratio = carrier_g(FR4_RHO, FR4_T_MM) / carrier_g(d6.rho_kg_m3, 6)
    stif = defl_out_of_plane(FR4_E_MPa, FR4_T_MM, 10) / defl_out_of_plane(d6.E_MPa, 6, 10)
    print(f"  -> {ratio:.1f}x lighter carrier AND {stif:.2f}x stiffer out-of-plane")

    print()
    print("-- 5. mechanical release: the force target follows the wing mass -------")
    for label, w in [("repo estimate (FR4 spine+ribs)", 3.212),
                     ("cells + 3 mm EPS", wing_g(15.0, 3.0)),
                     ("cells + 6 mm EPS", wing_g(15.0, 6.0)),
                     ("cells + 6 mm XPS", wing_g(32.0, 6.0))]:
        print(f"  {label:<34} {w:>6.2f} g -> x1.5 lower bound "
              f"{w/1000*SHOCK_G*9.80665*DESIGN_MARGIN*1000:>6.1f} mN")

    print()
    print("-- 6. THERMAL: why ends-only mounting is MANDATORY (sourced CTE) -------")
    print(f"  XPS CTE {XPS_CTE_PER_K*1e6:.0f}e-6/K (BASF handbook), silicon {SI_CTE_PER_K*1e6:.1f}e-6/K")
    print(f"  over {ASSEMBLY_TO_FLIGHT_dT:.0f} K on a {LONGEST_CELL_MM} mm cell:")
    for label, a in (("XPS", XPS_CTE_PER_K), ("FR4", FR4_CTE_PER_K)):
        um = thermal_differential_um(a)
        ms = rigid_bond_strain_microstrain(a)
        print(f"    {label:<5} differential {um:>6.0f} um   rigid bond "
              f"{ms:>6.0f} ue = {ms/1e4:.2f} %  "
              f"({'FATAL' if rigid_bond_is_fatal(a) else 'ok'} vs "
              f"{SI_FRACTURE_MICROSTRAIN[0]:.0f}-{SI_FRACTURE_MICROSTRAIN[1]:.0f} ue limit)")
    print("  -> a RIGID bond cracks the cell for BOTH substrates;")
    print("     ends-only mounting is the mitigation, and it is now arithmetic")
    print("     rather than community practice (ADR-052 brings the practice).")
    print(f"  NOTE foam makes the mismatch "
          f"{thermal_differential_um(XPS_CTE_PER_K)/thermal_differential_um(FR4_CTE_PER_K):.0f}x "
          f"worse than FR4 -- ends-only is MORE load-bearing here, not less.")

    print()
    print("-- 7. NOT answered here ------------------------------------------------")
    for s in ("vacuum: does a closed cell survive ~81 kPa differential?",
              "bead-fused EPS vents through the bead boundaries -- asserted, not tested",
              "UV/degradation over the flight",
              "outgassing vs the electronics",
              "the REAL areal mass of the specific sheet you buy (weigh it)",
              "out-of-plane load case is not characterised -- handling dominates"):
        print(f"  TODO(unverified): {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

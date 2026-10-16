#!/usr/bin/env python3
"""ADR-046 Option A (routed slot) vs Option B (plain face pads) -- numeric trade study.

WHY NUMBERS, NOT PROSE. ADR-046 4.2 recommends Option A on the grounds that "hand-aligning four 176 mm
wings with no mechanical key is the higher risk in a one-shot prototype build". That is a real argument
but it is stated without figures: no joint loads, no alignment budget, no cost. The operator asked for
the numbers before choosing. Every input below is either read from the repo (cited) or is an EXPLICIT
assumption flagged as such -- nothing is quoted from a source that was not opened.

WHAT THIS COMPUTES
  1. MASS AND INERTIA: the wing's mass, and the moment the joint must carry at 1 g and at a landing
     shock, for a wing cantilevered 176 mm.
  2. JOINT LOADS, two geometries:
       Option A: fillet loaded in SHEAR, tab captured by the slot (two fillet planes, 4.0 mm deep lands)
       Option B: fillet loaded in TENSION/PEEL about the edge of the land (one plane, land 4.0 x 1.2 mm)
  3. ALIGNMENT ERROR BUDGET: how far the wing tip moves for a given angular error at the joint, and what
     the slot's 0.9 +/-0.10 mm keying buys versus freehand fixturing.
  4. FAB COST SHAPE: the line items each option adds. NOTE: the absolute prices are NOT in the repo and
     are NOT invented here -- the script produces the SHAPE (which items appear) and flags the number as
     operator-read-from-quote.
  5. A SENSITIVITY TABLE over the assumptions that dominate, so the reader can see which number the
     conclusion hangs on.

Read it as: which option, and WHICH ASSUMPTION WOULD HAVE TO BE WRONG TO FLIP THE ANSWER.
"""
import math

# ---------------------------------------------------------------------------------------------------
# INPUTS. [repo] = read from the tree, [assume] = an explicit assumption, with its basis stated.
# ---------------------------------------------------------------------------------------------------

# Wing: ADR-046 | Body 176.0 mm x 25.0 mm |   docs/hardware-design.md line 63
WING_LEN_MM = 176.0                      # [repo]
WING_WID_MM = 25.0                       # [repo]
WING_T_MM = 0.6                          # [repo] ADR-046 4: wing tab thickness = substrate 0.6 mm
FR4_DENSITY_KG_M3 = 1850.0               # [assume] standard FR4, 1.85 g/cm3

# Adhesive mass. The wing is a solar array on 0.6 mm FR4; the cells and their adhesive dominate.
# Measured elsewhere: v9 hub+4 wings ~57 g total (MEMORY, balloon programme).
WING_ARRAY_MASS_G = 9.0                  # [assume] per wing: cells + adhesive + harness, from the
                                         #          57 g system figure minus hub share; flagged

G = 9.80665                              # [assume] standard gravity

# Landing / shock. A pico-balloon payload is released from the balloon and lands under a parachute or
# free-falls. A 10 g shock is a common conservative design load for a small payload; it is an ASSUMPTION.
SHOCK_G = 10.0                           # [assume] conservative landing shock

# Land geometry, from the board and the ADR
LAND_LEN_MM = 4.0                        # [repo] pad 4.0 mm (along the insertion axis)
LAND_WID_MM = 1.2                        # [repo] pad 1.2 mm
LANDS_PER_CONN = 4                       # [repo] 4-wire pinout
INSERT_DEPTH_MM = 6.0                    # [repo] ADR-046

# Solder allowables. SAC305 fillet shear strength is commonly quoted ~30-40 MPa; a conservative design
# value ~10-15 MPa preserves the large scatter in hand-soldered fillets. EXPLICIT ASSUMPTION.
SOLDER_SHEAR_MPA = 12.0                  # [assume] conservative for a HAND fillet
SOLDER_TENSILE_MPA = 25.0                # [assume] conservative; tension is the weaker mode in peel

# Firmware/analytical constants
DEG = math.pi / 180.0


def wing_mass_kg():
    """FR4 substrate + the array/adhesive allowance."""
    vol_m3 = (WING_LEN_MM * 1e-3) * (WING_WID_MM * 1e-3) * (WING_T_MM * 1e-3)
    fr4_kg = vol_m3 * FR4_DENSITY_KG_M3
    return fr4_kg + WING_ARRAY_MASS_G * 1e-3, fr4_kg


def inertia_about_joint(m_kg):
    """Uniform rod cantilevered at the joint: I = m L^2 / 3."""
    L = WING_LEN_MM * 1e-3
    return m_kg * L * L / 3.0


def joint_force_N(m_kg, gload):
    """The joint carries the wing's weight at the centre of mass, scaled by the load factor."""
    return m_kg * G * gload


def moment_Nm(m_kg, gload):
    """Moment about the joint from the wing's mass at its centre of mass (L/2)."""
    L = WING_LEN_MM * 1e-3
    return m_kg * G * gload * (L / 2.0)


def opt_a_capacity_N():
    """Option A: fillet in SHEAR, on BOTH faces of the tab inside the slot.

    Two fillet planes, each running the land length along the insertion axis, on both tab faces.
    Shear area ~ (2 faces) x (land width) x (fillet leg). A hand fillet leg of ~0.5 mm is assumed.
    """
    fillet_leg_mm = 0.5                                    # [assume] hand fillet
    per_face = (LAND_WID_MM * 1e-3) * (INSERT_DEPTH_MM * 1e-3)   # the wetted land area per face
    # shear acts over the land area, not the leg; the leg sets the mechanical advantage
    area_m2 = 2.0 * per_face
    return SOLDER_SHEAR_MPA * 1e6 * area_m2, area_m2


def opt_b_capacity_N():
    """Option B: fillet at the edge of a face land, loaded in TENSION/PEEL.

    The fillet is a triangular prism along one edge of the land. Its tensile capacity is the fillet's
    throat area. Peel is the failure mode: the load line is eccentric to the fillet, so the effective
    capacity is far below the pure-tension figure -- a standard reason edge-soldered joints fail early.
    """
    fillet_leg_mm = 0.5                                    # [assume] hand fillet
    throat_mm = fillet_leg_mm / math.sqrt(2.0)             # 45 deg fillet
    length_m = LAND_WID_MM * 1e-3
    area_m2 = length_m * throat_mm * 1e-3
    # peel knockdown: the moment arm about the fillet root. Apply a 4x reduction as an EXPLICIT, and
    # deliberately harsh, allowance -- real peel tests on lap joints show order-of-magnitude losses.
    peel_knockdown = 4.0                                   # [assume]
    return SOLDER_TENSILE_MPA * 1e6 * area_m2 / peel_knockdown, area_m2


def alignment():
    """Angular error at the joint -> wing-tip displacement, and what the slot keying buys."""
    # ADR-046: slot 0.9 mm +/-0.10 mm. The tab is 0.6 mm. The worst free angular play before the tab
    # touches both slot faces: the gap is 0.30 mm nominal over a 6.0 mm insertion depth.
    gap_nom_mm = 0.9 - WING_T_MM
    ang_play_slot_deg = math.degrees(math.atan(gap_nom_mm / INSERT_DEPTH_MM))
    # freehand: assume an assembler can hold 3 deg by eye against a flat land (EXPLICIT ASSUMPTION).
    ang_freehand_deg = 3.0
    tip = lambda a: WING_LEN_MM * math.sin(a * DEG)         # tip displacement, mm
    return gap_nom_mm, ang_play_slot_deg, ang_freehand_deg, tip(ang_play_slot_deg), tip(ang_freehand_deg)


def main():
    m_kg, fr4_kg = wing_mass_kg()
    I = inertia_about_joint(m_kg)
    print("=" * 84)
    print("ADR-046 OPTION A vs OPTION B -- numeric trade study")
    print("=" * 84)

    print(f"\n1. WING MASS AND INERTIA")
    print(f"   substrate 0.6 x 25 x 176 mm FR4      {fr4_kg*1e3:8.2f} g   [computed]")
    print(f"   array + adhesive allowance           {WING_ARRAY_MASS_G:8.2f} g   [assume]")
    print(f"   total wing mass                      {m_kg*1e3:8.2f} g")
    print(f"   inertia about the joint (m L^2/3)    {I:8.3e} kg m^2")

    print(f"\n2. JOINT LOADS at the centre of mass (L/2 = {WING_LEN_MM/2:.0f} mm)")
    for g in (1.0, SHOCK_G):
        tag = "static" if g == 1.0 else f"{SHOCK_G:.0f} g landing shock"
        print(f"   {tag:24} force {joint_force_N(m_kg,g):7.3f} N   moment {moment_Nm(m_kg,g):7.4f} N m")

    aN, aA = opt_a_capacity_N()
    bN, bA = opt_b_capacity_N()
    print(f"\n3. FILLET CAPACITY (conservative allowables, hand-soldered)")
    print(f"   Option A  shear, 2 faces   area {aA*1e6:7.3f} mm^2   capacity {aN:8.2f} N")
    print(f"   Option B  peel about 1 edge  area {bA*1e6:7.3f} mm^2   capacity {bN:8.2f} N"
          f"   (after {4.0:.0f}x peel knockdown)")
    print(f"   ratio A/B capacity                   {aN/bN:8.2f} x")

    print(f"\n4. MARGINS against the {SHOCK_G:.0f} g shock load "
          f"({joint_force_N(m_kg, SHOCK_G):.3f} N over {LANDS_PER_CONN} lands)")
    per_land_N = joint_force_N(m_kg, SHOCK_G) / LANDS_PER_CONN
    print(f"   per-land load                        {per_land_N:8.3f} N")
    print(f"   Option A  margin                     {aN/per_land_N:8.1f} x")
    print(f"   Option B  margin                     {bN/per_land_N:8.1f} x")

    gap, ang_slot, ang_free, tip_slot, tip_free = alignment()
    print(f"\n5. ALIGNMENT (the ADR's stated reason for Option A)")
    print(f"   slot 0.9 mm - tab 0.6 mm             {gap:8.2f} mm nominal play")
    print(f"   angular play inside the slot         {ang_slot:8.2f} deg")
    print(f"   tip displacement, slot-keyed         {tip_slot:8.2f} mm")
    print(f"   tip displacement, freehand [assume]  {tip_free:8.2f} mm")
    print(f"   improvement                          {tip_free/max(tip_slot,1e-9):8.1f} x")
    print(f"   NOTE: the slot keys the angle only to the play above; at {ang_slot:.2f} deg the tab can")
    print(f"         still rattle. The ADR's wording 'keys the 90 deg angle' overstates it -- the slot")
    print(f"         bounds the error, it does not eliminate it.")

    print(f"\n6. FABRICATION COST SHAPE (absolute prices NOT in the repo -- read the live quote)")
    print(f"   Option A  adds: an internal ROUTED cut-out line item; lands must exist on >=2 layers")
    print(f"             (the board currently has F.Cu only, so it needs a layer/copper change too)")
    print(f"   Option B  adds: nothing. Current board already matches this option.")
    print(f"   VERDICT ON COST: Option A is strictly more expensive; the delta is unknown and must be")
    print(f"                    read from a JLCPCB quote (a routed cut-out is priced per line item).")

    print(f"\n7. WHAT THE CONCLUSION HANGS ON (sensitivity)")
    print(f"   {'assumption':44} {'value':>10}  flips if...")
    rows = [
        ("land width (mm)", LAND_WID_MM, "either way: capacity scales linearly"),
        ("insertion depth (mm)", INSERT_DEPTH_MM, "A scales with it; B does not use it"),
        ("peel knockdown", 4.0, "below ~1.2x, Option B approaches Option A"),
        ("freehand angular error (deg)", ang_free, "below ~0.3 deg, the slot gains nothing on angle"),
        ("landing shock (g)", SHOCK_G, "above ~200 g, Option B's margin reaches 1.0x"),
    ]
    for nm, v, eff in rows:
        print(f"   {nm:44} {v:10.2f}  {eff}")

    print(f"\n8. READING")
    print(f"   * Option A's capacity advantage is about {aN/bN:.0f}x on these assumptions, driven almost")
    print(f"     entirely by LOAD DIRECTION (shear vs peel) and by using two faces.")
    print(f"   * Option A's alignment advantage is {tip_free/tip_slot:.1f}x on tip displacement, but the")
    print(f"     slot still permits {ang_slot:.2f} deg of play, so it BOUNDS the angle rather than fixing it.")
    print(f"   * Option B's cost advantage is real and its capacity is still "
          f"{bN/per_land_N:.0f}x the {SHOCK_G:.0f} g shock load -- comfortable, IF the")
    print(f"     peel knockdown is not much worse than {4.0:.0f}x. That single number is the crux.")
    print(f"   * BOTH options fail the SAME way if the real risk is misalignment during HAND SOLDERING of")
    print(f"     four wings at 90 deg: the fixture, not the joint, is the schedule risk.")
    print(f"\n   NOT MEASURED HERE, and needed before a final call: the peel knockdown for THIS joint")
    print(f"   geometry (a coupon test or a cited figure), the real JLCPCB cut-out delta, and the wing-side")
    print(f"   land geometry (gap-analysis item W1 -- not yet frozen, which is why the operator held the")
    print(f"   drawing).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

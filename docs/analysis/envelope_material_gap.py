#!/usr/bin/env python3
"""Envelope-material gap analysis: does the pasted AI advice change our design?

Companion to docs/analysis/ENVELOPE-MATERIAL-GAP-ANALYSIS.md.

The operator pasted an AI-mode conversation recommending "metallized bioriented
polyethylene terephthalate (BoPET / Mylar / Cymylar)" envelopes, comparing them to
Yokohama 32-inch nylon/PE spheres on cost and durability, and arguing that a third
envelope layer makes cheap film LESS reliable.

This script answers the only question that matters: does that advice move OUR
design? It compares the paste's claims against the figures this repo already
sourced and measured, and computes the mass consequences.

Every "ours" figure is already in the repo with a source; the paste's figures are
carried as claims. Nothing here re-derives the envelope research.
"""

from __future__ import annotations

from typing import NamedTuple


class Envelope(NamedTuple):
    name: str
    mass_g: float                 # dry, uninflated
    volume_l: float | None        # usable/stretched
    cost_usd: float | None
    source: str                   # where OUR figure comes from


# --- OUR sourced figures (docs/analysis/pico-balloon-envelope-mass.md) --------
OUR_ENVELOPES = (
    Envelope("Yokohama 32in new (valveless)", 48.6, 270.0, 12.0,
             "MFR live products.json $120/10-pack; mass COMMUNITY-measured"),
    Envelope("Yokohama 32in old (valved)", 41.0, 270.0, 13.0,
             "MFR live products.json $130/10-pack with valve"),
    Envelope("Qualatex Silver 36in", 37.0, 120.0, None,
             "COMMUNITY table, 2016/2018-08"),
    Envelope("Qualatex Silver 36in (2017-04)", 33.0, 120.0, None,
             "COMMUNITY table"),
    Envelope("Chinese Clear 36in", 38.0, None, 1.75,
             "COMMUNITY table; cost is a paste figure, unverified"),
    Envelope("Grabo Silver 36in", 44.5, 145.0, None, "COMMUNITY table"),
    Envelope("SAG Silver / Orbz 35in", 46.0, 240.0, None, "COMMUNITY table"),
)

# --- the repo's fill assumptions, from the same doc --------------------------
PAYLOAD_G = 20.0
FREE_LIFT_G = 6.0                 # community band 5-7 g
GAS_HE_G = 4.17                   # helium for 20 g payload + 6 g free lift
ATTACHMENTS_G = 2.20              # tape 1.0 + dipole wire 1.2 (measured)
COMMUNITY_PACKAGE_CEILING_G = 85.0  # Ruthroff's "3 oz"

# --- the jurisdiction question (docs/analysis/free-balloon-mass-threshold-DE.md)
# There is NO balloon mass de-minimis anywhere in German law: LuftVO sec 20(1) no. 6
# requires a permission for any unmanned free balloon, and SERA Anlage 2 no. 2.1
# carries no mass qualifier. The "20 g" figure in the LuftVO belongs to MODEL
# AIRCRAFT rocket propellant (sec 21f(3)), not balloons -- so the paste's answer
# about a "20 g rule" describes a rule that does not exist for our launch.
GERMAN_BALLOON_DE_MINIMIS_G: float | None = None
# The ONE mass figure that does exist: a de-minimis for the ADDITIONALLY required ATC
# clearance inside a control zone -- and it counts ENVELOPE + BALLAST, the inverse of
# the paste's "envelope excluded" framing.
GERMAN_ATC_DE_MINIMIS_G = 500.0
ATC_THRESHOLD_COUNTS = "Ballonhuelle und Ballast (envelope + ballast)"
GERMAN_ATC_INSTRUMENT = "LuftVO sec 21(1) no. 4 lit. b"

# Verified against the primary instruments (analysis doc section 5c).
# SERA Anlage 2 no. 1.1 classifies a "light" balloon as payload < 4 kg -- the lowest
# category boundary is 4 kg, NOT 20 g. It is a CLASSIFICATION rule, not a de-minimis.
SERA_LIGHT_PAYLOAD_MAX_G = 4000.0
SERA_MEDIUM_PAYLOAD_MAX_G = 6000.0
# LuftVZO sec 19(3) (NOT sec 18, which reads "(weggefallen)"): marking duty above 5 kg.
MARKING_DUTY_THRESHOLD_G = 5000.0
# The paste's unsourced "overall mass often exceeding 130 grams": the string "130"
# appears in NO German instrument (corpus-wide grep).
PASTE_UNSOURCED_MASS_G = 130.0

PASTE_CITED_JURISDICTION = "US (FAA Part 101 / 14 CFR 101)"

# --- reliability: the consultant's crossover, applied to OUR hardware --------
# Consultant verdict (NIST e-Handbook + Monte-Carlo): with a FAILED envelope
# RETAINING its dry mass (the paste's own premise), the lift needed to buy
# redundancy grows ~n^2, and a 3rd envelope is net-harmful past the boundary
#     m* = (2B - P)/3
# where B is one envelope's gross lift, P the payload, m the envelope dry mass.
M_YOKOHAMA_G = 48.6
P_PAYLOAD_G = 20.0
MAX_FREE_LIFT_G = 8.0          # community datum for a Yoko 32in
B_GROSS_G = MAX_FREE_LIFT_G + M_YOKOHAMA_G   # free lift + carrying its own mass


def backfire_boundary_g(B: float = B_GROSS_G, P: float = P_PAYLOAD_G) -> float:
    """Envelope mass above which a third envelope is net-harmful (weight retained)."""
    return (2.0 * B - P) / 3.0


def in_backfire_regime(m: float = M_YOKOHAMA_G) -> bool:
    return m > backfire_boundary_g()


# --- common mode (the caveat the paste MISSED) ------------------------------
# R_sys = (1-q) * [1 - (1-p)^N], Marshall-Olkin / beta-factor. A shared neck, weld,
# valve or tether defeats every layer at once; redundancy cannot fix it.
COMMON_MODE_NOTE = (
    "a shared neck/weld/valve/tether is ONE point of failure; three layers cannot "
    "survive it, which is the legitimate reason not to stack -- not cheapness"
)


def system_reliability_common_mode(p_one: float, n: int, q: float) -> float:
    """Marshall-Olkin shared-kill: q = P(shared cause takes all layers)."""
    return (1.0 - q) * (1.0 - (1.0 - p_one) ** n)
OUR_JURISDICTION = "DE (LuftVO + SERA)"

# --- the paste's claims (verbatim, for the verdict table) --------------------
PASTE_CLAIMS = (
    ("Envelope material should be metallized BoPET / Mylar / Cymylar",
     "structural"),
    ("The film must be inelastic and ~1/1000 inch thick", "structural"),
    ("Yokohama 32in dry weight ~48.6 g", "REAL (matches our measurement)"),
    ("Yokohama 32in costs ~$25 / ~$250 per 10-pack", "UNVERIFIED"),
    ("Yokohama volume ~0.27-0.50 m3", "INFLATED (ours: 0.24-0.27 m3)"),
    ("Yokohama floats 40,000-45,000 ft", "UNVERIFIED"),
    ("Clear Cymylar floats 35,000-38,000 ft", "UNVERIFIED"),
    ("Clear Cymylar costs $1.50-2.00", "UNVERIFIED"),
    ("Clear Cymylar weighs 15-25 g", "UNVERIFIED"),
    ("Yokohama leak rate ~1/6 of cheap film, 'SBS-13 class'", "UNVERIFIED"),
    ("SBS-13 costs ~$165", "UNVERIFIED"),
    ("'36-inch to 60-inch' Yokohama-class foil envelopes exist",
     "FABRICATED (Yokohama range is 7-32in)"),
    ("Three layers make cheap film less reliable", "modelling claim"),
)


def non_payload_g(env: Envelope) -> float:
    return env.mass_g + GAS_HE_G + ATTACHMENTS_G


def envelope_share(env: Envelope) -> float:
    """Fraction of non-payload mass that is the envelope itself."""
    return env.mass_g / non_payload_g(env)


def cost_per_gram_of_envelope(env: Envelope) -> float | None:
    if env.cost_usd is None:
        return None
    return env.cost_usd / env.mass_g


def cluster_non_payload_g(n: int, envelope_mass_g: float) -> float:
    """n envelopes, each retaining its dry mass (the paste's dead-weight point)."""
    return n * envelope_mass_g + GAS_HE_G + ATTACHMENTS_G


def cluster_is_feasible(n: int, envelope_mass_g: float,
                        ceiling: float = COMMUNITY_PACKAGE_CEILING_G) -> bool:
    return cluster_non_payload_g(n, envelope_mass_g) < ceiling


def free_lift_needed_for_cluster(n: int, envelope_mass_g: float) -> float:
    """Extra lift required to carry n-1 ADDITIONAL envelopes' dry mass."""
    return (n - 1) * envelope_mass_g


def main() -> int:
    print("=" * 78)
    print("ENVELOPE-MATERIAL GAP ANALYSIS")
    print("=" * 78)
    print(f"payload {PAYLOAD_G} g + free lift {FREE_LIFT_G} g | helium {GAS_HE_G} g | "
          f"attachments {ATTACHMENTS_G} g")

    print()
    print("-- 1. the repo's measured envelope set --------------------------------")
    print(f"{'envelope':<32}{'mass':>7}{'volume':>9}{'cost':>8}{'share':>8}")
    print("-" * 78)
    for e in OUR_ENVELOPES:
        vol = f"{e.volume_l:.0f} L" if e.volume_l else "-"
        cost = f"${e.cost_usd:.2f}" if e.cost_usd else "-"
        print(f"{e.name:<32}{e.mass_g:>6.1f}g{vol:>9}{cost:>8}{envelope_share(e)*100:>7.0f}%")
    print("-" * 78)
    print("'share' = envelope as a fraction of total NON-PAYLOAD mass.")

    print()
    print("-- 2. the design is ENVELOPE-MASS-dominated, not cost-dominated --------")
    y = OUR_ENVELOPES[0]
    cpg = cost_per_gram_of_envelope(y)
    print(f"  {y.name}: {envelope_share(y)*100:.0f}% of non-payload mass is the envelope")
    print(f"  at ${y.cost_usd:.2f} that is ${cpg:.2f} per gram of envelope")
    print("  -> we buy ONE envelope, once. Cost is a rounding error; mass and leak")
    print("     rate decide whether the flight lasts a day or a month.")

    print()
    print("-- 3. the paste's cost argument at OUR volume --------------------------")
    cheap = OUR_ENVELOPES[4]
    y_cost, c_cost = y.cost_usd, cheap.cost_usd
    if y_cost is None or c_cost is None:
        raise AssertionError("cost comparison needs both costs present")
    delta = y_cost - c_cost
    print(f"  paste: 'five budget balloons < $10, a Yokohama hurts at $25'")
    print(f"  ours : ONE flight, one envelope. Delta ${y_cost:.2f} -> ${c_cost:.2f} = ${delta:.2f}")
    print(f"  = ${delta/y.mass_g:.2f} per gram of envelope mass. Not a tradeoff.")

    print()
    print("-- 4. the paste's own rationale contradicts its own pick -------------")
    print("  it asserts the envelope must be INELASTIC ~1/1000 in foil,")
    print("  then recommends Yokohama -- which the MANUFACTURER describes as")
    print("  'Nylon, Polyethylene', a laminate DESIGNED TO STRETCH (repo MFR read).")
    print("  Opposite mechanical regimes; its rationale does not support its pick.")

    print()
    print("-- 5. multi-layer: the dead-weight arithmetic -------------------------")
    print(f"  free-lift allowance is {FREE_LIFT_G} g. Each extra envelope adds its DRY mass.")
    print(f"{'n':>3}{'envelope dry':>14}{'non-payload':>13}{'extra lift':>12}  verdict")
    print("-" * 78)
    for n in (1, 2, 3):
        dry = n * y.mass_g
        npg = cluster_non_payload_g(n, y.mass_g)
        extra = free_lift_needed_for_cluster(n, y.mass_g)
        print(f"{n:>3}{dry:>13.1f}g{npg:>12.2f}g{extra:>11.1f}g  "
              f"{'FEASIBLE' if cluster_is_feasible(n, y.mass_g) else 'EXCEEDS 85 g ceiling'}")
    print("-" * 78)
    print(f"  a SECOND envelope costs {y.mass_g} g against a {FREE_LIFT_G} g free-lift")
    print(f"  allowance -- {y.mass_g/FREE_LIFT_G:.1f}x more than the allowance itself.")

    print()
    print("-- 6. claim verdicts (ours vs the paste) ------------------------------")
    for claim, verdict in PASTE_CLAIMS:
        print(f"  [{verdict:>44}] {claim}")

    print()
    print("-- 7. the gap, stated plainly ----------------------------------------")
    print("  The paste's TOP recommendation is 'use a high-grade low-permeability")
    print("  envelope (Yokohama/SBS-13 class), not cheap film'. That is what this")
    print("  repo already flies. There is NO ACTION to take on the envelope.")
    print("  Its one substantive contribution -- that redundancy on cheap film")
    print("  backfires because a failed envelope keeps its dry mass -- agrees with")
    print("  our own arithmetic above, and we are not on cheap film anyway.")
    print()
    print("  TODO(unverified): every cost/altitude figure the paste gives. None is")
    print("  needed for the decision, because the decision does not depend on them.")

    print()
    print("-- 8. the second paste: the 20 g / jurisdiction question --------------")
    print(f"  paste cited {PASTE_CITED_JURISDICTION}")
    print(f"  our law    {OUR_JURISDICTION}")
    print(f"  German balloon de-minimis: {GERMAN_BALLOON_DE_MINIMIS_G}  "
          f"-> the '20 g rule' does not exist for our launch")
    print(f"  the real figure: {GERMAN_ATC_DE_MINIMIS_G:.0f} g, {GERMAN_ATC_INSTRUMENT}")
    print(f"  counts: {ATC_THRESHOLD_COUNTS}")
    y_plus = y.mass_g + ATTACHMENTS_G
    print()
    print("-- 9. the reliability verdict (consultant, NIST + Monte-Carlo) ---------")
    print("  the paste's Markov framing: state space {n..0} is a legitimate absorbing")
    print("  chain, but the HOLDING TIMES are non-exponential -> correct name is a")
    print("  SEMI-MARKOV process. Fix = phase-type/Coxian expansion (age -> states).")
    print("  'Markov chains assume exponential' is right for CTMC, FALSE for discrete-time.")
    print("  The dead-weight point is a REWARD/drift claim, not a Markov claim.")
    print()
    print(f"  backfire boundary m* = (2B-P)/3 with OUR hardware:")
    print(f"    B (gross lift) = {B_GROSS_G:.1f} g   m = {M_YOKOHAMA_G:.1f} g   "
          f"m* = {backfire_boundary_g():.2f} g")
    print(f"    in backfire regime: {in_backfire_regime()}  "
          f"({'m > m* -- a 3rd envelope IS net-harmful' if in_backfire_regime() else 'm < m*'})")
    print("  -> the consultant's formula CONFIRMS our n=2/n=3 infeasibility, for OUR")
    print("     hardware, on grounds independent of the mass-allowance argument.")
    print()
    print("  the paste's own hypothetical (m=18 g, B=110 g -> m*=65 g) is NOT in the")
    print("  backfire regime, so its 'triple makes cheap film less reliable' claim is")
    print(f"  FALSE for its own numbers. Its real cause would be SIZING or COMMON MODE:")
    print(f"    {COMMON_MODE_NOTE}")
    print()
    print(f"  -> the paste says the envelope is EXCLUDED; our law counts it. Our design")
    print(f"     passes anyway ({y_plus:.1f} g of {GERMAN_ATC_DE_MINIMIS_G:.0f} g), but for a")
    print(f"     different reason, under a different instrument, counting a different quantity.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

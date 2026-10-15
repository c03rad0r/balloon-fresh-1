# ADR-117 — The wing airframe is a bought XPS/Depron sheet, end-mounted, 3 mm first build

- **Status:** **Accepted by operator** (Felix, 2026-10-15): *"yes please lock this decision in
  and merge it to the default branch with your reasoning."*
- **Date:** 2026-10-15
- **Decision owner:** Felix (operator)
- **Author:** balloon-hermes (manager CW)
- **Related:** ADR-049 (wing architecture — the spine-and-ribs recommendation this record
  narrows), ADR-052 (cell mounting, end-only — **binding** here), ADR-046 (wing↔hub interface —
  **re-opened** by removing the board), ADR-051 (release/cutdown), ADR-053 (per-cell bypass).
- **Extends the operator's plan** stated 2026-10-15: *"I intend to remove the circuit board from
  the equation and to fly just the solar panels attached to styrofoam."*
- **Evidence:** `docs/analysis/foam_airframe_selection.py` +
  `docs/analysis/FOAM-AIRFRAME-SELECTION.md`.
  Reproduce: `python3 docs/analysis/foam_airframe_selection.py`
  Tests: `tests/test_foam_airframe_selection.py` (11 cases).

---

## Context

The operator asked which foam to buy, and the question is not answered by density. Two
requirements pull in opposite directions on the **same** variable, thickness:

| requirement | scaling | prefers |
|---|---|---|
| **mass** | areal mg/cm² = `0.1 × ρ × t` — **linear** in thickness | thin, low density |
| **stiffness** | bending stiffness `EI ∝ E × t³` — **cubic** in thickness | thick |

Because areal mass grows *linearly* while stiffness grows *cubically*, a soft foam that is thick
can beat a stiff foam that is thin **on mass, at equal stiffness**. That is the finding the
decision rests on, and it is the opposite of the intuitive "buy the stiffer foam" reading.

### The orientation decides which stiffness matters — and it was recorded inconsistently

ADR-049 §Decision builds each wing as **three LARGE cells in series, in a VERTICAL plane** (a
blade). So:

- **gravity and the vertical burst shock act IN-PLANE** → bending about the **strong** axis;
- **only lateral load** (gust, handling, deployment) bends about the **weak** axis.

An earlier version of the model computed only out-of-plane and therefore made foam look
unusable at any sane thickness. Both axes are now computed, and they differ by orders of
magnitude:

| EPS 3 mm, 40 g | tip deflection |
|---|---|
| in-plane (gravity / burst shock) | **0.58 mm** — fine |
| out-of-plane (lateral) | 486 mm — unusable |

**So gravity is not the binding constraint; lateral load and handling are.** `docs/ADR-049`
(row *Wing plane orientation*) and `WING-TO-HUB-SOCKET-SPEC.md` §1 were recorded as asserting
**vertical** vs **horizontal**; ADR-049's **vertical** is the governing value used here.

## Decision

> **Buy a sheet of XPS ("Depron"-class) foam. Build the first wing at 3 mm. The cells are
> attached at their ENDS ONLY. Do not build a full-area FR4 carrier. Do not laminate the cells
> to the foam.**

### Why 3 mm first

- At 3 mm the wing is **5.54 g** (carrier 1.39 g + 3 measured cells 4.146 g) against the
  repo's **19.81 g** for a full-area 0.6 mm FR4 carrier on the same 167.1 × 86.8 mm arm.
- 3 mm is the **cheap, universally available, RC-standard** thickness; it is the sheet you can
  have in days and cut with a hobby knife.
- The stiffness requirement that would force 6 mm applies to the **out-of-plane** load case,
  which is currently **not characterised** — we do not have a lateral load number to size
  against. Buying the thin sheet first means the *first* build tests the mass budget, which is
  the number we can actually compute, before we spend mass on stiffness we cannot yet justify.
- **Both thicknesses are A/B-testable from one purchase** if the sheet is bought in one
  thickness and the same vendor stocks both — the fallback is 6 mm, which is **1.5× stiffer
  out-of-plane than the current FR4** at **5.6× less carrier mass**.

### Why XPS/Depron and not EPS

EPS is the lighter carrier at equal stiffness (7.6 mm needed, 11 mg/cm², carrier 1.64 g vs XPS
5.2 mm / 17 mg/cm² / 2.43 g). XPS is chosen anyway for the **first** build on handling and
availability, not on mass:

| | EPS (Styrofoam / foam plate) | XPS (Depron / Styrodur) |
|---|---|---|
| bead structure | **fused beads**, open between them | **closed cell**, continuous skin |
| cut quality | crumbles, beads tear out | clean knife cut, holds an edge |
| thin sheets | rare below ~10 mm | **standard at 2–6 mm** |
| section stiffness | lower per mm | higher per mm |

**The vacuum question decides this in the long run, and it is NOT settled.** Both are polystyrene
so CTE and temperature behaviour match, but their *void* behaviour differs: a closed cell holds
~1 atm inside, while bead-fused EPS vents through the bead boundaries. At pico-balloon float
(~0.19 atm ambient, ~81 kPa differential) the closed cell sees the full differential. ADR-052
§Open-items records this honestly: *"I found no balloon-world evidence either way on
void-cracking. I am not borrowing the CubeSat conclusion."* **XPS is not chosen because it is
proven in vacuum — it is not — but because it is the standard airframe sheet the community
already builds with (NIBBB foam plate, KC9IKB Styrofoam airframe), and it is the one that
survives handling.**

## Binding constraints (ADR-052)

> **Each cell is attached at its two ends only, and is otherwise free to move. There is no
> adhesive bond between a cell face and a substrate, and no full-face lamination.**

The rationale is **thermal, not vacuum**: differential contraction between the assembly
temperature and the flight cold can crack a cell. KC9IKB, verbatim: *"Some people glue their
cells to the airframe. I don't do this because of the possibility that the temperature change
between the assembly area and the cold at 40,000 feet + may crack a cell."*

**Laminating the panel to the foam is therefore not an available option.**

## Consequences

1. **The wing↔hub interface re-opens and must be designed WITH the release, not after it.**
   ADR-046 §2.1 fixes the wing tab as a **9.0 mm, 4-land, single-edge tab** with a soldered land
   row, and the hub is routed against it. A foam wing has no tab. The 4-pin soldered lands and
   the `SOLAR_P`/`SOLAR_N`/`GND` row go away with the board, so the keeper/slip-fit and the
   electrical interface are now the **same** design problem. Sequence them together.
2. **The bypass `D_BP` position is unaffected** — it is **hub-side** and stays valid.
3. **The mechanical-release force target follows the wing mass.** The keeper's lower bound is
   `wing mass × 10 g × 1.5` (ADR-051):

   | build | wing mass | ×1.5 lower bound |
   |---|---|---|
   | repo estimate (FR4 spine+ribs) | 3.212 g | 472 mN |
   | **cells + 3 mm XPS (this ADR)** | **5.54 g** | **815 mN** |
   | cells + 6 mm XPS (fallback) | 6.93 g | 1020 mN |

   The target is therefore **~815 mN, not ~471 mN** — 73 % higher than the estimate it
   replaces, in the conservative direction for a joint that must not open in flight.
4. **ADR-049's spine-and-ribs recommendation is narrowed, not overturned.** It remains the
   answer for a **stiff** wing; this record adds that a full-area foam carrier is lighter than
   both FR4 options, and that the FR4 carrier's stiffness is not currently *required* by any
   characterised load case.

## Open items (all `TODO(unverified)`)

1. **Vacuum.** Does a closed cell survive ~81 kPa differential, or do cells rupture / the sheet
   deform? No balloon-world evidence found either way (ADR-052 §Open-items). **This is the
   single most important unknown for this decision.**
2. **Out-of-plane load case is not characterised.** The stiffness requirement is therefore not
   sized against a number. Handling dominates and is unmeasured.
3. **UV / degradation** over the flight.
4. **Outgassing** versus the electronics.
5. **The specific sheet's real areal mass.** Weigh it. The class values used here are nominal.
6. **The adhesive mass.** Ends-only keeps it small, but "small" is not a number.

## What would reverse this decision

- A vacuum test showing closed-cell XPS deforms unacceptably at 81 kPa → switch to bead-fused
  EPS (vents) or a perforated/vented variant.
- A measured out-of-plane load requiring more stiffness → 6 mm, or revert to ADR-049 spine+ribs.
- A measured wing mass materially below 5.54 g → the release force target drops back toward the
  original estimate.

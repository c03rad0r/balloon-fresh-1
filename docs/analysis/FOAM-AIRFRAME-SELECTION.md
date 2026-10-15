# Foam airframe selection — which sheet to buy, and why thickness beats density

**Date:** 2026-10-15 · **Feeds:** `docs/adr/117-wing-airframe-foam-selection.md`
**Reproduce:** `python3 docs/analysis/foam_airframe_selection.py`
**Tests:** `tests/test_foam_airframe_selection.py` (11 cases)

Answers the operator's question — *"I don't have the foam yet, which one do you recommend
buying?"* — for a backing plate of **167.1 × 86.8 mm** carrying **3 large cells (4.146 g
measured)** on the wing of a pico balloon.

---

## 0. The answer, in one line

> **Buy XPS ("Depron"-class) sheet, 3 mm for the first build — and buy thickness, not density,
> when you need more stiffness.**

## 1. Why density is the wrong dial

Two requirements act on the **same** variable — thickness — and pull opposite ways:

| requirement | formula | scaling in thickness |
|---|---|---|
| areal mass | `0.1 × ρ[kg/m³] × t[mm]` mg/cm² | **linear** |
| bending stiffness | `E × I`, `I ∝ t³` | **cubic** |

Mass is linear, stiffness is cubic. So **a soft foam made thick can beat a stiff foam made
thin on mass, at equal stiffness.** That is the whole result, and it inverts the intuitive
"buy the stiffer foam" reading.

Getting to FR4 0.6 mm's out-of-plane stiffness for the same arm:

| foam | required t | areal mass | carrier | wing |
|---|---|---|---|---|
| **EPS** (softest) | 7.56 mm | **11 mg/cm²** | **1.64 g** | 5.79 g |
| XPS / Depron | 5.24 mm | 17 mg/cm² | 2.43 g | 6.58 g |
| EPP | 7.11 mm | 21 mg/cm² | 3.10 g | 7.24 g |
| *FR4 0.6 mm (current)* | *0.6 mm* | *108 mg/cm²* | *15.66 g* | *19.81 g* |

**EPS wins on mass at equal stiffness.** It is still not the recommendation — see §3.

## 2. The orientation is the answer, and I had it wrong first

**ADR-049 builds the wing as a VERTICAL blade.** That decides which stiffness matters:

- **gravity and the vertical burst shock act IN-PLANE** — bending about the **strong** axis
- **only lateral load** bends about the **weak** axis

An earlier draft of this model computed **only** out-of-plane and therefore concluded foam was
unusable at any sane thickness. That was wrong, and the error is now a regression test.

| EPS 3 mm, 40 g | tip deflection |
|---|---|
| in-plane (gravity / burst shock) | **0.58 mm** |
| out-of-plane (lateral) | 486 mm |

**Gravity is not the binding constraint. Lateral load, handling and deployment are.**

### Stiffness reference points (tip deflection, mm, under the cells' own mass)

| option | wing g | in-plane 10 g | in-plane 40 g | out-plane 10 g | out-plane 40 g |
|---|---|---|---|---|---|
| EPS 3 mm | 4.80 | 0.15 | 0.58 | 121.4 | 485.7 |
| EPS 6 mm | 5.45 | 0.07 | 0.29 | 15.2 | 60.7 |
| XPS 3 mm | 5.54 | 0.05 | 0.19 | 40.5 | 161.9 |
| **XPS 6 mm** | **6.93** | 0.02 | 0.10 | **5.1** | **20.2** |
| PMI 6 mm | 8.67 | 0.01 | 0.06 | 2.9 | 11.7 |
| balsa 3 mm | 8.93 | 0.00 | 0.00 | 0.4 | 1.6 |
| *FR4 0.6 mm (current)* | *19.81* | *0.00* | *0.00* | *7.6* | *30.4* |

**XPS 6 mm beats the current FR4 on both axes**: 5.6× lighter carrier **and** 1.5× stiffer
out-of-plane.

## 3. Why XPS for the first build, when EPS is lighter

| | EPS (Styrofoam, foam plate) | XPS (Depron, Styrodur) |
|---|---|---|
| structure | fused beads, **open between beads** | **closed cell**, continuous skin |
| knife cut | crumbles, beads tear out | clean, holds an edge |
| thin sheet availability | rare below ~10 mm | **standard at 2–6 mm** |
| section stiffness per mm | lower | higher |

Two reasons, and neither is mass:

1. **Handling.** A 3 mm EPS sheet crumbles at the edge; XPS cuts clean and keeps a straight
   leading edge. This wing is hand-built.
2. **It is the sheet that exists in 2–6 mm.** EPS thin sheet is not a stocked product in the
   sizes needed; the NIBBB precedent uses a **disposable foam plate**, which is a fixed
   thickness nobody specifies.

**But the vacuum question may decide this in the long run, and it is NOT settled.** Both are
polystyrene, so CTE and temperature behaviour match. Their *void* behaviour differs:

- **closed cell (XPS)** holds ~1 atm inside → at float the cell sees the full **~81 kPa**
  differential
- **bead-fused (EPS)** vents through the bead boundaries

ADR-052 §Open-items states this honestly: *"I found no balloon-world evidence either way on
void-cracking. I am not borrowing the CubeSat conclusion."* The CubeSat analogue is rejected on
the numbers: AlbertaSat's regime is <10⁻⁶ Torr against ~1.9×10⁴ Pa at 12 km — a pressure ratio
of ≈1.4×10⁸, and a different gas inventory and thermal-cycle count.

**XPS is not chosen because it is proven in vacuum. It is not proven.** It is chosen because it
is the standard airframe sheet and the one that survives being built by hand. **Vacuum is the
open item most likely to reverse this.**

## 4. The force target this creates

The keeper's lower bound is `wing mass × 10 g × 1.5` (ADR-051):

| build | wing mass | ×1.5 lower bound |
|---|---|---|
| repo estimate (FR4 spine+ribs) | 3.212 g | 472 mN |
| **cells + 3 mm XPS (first build)** | **5.54 g** | **815 mN** |
| cells + 6 mm XPS (fallback) | 6.93 g | 1020 mN |

**~815 mN, not ~471 mN** — 73 % higher. Conservative for a joint that must not open in flight.

## 5. What buying a sheet does NOT settle

| open item | why it matters |
|---|---|
| **closed cell at 81 kPa** | could deform or rupture; the decision's biggest unknown |
| **out-of-plane load case** | the stiffness requirement is sized against *handling*, which is unmeasured |
| **UV over the flight** | polystyrene degrades; no test in the repo |
| **outgassing** | versus the electronics |
| **the real areal mass of *your* sheet** | class values here are nominal — weigh it |
| **adhesive mass** | ends-only keeps it small; "small" is not a number |

## 6. Method and honesty notes

- Material property values are **nominal class values** used to *rank* the classes, not
  datasheet values for a specific sheet. Every one is marked as such in the script's `FOAMS`
  table. The number that matters for the build is the **areal mass of the sheet you buy**,
  which is one weighing.
- The `0.1 × ρ × t` mg/cm² identity is pinned by test.
- The two failure modes this model has already had — **out-of-plane-only** (which made foam look
  hopeless) and **claiming the stiffer foam is lighter** — are both regression tests.
- The wing↔hub interface consequence is **not** a mass question and is recorded in the ADR:
  removing the board removes ADR-046 §2.1's 9.0 mm 4-land tab, so the release and the electrical
  interface must be designed together.

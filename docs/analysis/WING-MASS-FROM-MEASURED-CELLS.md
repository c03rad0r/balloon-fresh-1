# Wing mass derived from the operator's own weighings

**Date:** 2026-10-14 · **Question:** *"Can you derive the wing mass from the weight data I already
provided?"*
**Reproduce:** `python3 docs/analysis/wing_mass_from_measured_cells.py [--foam 15 3]`

## 0. Answer in two parts — and the split matters

| Part | Derivable from your readings? | Why |
|---|---|---|
| **The cells** | **YES — exact** | You weighed the cells. Cells/wing × per-cell mass is arithmetic. |
| **The carrier** | **NO — bounded only** | You weighed cells and an envelope. **No carrier was ever on the scale.** |

Presenting the carrier as "derived" would be the same defect class as the BAT54 part name and the
"3.2 g wing": a number that *looks* sourced and is not. So it is given as a **bound**, with the
material densities named.

**But the carrier bound is the interesting result — see §2.** Your plan is **lighter than the
configurations the repo has been costing**, and it is also the pattern the repo already records as
the community-proven one.

---

## 1. The cells — exact, from your scale

Your readings: single large **1.382 g**, 10-pack mean **1.4040 g** (1.6 % apart);
single small **0.440 g**, 10-pack mean **0.4462 g** (1.4 % apart).

ADR-049 fixes the cell count, so the cell term follows directly:

| Configuration | Cells/wing | Per wing | Array (4 wings) | Solder joints/wing |
|---|---|---|---|---|
| **Large cells (ADR-049 preferred)** | 3 | **4.1460 g** | **16.5840 g** | 3 |
| Small cells (fallback) | 9 | **3.9600 g** | **15.8400 g** | 9 |

- **Per-wing difference: +0.186 g (+4.7 %)** in favour of small — **negligible**.
- **Array difference: +0.744 g** — also negligible.
- **But large cells need 3× fewer solder joints per wing.** That, not mass, is the deciding
  argument, and it agrees with ADR-049.

**Cross-check:** against the repo's *estimate* of **0.5006 g** per small cell, your measured
0.440 g is **12.1 % lighter**. The repo's per-wing totals are therefore stale in one direction
(they over-count the cells) — they should be recomputed, not treated as a floor.

---

## 2. The carrier — and why your plan beats what the repo was costing

The carrier is the **structural backing** the cells sit on. Two reference points, both cited from
the repo:

- **0.6 mm FR4 = 127.6 mg/cm²** (ADR-049, `docs/analysis/wing-mass-shape.md`) — and ADR-049's own
  verdict is that it is **2.61× heavier per unit area than the silicon it carries**, which is why
  the full-area FR4 carrier was **REJECTED**.
- **0.21 mm silicon cell = 48.9 mg/cm²** — for comparison only.

Using ADR-049's recommended large-cell arm (**167.1 × 86.8 mm = 145.04 cm²**, carrying 3 cells =
91.80 cm², leaving **53.24 cm² = 37 % of the arm bare**):

| Backing (full area of the same arm) | mg/cm² | Carrier g/wing | Wing total g |
|---|---|---|---|
| **EPS 15 kg/m³, 2 mm** | 3.00 | **0.435** | **4.581** |
| **EPS 15 kg/m³, 3 mm** | 4.50 | **0.653** | **4.799** |
| EPS 20 kg/m³, 3 mm | 6.00 | 0.870 | 5.016 |
| XPS/Depron 32 kg/m³, 3 mm | 9.60 | 1.392 | 5.538 |
| XPS/Depron 32 kg/m³, 6 mm | 19.20 | 2.785 | 6.931 |
| *FR4 0.6 mm (repo's REJECTED option)* | *127.6* | *18.508* | *22.654* |

**Foam is 28× lighter per unit area than 0.6 mm FR4 — and 10.9× lighter per unit area than the
silicon it carries.** That inversion is the whole point: with foam, the carrier stops being the
dominant term.

### 2.1 It also beats the repo's *recommended* option

The repo's recommended build is **spine + ribs FR4** (option b), at **1.620 g** of FR4 for the
30.69 cm² cell court. Scaled by area to the large-cell arm that is **~2.37 g**. Against that:

| Carrier | Mass | Covers |
|---|---|---|
| spine + ribs FR4 (repo option b, scaled) | ~2.37 g | the cell court only |
| **EPS 15 kg/m³, 3 mm (full area)** | **0.653 g** | **the whole 145 cm² arm** |

So the foam backing is **~3.6× lighter while covering 4.7× the area.** ADR-049 rejected the
*full-area FR4* carrier on mass and chose spine+ribs — but a **full-area foam** carrier is lighter
than either, which is an option ADR-049 **never costed**.

### 2.2 And it is the pattern the repo already records as proven

This is not a novel idea — **`docs/adr/052-cell-mounting-end-only.md` §1 already documents your
plan as a community pattern**:

| Builder | Attachment | Substrate |
|---|---|---|
| **NIBBB** "Standard Solar Array" | **glue the cell corners** to a foam plate | **foam plate frame** |
| **KC9IKB** (John Ruthroff) | **epoxy the array ends only**; cells float | **Styrofoam airframe** |

ADR-052 §2.1 then *adopts* that pattern for our cells: **mount the cells by their ends only**, no
adhesive bond to a face, no full-face lamination. Rationale, verbatim from KC9IKB:

> *"the temperature change between the assembly area and the cold at 40,000 feet + may crack a
> cell. I just attach each end of the solar array to the airframe with epoxy, so the cells can
> 'float' and contract a certain amount."*

**So "solar panels attached to styrofoam" is not a deviation from the design — it is closer to what
ADR-052 decided than the FR4 spine-and-ribs build is.** The board was carrying structure that the
cells never needed.

---

## 3. What removing the board also removes

You did not only save mass. The wing board carried:

| Removed with the board | Consequence |
|---|---|
| the 4-pin soldered tab lands | **no electrical interface** — the keeper/slip-fit now has to land on the cells directly, or on a new small carrier |
| the `SOLAR_P`/`SOLAR_N`/`GND` land row | the hub's 4-land geometry (`docs/WING-TO-HUB-SOCKET-SPEC.md`) no longer matches anything on the wing |
| rigidity (0.6 mm FR4 plate) | see §4 — this is the open risk |
| the wing's own bypass-diode position | the bypass `D_BP` is **hub-side** and stays valid |

**The interface change is the one that touches a landed ADR.** ADR-046 §2.1 fixes the wing tab as a
**9.0 mm, 4-land, single-edge tab**; the hub is routed against it. A foam wing has no tab. So this
is **not** a free swap — it re-opens the wing↔hub interface, which is exactly the joint the
keeper/slip-fit work was going to redesign anyway. **They should be designed together, not
sequentially.**

---

## 4. What is still unknown (all `TODO(unverified)`)

1. **Stiffness.** ADR-049 chose spine+ribs for a **179 mm cantilever arm**. Foam is far less stiff
   than a 0.6 mm FR4 plate. **No analysis in the repo covers a foam arm's deflection or its
   behaviour at the assumed 40 g load.** This is the main risk of the plan and it is *not* a mass
   question.
2. **Interconnect.** Bus ribbon / solder / 30 AWG wiring mass — never weighed.
3. **Adhesive.** The glue or epoxy holding cells to foam — never weighed. ADR-052 says ends only,
   which keeps this small, but "small" is not a number.
4. **Foam behaviour at −60 °C in vacuum.** EPS outgasses; no chamber test exists in the repo.
5. **Which foam.** The table uses generic densities (15/20/32 kg/m³). Your actual plate's density
   and thickness are the two numbers that pick the row.

---

## 5. What this changes in the pending work

- **Measurement A ("weigh one real wing") is now partly answered.** You cannot weigh a wing that
  does not exist yet — but the **cell term is closed** (§1) and the **carrier term is bounded**
  (§2). What remains is the *interconnect + adhesive + fastener* term, which is only weighable
  once a build exists. **So A is no longer blocking the mass budget** — it is blocking the
  *verification* of the mass budget.
- **The force window can now be run on a real number.** Use the wing total from §2 for your chosen
  foam: e.g. **4.80 g** (EPS 3 mm + large cells) instead of the repo's 3.2 g estimate —
  `python3 docs/analysis/wing_release_force_window.py 4.80`.
- **ADR-049 and ADR-052 need a line each** recording that a full-area foam carrier was costed and
  is lighter than both FR4 options. That is a design-record change, not a comment.

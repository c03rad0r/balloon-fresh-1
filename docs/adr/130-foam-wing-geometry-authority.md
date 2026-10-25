# ADR-130 — The FOAM wing is the wing of record; the wing has no PCB, and its geometry is parametric

> Numbered **130** on 2026-10-25. Verified before writing with this repo's own
> allocator: `python3 scripts/adr_next_number.py --number 130` → `130` (exit 0) and
> `--path docs/adr/130-foam-wing-geometry-authority.md` → `130` (exit 0), i.e. the
> number is free and no file claims it. Cross-checked across **all refs**:
> `git log --all --name-only --pretty=format: -- 'docs/adr/130*'` returns nothing,
> with 303 remote heads inspected.

- **Status:** **Proposed** — the design direction is worker-derivable; the operator
  corrects pass 2 (standing authority, AGENTS.md §"STANDING AUTHORITY").
- **Date:** 2026-10-25
- **Author:** balloon-hermes (manager CW), branch `feat/foam-wing-3d`.
- **Decision owner for the *airframe*:** already decided — Felix, 2026-10-15
  (ADR-117, "Accepted by operator"). This record **executes** that decision's
  geometry side and resolves two records that contradicted it.
- **Supersedes (carrier part only):** ADR-049 §Decision — the **spine-and-ribs FR4
  frame** is no longer the wing carrier. ADR-049's **cell class, plane orientation
  and end-mount constraints stand.**
- **Amends:** ADR-046 §2.1/§3 (the wing tab) — **re-opened, not deleted**.
- **Composes with:** ADR-117 (foam airframe), ADR-065 (double-sided cells),
  ADR-052 (end-only mount — **binding**), ADR-063 (board/array decoupling).
- **Evidence:** `docs/analysis/FOAM-WING-GEOMETRY-AND-MASS.md`,
  `docs/analysis/foam_wing_geometry.py`, `docs/analysis/render_foam_wing.py`,
  `docs/fab/wing-3d/*.png`.
  Reproduce: `python3 docs/analysis/foam_wing_geometry.py` and
  `python3 docs/analysis/render_foam_wing.py --out docs/fab/wing-3d`.
- **No hardware is ordered, no board generated, no BOM changed.** Design work only.

---

## 0. The decision, in one paragraph

**A wing consists of a bought foam sheet carrying cells attached at their ends
only. There is no wing PCB, and therefore no `kicad_pcb` to render — the wing's
geometry of record is parametric, in `foam_wing_geometry.py`, and both the VRML
models and the PNG renders are generated from it.** The FR4 spine-and-ribs frame
of ADR-049 is retired as the wing carrier (ADR-117 already replaced it on mass
grounds; this record removes the last record that still showed it at the wing).

---

## 1. Why this record is needed — the live contradiction it closes

The repo carried a **structural contradiction that named no winner** (the defect
class AGENTS.md calls out):

- **ADR-049** (Proposed) builds a wing around a **spine-and-ribs FR4 frame**.
- **ADR-117** (Accepted by operator, 2026-10-15) says the airframe **is a bought
  XPS/Depron sheet** and *"do not build a full-area FR4 carrier."*
- **ADR-065** (Accepted) skeletonises the **wing carrier** and double-sides it —
  i.e. it still assumes an FR4 wing carrier exists.

ADR-117 narrows ADR-049 ("narrowed, not overturned", its own words) but **never
says the wing carrier ceases to be a PCB**, and never touches ADR-065. The
practical consequence measured on 2026-10-25: **the newest wing render in the repo
still shows the retired board**, because the wing stopped being a PCB and nothing
replaced its geometry. That is what the operator saw and objected to.

## 2. Decision

### D1 — The foam airframe is the wing, and the wing has **no PCB**

The wing's carrier is the bought sheet (ADR-117). The 4-pin soldered **tab lands,
the `SOLAR_P`/`SOLAR_N`/`GND` land row, the FR4 plate and the wing's own diode
position are gone.** `wing_board_v9.kicad_pcb` is **frozen history** — not a design
of record, not to be re-spun, not to be rendered as "the wing".

### D2 — The wing's geometry of record is **parametric**, and renders come from it

`docs/analysis/foam_wing_geometry.py` owns the wing's dimensions; it emits both
VRML models and (via `render_foam_wing.py`) PNG renders. **A wing render that does
not come from this file, or from a successor, is stale by definition.** Every
dimension is cited in the module; anything the repo lacks prints `TODO(unverified)`.

### D3 — Two constructions, one cell-count option, all costed

Per `FOAM-WING-GEOMETRY-AND-MASS.md` §1/§2: **A** full-area foam plate (lightest),
**B** foam cut to a spine (only if the plate's out-of-plane behaviour is judged
unacceptable), **C** double-sided cells (ADR-065) composed onto either. Mass per
wing, subtraction shown: **EPS 3 mm single-sided 5.25 g**, **XPS 3 mm 5.99 g**,
**XPS 6 mm 7.38 g**; double-sided roughly **+4.15 g** (six cells instead of three).
The retired FR4 carrier was **20.26 g**.

### D4 — Thickness is the stiffness dial; 3 mm is the **first** build, not a verdict

Out-of-plane deflection is the binding case (in-plane gravity/burst is harmless at
0.58 mm @ 40 g; lateral is 486 mm @ 40 g and **unmeasured**). 3 mm tests the mass
budget, which is computable, before mass is spent on stiffness that no
characterised load case yet requires. The 6 mm fallback is **1.5× stiffer than the
retired FR4 at 5.6× less carrier mass** and is stocked by the same DE vendor.

### D5 — **OPEN** — the wing↔hub interface is re-opened and must be designed once

Removing the board removes the tab ADR-046 §2.1 fixes (9.0 mm, 4-land, single
edge) and against which the hub is routed. **A foam wing has no tab**, so the
keep/slip-fit and the electrical interface are **one** problem. **This record does
not solve it** — it sequence-locks it: interface and release are designed together,
not sequentially. **CLOSED by ADR-131** (which keeps the 4-pin row, moves the
mechanical normal force to a carried insert, and sizes the keeper to the measured
wing mass).

### D6 — **OPEN** — "more panels" is bounded by the ARM, not by a board

ADR-063 decoupled board area from array area; applied to the wing, the cell court
is bounded by the **`167.1 × 86.8 mm` arm**, and panels may overhang. The number of
cells a wing can carry is therefore an **arm** limit plus whatever the
redesigned interface (D5) can land. No ceiling is frozen here.

---

## 3. What this changes, record by record

| Record | Disposition | Why |
|---|---|---|
| **ADR-049** (wing architecture) | **carrier part SUPERSEDED**; cell class, vertical plane, end-mount stand | ADR-117 accepted the foam sheet; this record stops ADR-049's FR4 frame being drawn as the wing |
| **ADR-065** (skeletonised double-sided) | **carrier part SUPERSEDED**; double-siding stands as option **C** | it skeletonised an FR4 carrier that no longer exists; the 2× energy argument is unaffected |
| **ADR-117** (foam airframe) | **CONFIRMED and executed** | this record supplies the geometry ADR-117 left implicit |
| **ADR-046** §2.1/§3 (tab) | **RE-OPENED** (D5) | the board carrying the tab is gone |
| **ADR-052** (end-only mount) | **BINDING, unchanged** | it is the reason the cells are not laminated to the foam |
| **ADR-063** (decoupling) | **EXTENDED to the wing** (D6) | the same decoupling bounds the wing's cell court |

## 4. Consequences

**Positive**
- The wing render stops being wrong: geometry now has a parametric source and real
  renders exist (`docs/fab/wing-3d/`), generated from the same numbers as the mass
  table.
- The mass picture is unambiguous: the carrier is no longer the dominant term
  (cells weigh **6.3×** the EPS carrier, versus the board weighing **3.8×** the
  cells on the retired FR4 design).
- A contradiction that named no winner is resolved **without editing the losing
  record's body** — ADR-049/065 are superseded *in part*, explicitly and by field.

**Costs (real, stated)**
- **The interface is now unsolved** (D5). This is the price of removing the board
  and it is the next design deliverable, not a footnote.
- **Out-of-plane stiffness is unquantified** (D4); the first build is deliberately
  a mass test, not a flight article.
- **Double-siding four wings costs ~16.6 g** — most of the corrected ≈42 g payload
  — so "more panels" and "double-sided" compete for the same budget.
- **One more design artefact** (a parametric generator) exists to keep the wing
  drawable, because there is no board to render.

## 5. For future sessions

- **The wing has no PCB. Do not re-spin `wing_board_v9`, and do not render it as
  the wing.** The wing's dimensions live in `docs/analysis/foam_wing_geometry.py`.
- **Next mechanical deliverable: the wing↔hub interface + release, designed
  together** (D5), matching ADR-117 consequence §1. Nothing there is frozen.
- **Before buying foam, weigh the actual sheet** (ADR-117 open item 5) — the class
  densities here are nominal.
- **The lateral load case is the gate.** Until it is measured, 3 mm is a first
  build and every lightness follow-up is deferred.
- Reproduce everything: `python3 docs/analysis/foam_wing_geometry.py` and
  `python3 docs/analysis/render_foam_wing.py --out docs/fab/wing-3d`.

---

*Proposed. No order, no BOM, no board, no fab authorisation. Geometry and mass only.*

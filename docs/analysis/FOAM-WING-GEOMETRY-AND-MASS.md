# Foam wing — geometry, mass, and the two constructions worth building

**STATUS: CONSULTANT ANALYSIS — NOT A DECISION RECORD.** No board, BOM, order or
flight procedure is authorised by this file. Every number is **CITED** to an in-repo
source, **COMPUTED** by `docs/analysis/foam_wing_geometry.py` (run it), or marked
`TODO(unverified)`. Nothing is invented.

- **Date:** 2026-10-25
- **Branch:** `feat/foam-wing-3d`
- **Context:** the operator asked why the last render still showed the cells lying
  flat on the board, and asked for cells mounted on foam with a board that can
  handle a good number of panels.
- **Model:** `python3 docs/analysis/foam_wing_geometry.py` (mass + VRML),
  `python3 docs/analysis/render_foam_wing.py --out docs/fab/wing-3d` (PNGs).
- **Reads with:** ADR-117 (XPS sheet airframe, accepted), ADR-065 (skeletonised
  double-sided), ADR-052 (end-only mount), ADR-049 (the carrier this supersedes),
  ADR-129 D5 (cut channels), ADR-054 (array topology).

---

## 0. Why the previous render was wrong — and it was

The render the operator objected to is of **`wing_board_v9.kicad_pcb`**, which is a
**PCB**. Its cells are laid flat on copper **because v9 IS a board** — there is
nothing mis-drawn. The mistake is that **v9 is the superseded design**: ADR-117
(Accepted by the operator, 2026-10-15) replaced the FR4 carrier with a **bought
XPS/Depron sheet**, and ADR-117's own context quotes the operator:

> *"I intend to remove the circuit board from the equation and to fly just the
> solar panels attached to styrofoam."*

A foam wing **has no `kicad_pcb`**, so `kicad-cli pcb render` has nothing to draw
and the only wing render in the repo stays the retired one. That is the whole
reason the picture looked wrong. This analysis supplies the missing geometry.

**A correction to a prior claim, stated plainly.** An earlier message in this
window asserted that full-area foam was *"the option nobody costed."* **That is
false.** `docs/analysis/WING-MASS-FROM-MEASURED-CELLS.md` §2 already carries the
foam table, ADR-117 already costed and **accepted** it, and `#200` already sourced
the sheet in DE. The proposal was correct in direction but wrong about the record —
the record was ahead of it.

---

## 1. The constructions worth building

Two constructions, both already named by the record, differ only in what carries
the cells:

**Construction A — full-area foam plate (ADR-117).** One sheet cut to
`167.1 × 86.8 mm`; the three cells sit on its face, attached **at their ends only**
(ADR-052). This is the operator's own plan and is the lightest carrier found.

**Construction B — foam as a spine, not a plate.** Keep the foam but cut it to a
spine + end-pads, so it carries the cell ends and not the whole court. This is
ADR-049's spine-and-ribs idea, executed in foam instead of FR4 — it matters only
if the full plate's out-of-plane behaviour (§3) is judged unacceptable, in which
case thickness buys stiffness far cheaper than material choice (ADR-117).

**Construction C** — cells on **both faces** (ADR-065). Not a carrier, a cell
count: 3 → 6 per wing, 2× rotationally-averaged energy, ~2× the joints. It
composes with A or B.

---

## 2. Mass, with the subtraction shown

All per **one wing**. `carrier = areal(ρ,t) × 145.0 cm²`; `areal = 0.1·ρ·t` mg/cm²;
`cells = n × 1.382 g` (operator's own weighed single cell); `mount = 0.15 g/cell`
(NIBBB measured frame+glue+wire+solder, `PANEL-MOUNTING-OFF-BOARD.md` §2).

**Single-sided (3 cells = 4.146 g)**

| option | areal mg/cm² | carrier g | cells g | mount g | TOTAL g |
|---|---:|---:|---:|---:|---:|
| **EPS 3 mm** | 4.5 | **0.653** | 4.146 | 0.45 | **5.249** |
| **XPS 3 mm** (ADR-117 pick) | 9.6 | 1.392 | 4.146 | 0.45 | 5.988 |
| XPS 6 mm (stiffness fallback) | 19.2 | 2.785 | 4.146 | 0.45 | 7.381 |
| EPS 7.56 mm (equal out-of-plane) | 11.3 | 1.645 | 4.146 | 0.45 | 6.241 |
| *FR4 0.6 mm full-area (RETIRED)* | *127.6* | *15.665* | *4.146* | *0.45* | *20.261* |

**Double-sided (6 cells = 8.292 g)** — ADR-065

| option | carrier g | cells g | mount g | TOTAL g |
|---|---:|---:|---:|---:|
| **EPS 3 mm** | 0.653 | 8.292 | 0.90 | **9.845** |
| **XPS 3 mm** | 1.392 | 8.292 | 0.90 | 10.584 |
| XPS 6 mm | 2.785 | 8.292 | 0.90 | 11.977 |

**Against the payload budget.** The corrected payload figure is **≈ 42 g**
(`ALTITUDE-AND-MASS-REQUIREMENTS.md` D10; the file's own ⚠️ says the parts term is
still to be re-measured). Four **single-sided EPS 3 mm** wings = **21.0 g** of
vehicle; four **double-sided** = 39.4 g, which is **more than the whole remaining
payload** — so double-siding the full array is a budget decision, not a free 2×.

**The finding, unchanged from ADR-117 but now with the numbers side by side:** the
carrier stops being the dominant term. On the retired FR4 carrier the board weighed
**3.8×** the silicon; on EPS 3 mm the *cells* weigh **6.3×** the carrier.

---

## 3. The one risk that picks the thickness: out-of-plane, not mass

`foam_airframe_selection.py` measured this and it is the reason ADR-117 chose 3 mm
as a *first* build rather than a final one:

```
EPS 3 mm : in-plane (gravity/burst) 0.58 mm at 40 g  -> fine
           out-of-plane (lateral)  486 mm at 40 g  -> unusable
```

Gravity and the burst shock act **in-plane** on a vertical blade and are harmless.
**Lateral load and handling** bend the weak axis and are the binding case — and
that load is **not characterised** (`TODO(unverified)`). So:

- **3 mm** is right for the **first** build: it tests the mass budget, which is
  computable, before spending mass on stiffness we cannot yet justify.
- If a measured lateral load demands it, buy **6 mm** from the same shop on the
  same order — 1.5× stiffer out-of-plane than the retired FR4 at 5.6× less carrier.

---

## 4. What the operator's second question asks — "a board that handles more panels"

ADR-117's consequence §1 is the answer and it is a **re-opened interface**:
removing the board removes the **4-pin soldered tab lands** (ADR-046 §2.1, a
9.0 mm 4-land single-edge tab) and the `SOLAR_P/SOLAR_N/GND` row. A foam wing has
no tab, so the **keeper/slip-fit and the electrical interface become one design
problem** and must be sequenced together.

**"Handling more panels" is a cell-count and area question, and ADR-063 already
decoupled it:** board area and array area are independent, and panels may overhang.
On the wing that means the cell court is bounded by the **arm**, not by a board —
so a wing can carry as many cells as the `167.1 × 86.8 mm` arm holds, with the
interface redesigned to match. That redesign is **not done here**; it is named.

---

## 5. What this analysis does NOT establish

- **No lateral load case.** §3's risk is sized against nothing; handling dominates
  and is unmeasured. `TODO(unverified)`.
- **No weighed mounting overhead for our build.** 0.15 g/cell is NIBBB's number
  and is used as such, not as ours.
- **No vacuum/cold result.** ADR-117's open items 1 (81 kPa differential) and the
  −60 °C behaviour stand unclosed.
- **No interface design.** §4 names the problem; it does not solve it.
- **No order, no BOM, no fab authorisation.**

---

*Analysis only. Nothing frozen, nothing ordered, no board touched.*

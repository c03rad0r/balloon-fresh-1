# HUMAN TODO — measurements and purchases only the operator can do

**Owner:** Felix (operator) · **Status:** open items below · **Chaser:** cron job
`balloon-human-measurements-nudge` (every 2 days, 10:00)

Two classes of item live here, both of which **cannot be retrieved from the
internet**: things that must be **measured** on real hardware (M-series), and
things that must be **bought** (P-series). Each one blocks a documented decision,
and the value recorded against it is the number the model consumes.

| # | Item | Why it matters | Value |
|---|---|---|---|
| **M1** | Empty balloon mass (as-shipped, the one to fly) | Envelope mass is subtracted from available lift; it dominates the budget (community: 41–49 g vs a 9–22 g payload) | _pending_ |
| **M2** | One 52×19 mm solar cell mass | Array mass = cell mass × count; `wing_mass_model.py` assumes **1.5 g**; earlier budgets assumed 0.8 g — the spread is 6→12 g for 8 cells | _pending_ |
| **M3** | One latex balloon mass, as-flown | Decides float altitude. The "36 in ≈ 25 g" figure was a **model assumption, not a real envelope** — the real 36 in products measure **33–46 g** | _pending_ |

## Purchases (P-series)

| # | Item | Why it matters | Value |
|---|---|---|---|
| **P1** | **XPS/"Depron"-class foam sheet, 3 mm** — one 70 × 100 cm sheet | The wing airframe (ADR-117). Its **density sets the carrier mass** and therefore the wing mass and the cutdown force target | _pending_ |

### P1 — the foam sheet, with the ladder in the same order

**Recommended:** architekturbedarf.de — *Modellbauschaum, weiß ca. 3 mm*, 70 × 100 cm,
**4.85 EUR**
<https://www.architekturbedarf.de/pappe-+-papier/depron-+-modellbauschaum/modellbauschaum-weiss-ca-3-mm>

**The only DE source found that publishes a density: 40 kg/m³** — that number is the
whole point, because the mass budget is `0.1 × ρ × t` mg/cm² and every other vendor
found leaves ρ unstated. One sheet covers all four wings **~9× over**.

**Order the thickness ladder in the SAME purchase.** ADR-117's finding is that
**thickness is the dial** (mass ∝ t, stiffness ∝ t³) — all at the same stated
40 kg/m³, one shipping charge, so the first build can A/B the trade on identical
material:

| thickness | price | areal mass | per wing | sheet |
|---|---|---|---|---|
| 2 mm (B-Ware) | 3.95 EUR | 8.0 mg/cm² | 1.16 g | 70 × 100 cm |
| **3 mm (first build)** | **4.85 EUR** | **12.0 mg/cm²** | **1.74 g** | 70 × 100 cm |
| 4 mm | 4.95 EUR | 16.0 mg/cm² | 2.32 g | 70 × 100 cm |
| 5 mm | 5.90 EUR | 20.0 mg/cm² | 2.91 g | 70 × 100 cm |

*All incl. 19 % VAT, excl. shipping. Full vendor list: `docs/analysis/FOAM-SOURCING-DE.md`.*

**Alternative worth one thought** if the vacuum or handling risk bites: Höllein
**EPP 900 × 600 × 3 mm, 8.95 EUR**, density stated **30 kg/m³** → 1.31 g/wing — the
lightest option with a published density, and EPP does **not shatter**.

**Do not buy:** OBI Qboard / Duschparadies (XPS core but cement+mesh faced — not bare
foam); OBI "Styropor EPS 040" (**"040" is a thermal class, not a density**); genuine
Depron sheets whose pages state **no** density.

### What P1 changes

- **The carrier mass**, and with it the wing mass: 3 mm → 5.54 g/wing vs the repo's
  3.212 g estimate.
- **The cutdown force target**: `wing mass × 10 g × 1.5` → **~815 mN** at 3 mm
  (vs ~471 mN from the estimate). This is the number the keeper/slip-fit must use.
- **The P1 weigh-in feeds M-series form:** weigh the sheet you receive (one wing
  blank is enough) and record it as a line — the ADR's carrier figures are nominal
  **class** values, and the real sheet is the number that closes the budget.

### P1 follow-through that is NOT a purchase

Recorded here so it is not lost: a **vacuum test** of the sheet (does a closed cell
survive the ~81 kPa float differential?) is the one unknown most likely to reverse
ADR-117. A kitchen vacuum container plus a measured deformation is enough to start.

## What each number changes

- **M1** — sets the envelope's own weight in the lift equation. A 20 g error
  moves the float ceiling by roughly a kilometre.
- **M2** — a 0.7 g error × 12 cells ≈ **8.4 g**, i.e. ~1 km of altitude.
- **M3** — this is the number that decides latex vs superpressure. If a real
  36 in latex balloon is ~40 g rather than ~25 g, the latex route loses most of
  its advantage over the nylon/PE laminate from Yokohama.

## How to measure

Kitchen/postal scale, 0.1 g resolution ideally (0.5 g acceptable — the errors
above are all ≥ 0.5 g). Weigh **as-flown**: cut the neck tie, weigh the balloon
alone, weigh one cell with its interconnect, and the latex balloon uninflated.

Record each as a line: `M1 <grams>` — e.g. `M1 47.3`. Send it in the balloon
group and the numbers get folded into
`docs/analysis/wing_mass_model.py` + `ALTITUDE-AND-MASS-REQUIREMENTS.md`.

## Why the model cannot substitute

The repo's own envelope survey says the community's proven long-duration payload
band is **9–22 g** and that the envelope is counted **separately at ~41–49 g**.
Both are *measured* figures from named operators. Any flight plan built on an
assumed envelope mass is a plan built on a guess, and the whole point of the
altitude analysis is to stop guessing.

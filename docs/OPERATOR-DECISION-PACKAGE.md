# OPERATOR DECISION PACKAGE — remaining boards

**Date:** 2026-10-14 · prepared while the operator was unreachable for 8 h
**Scope:** what I completed, what is genuinely blocked, and the decisions only
the operator can make. Every number here is measured or documented; nothing is
estimated silently.

---

## 1. Completed in this window

| Item | State | Commit |
|---|---|---|
| `quote_pcba_sweep` — deterministic browser-free qty sweep, CVM tool | **MERGED to `cvm-service-kit` main** | PR #22, main `b9a50bf` |
| `pcba_plan.py` — board cost planner (log axis, per-part colours, cliffs, selective population) | committed, both remotes | `0cde7731` |
| Model cross-validation against the real JLC page | committed | `84c8e1b4` |
| `plan_from_checklist.py` — module-board planner + base-station cost plan | committed | `389222bc` |
| Masthead **Dispute A resolved** from the manufacturer | committed | `493de636` |

---

## 2. DECISION 1 — Masthead LNA (was Dispute A; now resolved to a choice)

**Resolved fact:** Qorvo's own page states **"0.7 – 6 GHz operational bandwidth"**
for the TQP3M9037. The operator's 0.1 MHz figure is not supported. **433 MHz is
below the specified band.** This is the case ADR-079 flagged.

**Choose one:**

1. **Measure first (recommended).** LiteVNA €166.99 → sweep S21 400–500 MHz on
   the owned part. Keep ADR-079 if usable, recorded as out-of-spec use.
2. **Reopen ADR-079**, select a 433-specified LNA. Removes the risk; costs a new
   part + netlist/link-budget re-run.
3. **Zero-cost:** netlist a 433-specified LNA footprint, keep the TQP3M9037 as a
   **DNP alternative** for the bench comparison. Blocks nothing, defers to
   measurement.

**My recommendation: option 3, then 1.** Option 3 costs one footprint and keeps
both paths alive; option 1 is the only way to answer whether the owned part is
usable anyway. Note the spec question is now **closed without spending anything** —
the VNA is only needed for verification, not for the decision.

---

## 3. DECISION 2 — Shack form factor (Gate 2, hard blocker)

The plan states verbatim: *"Nothing is placed, routed, or ordered until these are
answered."* I will not cross that gate. The five open items:

| # | Decision | Options |
|---|---|---|
| 1 | **Masthead topology** | one shack board + masthead LNA module, **or** split masthead+shack design (ADR-079 INV-1 forces the LNA to the masthead) |
| 2 | **Layer count** | 2-layer (cheaper, harder 433/2.4 GHz co-existence) vs **4-layer** (solid inner ground between bands) |
| 3 | **First-flight population** | full AGC+DSA (qty 2) vs **qty 1 on TX only** (RX then manual/commanded gain) |
| 4 | **TQP3M9037 dispute** | see Decision 1 |
| 5 | **Enclosure** | which enclosure — drives the board outline |

**My recommendation:** split design (1), **4-layer** (2) — the hub board taught us
to lock geometry early and the band-split needs the ground plane — qty-1 TX-only
first flight (3), option 3 above (4). Enclosure (5) is genuinely the operator's
call and I have no basis to recommend one.

**What I can do without you:** nothing that advances the outline. Per your own
rule, form factors are not chosen unilaterally.

---

## 4. Costs — with the costly items separated, as requested

### Hub v9, assembled (parts included)
Parts are **72–86%** of the total. Two real cliffs in qty 5→20: **qty 10** (five
ICs break together, −$2.11/board, ~72% of all the improvement) and **qty 13**
(U.FL, −$0.27/board). Six costly parts, each plotted in its own colour:
MAX-M10S, MS5611, ESP32-S3, SX1280, U.FL ×4, LDO.

**Selective population** (leave costly parts off some boards): order 10 → all 10
populated $338.99 ($33.90/board); none populated $73.68 ($7.37/board). The step
from K=9 to K=10 barely moves because at 10 boards the ICs hit their qty-10
break — so hand-soldering only pays if you populate **≤9**.

### Base-station, from the living checklist
- **Board parts: €278.** **Bench instruments: €292 (51%).** Grand total €570.
- The bench share is the single biggest deferrable item and it is *test equipment,
  not board parts* — the LiteVNA alone is €167.
- 7 required rows have **no verified price** (AD8318, RP2040, bias tee, XR-613,
  unmarked mixer, + 2 deliberate DNP rows). Counted as 0 and named, not absorbed.
- The parser reproduces the checklist's own documented €441.57 to-buy total
  **exactly** — that agreement is what licenses the figures.

---

## 5. Honest corrections to my own earlier work

1. **BAT54W.** I previously "corrected" ×4 → ×1 and dismissed the ×4 as an error.
   Half wrong. **Placement** is ×1 (BOM and CPL agree). **Purchase** is 20 units at
   a 5-board order, because JLC buys Extended parts in a minimum quantity. Both
   numbers are real. The ×4 was a purchase quantity read as a placement quantity.
2. **Model limitation, stated not hidden.** `pcba_plan.py` computes parts cost as
   `placements × unit price`, so for Extended parts at small quantities it
   **understates** cost. Direction known, magnitude measurable per line, not yet
   modelled. The mechanism is recorded as a **hypothesis**, not fact.
3. **Hub curve CSV.** The first derived curve used BAT54W ×4; the BOM-corrected
   figure is $202.33 at qty 5 (not $202.83). ~$0.50/order; shape and cliffs
   unaffected.
4. **SS24.** Committed BOM said `C78573` — stock 0, no price bands, **cannot be
   ordered**. Corrected to `C50645` (stock 777,745). The mapping report had
   recommended this; the BOM now agrees.

---

## 6. Still not measured (so not claimed)

- **JLC per-placement assembly fee** — never captured; only the $25/side setup is
  measured. Computed totals are therefore **lower bounds**; the cliff structure is
  unaffected.
- **The hub's full assembled quantity curve from the page** — the browser run
  reached the Quote & Order tab but the price was never read. The curve you have
  is derived from published break tables, cross-validated to 0.7% at qty 5 and
  **line-by-line to the cent on 10 of 13 lines** at qty 5.

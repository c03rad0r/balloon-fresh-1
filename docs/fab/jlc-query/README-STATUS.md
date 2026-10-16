# Status of the interface drawing in this directory

**`edge-launch-cross-section.svg` / `.png` were generated but must NOT be sent to a fabricator yet.**

## Why it is here and not in the query message

The drawing depicts the **hub-side wing interface**. That geometry is **undecided**:

- `ADR-046 §4.2` recommends **Option A** — the hub's edge carries a routed **0.9 × 6.0 mm slot**, the wing
  tab inserts 6.0 mm **into** it, lands on the slot's faces, fillet loaded in **shear**.
- `hub_board_v9.kicad_pcb` **implements Option B** — no slot, `J_W*` lands on `F.Cu` only, fillet loaded
  in **peel**. Measured with `tracker/hardware/introspect_edge_interface.py`:
  **one Edge.Cuts contour (the 70 × 70 outline), no slot, all `J_W*` pads `F.Cu`.**
- `ADR-046 §4.2.1` (added 2026-10-16) records the disagreement, marks the interface **OPEN**, and notes
  that §4.2's stated reason — that the slot keys the 90° angle — **does not survive the numbers**: the
  slot permits 2.86° of play (8.79 mm of wing-tip movement) against 9.21 mm freehand, a 1.0× improvement.

**A drawing of an undecided interface is worse than no drawing**: it would be read as a specification.
The operator's ruling on 2026-10-16 was to **hold the geometry** until the wing-side lands are frozen
(gap-analysis item **W1**), and to decide only after seeing the trade study.

## What the drawing gets wrong today, and why that is expected

A visual review of it found, correctly:

1. it shows **two boards end-to-end with a solder bridge**, not a tab seated in a slot — **because that is
   what the board implements** (Option B), while the ADR recommends Option A. The drawing was accurate to
   the board and in disagreement with the ADR. Neither document surfaced the conflict.
2. **ENIG on the pad faces does not establish a finish on copper newly exposed by routing** — a real
   fabrication point that must be answered for the *routed edge face*, not the pad.
3. layout: inward-pointing dimension arrows, View B's 4.0 mm drawn as a plain underline, the named 0.9 mm
   slot never drawn, and (in the reviewed render) a misspelled finish abbreviation.

## To unblock it

1. Freeze the wing-side land geometry (**W1**).
2. Decide A or B — inputs: a **peel figure for this joint geometry** (the trade study's crux: below ~1.2×
   knockdown, Option B approaches Option A on capacity), and the **JLCPCB routed-cut-out cost delta**.
3. Rewrite the drawing for the chosen geometry, then **loop: fix → re-render → `ask_astra.py --review` →
   act → until the verdict is CLEAN.** Never review a stale render.
4. Only then send it with `JLC-QUERY-DRAFT-MESSAGE.md`.

**Trade study:** `tracker/hardware/trade_study_wing_joint.py`
(output committed as `docs/fab/WING-JOINT-TRADE-STUDY.txt`).

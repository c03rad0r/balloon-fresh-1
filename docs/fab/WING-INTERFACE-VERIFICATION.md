# Wing interfaces: the four milled slots are NOT equivalent (independently verified)

**Board:** `tracker/hardware/hub_board_v9.kicad_pcb`, sha256 `e55a294628fd38a73e5006fa7fa91389…`
**Reproduce:** `~/venvs/kicad/bin/python tracker/hardware/verify_wing_interfaces.py`

**Source of the finding:** the milestone 3D render review, `docs/boards/reviews/hub-v9-render-r1.md`
(commit `14e8e9410`, served model `gpt-6-astra`, `DEFECTS_PRESENT 7`, defects D-1/D-2).

**This file is the INDEPENDENT verification.** A worker reported it; a self-report is not evidence, so the
board was read directly and the numbers below are from the file.

## Measured

Outline `70.15 × 70.15 mm` (`Edge.Cuts` bbox `-0.07 … 70.08` on both axes).

```
tab    origin            rot      slot union (absolute mm)          slot vs edge
J_W1   ( 5.20, 35.00)     0.0      x  5.17 … 11.22   y 34.52…35.48   WHOLLY INSIDE, 5.25 mm
J_W2   (35.00, 64.80)   -90.0      x 34.52 … 35.48   y 64.78…70.83   reaches bottom, +0.75 mm past
J_W3   (64.80, 35.00)   180.0      x 58.77 … 64.83   y 34.52…35.48   WHOLLY INSIDE, 5.25 mm
J_W4   (35.00,  5.20)    90.0      x 34.52 … 35.48   y -0.82… 5.22   reaches top,    +0.75 mm past
```

**The pads ARE equivalent.** Every tab's pad set is identical to `J_W4`'s after a 90° multiple:

```
J_W1: IDENTICAL after 270°     J_W2: after 180°     J_W3: after 90°     J_W4: at 0°
```

**The SLOTS are not.** `J_W2`/`J_W4` mill their slots so they **cross the board edge by 0.75 mm**;
`J_W1`/`J_W3` mill theirs **wholly inside, 5.25 mm from the outline.**

## What this means, stated precisely

**The electrical interface is symmetric and fine.** The defect is confined to the **milled slot**, which is
the mechanical feature the wing tab seats into.

This violates the requirement in two places:

- `docs/adr/048-v9-hub-wing-interfaces.md` §2.2 — *"Identical geometry, differing only in assembly tilt | yes"*
- `docs/WING-TO-HUB-SOCKET-SPEC.md` §2.1 — Option A is a **"milled edge slot"**, i.e. *in the hub edge*

**A slot that is wholly inside the board is not an edge slot.** The top/bottom tabs have one; the left/right
tabs do not.

## Consequence

The wings are **176 mm** panels soldered into these slots at **90° spacing**. If the left/right slots sit
**5.25 mm inboard** while the top/bottom ones open onto the edge, **the four wings cannot seat
symmetrically** — which changes the array geometry and the solder-joint load case that
`docs/fab/hub-v9/PEEL-COUPON.md` exists to measure.

## Contributing cause, cited not guessed

`docs/adr/048-v9-hub-wing-interfaces.md` §2.1 still records the outline the slots sit on as **22 × 22 mm**,
while the board is **70 × 70 mm** (`docs/adr/068-hub-v9-outline-60x60.md`). **The placement rule was written
against a board a third the size and the tabs were never re-derived for the larger outline.**

That is the same defect class as four others found this session: two live records asserting different values
for one parameter, with nothing surfacing it.

## Two bugs in MY FIRST verification attempt, recorded because they nearly produced a false refutation

The first run printed `J_W1: DIFFERENT`, `J_W3: DIFFERENT`, and `J_W4: WHOLLY INSIDE` — which looked like a
refutation of the worker's report. It was not. Both causes were mine:

1. **Last-item-wins.** The slot was taken as the bounding box of ONE `Edge.Cuts` item per footprint, so each
   slot measured as a thin fragment (e.g. `x 5.17…11.22  y 35.42…35.48`) rather than the full rectangle.
   **Fixed by unioning all four items.**
2. **Rotation set too narrow.** Equivalence was tested only at 0° and 180°. The tabs sit at **90° spacing on
   a square outline**, so equivalence must be tested at every multiple of 90. `J_W1` measured "DIFFERENT"
   purely because it was compared at the wrong angles.

**A measurement that is wrong is worse than no measurement when it contradicts a correct report** — so both
bugs are written into the script's docstring, not just fixed.

## Status

Reported, verified, and filed as `t_b1f63b47` (urgency **now**). **Not fixed here** — the fix is a
**placement-rule change in `build_hub_board_v9.py`** (rule R2 forbids hand-typed coordinates), and it needs
an ADR stating the slot-placement rule for a 70 × 70 outline rather than a rotation of two instances.

# Peel coupon — status of the SPECIMEN DRAWING

**The DESIGN is sound. The DRAWING is not yet clean, and this file records exactly what is wrong.**

## What is settled

`tracker/hardware/peel_coupon_design.py` derives the coupon geometry and load cases from the **same
constants** as `trade_study_wing_joint.py`, so the coupon and the study cannot diverge:

- **SPECIMEN B (peel — Option B's mode)**: face land 4.0 × 1.2 mm on 0.6 mm FR4, **one** fillet along a
  single 1.2 mm edge, load applied **2.0 mm from the fillet root** (the wing's own L/2-over-L ratio).
- **SPECIMEN A (shear — Option A's mode)**: tab 6.0 × 1.2 mm soldered on **both** faces into a 0.9 mm
  slot, pulled along the insertion axis.

**Per-land load at a 10 g landing shock: 0.340 N.** Measure peak force at failure, n ≥ 5 per condition;
derive `knockdown_B`; feed it back into the trade study. Variants: as-soldered, **cold-soak (−40 °C)**,
a deliberately weak fillet, and the build's own alloy.

## What is NOT settled: the specimen drawing

`tracker/hardware/draw_peel_coupon.py` generates `peel-coupon-specimens.svg`/`.png`. **Three review
cycles have each found real defects in it, all in the drawing rather than the design:**

**Cycle 1** — 6 defects, one of them *physical*: the peel force arrow pointed **down INTO the land**
instead of away from it. A peel test pulls the land **off** the substrate; the arrow inverted the test's
meaning. Also: clipping at the top, left and bottom boundaries, and no identifiable tab inside the slot.

**Cycle 2** — the tab-in-slot and clipping were fixed and confirmed (*"clearly drawn within the white gap
between the green walls... two gold fillets total, one on each face"*), but the fix introduced a **new**
defect: the `arU` marker uses `orient="auto"`, which rotates the head to the **path direction**, so both
force arrowheads render **pointing right and left instead of up** — the graphic contradicting its own
label for the second time, in a different way.

**Cycle 3 — remaining, unfixed:**
1. both force arrowheads mis-oriented (right / left instead of up) — `orient="auto"` on a vertical path
   should work, so the marker's `refX`/`refY` and viewBox are the likely cause and need a direct test
2. Specimen B's two grey explanatory lines overlap each other
3. Specimen A's grey note overlaps its bold heading
4. `fillet — face 1` / `face 2` labels sit over the green walls (poor contrast)
5. `tab 0.6 mm thick, seated in the slot` crosses the walls **and the force arrow**
6. Specimen A's red force text overlaps the right wall and extends past it
7. the `wall · slot 0.9 mm` label overlaps the `What the two specimens decide` heading
8. Specimen A's `slot 0.9 mm` dimension does not span the slot; it runs across the left wall
9. Specimen B's `load arm 2.0 mm` dimension has collapsed into a pair of opposing arrowheads and does not
   visibly span root-to-load

## Why this is recorded instead of iterated again

Three cycles produced three improving-but-imperfect drawings, and **two of the three introduced a
graphic that contradicted its own caption.** That is the signature of the wrong person doing the work:
this session's error rate on spatial/drawing output is high, review catches it reliably, and my
corrections keep creating new faults of the same kind.

**The drawing needs a worker whose acceptance test is the render-and-review loop itself.** The task is
well-defined: the nine numbered defects above, the generator at
`tracker/hardware/draw_peel_coupon.py`, and `ask_astra.py --review` as the gate. Loop until the verdict
is CLEAN, and never review a stale render.

**Meanwhile the coupon is buildable from the design alone** — the two specimens are defined by four
numbers (4.0 × 1.2 mm land, 1.2 mm fillet edge, 6.0 × 1.2 mm tab, 0.9 mm slot) and a known load case.
The drawing is for the work order's legibility, not for the measurement's validity.

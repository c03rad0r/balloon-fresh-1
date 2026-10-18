# Hub v9 — fab-review state: what is done, what is waived and why

**Date:** 2026-10-17 · **Board:** `tracker/hardware/hub_board_v9.kicad_pcb`, sha256
`e55a294628fd38a73e5006fa7fa91389…` (70.15 × 70.15 mm, 57/59 nets routed, 834 tracks, 286 vias)

**This document answers the exit condition's last clause: what is done, what is waived and why, and the
exact questions for JLCPCB. NO ORDER HAS BEEN PLACED.**

---

## 1. The six exit-condition items, with their real state

| # | Item | State | Evidence |
|---|------|-------|----------|
| 1 | package matches board | **DONE** | suite check `C2` passes: *"the PACKAGED board carries everything the committed board does"*; board / packaged / manifest all sha256 `e55a294628fd38a7…` |
| 2 | F checks resolved or waived | **WAIVED, fail-closed** | `2cb354207`. Printed reason names the cause. **Deleting the waiver record turns it into a FAIL** — proven by moving the record aside: `14 pass, 2 FAIL`, exit 1 |
| 3 | edge drawing CLEAN per Astra, matching ADR-046's slot | **NOT DONE — WIP, 5 defects** | `673b91531`. Draws the committed ADR-048 slot geometry; verdict `DEFECTS_PRESENT 5`. **2 of the 5 are not closable by drawing** (§4) |
| 4 | all three gates pass or waived | **DONE** | §2 below |
| 5 | merged with CI green | **NOT DONE** | blocked on item 3's disposition; merge order measured (§5) |
| 6 | READMEs + gallery committed and reviewed | **DONE** | top-level README has the generated system diagram + per-board status table; gallery `--check` **4 current / 0 stale**, terminal verdict **CLEAN** (served `gpt-6-astra`, exit 0); docs reorganisation 3 stages pushed (`55aba9589`) |

**Four of six closed. Item 3 is the only blocker, and part of it may be unfixable by drawing at all.**

---

## 2. The three gates — measured, not reported

| Gate | Exit | Result |
|------|------|--------|
| `test_netlist_integrity.py` | **0** | `14 pass, 0 FAIL, 2 WAIVED, 0 PENDING` |
| `run_erc.sh` | **1** | `19 ERC error(s)`, 36 warnings; parity **PASSES** (266 nodes, 0 mismatches). **WAIVER PRINTS** naming every disposition |
| `fab_grade.sh` | **1** | `NOT ORDERABLE` — 4 unconnected items, 154 violations (16 error / 138 warn) |

**The ERC exit 1 is EXPLAINED, not ignored.** Its waiver text, printed at run time:

```
WAIVER -- ERC cannot reach exit 0 honestly. This non-zero exit is EXPLAINED, not ignored.
  19 ERC error(s) remain. Every one is a DISPOSITION, not a repair:
         AWAITING-DECISION: OPEN-25 + OPEN-28 -- cut-sense GPIO/divider and the latched one-shot part
         AWAITING-DECISION: declare the SX1280 rails driven (PWR_FLAG) -- the generator's own idiom
         AWAITING-DECISION: OPEN-26 -- harvester part and H2/H3 vs M5/M6 topology
```

**Why this is a waiver and not a repair:** the classifier's own rule — *"Connecting a pin is a design
decision. If a pin is unconnected because a decision is still open, wiring it would INVENT that decision and
hide the open item."* Twelve of the errors are provisioning pins on a circuit ADR-051 §2.5.1 says is
**undecided**. **Wiring them would have invented a design decision and buried an open item.**

**One genuine fix landed:** an orphan wire stub `(121.92, 63.5)→(127, 63.5)` deleted at its source. **My
card called it "2 mil"; the worker corrected it to 5.08 mm** — ERC's JSON reports schematic values ÷ 100.
**A 100× dimension error in my own instruction, caught by the worker.**

---

## 3. The most consequential finding: the four wing interfaces are NOT equivalent

**Found by the milestone 3D render review, then independently verified by me from the board file.**

```
tab    edge    rot     slot union (absolute mm)         slot vs edge
J_W1   west      0.0   x  5.17 … 11.22  y 34.52…35.48   ** WHOLLY INSIDE, 5.25 mm **
J_W2   north   270.0   x 34.52 … 35.48  y 64.78…70.83   reaches the edge, +0.75 mm past
J_W3   east    180.0   x 58.77 … 64.83  y 34.52…35.48   ** WHOLLY INSIDE, 5.25 mm **
J_W4   south    90.0   x 34.52 … 35.48  y -0.82… 5.22   reaches the edge, +0.75 mm past
```

**Root cause:** all four footprints have **identical local geometry** and the **same 5.20 mm offset**; only
the **rotation** differs, and it sends the slot in **opposite directions**. The rotation set is **180°
inconsistent between {west,east} and {north,south}** — which is what `ADR-048 §2.2`'s *"identical geometry,
differing only in assembly tilt"* forbids.

**Why it survived:** the builder carries a documented 2026-10-14 repair that added a uniform inboard offset
because **16 of 32 wing pads had landed OUTSIDE the outline** — and they landed outside **because the
rotations were already inconsistent**. **The offset compensates for a rotation error, applied uniformly, so
it hides the error on two edges and creates a new defect on the other two.**

**Neither number alone fixes it:** offset 0 puts the slot on the edge and the pads off the board; offset 5.2
puts the pads on and the slots inboard. **The rotations must be made consistent from the datum convention
and the offset re-derived afterwards.**

**Consequence:** the wings are 176 mm panels soldered in at 90° spacing. If left/right slots sit 5.25 mm
inboard while top/bottom open onto the edge, **the four wings cannot seat symmetrically** — changing the
array geometry **and the solder-joint load case the peel coupon exists to measure.**

**Nothing electrical sees this class of defect.** The netlist passes; DRC files these as the 16 accepted edge
findings; the pad audit passes. **Only the render caught it.** Filed `t_b1f63b47`, urgency **now**.

**And it is coupled to the peel coupon:** settle the slot rule **before** freezing the coupon's specimen
geometry.

---

## 4. Item 3: why the edge drawing is not CLEAN, and why part of that is correct

Four review cycles (`r1`-`r4`, served model `gpt-6-astra`). The drawing is **more truthful than before** — it
now draws the **committed ADR-048 geometry** (routed slot 0.9 × 6.0 mm, 0.6 mm tab seated 6.0 mm in, lands
on the slot's faces, fillet loaded in **SHEAR**) and **states on the sheet that the board as built is still
Option B**, so it cannot be misread as a claim that the board is already slotted.

**Five defects remain. Three are mechanical and are being fixed. Two are NOT drawing problems:**

- **Slot-face copper construction.** r4: *"Q6 identifies lands on internal routed-slot faces as 'F.Cu and
  B.Cu', which are outer PCB copper layers, not internal slot-wall surfaces; the required construction
  remains undefined."* **This is a fabrication question, now asked as section 2A of the JLCPCB query
  (PR #215).** A drawing cannot answer it.
- **Mating-fit spec.** finished tab thickness, slot width/depth tolerances, finished solder clearances,
  slot-end radius, tab-tip relief. **These are design decisions.** Inventing numbers would be worse than
  leaving them marked unresolved.

**The correct disposition is a waiver of the same form the ERC and F checks already use** — *drawing depicts
the committed geometry, states it is not the as-built board, and discloses the slot-face construction as
UNVERIFIED pending JLCPCB* — **with the three mechanical defects fixed first.**

**One defect must be fixed regardless of disposition:** r4 found that **the continuous tab-face copper in
View B would connect `W1_SOLAR_P`, `GND`, `W1_RF` and `W1_SOLAR_N` if fabricated literally.** **A fab
drawing depicting four shorted nets is a defect whether or not the drawing is ever sent.**

---

## 5. Merge readiness

**Six branches, all pushed, all verified by my own runs.** Only **2 files** are contended across all of them:

```
3x  docs/fab/GATE-RESULTS.md    pr/u1-footprint · pr/hub-milestone · pr/erc-classification
2x  docs/fab/README.md          pr/hub-milestone · pr/erc-classification
```

**Measured order** (`tracker/hardware/plan_merge_order.py`) — least-contended and most-foundational first,
so later branches merge *onto* a shared file rather than over it:

```
1. pr/peel-coupon          3 commits    0 contended
2. pr/presentation         2 commits    0 contended
3. pr/repo-cleanup         2 commits    0 contended
4. pr/u1-footprint         3 commits    1 contended
5. pr/hub-milestone        8 commits    2 contended   ← carries fab_grade.sh + GATE-RESULTS + README
6. pr/erc-classification   2 commits    2 contended   ← LAST: it corrects the ERC counts to 19/36
```

**`erc-classification` goes last on purpose:** it corrects `GATE-RESULTS.md`'s ERC counts to **19/36**, so
merging it before `hub-milestone` (which also edits that file) would put them back to 20/37.

**⚠️ Note:** most of these branches have **no open PR yet** — only #214 (peel-coupon) and #215 (query). The
rest need PRs created before the merge ritual can run.

---

## 6. The exact questions for JLCPCB

Full text: `docs/fab/JLC-QUERY-DRAFT-MESSAGE.md`. **The blocking ones:**

### Blocking — the wing interface

- **2.1** Can you **rout the board edge through these pads** so the copper is exposed at the edge? Does this
  require a **special process**, or is it a standard routed edge?
- **2.2** Does this imply **edge plating or castellation**? We do **not** want either — we want exposed copper
  on the pad, exposed at the board edge, with the edge simply being the finished cut. **Which would we
  actually get, and how must we specify it** (what to draw/say on the fabrication notes) to get plain
  exposed copper and **not** castellations?
- **2.3** What is the **positional tolerance** of the routed edge relative to the copper?
- **2.4** Will there be **burrs or copper peeling** at the edge? If so, is there a recommended finishing or
  process note?

### Blocking — NEW: copper on the INTERNAL FACES of a routed slot (section 2A)

*Separate from 2.1/2.2: those concern copper terminating at the board edge; this concerns the walls of a
routed cut.*

- **2A.1** **How would copper be present on the internal faces of a routed slot at all?** Ordinary F.Cu/B.Cu
  is on the board's outer surfaces. A routed cut exposes **substrate** on its walls, not copper. Please
  describe what process (if any) produces conductive surfaces on those internal faces, **or state that it is
  not achievable by routing alone.**
- **2A.2** If it **is** achievable: what must we specify on the fabrication drawing, and what is the
  resulting surface (bare copper? plated? which finish, and does it differ from the outer-surface finish)?
- **2A.3** If it is **not** achievable: **what alternative would you recommend** for a 0.6 mm tab that must
  make four connections inside a 0.9 × 6.0 mm slot — **and what would adding it cost?**
- **2A.4** **Positional tolerance** of the slot's internal faces relative to the intended land positions, and
  the tolerance of the slot **width** (nominal 0.9 mm)?
- **2A.5** The slot is a **routed internal cut-out**, not an edge rout. Does that change the minimum slot
  width, the achievable depth-to-width ratio, or the tooling?

### Deferrable — stackup and impedance (section 1)

- **1.1** the 4-layer 0.6 mm stackup numbers
- **1.5/1.6** minimum trace **width and spacing** (we assume 0.20 mm) and whether 0.20 mm is reliably
  manufacturable on 0.6 mm 4-layer, in particular for an impedance-controlled trace

**1.x is deferrable** to a follow-up revision: for a first prototype we can order at 0.20 mm and document
the unverified impedance. **Per Astra: *"neither '0.20 mm is wrong' nor '0.20 mm is 50 ohm' is justified
without the stackup."***

### Handling (section 3)

- **3.1** for a 0.6 mm board, anything needed on panelisation or handling, and any minimum panel size?
- **3.2** with JLCPCB assembly, special handling or minimum quantity rules for 0.6 mm?

**If 2.1/2.2 or 2A comes back negative, the wing-tab design needs revising — an ADR-046/048 change on our
side.** That is why these are the blocking questions.

---

## 7. The pattern worth recording

**Every step of this programme has found a claim that was believed and unmeasured.** Instances, all found by
measuring rather than assuming:

1. the fab package matched a board that **no longer existed**
2. the gallery cited a board **hash that no longer existed**
3. the `U1.41` "electrical defect" claim was **disproven**, and the correction reached **one of five
   documents** — and **not the fabricator's entry point**. Worse: `GATE-RESULTS.md` gained a CORRECTIONS
   section **while the false claim stayed live in its body**, so a top-down reader met the disproven claim
   with no signal it was wrong.
4. the gallery review happened but **its verdict was never recorded**, so its defect survived in the
   published gallery
5. `fab_grade.sh` **printed `NOT ORDERABLE` and exited 0** — the exit code, the only machine-readable part,
   read as PASS
6. **the wing-interface defect** (§3) — invisible to every electrical gate
7. **a 100× dimension error in my own task instruction**, caught by the worker
8. **my own verification script produced a false refutation** of the wing defect, from two bugs (last-item-
   wins on the slot bbox; equivalence tested at only 0°/180° when the tabs sit at 90° spacing)

**Generating an artefact is not the same as keeping it current. Reviewing one is not the same as concluding
it. And a measurement that is wrong is worse than no measurement when it contradicts a correct report.**

The detectors now in the tree exist because of this: `make artefacts-check`, `find_disproven_claim.py`,
`verify_wing_interfaces.py`, `plan_merge_order.py`, and a `fab_grade.sh` whose exit code is driven by its
verdict.

---

## 8. What is explicitly NOT done

- **No order has been placed.** Nothing here authorises one.
- **Item 3 is not CLEAN** — 5 defects, 3 being fixed, 2 requiring JLCPCB's answer or a design decision.
- **Item 5 is not merged** — blocked on item 3's disposition.
- **`/SX1280_MOSI` and `/SX1280_SCK` remain unrouted** (2 of 59). Each holds one via and zero tracks.
  **B.Cu escape is clear (12 mm, 7 directions).** Operator will hand-route in the KiCad GUI. **Clear the
  `/SX1280_MOSI` escape via at `(49.95, 11.84)` first — it sits exactly where that route must start.**
- **`holes_co_located 2`** — a via drilled inside `C_CAP2` pad-2's hole at `(56.792502, 47.292502)`. **An
  ERROR-class fabrication fault.** Card `t_e4d0f437`.
- **`via_dangling 8`** — routing debris, same card.
- **ERC 19 errors** — dispositions awaiting decisions `OPEN-25`/`OPEN-26`/`OPEN-28`.
- **`ADR-048 §2.1` still records the outline as 22 × 22 mm** while the board is 70 × 70. **Two live records
  disagree with nothing surfacing it.**
- **The 0.6 mm stackup is unknown** — 50 Ω width varies 3.7× with the L1-L2 dielectric.
- **The base station** has 44 nets, ZERO tracks, and a netlist but **no editable schematic**.

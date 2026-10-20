# DFM REVIEW SNAPSHOT — hub v9

> ## ⛔ DFM REVIEW ONLY — NOT RELEASED FOR MANUFACTURE
>
> **Fabrication is not authorized.** This snapshot exists so a fabricator can review the board and
> answer one blocking feasibility question. It must not be treated as an approved production release.

**Board:** `tracker/hardware/hub_board_v9.kicad_pcb` · 70.15 × 71.65 mm · 0.6 mm · 4 layers · 59 footprints
**Board sha256:** `374132814682a432…` (carries PRs #239 In1 stitch, #240 C_CAP2 fix, #245 MOSI+SCK routing, #247 J_W silk)
**Snapshot refreshed:** 2026-10-19
**Gate state:** netlist **PASS** (14 pass / 0 FAIL / 2 WAIVED, fail-closed) · ERC **19 errors / 36
warnings, waived with a printed waiver** · **direct DRC (the committed board, fresh refill): 105
violations, 2 unconnected** · `fab_grade.sh` **NOT ORDERABLE** — but see
`docs/fab/FAB-GRADE-TOOL-DEFECT.md`: the fab_grade chain re-routes the board with the KRT router before
grading, and the router **re-introduces the C_CAP2 phantom via** that PR #240 removed. Its numbers are a
router-capability signal, not the board's state. **Quote the direct DRC for board state.**

---

## 1. The one blocking question: `U4.13`

**`U4.13` is a GND pin on the SX1280 (2.4 GHz radio, QFN24, 0.50 mm pitch). It is assigned to `GND` in
the netlist but is electrically unconnected to board ground.**

Its only attached copper is an **isolated 0.278 mm² F.Cu fragment containing zero vias** — a floating
copper extension of the pad, not a ground connection. **This is a known unresolved layout defect, not an
intended circuit condition.**

See `docs/fab/jlc-query/u413-open-ground.png` for the close-up (rendered from this board; reviewed CLEAN
by the visual consultant after five rounds).

### Why it is open — measured, not assumed

The pad is `0.80 × 0.30 mm` at `(55.150, 27.250)` in a column of nine pads at `0.500 mm` pitch. Its
neighbours `U4.12` (`VDD`, `y=27.750`) and `U4.14` (`DCC_SW`, `y=26.750`) leave an exit lane of
`y ∈ [27.200, 27.300]` — **0.100 mm**.

| avenue | measurement | result |
|---|---|---|
| via inside the fragment | fragment is **0.298 mm tall**; a 0.50 via needs a 0.90 mm envelope | impossible |
| F.Cu escape east | stub legal only at `x=55.50` (`+0.200`); via there is `−0.315` on `In2.Cu` | blocked |
| F.Cu escape west | `/SX1280_DCC_SW` blocks at every y from 26.65 to 27.25 | blocked |
| move `DCC_SW` west | thermal pad edge `x=54.100` + 0.300 clearance ⇒ **minimum legal x is 54.400** = where it is | cannot nudge |
| `DCC_SW` → inner layer | run clear on `B.Cu` (`+0.862`) but **no legal via at either end** within 0.3 mm | needs long reroute |
| `VDD` → inner layer | `−0.400` on In1, In2 **and** B.Cu (its own via blocks); pad12-side via: none within 0.5 mm | blocked |
| exhaustive sweep | `x 55.20…56.20`, `y 26.95…27.55` at **10 µm**, requiring stub **and** via legal | **0 viable sites** |

### What a compliant via-in-pad would need

Measured from the board and verified two independent ways (formula `c = 0.500 − 0.150 − D/2` agrees with
edge-measured geometry to 4 dp at every diameter):

| via copper Ø | clearance to adjacent pad | annular ring (0.20 drill) | meets 0.20 rule? |
|---|---|---|---|
| 0.60 | 0.050 | 0.200 | no |
| 0.50 | 0.100 | 0.150 | no |
| 0.40 | 0.150 | 0.100 | no |
| **0.30** | **0.200** | **0.050** | **yes — but ring is 0.050** |

**A compliant centred via here is ≤ 0.30 mm copper with a ≈ 0.050 mm annular ring**, against a board
minimum via of **0.500 mm**. **That is a manufacturing-capability question, not a layout preference** —
hence question **4A** in `docs/fab/JLC-QUERY-DRAFT-MESSAGE.md`.

**Decision gate:** *if the fabricator cannot supply an acceptable construction that passes full-board
geometry checks, or the process premium is unacceptable, the next step is a deliberate revision of
`U4`'s local escape geometry — not another speculative routing attempt.*

---

## 2. The other open ground: `U_HUB_CVT.2`

`U_HUB_CVT` is the `BQ25504` energy harvester. **Pad 2 is `GND`** and its only copper is a **0.445 mm²
fragment with zero vias**; nearest real GND copper is **2.935 mm** away.

**This one is also boxed** — the same failure mode as `U4.13`. `U_HUB_CVT.2` is pad 2 in a **column of
four pads at `x = 25.683`**, so no route may pass between them. Its only legal exit window is
`yc ∈ [2.820, 2.970]` (**0.150 mm**), west is legal only to `x = 25.35`, and **no via fits at the end of
that corridor**:

```
(25.30, 2.895): +0.050 vs In1.Cu trk /HUB_PV_P     need +0.200
(25.25, 2.895): +0.001 vs via /HUB_PV_N
```

A via **on the pad itself** is also illegal (`+0.125` against `U_HUB_CVT.1`). **The walls are the vias of
the very nets this pad is meant to serve**, `/HUB_PV_P` and `/HUB_PV_N`.

*(An earlier version of this snapshot said this pad was "routable at `y=4.40`". That was wrong — those
points are on the far side of the package, 12 pads away. Corrected in
`docs/fab/D12-VIALESS-GND-FRAGMENTS.md`.)*

---

## 3. What IS resolved

**`C_CAP2.2` — FIXED and verified (PR #240, found 2026-10-19).** The `holes_co_located` DRC error was
pointing at a **third open ground**: the 0.60/0.30 GND via at the pad's exact centre was a **CAD
fiction** — the drill file carries two holes at one point, a fabricator resolves it to one 1.0 mm hole,
and the via's land does not survive drilling. And the naive fix (delete the via) would have floated the
pad (no GND tracks touch it; outside all inner pours). Fixed by deleting the via and adding a **real
0.49 mm GND track** from the pad's surviving annulus into the main F.Cu pour. `holes_co_located 2 → 0`,
zero new violations.

**`In1.Cu` reference-plane island — FIXED and verified (PR #239, landed in the canonical board).** A 29.2 mm² island of the inner GND plane had
**one** via tie, co-located with the 433 MHz LoRa module's ground pad. Three stitching vias were added at
`(35.00,43.00)`, `(33.00,44.00)`, `(34.00,44.00)`, each re-verified against the loaded board
(`+0.390`, `+0.200`, `+0.223`):

```
In1 island1 tie vias:  1 → 4       all four also land in B.Cu main
DRC at PR #239:       168 → 168 violations, unconnected 4 → 4, no new violation
```

**The five other F.Cu GND fragments are proven connected** to both main planes through vias that land in
`In1.Cu` main **and** `B.Cu` main. Nothing else is floating.

---

## 4. Known issues a reviewer should see, in priority order

| # | issue | state |
|---|---|---|
| 1 | **`U4.13` open ground on the SX1280** | **blocking** — question 4A |
| 2 | `U_HUB_CVT.2` open ground | **boxed** — same failure mode as `U4.13`; covered by question 4A.4 |
| 3 | Edge-launch slot-face land construction | **UNVERIFIED** — question 2A |
| 4 | Mating fit across the 0.9 mm slot / 0.6 mm tab | question 2A.4 |
| 5 | `0.50/0.25 mm` via, 0.125 mm annular ring — standard tier? | question 5 |
| 6 | Open via at `U1.8` pad centre — solder wicking | question 4 |
| 7 | ENIG on copper newly exposed by routing | question 6 |
| 8 | `holes_co_located` at `C_CAP2.2` | **FIXED** — phantom via → real track (PR #240) |
| 9 | `via_dangling 7` | **not debris** — 6 are the unrouted nets' own escape points; resolve in the GUI session |
| 10 | Six QFN escape nets | two routed (`MOSI`, `SCK`), see `docs/fab/ROUTING-DECISION-STOP.md` |

---

## 5. What this snapshot must NOT be read as

- **Not** an approval to manufacture.
- **Not** evidence of RF performance — no VSWR, S-parameter, or range measurement exists.
- **Not** a claim that the open grounds are harmless. Astra: *"Do not characterize the open pin as
  harmless because other grounds exist. Without explicit component guidance, that would be an
  unsupported functional assumption."*
- **Not** complete: impedance, copper thickness and finish need tooling, not review.

---

## 6. Reproduce

```
~/venvs/kicad/bin/python tracker/hardware/apply_gnd_fixes.py --in <board> --out <out>   # the In1 stitching
kicad-cli pcb drc --format json --output /tmp/drc.json <board>
~/venvs/kicad/bin/python tracker/hardware/fix_vialess_gnd.py --in <board> --out <out>  # dry-run planner
```

Sources: `docs/fab/D12-VIALESS-GND-FRAGMENTS.md`, `docs/fab/ROUTING-DECISION-STOP.md`,
`docs/fab/FAB-REVIEW-DISCLOSURE.md`, `docs/fab/JLC-QUERY-DRAFT-MESSAGE.md`.

---

## 1a. Severity of the residual DRC items — and three refuted attempts to clear the silk

**Measured severity at master `baef25a1e`:**

```
silk_overlap          32   warning      <- cosmetic layer
silk_over_copper      26   warning
silk_edge_clearance   12   warning
via_dangling           5   warning
copper_edge_clearance  30  ERROR        <- the J_W* castellation geometry: JLC section 2A
unconnected            2   ERROR        <- the GND zone pairs: JLC question 4A
```

**Only two ERROR classes remain, and both are fabricator questions.** The 70 silk items are
warnings on a cosmetic layer: silkscreen that overlaps another line or a mask opening is clipped
or overprinted by the fabricator and does not affect copper, mask or drill. **Treating them as
order blockers was wrong.**

### Attempt 1 — REFUTED: unrestricted reference-text re-placement

Search a clean spot per reference, nearest-first with a wide ring. Discarded, not merged: to
satisfy the checks it walked labels far from their components — `D_HUB1`'s ref moved **16.4 mm**
— and still could not place `R_MON2`. A board whose designators are scattered across the
silkscreen passes DRC and is **worse for assembly**.

### Attempt 2 — REFUTED: bounded nudge (<= 1.2 mm)

Rule adopted from attempt 1 (a ref move is acceptable only if the text stays adjacent). Result:
**7 moves bought 2 fewer overlaps** — 0.29 per move. Churn, not a fix. Worse: the first version's
predictor EXCLUDED same-footprint silk from its cleanliness test while the grader INCLUDES it, so
an early run "improved" 32 -> 50 by pushing refs onto their own outlines. **A predictor whose
rule differs from the grader's manufactures false confidence.**

### Attempt 3 — REFUTED: shrink the ref text

Premise checked and found false: the ref texts are **already 1.00 mm** tall. `U_CUT2`'s text
measures 5.82 mm wide because **"U_CUT2" is six characters at 1.00 mm pitch plus spacing** — the
width is string length, not font size. Shrinking further would be unreadable and still not fit.

### The actual cause

```
U_CUT2 / U_CUT3   texts 5.82 mm wide, the parts are 5.00 mm apart
R_MON2            6.20 mm wide at x = 68.0
C_CAP2            5.82 mm wide
70 x 70 mm board, 59 parts, six-character designators
```

**The labels are wider than the gaps.** Resolving them means renaming designators, editing
footprint silk, or accepting the warnings — design choices, not routing cleanup, and **none of
them an order blocker.** All three scripts were reverted; nothing was shipped.


**Measured severity at master `baef25a1e`:**

```
silk_overlap          32   warning      <- cosmetic layer
silk_over_copper      26   warning
silk_edge_clearance   12   warning
via_dangling           5   warning
copper_edge_clearance  30  ERROR        <- the J_W* castellation geometry: JLC section 2A
unconnected            2   ERROR        <- the GND zone pairs: JLC question 4A
```

**Only two ERROR classes remain, and both are fabricator questions.** The 70 silk items are
warnings on a cosmetic layer: silkscreen that overlaps another line or a mask opening is clipped
or overprinted by the fabricator and does not affect copper, mask or drill. **Treating them as
order blockers was wrong.**

### Attempt 1 — REFUTED: unrestricted reference-text re-placement

Search a clean spot per reference, nearest-first with a wide ring. Discarded, not merged: to
satisfy the checks it walked labels far from their components — `D_HUB1`'s ref moved **16.4 mm**
— and still could not place `R_MON2`. A board whose designators are scattered across the
silkscreen passes DRC and is **worse for assembly**.

### Attempt 2 — REFUTED: bounded nudge (<= 1.2 mm)

Rule adopted from attempt 1 (a ref move is acceptable only if the text stays adjacent). Result:
**7 moves bought 2 fewer overlaps** — 0.29 per move. Churn, not a fix. Worse: the first version's
predictor EXCLUDED same-footprint silk from its cleanliness test while the grader INCLUDES it, so
an early run "improved" 32 -> 50 by pushing refs onto their own outlines. **A predictor whose
rule differs from the grader's manufactures false confidence.**

### Attempt 3 — REFUTED: shrink the ref text

Premise checked and found false: the ref texts are **already 1.00 mm** tall. `U_CUT2`'s text
measures 5.82 mm wide because **"U_CUT2" is six characters at 1.00 mm pitch plus spacing** — the
width is string length, not font size. Shrinking further would be unreadable and still not fit.

### The actual cause

```
U_CUT2 / U_CUT3   texts 5.82 mm wide, the parts are 5.00 mm apart
R_MON2            6.20 mm wide at x = 68.0
C_CAP2            5.82 mm wide
70 x 70 mm board, 59 parts, six-character designators
```

**The labels are wider than the gaps.** Resolving them means renaming designators, editing
footprint silk, or accepting the warnings — design choices, not routing cleanup, and **none of
them an order blocker.** All three scripts were reverted; nothing was shipped.

---



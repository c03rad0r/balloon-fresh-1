# DFM REVIEW SNAPSHOT — hub v9

> ## ⛔ DFM REVIEW ONLY — NOT RELEASED FOR MANUFACTURE
>
> **Fabrication is not authorized.** This snapshot exists so a fabricator can review the board and
> answer one blocking feasibility question. It must not be treated as an approved production release.

**Board:** `tracker/hardware/hub_board_v9.kicad_pcb` · 70.15 × 71.65 mm · 0.6 mm · 4 layers · 59 footprints
**Snapshot date:** 2026-10-18
**Gate state:** netlist **PASS** (14 pass / 0 FAIL / 2 WAIVED, fail-closed) · ERC **19 errors / 36
warnings, waived with a printed waiver** · DRC **168 violations, 4 unconnected** · `fab_grade.sh`
**NOT ORDERABLE** (exit 1, verdict-driven)

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

**`In1.Cu` reference-plane island — FIXED and verified.** A 29.2 mm² island of the inner GND plane had
**one** via tie, co-located with the 433 MHz LoRa module's ground pad. Three stitching vias were added at
`(35.00,43.00)`, `(33.00,44.00)`, `(34.00,44.00)`, each re-verified against the loaded board
(`+0.390`, `+0.200`, `+0.223`):

```
In1 island1 tie vias:  1 → 4       all four also land in B.Cu main
DRC:                  168 → 168 violations, unconnected 4 → 4, no new violation
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
| 8 | `holes_co_located 2` (via inside `C_CAP2` pad-2 hole) | known, unresolved |
| 9 | `via_dangling 8` | known routing debris |
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

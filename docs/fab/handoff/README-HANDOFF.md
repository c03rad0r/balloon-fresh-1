# HUB v9 — GUI HANDOFF: route the last two nets

**Purpose:** everything that can be done mechanically is done. Two nets remain, and they are short and
local enough to hand-route in the KiCad GUI in a few minutes.

## Open this

```
docs/fab/handoff/hub_board_v9.kicad_pcb
```

The directory also contains `hub_board_v9.kicad_pro`, `hub_board_v9.kicad_prl` and
`hub_board_v9.kicad_dru`. **Open the whole directory, not the file alone** — KiCad auto-loads custom
rules from `<project-name>.kicad_dru`, and the copy shipped here is the **amended conditionless** one.

## State of the board you are receiving

| | |
|---|---|
| tracks | **834** |
| vias | **286** |
| **nets routed** | **57 of 59** |
| errors | **16**, all `copper_edge_clearance` — the `J_W*` wing interface, documented as zero real defects |
| `starved_thermal` | **0** |
| outline | 70.15 × 71.65 mm |
| stackup | 0.6 mm, 4-layer (deliberate — ADR-028 weight budget). No stackup declared; see below |

## The two nets to route

### `/SX1280_MOSI` — 14.38 mm span
```
U1.8    (49.95, 11.84)   1.50 x 0.90 mm pad, F.Cu     <- ESP32-S3 west edge
U4.17   (55.15, 25.25)   0.80 x 0.30 mm pad, F.Cu     <- SX1280 east edge
```

### `/SX1280_SCK` — 6.79 mm span
```
U1.22   (60.60, 20.71)   1.50 x 0.90 mm pad, F.Cu     <- ESP32-S3 east edge
U4.18   (55.15, 24.75)   0.80 x 0.30 mm pad, F.Cu     <- SX1280 east edge
```

## What the measurements say about HOW to route them

`find_pinch_point.py` measured escape reach outward from each pad, per layer:

| pad | F.Cu | B.Cu |
|---|---|---|
| `U4.17` | **1.05 mm** (blocked by `+3V3`) | **12.00 mm, 7 directions ≥ 2 mm** |
| `U4.18` | 10.75 mm | **12.00 mm, 7 directions ≥ 2 mm** |

**So route both nets on `B.Cu`.** At the `U4` end, `F.Cu` has essentially no room — `+3V3` sits 1.05 mm
away — while `B.Cu` is wide open. Drop a via near each `U4` pad and run the net on the back layer.

**Via geometry that is known to work:** 0.60 mm diameter / 0.30 mm drill (the board's frozen rule).

## What NOT to do, and why — all measured

- **Do not widen the board.** The region east of `U4` (x 55.8–60.0, y 23.5–26.5) is **already empty of
  copper on all four layers**; adding area there cannot help.
- **Do not move `U4`.** Only **0.39 mm** of free space exists south of it, occupied by the reviewed RF
  match (`C0`, `L1`).
- **Do not try to re-scope other nets out of the `U1`/`U4` slot.** All eight nets crossing it have pads
  on **both** sides, so each is structurally required to cross.

## Why this was not done mechanically

Five attempts, recorded in `docs/fab/HUB-V9-BOXED-IN-NETS.md` and the commit log:
1. full route — **55/57**, these two failed
2. focused re-route with rip-up allowed on 10 nets — **0/2**
3. "boxed in on all four layers" — **wrong measurement window** (retracted)
4. "grow the outline" — **the region is already empty** (retracted)
5. hand-placed vias to `B.Cu` — **8 shorts**, because the via sites were chosen from the *stitched*
   board and graded on the *refilled* one

The router's own verdict is `boxed_in_static` (5014 / 5029 iterations, `layer_swaps: 0`) — but
`find_pinch_point.py` shows that is **not** full saturation: `B.Cu` is open. A graded search for the via
sites is what is needed, and the GUI is a faster path to it than another script iteration.

## After you route them

Run the canonical grade from the repo root:
```bash
bash tracker/hardware/fab_grade.sh <your_board.kicad_pcb> tracker/hardware/output/fabgrade_gui
```
It refills before grading, which matters: 208 of an earlier "235 errors" figure were stale zone fill.

## Still open before an order (neither blocks your GUI work)

- **Stackup undeclared** — `docs/fab/FAB-QUESTIONS-FOLLOWUP-REVISION.md`; six questions to answer for a
  follow-up revision. The RF route is at the board's declared 0.20 mm and is **not** presented as a
  50-ohm figure.
- **The 16 `copper_edge_clearance` items** — documented as a rule-applicability artifact, no real copper
  defect. See `docs/fab/EDGE-EXEMPTION-MECHANISM.md`.

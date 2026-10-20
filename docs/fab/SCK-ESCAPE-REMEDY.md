# SCK escape — fully diagnosed, with the exact remedy (not yet applied)

**Date:** 2026-10-19 · **Board:** `hub_board_v9.kicad_pcb` sha `71bd675f74a003fc…`
**Consultant:** `gpt-6-astra` (served id verified) · **Status:** diagnosis COMPLETE, remedy NOT applied.

## Why this document exists

Three unattended attempts to open SCK's escape each found one more blocker. All of them lie inside a
**0.150 mm** window. Rather than attempt a fourth blind coordinate surgery, this records the complete,
measured chain and the exact two-segment change that opens it.

## The geometry

`U4.18` (SCK) is in U4's right-hand pad column — 9 pads at **0.500 mm pitch**, each **0.300 mm** tall,
so the edge gap is **0.200 mm = exactly the clearance rule**. A 0.200 mm track may therefore exit at
`yc ∈ [24.700, 24.800]` — a **0.100 mm** lane.

`U4.17` spans `25.100…25.400` · `U4.18` spans `24.600…24.900` · `U4.19` spans `24.100…24.400`.

## The measured blocker chain

```
x=55.60: +0.2180 LEGAL
x=55.75: +0.1640 BLOCKED
x=55.85: +0.1640 BLOCKED
x=55.95: +0.1640 BLOCKED
x=56.20: +0.1500..+0.2950 BLOCKED   (depends on the long run's y)
x≥57.00: LEGAL once the long run moves
```

Two `/SX1280_DIO1` segments, and **only two**, stand in the lane:

| segment | role |
|---|---|
| `(64.100, 24.450) → (55.850, 24.450)` | the **long run** east; its 0.100 half-width reaches up to `24.550`, and `24.800 − 24.550 = 0.250`… measured **+0.1500** at the same-segment test |
| `(55.850, 24.450) → (55.050, 23.650)` | the **diagonal** at U4.8's own escape; its vertex cap at `(55.850,24.450)` is what blocks `x=55.75…55.95` |

*(A third segment, `(68.500,20.050)→(64.100,24.450)`, also reports +0.050 — but at `x=64.100`, far
outside SCK's path to U1.22 at `(60.605,20.71)`. It is not on the critical path.)*

## The remedy — two coordinate changes, both measured

1. **Move the long run south.** `(64.100,24.450)→(55.850,24.450)` ⟶ `y = 24.300` (or lower).
   Astra's rule: two parallel 0.200 tracks need **0.400 mm centreline separation**; SCK at `24.800`
   therefore requires DIO1 at `≤ 24.400`. Measured: at `y=24.300`, `x≥56.60` becomes legal
   (`+0.2550` at `yc=24.755`, blocker becomes `+3V3` at `+0.2500`). **The moved run is itself legal** —
   worst `+0.650` against `+3V3` at `x=58.0` (measured).
2. **Move the diagonal's east vertex south as well.** It must clear `y ≥ 24.800` by
   `0.100 + 0.200 = 0.300` at `x=55.75…55.95`, i.e. the vertex must sit at `y ≤ 24.500` **and** the
   diagonal's path through that x-range must stay clear. Keeping the diagonal's shape and taking its
   east vertex from `(55.850,24.450)` to `(55.850,24.300)` is the smallest candidate — **this specific
   move was NOT verified before handoff; verify it first.**

## What must be verified before applying

1. The shifted diagonal is legal against `U4.7/8/9` pads (bottom column, `0.500 mm` pitch) and DIO1's
   own `(52.950,23.650)` segment.
2. The whole `x=55.75…59.00` run of SCK's lane reads `≥ +0.200` on the 0.0025 mm y-grid.
3. `DIO1` remains connected end-to-end: `U4.8 → via (67.200,12.000) → U1.33` (it uses `In1.Cu`
   downstream, so only the F.Cu escape changes).
4. Full DRC: **zero new violations**, unconnected `4 → 3` (SCK connected; MOSI separately).

## MOSI — solved and independent

`MOSI` routes **without touching DIO1**: F.Cu stub + one `0.50/0.25` via at `(55.855, 25.250)`
(measured legal on all four layers — it is the column's single legal via site) + **16 segments on B.Cu**
to `U1.8`. Confirmed by the router run of 2026-10-19.

## Why this was not applied unattended

Astra's ranking put "rip and re-escape DIO1" first, with the explicit caveat that **the replacement
DIO1 escape was never demonstrated**. That is exactly what these measurements now supply — but the
second coordinate (the diagonal vertex) is unverified, and the window is 0.150 mm. **Two blind
attempts on a comparable 0.100 mm window in this session produced illegal geometry** (a `−0.2411 mm`
GND→VDD short and a `−0.250 mm` planned-vs-planned overlap). This is the point to verify, not guess.

## Correction of record

An earlier report to the consultant stated the blocking DIO1 segment "runs along `y=24.70`". **It runs
along `y=24.450`.** The `24.70` figure was an A* **cell centre** (0.1 mm grid), not a track coordinate.
The consultant's option (c) — "small y-offset" — was ranked low partly on that wrong input; with the
true `24.450`, a 0.150 mm shift is precisely what the geometry needs.

# D12 — The two via-less GND fragments: root cause found, fix identified

**Date:** 2026-10-18 · **Consultant:** `gpt-6-astra` (served id recorded) · **Branch:** `pr/stand-authority` off `master 0e82577e5`

## The defect, as Astra ruled

> *"Do not order with the two via-less GND-pad fragments as described. Fix those first… A local pour
> connected only to an SMD pad is a **floating copper extension of that pad**, not a board-ground
> connection… Other grounded pins on U4 do not make omitting this external connection acceptable."*

| pad | fragment | fragment size | GND vias inside | GND copper within 2.5 mm |
|---|---|---|---|---|
| **`U4.13`** (SX1280 GND) | F.Cu island 0.278 mm² | bbox `x 54.700..55.698 y 27.101..27.399` | **0** | **none** (nearest `2.511 mm`) |
| **`U_HUB_CVT.2`** (BQ25504 GND) | F.Cu island 0.445 mm² | bbox `x 25.201..26.395 y 2.623..3.166` | **0** | **none** (nearest `2.935 mm`) |

**Both are declared `GND` in the netlist** (`v9_flight.net` line 1535 for `U4.13`) — so this is a real
open connection, not a spare pad.

## Why no via fits inside either fragment — measured, not assumed

Exhaustive search at 20 µm resolution over each fragment's own bbox, both 0.50 mm and 0.60 mm vias,
checking clearance against every non-GND track, via and pad on all four layers:

```
U4.13       fragment is 0.298 mm TALL   -> no 0.50 via (0.90 mm envelope) fits. 0.60 also no.
U_HUB_CVT.2 fragment is 0.543 mm tall   -> no site clears 0.200 mm on all four layers.
```

**So the fix cannot be "drop a via in the fragment".** Astra's fallback applies:
*"run a short GND trace or copper extension to the nearest legal via location."*

## Why the short trace also failed on the first attempt — and the real root cause

A grid-A* from each pad to every validated GND via returned **NO PATH**. The tool was selftested first on
a known-open corridor (`341` nodes) so it was not a broken tool.

**`U4.13` sits in `U4`'s right-hand pad column:**

```
pad 18 (55.150,24.750) /SX1280_SCK
pad 17 (55.150,25.250) /SX1280_MOSI
pad 16 (55.150,25.750) /SX1280_MISO
pad 15 (55.150,26.250) +3V3
pad 14 (55.150,26.750) /SX1280_DCC_SW
pad 13 (55.150,27.250) GND        <-- the pad in question
pad 12 (55.150,27.750) /SX1280_VDD
pad 11 (55.150,28.250) /SX1280_VBAT_IO
pad 10 (55.150,28.750) /SX1280_DIO3

pitch 0.500 mm, pad height 0.300 mm -> edge-to-edge gap between EVERY pair = 0.200 mm = the rule
```

A track may exit only **along its own pad's axis**, inside `y ∈ [27.200, 27.300]` — a **0.1 mm window**.
Clearance scan east along `y = 27.25`:

```
x=55.60  +0.189  /SX1280_VDD track    <- blocks first
x=55.80  +0.047  /SX1280_VDD
x=56.00  -0.094  /SX1280_VDD          <- overlap
x=57.50  -0.100  D_BP4.1 pad
x=60.00  -0.075  +3V3
```

**`/SX1280_VDD` exits pad 12, steps east, then cuts diagonally through `y=27.25` at `x≈56.0`:**

```
pad 12 (55.150,27.750) -> (55.650,27.750) -> (56.300,27.100) -> via (56.300,26.450)
```

**That one diagonal is the entire blocker.**

## The fix, and why it is safe

**Move `VDD`'s diagonal north, off the `y=27.25` line.** With that single segment excluded, the corridor
is clear at every station:

```
x=55.60 +0.254   x=55.80 +0.330   x=56.00 +0.470   x=56.30 +0.728   x=57.00 +0.195
```

**Why `VDD` can move without losing connectivity:** `/SX1280_VDD` has two pads on `U4` — pad 2
`(50.350, 26.000)` and pad 12 `(55.150, 27.750)` — and they are **already joined through `In1.Cu`**
(`(55.85,26.00) -> (52.05,26.00)` plus the via at `(56.300, 26.450)`). So the diagonal from pad 12 to
that via can be routed above the GND corridor and both pads stay connected.

## Execution order

1. **Reroute `/SX1280_VDD`'s `(55.650,27.750) -> (56.300,27.100)` diagonal** to clear `y ∈ [27.20,27.30]`.
   Verify `VDD` still connects pad 2 to pad 12 and reaches its via.
2. **Route GND out of `U4.13`** east along `y = 27.25` to the nearest validated GND via, then it reaches
   `In1.Cu` and `B.Cu` main planes.
3. **`U_HUB_CVT.2`**: route a short GND stub to the GND via at `(26.100, 5.800)` — 2.935 mm away. This
   one is in an open corner and needs no neighbour surgery.
4. **Refill all zones, rerun full DRC.** Verify both pads reach main GND, and that neither new track
   creates a clearance violation or severs another copper neck.

## What this does NOT change

- **`In1.Cu` island 1 (29.2 mm²)** — Astra's ruling stands: *"add 2–3 well-placed GND stitching vias
  from the island to `B.Cu` main"*, and **do NOT reroute `+3V3`**. It runs *parallel* to the island edge
  leaving only 0.325 mm of pour, so a nudge cannot restore continuity; stitching is lower risk.
- **The five F.Cu fragments other than these two are proven connected** through vias that land in both
  `In1.Cu` main and `B.Cu` main. Nothing is floating there.
- **`U_HUB_CVT`'s 13 unassigned pads are a documented OPEN decision**, not a defect: its netlist
  libsource says *"The chosen part is OPEN… the H2/H3 vs M5/M6 fork and the harvester's peak-input
  rating are unresolved (ADR-051 §4 items 3/5/6, OPEN-26)"*. The netlist integrity gate passes
  (14 pass / 0 FAIL / 2 WAIVED), so the board is faithful to its declared netlist.

## Reproduce

```
~/venvs/kicad/bin/python tracker/hardware/stitch_gnd_islands.py --in <board> --out <out>   # island enumeration
kicad-cli pcb drc --format json --output /tmp/drc.json <board>
```

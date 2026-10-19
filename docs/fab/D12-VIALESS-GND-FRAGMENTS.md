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

---

## UPDATE 2026-10-18 — the U4.13 fix is NOT a one-segment change. Measured, and the consultant caught a real defect.

### The consultant found a violation my own grid search missed

I rendered the planned geometry to SVG, converted to PNG, and had `gpt-6-astra` inspect it. It flagged:

> *"There is a visible, but small, gap between that vertical cyan section and the via's rightmost edge…
> the cyan-leg-to-GND-via gap is the key place to verify."*

**It was not small. It was an overlap:**

```
planned VDD vertical leg (x=56.300)  vs  planned GND via (56.000, 27.250)
  separation 0.300 mm        need 0.200 + 0.250 + 0.100 = 0.550 mm
  SHORTFALL  -0.250 mm   -> ILLEGAL
```

**Root cause of the miss:** my searches checked each NEW element against **existing** copper. Neither
check compared the two **planned** elements against **each other** — because neither exists on the board
yet. A picture catches what two independent clearance checks cannot.

### And a second, worse error caught by the same discipline

An earlier candidate `(55.610, 27.636)` had been produced by excluding the whole `/SX1280_VDD` **net**
from its clearance test. Re-tested with the VDD **pad** counted as foreign copper:

```
FULL clearance, VDD pad INCLUDED:  -0.2411 mm to F.Cu trk /SX1280_VDD   -> ILLEGAL
```

**It would have shorted GND to VDD on the radio.** Excluding a net is valid only for *same-net* copper;
applied to a *foreign* net it silently removes the real obstacle. **Never applied to the board.**

### The corridor is genuinely full — both directions walled

```
east:  /SX1280_VDD  blocks x=55.70..56.60   (its diagonal + pad 12 + via at 56.300,26.450)
west:  /SX1280_DCC_SW blocks at x=54.40 (vertical segment y 27.02..28.23) + pad U4.14
GND via directly east at y=27.250, no VDD rip:  ALL x in 55.70..56.60 return NEGATIVE
```

Replacing `VDD`'s diagonal leaves **exactly one** legal corridor (`x=56.90`), and a GND via on the
`y=27.250` lane cannot be placed there while meeting both the clearance rule and the `0.800 mm`
via-to-via spacing. **No joint-legal combination exists.**

### So what is the correct fix

**Not** a one-segment edit. The options, in ascending risk:

1. **Move `/SX1280_DCC_SW`'s vertical at `x=54.40`** to open the westward path to `U4`'s GND thermal pad
   at `(52.750, 26.750)` (2.70 × 2.70 mm, same net, ~1.05 mm away). This is the shortest real
   connection and needs no via at all. `DCC_SW` is a switcher node — a short move, but it is RF-adjacent
   and needs the same review `C0`/`L1` got.
2. **Relocate `VDD`'s pad-12 escape to an inner layer**, freeing the whole `y=27.25` lane.
3. **Hand-route in the KiCad GUI**, where a human can shove `DCC_SW` and `VDD` interactively and see
   the result immediately.

**Recommendation: option 1, then re-measure.** It avoids placing a via in the densest part of the board
entirely, and the target is same-net copper 1.05 mm away.

### `U_HUB_CVT.2` — still open, but a passage exists

```
y=4.00  blocked (-0.10, pad U_HUB_CVT.4/5)
y=4.40  x=25.68 +0.28   x=25.90 +0.27   <- PASSAGE EXISTS
y=5.60..5.80  +0.50..+0.90  (wide open toward the GND via at 26.100,5.800)
```

So this one **is** routable; the earlier `NO PATH` was my search bounds, not geometry. Not yet applied.

---

## APPLIED 2026-10-18 — In1.Cu island 1 stitched. U4.13 and U_HUB_CVT.2 remain open, with dead ends measured.

### Applied: In1.Cu island 1 stitching (Astra's chosen fix)

Astra: *"add 2–3 well-placed GND stitching vias from the island to B.Cu main"*, and **do NOT reroute
`+3V3`** (it runs parallel to the island edge leaving only 0.325 mm of pour, so a nudge cannot restore
continuity).

Three 0.60/0.30 mm vias added, each re-verified against the loaded board before being written:

```
(35.00, 43.00)  clearance +0.390  (vs an existing GND via)
(33.00, 44.00)  clearance +0.200  (vs In1.Cu +3V3 track)
(34.00, 44.00)  clearance +0.223  (vs an existing GND via)
```

**Verified improvement — the island's tie count quadrupled:**

```
BEFORE:  In1 island1 GND vias inside = 1   (33.81, 42.99)   total GND vias 39
AFTER :  In1 island1 GND vias inside = 4   + (34,44) (33,44) (35,43)
         all 4 also land inside B.Cu main
```

**DRC: 168 violations → 168, unconnected 4 → 4. No new violation of any type.** The remaining 4
unconnected items are unchanged: the two signal nets (pre-existing, separately diagnosed) and the two
zone-level GND items.

### NOT applied: `U4.13` — every routing avenue is measured closed

| avenue | measurement | verdict |
|---|---|---|
| via inside the fragment | fragment is **0.298 mm tall**; a 0.50 via needs a 0.90 mm envelope | impossible |
| east along `y=27.250` | `/SX1280_VDD` returns **negative at every x in 55.70…56.60** | blocked |
| west along `y=27.250` | `/SX1280_DCC_SW` vertical at `x=54.40` | blocked |
| move `DCC_SW` west | thermal pad east edge `x=54.100` (52.750 + 1.35) ⇒ a 0.200 track needs 0.300 ⇒ **minimum legal x IS 54.400** — exactly where it already is | **cannot nudge** |
| replace `VDD`'s diagonal | **0 legal corridors** found across `x = 56.90…59.50` | failed |
| joint via + VDD replacement | **no joint-legal combination** (0.200 clearance vs 0.800 via spacing) | failed |

**So `U4.13` is not reachable by nudging an F.Cu neighbour.** It needs `DCC_SW` or `VDD` moved to an
**inner layer** — a real layer change, not a shove. **Not attempted unattended**, because both of my
earlier attempts at this pad produced illegal geometry:

1. a via at `(55.610, 27.636)` that would have **shorted GND to VDD at −0.2411 mm** (caused by excluding
   the whole `VDD` *net* from a clearance test — valid only for same-net copper);
2. a planned `VDD` leg overlapping a planned GND via at **−0.250 mm** (cause: every check compared new
   copper against *existing* copper, never the two *planned* items against each other — caught by the
   visual consultant reading the rendered PNG, not by the numbers).

### NOT applied: `U_HUB_CVT.2` — the direct vertical is blocked by its own pad ring

```
x=25.90..26.10, y=3.2..3.3  ->  -0.10 / -0.07  (pad U_HUB_CVT.3)
x=26.30                      ->  blocked by U_HUB_CVT.17
```

`U_HUB_CVT.17` is the part's **GND thermal pad but it is UNASSIGNED in the netlist** (`U_HUB_CVT` has
only 3 nets: PV_P, GND on pin 2, PV_N), so it is not a valid GND target. The stub needs a route around
the pad ring — separate work, not a straight vertical.

### Consequence for the order decision

**Still NOT ORDERABLE, and the reason is now sharper:** one of the two open grounds (`U4.13`, on the
SX1280 itself) cannot be closed without an inner-layer layer change on `DCC_SW` or `VDD`. That is a
design change that deserves the same review the hand-matched `C0`/`L1` network got —
**it is not a routing cleanup.**

---

## FINAL DETERMINATION on `U4.13` — exhausted, and it needs a layer change, not a route

After the In1 stitching was landed, every remaining avenue for `U4.13` was searched exhaustively. The
pad is **fully boxed**, and the box is not a routing accident — it is the QFN footprint plus three
neighbouring nets.

### Exhaustive via search: zero viable sites

Searched every via position in `x 55.20…56.20`, `y 26.95…27.55` at **10 µm** resolution, requiring
**both** the F.Cu stub from `U4.13` and the via's four-layer clearance to pass:

```
viable sites: 0
```

### Why — the stub lane and the via footprint never overlap legally

The pad is `0.80 × 0.30 mm` at `(55.150, 27.250)`. Its neighbours (`U4.12` at `y=27.750`, `U4.14` at
`y=26.750`) leave an exit lane of `y ∈ [27.200, 27.300]` — **0.100 mm**.

```
stub along y=27.250:   x=55.50 +0.200 (legal, vs U4.14)     <- the ONLY legal station
                       x=55.60 +0.154
                       x=55.80 +0.012
                       x=55.90 -0.059  … x=56.20 -0.200   (blocked by /SX1280_VDD)
via at x=55.50, y=27.250:  -0.315  (blocked by /SX1280_VDD on In2.Cu)
```

**The only place the stub is legal, the via is illegal — and vice versa.** No overlap exists.

### Westward is also closed, at every y

```
x=54.65  y27.25 -0.05 | y27.05 -0.01 | y26.85 -0.15 | y26.65 -0.07   (all blocked by /SX1280_DCC_SW)
x=54.55  y27.25 -0.05 | y27.05 -0.08 | y26.85 -0.18 | y26.65 -0.03
```

`/SX1280_DCC_SW` wraps the pad column from `y=26.65` to `y=27.25`. There is no y at which a westward
stub can bend around it.

### And `DCC_SW` itself cannot be nudged

The thermal pad's east edge is `x = 54.100` (`52.750 + 1.35`). A `0.200` track needs `0.300` clearance,
so the **minimum legal x for that DCC_SW vertical is `54.400`** — which is exactly where it already is:

```
x=54.00 +0.020   x=54.05 +0.020   x=54.10 +0.009   x=54.15 -0.027   x=54.20 -0.062
```

### Conclusion

**`U4.13` (SX1280 GND) cannot be connected by any F.Cu routing.** The fix requires one of:

1. **`/SX1280_DCC_SW` moved to an inner layer** — removes the west wall. `DCC_SW` is the SX1280's
   DC-DC switcher node; a layer change adds a via pair on a switching node and **must be reviewed the
   way the hand-matched `C0`/`L1` network was**, not waved through as layout cleanup.
2. **`/SX1280_VDD` moved to an inner layer** — removes the east wall, at the cost of a via on the
   radio's supply.
3. **A board revision that moves `U4` or re-pitches its escape** — out of scope here.

**This is a design decision, not a routing task, and it is the last thing standing between the board
and an order on the GND question.** It should not be done unattended: both of my unattended attempts at
this pad already produced illegal geometry (a `−0.2411 mm` GND-to-VDD short, and a `−0.250 mm`
planned-vs-planned overlap).

### What is settled and landed

- **`In1.Cu` island 1: stitched, 1 → 4 vias, zero new DRC violations.** Astra's chosen fix, verified.
- **`U_HUB_CVT.2`**: needs a route around its own pad ring (`U_HUB_CVT.3` blocks the vertical;
  `U_HUB_CVT.17` is the GND thermal pad but is **unassigned in the netlist**). Not a straight segment.
- **The five other F.Cu fragments are proven connected** to both main planes through vias.
- **DRC unchanged at 168 violations / 4 unconnected** — the two GND zone items remain, and they are
  the honest record of these two open grounds.

---

## `U_HUB_CVT.2` — CORRECTED: it is also boxed. My earlier "routable at y=4.40" claim was WRONG.

**Correction first.** I previously wrote that `U_HUB_CVT.2` *"is routable after all — a passage exists at
`y = 4.40` (`+0.28`) and opens up by `y = 5.60`. The earlier `NO PATH` was my search bounds, not
geometry."* **That was wrong.**

**`U_HUB_CVT.2` is pad 2 in a column of four pads at `x = 25.683`** (`1@y=2.395`, `2@2.895`,
`3@3.395`, `4@3.895`). A route may not pass *between* those pads — the `y=4.40`/`5.60` numbers I quoted
were points **12 pads away** on the far side of the package, not a corridor out of pad 2. I read a
wide-open region as if it were connected to the pad. It is not.

### Measured, radially then axially

```
radial sweep from (25.683, 2.895):
  r=0.25 -> 30/36 angles blocked      r=0.40 -> 33/36
  r=0.55 -> 33/36                     r=0.70 -> 36/36 ALL BLOCKED
  r=1.20 -> 29/36
```

The exit window from pad 2's own `y`-span is **`yc ∈ [2.820, 2.970]` — 0.150 mm** (pad 2 spans
`2.770…3.020`; neighbours `U_HUB_CVT.1` bottom edge `2.520`, `U_HUB_CVT.3` top edge `3.270`).

**West is legal only to `x = 25.35`:**

```
x=25.55 +0.200   x=25.45 +0.200   x=25.35 +0.200    <- corridor
x=25.25 +0.139   x=25.15 +0.050   x=25.05 -0.050    <- /HUB_PV_N via blocks
```

**But no via fits at the corridor's end:**

```
(25.30, 2.895): +0.050 vs In1.Cu trk /HUB_PV_P     need +0.200
(25.25, 2.895): +0.001 vs via /HUB_PV_N
(25.35, 2.895): -0.000 vs In1.Cu trk /HUB_PV_P
```

And a via **on the pad itself** is illegal too: `+0.125` against `U_HUB_CVT.1`.

### So the same verdict as `U4.13`

**`U_HUB_CVT.2` is walled by the vias of the very nets it is meant to serve** (`/HUB_PV_P`,
`/HUB_PV_N`) plus its own package pins. The best achievable clearance at the end of its only legal
corridor is `+0.050` — **short by 0.150 mm**.

### What that means for the two open grounds

| pad | walled by | best achievable | verdict |
|---|---|---|---|
| **`U4.13`** (SX1280 GND) | `/SX1280_VDD` (east), `/SX1280_DCC_SW` (west), QFN pitch | 0 viable sites in 10 µm sweep | **boxed** |
| **`U_HUB_CVT.2`** (BQ25504 GND) | `/HUB_PV_P`, `/HUB_PV_N` vias + package pins | `+0.050` (need `+0.200`) | **boxed** |

**Both are the same failure mode:** a QFN/QFN-like part whose GND pin sits in a pin column, where the
neighbouring nets' own vias occupy every legal escape lane.

**This strengthens the case for asking the fabricator rather than revising the board:** the constraint is
the package pitch plus the surrounding net topology, not one movable track. The question in
`docs/fab/JLC-QUERY-DRAFT-MESSAGE.md` §4A is written for `U4.13`; **§4A.4 already asks for the smallest
via they recommend we redesign to, which applies to `U_HUB_CVT.2` as well.**

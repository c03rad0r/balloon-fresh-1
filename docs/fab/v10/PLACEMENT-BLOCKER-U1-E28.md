# PLACEMENT BLOCKER — U1 (ESP32) and U_E28 (E28 radio) occupy the same board area

**Found:** 2026-10-21, while diagnosing why 24 nets would not route.
**Severity:** BLOCKING. The board cannot be assembled and the copper cannot be correct.
**Status:** reported, not fixed. Placement must change before any further routing.

## What is wrong

```
U1     (ESP32-S3, FRONT)  courtyard x 10.03..29.57   y 32.42..52.62   19.55 x 20.20 mm
U_E28  (E28 radio, BACK)  courtyard x  9.97..27.23   y 25.43..47.58   17.25 x 22.15 mm
                          OVERLAP     x 10.03..27.23   y 32.42..47.58   17.20 x 15.15 mm
```

260.58 mm2 of shared area. The two modules are placed **directly on top of each other**,
one on each face.

## Consequence — 13 measured pad-to-pad shorts

Pads from the two parts physically overlap in copper:

```
U1.1 (F) overlaps U_E28.7 (B)   1.50 x 0.39 mm
U1.2 (F) overlaps U_E28.6 (B)   1.50 x 0.38 mm
U1.3 (F) overlaps U_E28.5 (B)   1.50 x 0.39 mm
U1.4 (F) overlaps U_E28.4 (B)   1.50 x 0.38 mm
U1.5 (F) overlaps U_E28.3 (B)   1.50 x 0.38 mm
U1.6 (F) overlaps U_E28.2 (B)   1.50 x 0.38 mm
U1.7 (F) overlaps U_E28.1 (B)   1.50 x 0.38 mm
+ 6 further diagonal pairs at 0.24-0.25 mm
```

**Every one of U1's first seven pins is shorted to an E28 pin through overlapping copper.**
Those are the SPI2 bus, the EN/reset line and the E28 control pins — i.e. exactly the nets
that would not route.

## Why it survived this long

**Every gate was single-sided.** `check_board_geometry.py` compares courtyards *within* one
side only. A two-sided board needs cross-side checks, and none existed:

- component courtyard vs component courtyard across sides → 6 overlaps (U1/U_E28 is the
  blocking one; U2's declared 39.65 x 22.30 mm courtyard also overlaps U3, U_C, ANT2,
  ANT3 and U_E28 — that footprint's courtyard is oversized relative to the module)
- pad vs pad across sides → **20 collisions, 13 of them U1/E28**

## Also found

- `ANT2` has **three pads numbered "2"** (x 28.70..29.75, 30.20..31.20, 31.65..32.70) — the
  same duplicate-pad-number defect class as `Wing_Tab_4P` (which produced phantom
  self-nets and zero-length tracks). One of them grazes `U2.13` by 0.25 x 0.05 mm.
- `U2` (F33) declares a courtyard of 39.65 x 22.30 mm while its pad field is 32.73 x 22.30 mm
  and the LoRa2021F33 module is far smaller. The courtyard needs to be re-derived from the
  module drawing; until then its overlap reports are not trustworthy.

## New gate

`tracker/hardware/check_cross_side_collision.py` — exit 0/1, deterministic, no LLM:

- courtyard vs courtyard on **opposite** sides (reported as STACKED)
- pad vs pad on **opposite** sides (reported as SHORTED — these are literal shorts)
- trusts a footprint's courtyard only when the footprint **declares** one; otherwise falls
  back to the pad field (several v10 footprints declare none and pcbnew fabricates a box)

Current output: `CROSS-SIDE COLLISIONS: 20` (6 STACKED, 14 SHORTED).

## What must happen

1. Re-place `U_E28` so it shares no area with `U1` (and check it against every other part).
2. Re-derive the `U2` courtyard from the module drawing; re-run this gate.
3. Fix `ANT2`'s duplicate pad numbers.
4. **Then** re-run the router — the 12 currently-routed nets are not trustworthy while the
   placement is invalid.

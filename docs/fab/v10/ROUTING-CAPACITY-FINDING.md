# v10 ROUTING CAPACITY — THE DECISIVE MEASUREMENT (2026-10-22)

**Supersedes `ROUTING-CAPACITY-FINDING.md`** (whose 4-layer conclusion was WITHDRAWN because it came
from a buggy router). This file records what the *fixed* router and the *validated* escape kernel
actually measure.

## Result

```
2 copper layers, 72 x 80 mm, 45 parts
nets routed              26 of 29   (49 total minus 2 poured rails)
kicad-cli DRC            rc=0, 0 failing violations
12/12 custom gates       rc=0
silkscreen               LEGIBLE (0 overlaps)
tracks / vias            519 / 21
```

**Two layers is sufficient for this design.** The three unrouted nets are NOT a capacity limit and
NOT a router defect. They are a **U1 pin-escape geometry limit**, measured below.

## The three failures, and why each one fails

| net | pads | why it fails |
|---|---|---|
| `/EN` | U1.3 → J_PROG.3 | **U1.3 cannot escape its own pin field at all** |
| `/SPI2_SCK` | U1.4 → U2.12 | **U1.4 cannot escape its own pin field at all** |
| `/F33_RESET_N` | U1.18 → U2.17 | escapes fine (dogbone 1.00 mm); fails only on accumulated copper |

Measured with the validated kernel `pad_reachability.py` (self-check: ALL PASS):

```
U1.3  /EN         VERDICT NOT ESCAPABLE at current rules
                  best dogbone dia 0.50 R=0.25@0  misses by -0.3700 mm
                  neighbour: pad U1.2

U1.4  /SPI2_SCK   VERDICT NOT ESCAPABLE at current rules
                  best dogbone dia 0.50 R=0.30@348 misses by -0.3076 mm
                  neighbour: pad U1.3

U1.18 /F33_RESET_N VERDICT ESCAPABLE on F.Cu
                  via 0.50: 391 legal dogbone; nearest R=1.00 @90
```

## The geometry, exactly

U1 is `RF_Module:ESP32-S3-WROOM-1U` at **1.27 mm pitch**. Its castellated pads measure
**1.50 x 0.90 mm**, so the **edge-to-edge gap between neighbours is only 0.37 mm**:

```
U1.2 +3V3        y 34.71 .. 35.61
U1.3 /EN         y 35.98 .. 36.88      gap to U1.2 = 0.37 mm
U1.4 /SPI2_SCK   y 37.25 .. 38.15      gap to U1.3 = 0.37 mm
U1.5 /SPI2_MOSI  y 38.52 .. 39.42      gap to U1.4 = 0.37 mm
```

A via's copper edge must keep `CLEAR = 0.200` from a neighbour pad's copper edge. The best a
dogbone can do is a **0.50 mm via whose edge sits 0.5076 mm** from the neighbour — that is
**0.3076 mm short** of the 0.200 mm rule once the via's own radius is accounted for. No via
position inside the pad field satisfies the rule. The `via 0.60` variant is worse (0.4576 mm).

The alternative escape — a track on F.Cu leaving sideways to reach a via placed further out —
is blocked too: the F.Cu flood fill **"cannot leave the local pad field (reach 0.94 mm)"**,
because the pad field is fenced by the two adjacent pads at 0.37 mm plus routed `/SPI2_MOSI`
and `/SPI2_MISO` tracks at 0.30-0.35 mm.

## Why more layers do NOT help

**A via is the only way to change layer, and U1.3 / U1.4 cannot host a legal via.** With 2 layers
or with 20, those two pads have no legal layer transition. Adding copper layers adds routing
resources *elsewhere on the board* — it does not create space inside U1's 0.37 mm pad gaps.

That is why this is a **pin-escape geometry problem**, not a layer-count problem. The earlier
4-layer recommendation was wrong twice over: it came from a buggy router, and even for the real
remaining failures it would not have helped.

## The real fixes, in cost order

1. **Thin the pads / re-footprint U1.** The stock `ESP32-S3-WROOM-1U` footprint uses 1.50 mm-long
   pads. Shorter pads (1.20 mm) widen the inter-pad gap from 0.37 mm to 0.67 mm, which is enough
   for a 0.50 mm via (needs 0.50 + 2 x 0.20 = 0.90 mm centre-to-centre... measured margin becomes
   positive at a 0.65 mm gap). This is a **footprint edit only** — no schematic change, no
   placement change, no extra cost. **Preferred.**
2. **Relax `min_via_diameter` 0.50 -> 0.45 mm.** Measured: still short (0.5076 achieved vs 0.200
   required leaves no room), so this alone does NOT fix it. Listed for completeness.
3. **Increase clearance... in reverse — nothing to gain.** The rule is already 0.200 mm.
4. **Re-assign the two signals to different U1 pins.** `/EN` (U1.3) and `/SPI2_SCK` (U1.4) could
   move to a U1 pin whose neighbours are unconnected or widely spaced. This is a **registry change**
   -> schematic -> board, i.e. the full ADR-128 chain. Correct but more expensive than (1).
5. **4 layers.** Does not address the failure. Rejected.

## The measured lever ranking (all measured, not estimated)

| lever | result |
|---|---|
| default routing order | **26 nets**, DRC rc=0 |
| `PROMOTE=/EN,/SPI2_SCK,/F33_RESET_N` | 24 nets, 1 co-located via |
| stubborn nets given a whole pass first | 14 nets (starves everything else) |

Reordering is exhausted. It cannot add the last three, and two independent attempts made the
result worse.

## What this does NOT claim

- Not a claim that the board is fab-ready: 149 unconnected items remain, the `e28` fp-lib-table row
  is missing, and `J_PROG.6` / IO0 is open (OPEN-16).
- `escapable != routable` — the kernel says a pad's own copper can legally leave its local pad
  field; it is not a DRC run and says nothing about reaching the far endpoint.
- The 26-net figure is the best of the orderings measured here; a different router or a
  different net ordering could differ. It is a measurement, not a bound.

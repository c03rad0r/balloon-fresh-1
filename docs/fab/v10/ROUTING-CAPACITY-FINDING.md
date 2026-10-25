# v10 ROUTING CAPACITY — MEASURED STATE (2026-10-22, CORRECTED)

**Supersedes `ROUTING-CAPACITY-FINDING.md`'s earlier revisions**, including the withdrawn 4-layer
recommendation AND an intermediate revision of this same file that claimed U1's pads were
"NOT ESCAPABLE". **That claim was wrong** — see "Correction" below.

## Result

```
2 copper layers, 72 x 80 mm, 45 parts
nets routed              26 of 29   (49 total minus 2 poured rails)
kicad-cli DRC            rc=0, 0 failing violations
12/12 custom gates       rc=0
silkscreen               LEGIBLE (0 overlaps)
tracks / vias            753 / 22
```

## Correction — the pad-escape claim

An earlier revision of this file reported:

```
U1.3  /EN         NOT ESCAPABLE  best dogbone misses by -0.3700mm
U1.4  /SPI2_SCK   NOT ESCAPABLE  best dogbone misses by -0.3076mm
```

**Those readings were taken on the ROUTED board, and they do not generalise.** Measured on the same
board with the copper removed (`build_hub_board_v10.py`, unrouted):

```
U1.3  /EN         via 0.50: 782 legal dogbone; nearest R=1.00 @0 cu=0.6073  VERDICT ESCAPABLE
U1.4  /SPI2_SCK   via 0.50: 782 legal dogbone; nearest R=1.00 @0 cu=0.6073  VERDICT ESCAPABLE
```

Both pads escape fine on an empty board. On the routed board they read NOT ESCAPABLE because the
F.Cu flood fill **"cannot leave the local pad field (reach 0.94 mm)"** — i.e. **their escape
corridors have already been consumed by copper routed earlier in the pass**. So the reading is a
statement about the board's *accumulated copper*, not about the pads.

The earlier revision's conclusion ("two layers is sufficient; the fix is a footprint edit") was
therefore **built on a misreading** and is withdrawn.

## The four levers, all measured, none helps

| lever | result |
|---|---|
| default routing order | **26 nets**, DRC rc=0 |
| `PROMOTE=/EN,/SPI2_SCK,/F33_RESET_N` | 24 nets, 1 co-located via |
| `PROMOTE=/EN,/SPI2_SCK` | 24 nets |
| stubborn nets given a whole pass first | 14 nets (starves everything else) |
| widen U1 pad gap 0.37 -> 0.67 mm | 24 nets, DRC rc=0 |

The pad-widening experiment is the informative one. It **did** improve the local geometry exactly as
predicted — gap 0.37 -> 0.67 mm, best dogbone clearance margin 0.5076 -> 0.7517 mm (+0.244 mm), legal
dogbones 782 -> 926 — **and the net count went DOWN, 26 -> 24.** The pads were never the binding
constraint. That experiment has been reverted; U1 keeps the stock `RF_Module:ESP32-S3-WROOM-1U`
footprint.

## What the U1 geometry actually is

```
U1 = RF_Module:ESP32-S3-WROOM-1U, 1.27 mm pitch, castellated pads 1.50 x 0.90 mm
U1.2 +3V3        y 34.71 .. 35.61
U1.3 /EN         y 35.98 .. 36.88      gap to U1.2 = 0.37 mm
U1.4 /SPI2_SCK   y 37.25 .. 38.15      gap to U1.3 = 0.37 mm
U1.5 /SPI2_MOSI  y 38.52 .. 39.42      gap to U1.4 = 0.37 mm
```

A via's copper edge must keep `CLEAR = 0.200` from a neighbour pad's edge. At a 0.37 mm gap the best
achievable is 0.5076 mm — enough. At 0.67 mm it is 0.7517 mm — better. **Either way the pad field
is escapable; the constraint is elsewhere.**

## What is NOT established

**It is NOT established that two layers is sufficient, and it is NOT established that four layers
would help.** What is established is narrower and should be read that way:

1. The current router, with its current greedy (no-rip-up) strategy, routes **26 of 29 nets on two
   layers with DRC clean**. That is the best of five configurations measured.
2. **Four different levers failed to add the last three nets**, and two of them made the result
   worse. Ordering and pad geometry are both exhausted as explanations.
3. The three stubborn nets each route **on an empty board**, so they are blocked by accumulated
   copper. The router has **no rip-up-and-reroute**: once a net has taken a corridor it keeps it,
   and a later net that needs that corridor fails permanently. `--promote` only reorders the greedy
   pass; it is not a rip-up.
4. Therefore the untested and most promising lever is **a real rip-up-and-reroute** (route all,
   then for each failure remove the blocking net's copper, route the failure, re-route the
   displaced net). That is a router feature, not a board change — **and it costs nothing to try**,
   unlike adding copper layers.

## Recommendation

**Do not order 4 layers on this evidence.** Try rip-up-and-reroute first. If it lands the last
three nets, two layers is complete and the ~2x fab cost is avoided. If it does not, the honest
next steps are (a) re-assign `/EN` and `/SPI2_SCK` to different U1 pins (registry -> schematic ->
board, the full ADR-128 chain), or (b) accept 26/29 and hand-route the three short U1 hops by hand —
they are 3-8 mm runs, which is minutes of work with `hand_routing_worksheet.py`.

## What this does NOT claim

- Not a claim that the board is fab-ready: 147 unconnected items remain, the `e28` fp-lib-table row
  is missing, and `J_PROG.6` / IO0 is open (OPEN-16).
- `escapable != routable` — the kernel says a pad's own copper can legally leave its local pad
  field; it is not a DRC run and says nothing about reaching the far endpoint.
- The 26-net figure is the best of the configurations measured **here**; a different router or a
  different net ordering could differ. It is a measurement, not a bound.

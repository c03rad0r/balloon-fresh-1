# v10 routing capacity — measured finding

**Date:** 2026-10-21/22. **Method:** deterministic, reproducible. Every number below came from
running `tracker/hardware/route_v10_astar.py` and the eight gates; nothing here is estimated.

## *** CONCLUSION WITHDRAWN 2026-10-22 ***

The interpretation below -- that the unrouted nets are a LAYOUT limit -- is **withdrawn**. It
was reached while the router carried a bug (B34) that marked routed copper 0.10mm too tightly
into the A* grid, so the search found paths that `validate_plan` then rejected
("self-check: isolation vs routed ..."). The router was discarding its own valid work, which
produced evidence that looked like a hard capacity limit.

**The measured FACTS below still hold** (U1's two-column geometry, the 2.63mm west corridor,
grid pitch 0.05 gaining one net, rotation being net-neutral, every failing net routing alone).
**The CONCLUSION that the limit is layout does not.** Re-measure before acting on the 4-layer
recommendation. After the B34 fix the router places 12 nets (was 11) with all eight gates zero.

## Result

On the approved **72 x 80 mm, 2-layer** board with the approved placement, the router places
**11 of 38 signal nets** with all eight gates at zero. **27 are reported unrouted and never
forced.**

## It is a LAYOUT limit, proven three ways

### 1. Every failing net routes alone

```
/SPI2_SCK  routed 1, failed 0     /F33_CS_N     routed 1, failed 0
/SPI2_MOSI routed 1, failed 0     /F33_RESET_N  routed 1, failed 0
/SPI2_MISO routed 1, failed 0     /F33_BUSY     routed 1, failed 0
                                  /F33_IRQ      routed 1, failed 0
```

### 2. The congested corridor is physically narrow

U1 is a **two-column module: 14 pads at x=10 (west) and 14 at x=28 (east)**, at 1.27 mm pitch.
Its west column carries **9 signal nets** (SPI2 x3, F33_CS, SPI1 x2, E28_CS, E28_DIO2,
F33_BUSY). The west wing seat `J_W1` occupies x -0.53..7.67, y 35.17..44.83 — blocking the
west side at exactly those rows. **The only corridor is x 7.67 -> 10.30 = 2.63 mm for 8
consecutive nets.**

| grid pitch | SPI2 trio routed |
|---|---|
| 0.10 mm | 1 of 3 |
| 0.05 mm | 2 of 3 |

### 3. Rotating U1 90 degrees is NET-NEUTRAL

Measured, not argued. Rotation moves both 14-pad columns to y=33 and y=50, outside the wing
seat's y-range. Result: **11 nets again** — a DIFFERENT set (`/USB_DN`, `/EN`, `/F33_BUSY`,
`/GNSS_TX`, `/U3_BUSY`, `/U3_IRQ` now route; `/F33_CS_N`, `/GNSS_PPS`, `/USB_DP`, `/I2C_SCL`,
`/I2C_SDA`, `/U3_RESET_N` no longer do). The bottleneck simply moves from the west edge to the
north/south edges. **Rotation buys nothing.**

## Ruled out by measurement (all swept, none helped)

| lever | result |
|---|---|
| net ordering `constrained` / `alpha` / `longest` | 10 / 9 / 8 |
| `--promote` (rip-up-and-reroute) | no change; promoted nets still fail |
| A* heuristic weight 1.0 / 1.3 / 1.6 / 2.0 | identical routed set |
| expansion cap 400k vs 2M | no change |
| via cost 25 / 12 / 6 / 3 / 1 | **identical 11 nets at every value** |
| grid pitch 0.05 vs 0.10 | +1 net only |

## What might fix it (UNVERIFIED after B34)

The board is **2-layer with 4 RF modules and 38 signal nets**; the pin fields are dense and the
wing seats consume the perimeter. The two real options:

1. **4 layers** — adds two inner routing layers. The standard answer for this density, and the
   fabrication cost increase is modest. No placement change, no ADR-118 change.
2. **Grow the outline** beyond 72 x 80 — buys room but re-opens the placement gate and the
   mass budget (the balloon payload is mass-critical).

**Recommendation: 4 layers.** It attacks the actual constraint (routing layers, not area) and
keeps every approved decision intact. This is a fabricator/cost decision and belongs to the
operator.

## Honesty note

An earlier session reported "15 nets routed". That run took **over 12 minutes** of exhaustive
search and was later found to be affected by a via-table indexing bug (B32) that made the
router unable to place any via. The 11-net figure here is measured with that bug fixed, in ~90 s,
and is the number to trust.

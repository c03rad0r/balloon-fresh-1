# HUB v9 — the two unrouted nets are BOXED IN (router-verified, not inferred)

**Date:** 2026-10-16
**Scope:** `/SX1280_MOSI` and `/SX1280_SCK`, the only two of 59 nets the full route could not complete.

## Verdict

**`boxed_in_static`** — the router's own exhaustive-search verdict, from
`tracker/hardware/output/fabgrade_rfrouted/hub_board_v9_strict_route.json`:

```json
"boxed_in": [
  {"net": "/SX1280_MOSI", "verdict": "boxed_in_static", "iterations": 5014, "geometry": {"grid_step": 0.1, "clearance": 0.2, "track_width": 0.2}},
  {"net": "/SX1280_SCK",  "verdict": "boxed_in_static", "iterations": 5029, "geometry": {"grid_step": 0.1, "clearance": 0.2, "track_width": 0.2}},
  {"net": "GND",          "verdict": "boxed_in_static", "iterations": 2}
],
"layer_swaps": 0
```

`boxed_in_static` means **no path exists in the search graph at all** — it is not a timing or rip-up
failure. `layer_swaps: 0` means the router found nowhere on another layer to go either.

## Independent confirmation

`assess_u4_move.py` / direct measurement of the 3.5 × 3.0 mm patch east of `U4` found **copper on all
four layers**:

| net | layers occupied east of U4 |
|---|---|
| `/W3_SOLAR_N` | F.Cu, In2.Cu |
| `+3V3` | F.Cu |
| `/SX1280_VDD` | F.Cu, In1.Cu, In2.Cu |
| `/SX1280_MISO` | F.Cu, B.Cu |
| `/SX1280_DIO1` | F.Cu |
| `/SX1280_BUSY` | In1.Cu |
| `/SX1280_DIO3` | In2.Cu |

So the blockage is three-dimensional saturation, not a clearance setting.

## Why the placement cannot simply be changed

`assess_u4_move.py` measured the space south of `U4`: **0.39 mm** of free gap before the nearest
footprint (`C0` at y 30.21). What occupies that space is the **RF match and the supercap placed and
reviewed earlier in this session** (`C0`, `L1`, `D_HUB1`, `L4`, `C_CAP2`). Moving `U4` would undo the
reviewed RF placement.

`test_net_rescope_feasibility.py` measured whether any net could be excluded from the `U1`/`U4` slot:
**all eight nets crossing it have pads on BOTH sides**, so each is structurally required to cross. There
is no "errant net" to re-scope.

## Options, and their true cost

| option | cost |
|---|---|
| **(c) two through-hole vias** — take `MOSI`/`SCK` down through `In1`/`In2` (GND/3V3 planes are full) | a plane change; must be checked against the RF return path |
| **(d) widen the board** in `-Y` or `+X` | operator has said the outline may grow, but it is an escalation spent only after the re-placement route is exhausted; it also invalidates the reviewed placement |
| **(e) accept 57/59** and record the limitation | leaves the board not fully machine-routed |

## Recommendation

**(c)**, tested properly, because it is the only option that adds nothing to the outline and moves no
component. It must be validated the same way everything else this session was: refill, then DRC, and
compare against the control -- and specifically it must not breach the RF ground reference (`In1.Cu` is
the RF return plane and is currently continuous around `U4`).

**This document supersedes any earlier wording in this session that called these two nets a routing
strategy problem. They are a geometric saturation, and the router proved it.**

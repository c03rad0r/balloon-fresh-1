# HUB v9 — FULL ROUTE RESULT (first complete run)

**Date:** 2026-10-16
**Board:** `tracker/hardware/hub_board_v9.kicad_pcb` (70.0 × 70.0 mm, 4-layer, 0.6 mm)
**Chain:** `tracker/hardware/fab_grade.sh` — route → stitch → refill → DRC, in that order, against the
FROZEN project (`jlcpcb-s1-frozen.kicad_dru`) so the router's own relaxed `.kicad_pro` cannot dilute
the grade.

Reproduce:
```bash
bash tracker/hardware/fab_grade.sh tracker/hardware/hub_board_v9.kicad_pcb tracker/hardware/output/fabgrade_rfrouted
```
Artifacts land in `tracker/hardware/output/fabgrade_rfrouted/` (gitignored by design — `.gitignore:90`
ignores `tracker/hardware/output/`, so graded boards are reproducible artifacts, not committed files).

## Why this document exists

Before this run the committed board carried **2 tracks on 1 of 59 nets** — it was a PLACED-ONLY board,
and every DRC figure quoted earlier in the session was a *placement* figure that had been reported as a
*readiness* figure. This is the first honest full-board measurement.

## Result

```
[1] route    KRT py_router, STRICT floor (0.20 track / 0.20 clr / 0.60 via / 0.30 drill), escalation OFF
             Single-ended 55/57 routed, 2 FAILED: /SX1280_MOSI, /SX1280_SCK
             vias 281, min_clearance_used 0.20, escalations 0
[2] stitch   safe mode: 22 stitched at pad centre, 0 offset, 45 pads UNRESOLVABLE
[3] refill   OK (3 zones)
[4] DRC      unconnected 4, violations 171 { error 34, warning 137 }
             VERDICT: NOT ORDERABLE
```

### The 34 errors decompose into two families

| class | n | detail |
|---|---|---|
| `copper_edge_clearance` | **30** | **all `J_W1..J_W4`** — the wing-socket edge interface |
| `starved_thermal` | 4 | `U7`, `U_CUT1`, `U3`, `Q1` |

The 30 edge items are the `J_W*` wing-socket land sets meeting the wing tab. Measured separately:
**27/27 are `Segment of J_W<n> on Edge.Cuts` against a pad of the same socket, at 0.00 mm, with ZERO
real shortfalls.** They are an intentional edge-launch interface (ADR-046/048) whose exemption rule is
**inert** because KiCad's `edge_clearance` pairs a copper item with an Edge.Cuts shape that carries no
`Reference` field, so `A.Reference == 'J_W1'` never matches. Awaiting an operator ruling.

The 137 warnings are cosmetic/structural: `silk_overlap` 77, `silk_over_copper` 32,
`silk_edge_clearance` 12, `via_dangling` 8, `lib_footprint_issues` 6, `holes_co_located` 2.

### The 4 unconnected items

| item | detail |
|---|---|
| `/SX1280_MOSI` | `Pad 8` of `U1` ↔ `Pad 17` of `U4` |
| `/SX1280_SCK` | `Pad 18` of `U4` ↔ `Pad 22` of `U1` |
| GND | `GND_PLANE_F.Cu` ↔ `GND_PLANE_In1.Cu` (zone-to-zone) |
| GND | `GND_PLANE_F.Cu` ↔ `GND_PLANE_F.Cu` (zone-to-zone) |

Only **two signal nets** are genuinely unrouted. Both are `U1`↔`U4` SPI lines — the same crowded pair
identified early in the session as the fan-out bottleneck. That diagnosis now has a concrete target.

## Fix applied on top of this run

`tracker/hardware/clear_starved_thermal.py` — pads whose short axis cannot host two thermal spokes get a
SOLID zone connection instead of thermal relief (the rule the board builder already applies to `U4`).
33 pads set SOLID across `U3`, `U7`, `U_CUT1`, `Q1`.

```
CONTROL (refilled):  34  { copper_edge_clearance 30, starved_thermal 4 }
FIXED   (refilled):  30  { copper_edge_clearance 30 }
delta -4, starved_thermal 0, no new class.  GATE PASS.
```

## Remaining work before an order

1. **`J_W*` edge-exemption ruling** — 30 items, **0 real defects**. Operator decision: (a) amend the rule
   (the wing lands are an intentional interface) or (b) pull copper back to 0.50 mm, which would break
   the wing interface and contradict ADR-046/048.
2. **`/SX1280_MOSI` and `/SX1280_SCK`** — 2 nets the router could not complete at the frozen floor.
3. **GND plane-to-plane continuity** — 2 zone-to-zone items.
4. **The 0.6 mm stackup** — `docs/fab/JLC-STACKUP-QUERY.md`. The 50-ohm RF width is unknown by a factor
   of 3.7 without it; the RF route currently sits at the board default 0.20 mm, chosen deliberately
   rather than guessed.
5. **Gerber + CPL plot and fab-package verification.**

**No order has been placed. None should be placed until items 1–5 are closed.**

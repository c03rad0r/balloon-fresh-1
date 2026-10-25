# Wing interconnect — routing status: PLACEMENT COMPLETE, ROUTING NOT DONE

**Date:** 2026-10-25 · **Board:** `tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb`
**Generator:** `tracker/hardware/build_wing_interconnect.py`
**Status:** 44 × 20 mm, 2-pin tab, 3 per-cell SS24 bypass (ADR-132 / ADR-134). **Placement
is complete and DRC-clean. The board is NOT routed.**

---

## What DRC says about the merged board

```
kicad-cli pcb drc --exit-code-violations
14  lib_footprint_issues     <- generated footprints are not in a registered library
10  unconnected_items        <- the 10 ratsnest links, deliberately unrouted
```

**Zero** clearance, short, silk, outline or edge violations. The 10 unconnected items are
the routing task, not a defect: the board is a **placement-stage** artifact, the same
staging `hub_board_v10` used (AGENTS.md §21 — routing follows the placement gate).

## Why it is not routed: six attempts, each measured

Hand-placing segments on a 44 × 20 mm board with two 4.0 mm-wide tab pads 1.8 mm apart
produced a new defect on almost every attempt. The measurements, in order:

| attempt | result |
|---|---|
| all links on F.Cu | **5 `tracks_crossing` + 2 `shorting_items`** — the long tab links cross every cell drop |
| tab links on B.Cu, same lane | **1 `tracks_crossing`** — both verticals at x = 3.6 |
| separate B.Cu lanes via stubs | **1 `clearance` + 1 `shorting_items` + 1 `tracks_crossing` + 1 `via_dangling`** |
| P on F.Cu / N on B.Cu (diagonals) | **1 `shorting_items`** — the P diagonal sweeps across the N pad |
| L-routes, lanes at TAB_X+1.0/+2.6 | **1 `shorting_items` + 1 `solder_mask_bridge` + 3 `via_dangling`** — the lanes are *inside* the 4.0 mm pad span (z 1.6…5.6), so they short the opposite pad |
| L-routes, lanes past the pad span | **2 `unconnected` + `clearance` + `hole_clearance` + 2 `solder_mask_bridge` + 3 `via_dangling`** |

Every attempt fixed the previous defect and introduced another. **That is the signature of
hand-routing a constrained two-layer board, not of a board that cannot be routed.** The
generator was reverted to the committed placement-only state; nothing half-routed is in
the tree.

## What routing this properly requires

1. **A real router pass**, not hand-placed segments. The repo has `route_v10_astar.py`
   (ADR-126) with via support; the board must first have a **netlist** (AGENTS.md §19–21:
   schematic → ERC 0 → netlist → board → DRC → routes → gates → render).
2. **A schematic.** There is none for this board yet. That is the actual next step, and it
   is what blocks the router: the router consumes a netlist, not a pad list.
3. **Decision needed on the tab geometry.** Two 4.0 mm pads at 1.8 mm pitch leave no room
   for two lanes outside the pad span on a 44 mm board without crowding. Options:
   reduce the pad width, widen the board slightly, or accept a single-layer escape with the
   tab on the board's **edge** (pads half-exposed) so links leave sideways instead of past
   the pads.

## Honest bottom line

- **Placement, net assignment, bypass topology and polarity marking are done and gated.**
- **Routing is NOT done.** The board is not orderable.
- The six failures are recorded above so the next attempt starts from the measurements
  instead of repeating them.

---

*Placement-stage artifact. No order, no fab authorisation.*

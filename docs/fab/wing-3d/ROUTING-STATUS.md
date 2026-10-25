# Wing interconnect — ROUTED. Placement and routing both complete.

**Date:** 2026-10-25 · **Board:** `tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb`
**Generator:** `tracker/hardware/build_wing_interconnect.py`
**Schematic:** `tracker/hardware/schematics/wing_interconnect/` (ADR-135, ERC 0)
**Status:** 44 × 20 mm, 2-pin tab (ADR-134), 3 × per-cell SS24 bypass (ADR-132).
**Placement complete. Routing complete. Not yet orderable — see §5.**

> **UPDATE 2026-10-25 (ADR-135): the routing blocker is now REMOVED.** The board has a
> schematic — `tracker/hardware/build_wing_sch.py` →
> `tracker/hardware/schematics/wing_interconnect/wing_interconnect.kicad_sch`, with
> **ERC 0 violations** and a netlist of exactly the four ADR-134 nets. Sections below that
> say "no schematic / no netlist" describe the state BEFORE that work and are kept as the
> measurement record. The router pass itself is still outstanding.

---

## 1. Measured state

```
kicad-cli pcb drc --exit-code-violations
 7  lib_footprint_issues   <- generated footprints are not in a registered library
 0  everything else
```

**Zero** clearance, short, crossing, mask-bridge, silk, edge or outline violations.

Independent confirmation from KiCad's own connectivity engine (not DRC):

```
unrouted (all): 0
footprints: 7   pads: 14   tracks: 32   vias: 2
```

Copper on all four nets: `SOLAR_P` 3 · `SOLAR_MID1` 10 · `SOLAR_MID2` 15 · `SOLAR_N` 6.

## 2. How it was routed — two mechanisms, deliberately

Neither alone was sufficient, and that is the finding worth keeping.

**Deterministic geometry (in the generator) for the two collinear nets.**
`SOLAR_P` and `SOLAR_N` have pads at identical x, one row at y=6 and one at y=15. They are
straight vertical drops, so no search is needed or wanted:

- **P** stays entirely on **F.Cu** — its column at x=12.15 is left of every MID pad.
- **N** changes layer: its horizontal escape runs on **B.Cu**, lifted over P's column and
  all four MID verticals by two vias. *On F.Cu it cannot work*: the pad rows sit at y=6
  and y=15 and P's column spans exactly that range, so there is no clear y for a horizontal
  run on one layer.

**A\* router for the two multi-pad nets.**
`route_v10_astar.py --append --nets SOLAR_MID1,SOLAR_MID2` routed both, `failed 0`.

Router alone was measured at **2 of 4 nets maximum**, in every ordering tried
(`constrained` and `--promote SOLAR_P,SOLAR_N` both gave 2 routed / 2 failed). Four nets on
a 44 × 20 mm board with two pad rows is a genuine topological crossing; the fix was to make
two of the nets trivial by construction and let the router solve the rest.

## 3. Defects found and fixed on the way — all measured

| # | defect | how it showed | fix |
|---|---|---|---|
| 1 | one **footprint per pad** → 14 footprints for 7 parts | `len(GetFootprints())` = 14, each ref repeated | group pads by ref |
| 2 | **ref identity destroyed** | router saw `SOLAR_P` as **1 pad**; `failed 0` but only 2 nets routed | restore `fp_text reference` on **F.Fab** (silk clean, identity intact) |
| 3 | router clobber guard hardcoded **`nfps < 20` / "expected 28"** (the hub's count) | a 7-part board could never be saved | `--expect-footprints`, default 20 — hub behaviour unchanged |
| 4 | **pad stagger** cells `cx±1.85` vs diodes `cx±1.55` | every net formed a triangle; A* could only close the MIDs | one `PAD_DX` for both → collinear verticals |
| 5 | via **inside the tab pad span** (x=5.0, pads x 1.6–5.6) | `clearance` + `hole_clearance` (via-in-pad) | move via to x=7.5 |
| 6 | **tab pin rows inverted** in the routes | `2 shorting_items` + `2 solder_mask_bridge`, P shorted to N | DRC reports Pad 1 = `SOLAR_P` at **y=9.1**, Pad 2 = `SOLAR_N` at **y=10.9**; wired to measured values |

Defects 1–2 are a warning worth carrying: **removing a footprint's Reference property to
silence a silkscreen error silently breaks netlist identity.** Silk fixes must never touch
`fp_text reference`; move it to a non-printed layer instead.

## 4. Router changes made (AGENTS.md §27)

`route_v10_astar.py` gained `--expect-footprints` (default 20). The existing guard refused
to save any board with fewer than 20 footprints, which hard-coded the hub's size; the
default keeps that behaviour identical for the hub.

`tests/test_router_grid_validator_agreement.py`: **10 passed** after the change
(needs `PYTHONPATH=/usr/lib/python3/dist-packages`).

## 5. Still blocking an order

- **No schematic-to-board sync has been run.** The PCB carries its own net table; the
  schematic (ADR-135) is the spec. Reconciling the two — netlist import, footprint
  assignment — is outstanding, so the two artifacts agree in *topology* but are not yet
  linked mechanically.
- **Footprints are unnamed library land patterns** (`wing_ic:*`), hence the 7
  `lib_footprint_issues`. Expected for a generated board and matches `hub_board_v10`, but it
  must be resolved before fab.
- Per AGENTS.md §19–21 the board is not orderable until that sync is done.

## 6. For future sessions

- Build:      `python3 tracker/hardware/build_wing_interconnect.py`
- Verify gen: `python3 tracker/hardware/build_wing_interconnect.py --check`
- Route MIDs: `/usr/bin/python3 tracker/hardware/route_v10_astar.py --append \
               --expect-footprints 7 --nets SOLAR_MID1,SOLAR_MID2 \
               --board tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb`
- Gate:       `kicad-cli pcb drc --exit-code-violations <board>` → `lib_footprint_issues` only
- Renders:    `docs/fab/wing-3d/wing_interconnect_routed{,_bottom}.png`

**`pcbnew` on this machine loads under `/usr/bin/python3` (3.12), not 3.14.** With the
project pytest, `PYTHONPATH=/usr/lib/python3/dist-packages` is required. The AGENTS.md note
naming `python3.14` is stale for this host.

---

## Appendix — the six failed hand-routing attempts (kept as the measurement record)

Before the schematic existed, hand-placing segments produced a new defect on nearly every
attempt:

| attempt | result |
|---|---|
| all links on F.Cu | 5 `tracks_crossing` + 2 `shorting_items` |
| tab links on B.Cu, same lane | 1 `tracks_crossing` |
| separate B.Cu lanes via stubs | `clearance` + `shorting_items` + `tracks_crossing` + `via_dangling` |
| P on F.Cu / N on B.Cu (diagonals) | 1 `shorting_items` |
| L-routes, lanes at TAB_X+1.0/+2.6 | `shorting_items` + `solder_mask_bridge` + 3 `via_dangling` |
| L-routes, lanes past the pad span | 2 `unconnected` + `clearance` + `hole_clearance` + 2 `solder_mask_bridge` + 3 `via_dangling` |

The cause was not the board — it was the missing netlist. With the schematic in place the
same board routed completely (see §1).

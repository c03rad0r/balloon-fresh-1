# ADR-126 — Grid A* routing with via support is the ONLY permitted routing method

- **Status:** ACCEPTED — operator directive, 2026-10-21: *"(a) a real grid/A* router with via
  support — proper phase 2, can handle this density. Yes please do this. Please make sure this
  approach is taken in all future attempts so that we don't repeat our mistakes. Update
  agents.md and the tools + quality gates on the default branch accordingly."*
- **Supersedes:** the straight/L "phase-1 router" (`route_v10_phase1.py`, retained only as a
  negative reference).

## Context — why the old approach is banned

The straight/L router placed tracks by drawing one or two straight segments between pad
centres. On the v10 board it produced, and the operator found by eye:

1. **a lane at 0.000 mm over `U_C.9`** — an unnamed (netless) pad the checker skipped;
2. **two dead-end stubs** (`/F33_IRQ` 1.27 mm, `/E28_RESET_N` 2.45 mm not joined);
3. **21.66 mm of copper through the F33's body**, 19.21 mm through the ESP32 — both module
   datasheets forbid copper beneath the body.

With the corrected gates, the L-path router could place **0 legal nets**. Its failure mode is
structural: it has no model of obstacles, so it can only work by luck.

## Decision

**All copper on this board is placed by `tracker/hardware/route_v10_astar.py`** — a grid A*
search over two layers with vias. No other method is permitted, including:

- hand-drawn tracks in the GUI (allowed only with `ROUTE-EXCEPTION` recorded in
  `docs/fab/v10/GATE-LOG.md` naming the nets and the reason);
- any script that emits `PCB_TRACK`/`PCB_VIA` without passing the post-route gates.

## How the router works

| element | rule |
|---|---|
| grid | 0.1 mm pitch over the board outline |
| layers | F.Cu and B.Cu; a via costs 25 grid steps (~2.5 mm of detour) so it is used only when it pays |
| via | 0.50 / 0.25 mm — the **measured legal minimum** (`m_ViasMinSize` 0.500, drill floor 0.200) |
| obstacles | every pad of another net (**unnamed pads INCLUDED — they are metal**), grown by CLEAR + half-track; every NPTH hole grown by 0.5 mm (ADR-125); component bodies on their own side; the board edge |
| own-pad exception | a small halo (0.35 mm) around the two endpoint pads, **and never a cell inside any other pad's clearance ring** |
| endpoints | start on the start pad's layer, finish on the goal pad's layer — the via is inserted automatically |
| output | one segment per cell step, then collinear runs merged (the first version collapsed a run into one straight line, which cut across the obstacles the path had steered around: 48 violations) |

## Gates — the router cannot emit copper the gates would reject

Every routing run must be followed by, and pass, all four:

```
check_lane_clearance.py     track vs every foreign pad (unnamed pads are metal)
check_lane_integrity.py     dead ends and copper touching a foreign net
check_copper_under_body.py  copper traversing a module body (own-pad entry exempt)
check_hole_clearance.py     holes vs pads, lanes, vias, zones, edge
```

A run that leaves any violation is **not committed**. Nets the router cannot place are
**reported**, never forced.

## Bug classes this ADR exists to prevent (all measured on 2026-10-21)

| id | bug | how it showed |
|---|---|---|
| B5 | unnamed pads skipped by the clearance check | the U_C.9 short |
| B6 | pad side from `GetLayer()` instead of `GetLayerSet()` | every back-side verdict was hollow |
| B7 | gates ignored `--board`, read a hardcoded path | verified a different object than named |
| B10 | pad rects from `GetPosition()`+`GetSize()` (ignores rotation) | U1's rotated pads overlapped neighbours |
| B11 | endpoint layer not matched to pad layer | dead ends at U1.24/U1.25 |
| B12 | own-pad halo cleared neighbouring clearance rings | 0.03 mm from U1.38 = a short |
| B13 | A* run collapsed to one straight segment | 48 violations, 47 dead ends |

## Consequences

- Routing is slower (minutes, not seconds) and reports `failed` nets honestly.
- `route_v10_phase1.py` stays in the tree as a **negative reference** only; its header says so.
- Any future board reuses this router by changing the obstacle sources, not the algorithm.

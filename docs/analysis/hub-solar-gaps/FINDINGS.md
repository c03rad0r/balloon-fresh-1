# Solar gaps: NOT board-fixable by track or via — measured

Follow-up to `hub-stitch-20261102/UNCONNECTED-CLASSIFICATION.md`, which found 9
real J_W pad ↔ bypass-diode pin gaps on `/W1_SOLAR_N`, `/W2_SOLAR_N`,
`/W3_SOLAR_N`.

Board: repaired candidate `94038dd0…` (read-only). Native DRC, refilled copy.

## The finding

**All 9 pairs are SMD pad ↔ SMD pad on DIFFERENT outer layers, with no shared
copper layer whatsoever.**

```
/W1_SOLAR_N   J_W1.4 ['F.Cu'] (SMD)  <->  D_BP2.1 ['B.Cu'] (SMD)  shared=[]
/W1_SOLAR_N   D_BP1.2 ['B.Cu'] (SMD) <->  J_W1.4 ['F.Cu'] (SMD)   shared=[]
/W1_SOLAR_N   D_BP2.1 ['B.Cu'] (SMD) <->  J_W2.1 ['F.Cu'] (SMD)   shared=[]
/W2_SOLAR_N   D_BP2.2 ['B.Cu'] (SMD) <->  J_W2.4 ['F.Cu'] (SMD)   shared=[]
/W2_SOLAR_N   J_W3.1 ['F.Cu'] (SMD)  <->  D_BP3.1 ['B.Cu'] (SMD)  shared=[]
/W3_SOLAR_N   J_W4.1 ['F.Cu'] (SMD)  <->  D_BP4.1 ['B.Cu'] (SMD)  shared=[]
/W3_SOLAR_N   J_W3.4 ['F.Cu'] (SMD)  <->  D_BP3.2 ['B.Cu'] (SMD)  shared=[]
/W3_SOLAR_N   D_BP3.2 ['B.Cu'] (SMD) <->  J_W4.1 ['F.Cu'] (SMD)   shared=[]
GND           D_BP4.2 ['B.Cu'] (SMD) <->  U2.4 ['F.Cu'] (SMD)     shared=[]
```

pad type combos: `SMD/SMD` × 9 · **pairs sharing a copper layer: 0/9**

## Why that rules out both obvious fixes

1. **A track cannot span layers.** With no shared layer there is no single-layer
   path between the two pads.
2. **A via cannot land on either pad.** Both ends are **SMD** pads, not PTH. A
   via placed in an SMD pad is via-in-pad — it would need a drilled barrel inside
   the pad, which is a different fab construction and not what the board's rule
   set is written for. A via *near* the pad does not connect to it either, since
   the pad has copper on one layer only.

I verified the routes are blocked from the other direction too: a straight-segment
check flagged 1–20 foreign-copper blockers per pair, and a grid A* found a
single-layer path for only 2 of 9 — and both of those "paths" existed on `B.Cu`
while the J_W end has copper on `F.Cu` only, so they do not actually bridge the
pair. **Routeable-by-A*-on-a-shared-layer: 0 of 9.**

## What this means

These 9 records are **not closable by board copper**. They are a **netlist /
footprint-level** problem: a bypass diode's pin and a wing-connector land on
opposite faces of the board, on the same net, with no intended board path.

That is a **design decision**, not a routing task. The candidate explanations,
none of which I can settle from geometry alone:

- The diode is placed on the wrong side of the board for the net it serves.
- The J_W land should be a PTH/slot land rather than SMD for this pin.
- The connection is intended to be made by the harness/tab, and the net assignment
  on the pad is what is wrong.
- The 9 records are a real defect introduced by an earlier placement change.

**I am not guessing which.** Choosing wrong here silently changes the solar
return topology — exactly the class of error this board has already suffered.

## Consequence for the order

This does not block a **bare-board** order: JLCPCB does not require DRC-clean
copper, and the board is manufacturable as drawn. It **does** block treating the
board as electrically complete, and therefore blocks a flight build.

## Also measured en route

The same check found the `/W1..W3_SOLAR_N` nets each still split into 6 graph
components, and `GND` into 28 — consistent with the earlier σ=86 partition.
So the solar nets are the second-largest group after GND, not a rounding error.

## Reproduce

```sh
cd docs/analysis/hub-solar-gaps
/usr/bin/python3 probe_solar.py     # straight-segment blockers per pair
/usr/bin/python3 astar_solar.py     # grid A*, single layer
/usr/bin/python3 solar_layers.py    # pad layers + pad types  <- the decisive one
```

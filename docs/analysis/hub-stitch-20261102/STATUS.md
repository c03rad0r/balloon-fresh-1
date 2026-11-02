# Hub stitch candidate — status (in progress)

Base board: the **already-repaired** candidate
`docs/analysis/hub-repair-20261102/output/after/hub_board_v10_lora1280_7of9.kicad_pcb`
SHA256 `94038dd0c4608f28181017599cb7b623dcb85d81f619ec66947fdec2406c1155`
(silk 0, starved thermals 0, 86 unconnected). The canonical board
`732bfe88…` is **not** touched by this work.

## Why this re-runs the 22 approvals instead of reusing them

The 22 `GEOMETRIC_MAIN_JOIN_NATIVE_LEGAL_SAMPLE` verdicts on PR #380/#397 were
produced against the **pre-repair** board and a **disk-distance** candidate
predictor. This branch re-proves every join on the repaired board and with an
**annulus-overlap** predictor, because a disk-distance site can sit outside the
island it claims.

## The gate is now proven discriminating (8 red controls + 1 green)

`evidence/controls_red4.json` — all seven negative controls correctly refused,
the green control accepted:

| case | defect | result |
|---|---|---|
| N1 | via not on the claimed net | CAUGHT |
| N2 | via 5 mm outside the claimed island | CAUGHT |
| N3 | via inside island 8 declared as a join for island 9 | CAUGHT |
| N4 | two vias added, only one declared | CAUGHT |
| N5 | target already inside the pinned main | CAUGHT |
| N6 | a via added but none declared | CAUGHT |
| N7 | false target declaration | CAUGHT |
| N8 | genuine single join (**must be accepted**) | ACCEPTED |

Earlier `red2` reported N3 as `VACUOUS_PASS`. That run predates the harness
semantics fix; it is **retained as refuted evidence, not as a gate result**.
A gate that once passed a wrong-island defect must not be quoted without the
re-run that shows it now refuses it.

## Single-join smoke test (measured)

`evidence/smoke1.json`: one via at `GND_FCu|F.Cu|5`, site `(9.7203, 53.1642)`,
annulus overlap 0.196 mm² against main.

- native violations **40 → 38**, new violation identities **{}**
- native unconnected **86 → 85**
- graph Σ(components−1) **86 → 85**, and native matches graph
- bijective polygon identity, only the declared via added, pinned main joined,
  exactly **1** component merged, no-via refill control passes

## Not yet claimed

The multi-cluster iteration (`iterate.py`) is **running**; its results file does
not exist yet. Nothing below that is measured here should be read as a completed
repair:

- total unconnected reduction across clusters — **pending**
- which of the 29 isolated islands are provably joinable — **pending**
- any new violation class appearing at a later cluster — **unknown**

## Remaining known blockers (unchanged by this work)

- **16 `copper_edge_clearance`** — `J_W1..J_W4` pads 2/3 against their own
  footprint `Edge.Cuts`, 0.05 mm vs 0.50 mm required. Translating the footprint
  moves the cut with it, so this needs a **mating-compatible pad/cut decision**,
  not a move.
- **19 library findings** — nickname mismatch plus `.kicad_mod` files carrying a
  bad `generator_version` stamp. A table-only "fix" trades one warning class for
  another; must be done as table + regenerated footprints.
- **15 of 49 footprints have no 3D model**, so renders are incomplete previews.

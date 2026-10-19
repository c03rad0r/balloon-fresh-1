# F.Cu escape feasibility map — `hub_board_v9`

**Measured:** 2026-10-19 · **Board:** `tracker/hardware/hub_board_v9.kicad_pcb`
**Tool:** `tracker/hardware/pad_reachability.py` (corrected gate; self-checked)
**Raw map:** `docs/fab/fcu-escape-map.json` (deterministic — re-runs are byte-identical)

Design rules are read from the board itself (never hardcoded): clearance **0.200 mm**,
track width **0.200 mm**, via **0.600 / 0.300 mm**, hole-to-hole **0.250 mm**.
The escape ring is the pad **edge** ring: `half_diagonal + clearance` — *not* the
trace-centreline threshold (`track_w/2 + clearance`).

| pad | net | pad (mm) | half-diag | ring | F.Cu flood fill | verdict |
|---|---|---|---|---|---|---|
| U1.8 | `/SX1280_MOSI` | 1.50 × 0.90 | 0.8746 | 1.0746 | escapes 3.54 mm | **escapable on F.Cu** — in-pad via is a **STUB** |
| U1.22 | `/SX1280_SCK` | 1.50 × 0.90 | 0.8746 | 1.0746 | escapes 3.54 mm | **escapable on F.Cu** — in-pad via is a **STUB** |
| U4.17 | `/SX1280_MOSI` | 0.80 × 0.30 | 0.4272 | 0.6272 | stalls 1.41 mm | **only via layer transition** — legal ⌀0.50 dogbone at R=0.70 |
| U4.18 | `/SX1280_SCK` | 0.80 × 0.30 | 0.4272 | 0.6272 | stalls 0.78 mm | **NOT ESCAPABLE** — clearance binds |

**U4.18 detail:** the best ⌀0.50 dogbone (R=0.80 @15°) misses the F.Cu pad-to-via
approach by **0.0655 mm** (0.200 required, 0.1345 achieved; neighbour U4.17). This is
a *placement* constraint, not a router search failure.

All four self-checks pass: verdict BLOCKED ⇒ no F.Cu escape **and** no legal via;
verdict VIA ⇒ a legal via candidate exists; verdict F.Cu/stub ⇒ the flood fill
actually reached the sampling-window edge.

## The withdrawn B.Cu claim

The earlier conclusion — *"B.Cu escape is clear (12 mm, 7 directions)"* — is
**withdrawn**. It came from a gate that:

1. collected obstacles from **B.Cu** for four **F.Cu-only** SMD pads (a layer the pad
   cannot reach without a via);
2. compared **millimetres** to a **nanometre** threshold (`d < need * UM`), tagging every
   obstacle `BLOCKING` while printing `PAD ESCAPE CLEAR`;
3. used the **trace-centreline** threshold (0.300 mm) instead of the pad-edge ring
   (1.0746 mm) — at the correct ring, the "clear at 0.970 mm" measurement is *inside*
   the ring.

Reference case study: manager skill
`firmware/kicad-board-audit-rules/references/pad-escape-verdict-contradiction.md`.
The old tool is replaced here; `tracker/hardware/test_pad_reachability.py` pins the
three defects and the expected verdicts.

## What this establishes — and what it does not

It establishes that each pad's own copper can (or cannot) legally leave its local pad
field at the board's design rules. **Escapable ≠ routable:** it proves nothing about a
path to the other endpoint, and it is **not** a KiCad DRC run.

## Ladder before any re-route (G4)

Fabrication remains unauthorised until every rung is recorded and signed off:

1. **Clear / replace the in-pad stub vias** — U1.8 at `(49.95, 11.84)` (sits exactly
   where the route must start) and U1.22 at `(60.40, 20.30)`.
2. **Resolve U4.18's placement constraint** (socket relocation or a local keep-out
   change) — re-run this map after moving anything.
3. **KRT re-route attempt**, then **regrade** (`fab_grade.sh` + DRC).
4. **Astra (oracle) reviews the diagnosis and the diff** — diagnostician, never the
   actor/router.
5. **Named human signoff** on the map + route + grade before any fabrication order.

None of these steps has been taken by this measurement. It only replaces a wrong
verdict with a reproducible one.

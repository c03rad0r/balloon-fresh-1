# ADR-125 — Wing string-attachment holes + deterministic hole-clearance test

- **Status:** ACCEPTED — operator instruction, 2026-10-21: *"Also please make holes for attaching the wing boards via a string. Please make a deterministic geometric test for ensuring that the holes don't overlap with any components or lanes in the circuit board."*
- **Decision owner:** Felix (operator)
- **Related:** ADR-124 (balloon tether holes), ADR-046/048 (wing interfaces), ADR-085 (seat rule).

## Decision

**1. One string hole per wing interface (`HW1..HW4`)**, Ø 2.5 mm NPTH, same construction
rules as ADR-124 (bare laminate, no plating). Purpose: the wing boards connect electrically
and mechanically via the `J_W*` castellated sockets, but flight loads (swing, cut recoil,
rotation) must not be carried by solder joints alone — a string tie through a board hole
gives load-bearing strain relief independent of the socket.

**2. A deterministic geometric test is the gate, not a visual check** —
`tracker/hardware/check_hole_clearance.py`:

| check | rule |
|---|---|
| hole ↔ every pad (both sides) | gap ≥ **1.0 mm** (edge-to-edge, pad radius from its size) |
| hole ↔ every track segment ("lanes") | gap ≥ **0.5 mm** (point-to-segment minus half-widths) |
| hole ↔ every via | gap ≥ **0.5 mm** |
| hole ↔ zone/pour bbox | no intersection (conservative) |
| hole ↔ board edge | ≥ **2.0 mm** |
| hole ↔ other hole | ≥ **4.0 mm** centre-to-centre |

Exit 0 = clean; exit 1 with every violation printed. A pytest wrapper
(`tests/test_v10_hole_clearance.py`) runs it in CI (loud skip where pcbnew is absent,
per the established pattern), and the builder runs it as a post-build self-check.

**Why these rules:** the 2026-10-21 U3 incident — holes 0.41 mm from pads passed a
courtyard-bbox check because containment is invisible to overlap tests. Distance-to-copper
is the only correct predicate for holes; "lanes" are included from day one so the test is
already binding when routing starts (tracks must dodge reserved hole columns).

## Consequences

- The left-edge column (x = 3.3) is reserved for the balloon tether (ADR-124); wing holes
  sit inboard of each wing seat, verified by the test.
- Routing must treat every `H*`/`HW*` hole as an obstacle: the deterministic test runs in
  CI after routing lands, so a lane through a hole column fails the build.
- v9: no wing holes (no retrofit; string ties on v9 articles go through the tether holes
  or wing tabs).

## Reproduce

```
~/venvs/kicad/bin/python tracker/hardware/check_hole_clearance.py \
    --board tracker/hardware/hub_board_v10.kicad_pcb
```

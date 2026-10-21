# ADR-124 — Tether holes: four NPTH line-attachment holes on the flight hub

- **Status:** ACCEPTED — operator instruction, 2026-10-21: *"include holes in the board so that a string can be attached for tying it to the balloon."*
- **Decision owner:** Felix (operator)
- **Related:** ADR-118/120 (v10 board + placement process), `docs/analysis/wing-ladder.md` §4.3 (payload pendulum: 241.3 mm chain, T = 0.99 s — the hub hangs from the balloon by a line), `docs/analysis/vertical-hub-load-cases.md` (static 1 g axial + swing loads).

## The gap

v9 has **zero mounting/tether holes** (measured: no Mounting-hole footprints, no NPTH). The hub hangs below the balloon on a string — the attachment was never designed.

## Decision

**Four NPTH (non-plated) through-holes, Ø 2.5 mm, in two pairs:**

| pair | position | use |
|---|---|---|
| H1/H2 | top edge (balloon side), symmetric about the vertical centre line | balloon tether line: passes H1 → out → H2, knots above — load shared by two holes + FR4 between |
| H3/H4 | bottom edge, mirrored | spare: payload/counterweight below, second tether, or lanyard for handling |

**Geometry rules (binding for the builder):**

- Hole centre ≥ **5 mm from board edge** (FR4 tear-out margin; the load is a swinging 1–2 g line, not a static pull — the pendulum model's dynamic case)
- Pair spacing **8 mm** between hole centres
- **Copper keep-out 2.0 mm** around each hole (NPTH must sit in bare laminate; no annulus, no plating)
- No wing-socket seat, courtyard, or RF keep-out overlap (checked geometrically like every other placement element)
- Holes are NPTH: no net, no plating — a string must never depend on a plated barrel

## Consequences

- v10 placement gains the hole pairs (top/bottom edge centres); round-2 gate renders show them.
- The builder emits them as a `MountingHole`-class footprint pair with custom Ø2.5 pads (hole 2.5, pad 2.5 = no annulus) on both sides' keep-outs.
- Mass impact ≈ 0 (four 2.5 mm holes in 0.6 mm FR4 ≈ 0.02 g).
- v9 keeps its gap (no retrofit) — a v9 flight article needs hand-drilled holes, noted in its handover doc.

## Reproduce

```
grep -n 'H1\|tether' docs/fab/v10/GATE-LOG.md   # gate renders must show the holes
```

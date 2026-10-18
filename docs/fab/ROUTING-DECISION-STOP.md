# ROUTING — hand-written router attempt, stopped. Decision record.

**Date:** 2026-10-18 · **Branch:** `pr/standing-authority` · **Consultant:** `gpt-6-astra` (served id recorded)

## The decision

**Stop the hand-written grid router. Hand-route the two nets in the KiCad GUI.**

This is not a budget complaint. It is a measured convergence failure: seven attempts, and the
outcome cycles between which net is broken rather than approaching zero.

## The measured evidence

Each row is a real `kicad-cli pcb drc` run, not an estimate.

| run | MOSI | SCK | DIO1 | unconnected | new electrical violations |
|---|---|---|---|---|---|
| baseline | ❌ | ❌ | ✅ | **4** | — (168 total: 2 holes_co_located, 8 via_dangling) |
| 1 (all F.Cu, nets blind to each other) | ✅ | ✅ | ✅ | **2** | **13** — 5 shorting, 4 clearance (worst 0.0236 mm), 2 crossing, 2 mask bridge |
| 4 (SCK → B.Cu) | ❌ | ✅ | ✅ | 2 | — MOSI's B.Cu leg lost to SCK |
| 5 (MOSI tries In1/B.Cu/In2) | ❌ | ✅ | ✅ | 3 | MOSI's via collided with SCK's dogbone: **0.5581 mm apart, 0.700 required** |
| **6 (DIO1 → In1.Cu)** | ✅ | ✅ | ✅ | **3** | **0** ← **the best state, archived** |
| 7 (DIO1 dogbone margin fix) | ✅ | ✅ | ❌ | 3 | DIO1's F.Cu stub could not reach its via |
| 8 (DIO1 untouched, MISO only ripped) | ❌ | ✅ | ✅ | 3 | **10** — 5 shorting, 5 clearance |

**Run 6 is the only run that connected both target nets with zero new electrical faults.** It is
**NOT committed to git**: the repo's `pad-audit` pre-commit gate correctly refuses any `.kicad_pcb`
carrying the known pre-existing defects (`U1` pad 41 x13, 9 paste-only pads, 16 unresolved 3D model
references), and that gate should not be circumvented for an archive copy. It is reproducible from
`tracker/hardware/route_remaining_nets.py` at commit `618dcf693`, and its hash is
sha256 `ef8c807b68ed5941054bc29b278780f3036b02eea3b1d79d0dca96519ea1258e` (recorded here so the exact
artefact is identifiable if it is regenerated). Its `DIO1` dogbone failed, so DIO1 was left disconnected — that is the
single defect in it, and it is the thing a GUI session fixes in one move.

## Why the router does not converge

Three independent reasons, each confirmed by a run:

1. **Sequential A* has no backtracking.** Whichever net routes first wins the contested cells, and
   the loser gets `no path`. Changing the order just changes the loser:
   `SCK→MISO→DIO1` breaks DIO1; `DIO1→SCK→MISO` breaks SCK.
2. **The escape geometry is unique, not generous.** Exhaustive search on all four layers finds
   **exactly one** legal via site for MOSI: `(55.850, 25.250)`, `dx = +0.700` from the pad edge,
   worst clearance `0.211 mm` to `U4.16`. There is no alternative to fall back on when something
   occupies it.
3. **The 4-layer stack is genuinely full at U4's escape zone.** Every SCK dogbone site to the right
   of `U4.18` is blocked — by `/SX1280_DIO1` on F.Cu (`-0.100`), `+3V3` (`-0.350`),
   `/SX1280_MISO` on B.Cu (`-0.150`), `/SX1280_BUSY` on In1.Cu (`-0.250`),
   `/W3_SOLAR_N` on In2.Cu (`-0.209`). This is not a search-parameter problem.

**A router that needs to move a neighbouring power track to reach its target is not a router; it is
a constraint solver with a rip-up-and-retry loop, and this one does not have one.**

## Astra's ruling that predicted this

> *"Algorithmic search should own detailed route selection. Neither the 14.38 mm and 6.79 mm distances
> nor four layers and clear B.Cu guarantee endpoint access. Reasoning should diagnose inconsistent
> evidence, select constraints and routing strategy, and decide whether rip-up is acceptable."*

**The part I got wrong:** I read that as "write a better search". It says search owns *selection*
within a space **that a human has already made routable**. At `U4` the space is not made routable —
it needs interactive shoving of `+3V3` and `/SX1280_DIO1`, which is exactly what GUI routing is for.

## What is proven and should be carried into the GUI session

```
SCK escape:   U4.18 exits on F.Cu at y = 24.700  -- INSIDE its own pad's y-span (24.600..24.900)
              A track may offset within the pad's own height and slide out sideways.
              Run 1 proved this with ZERO DRC violations at the pad.
MOSI escape:  exactly ONE legal via site on all four layers: (55.850, 25.250)
              0.50 mm dia / 0.25 mm drill (== m_ViasMinSize, so NO waiver needed)
              worst clearance 0.211 mm to U4.16
              then route on B.Cu to U1.8 (16 segments, proven in run 6)
MISO stub:    routable at a 0.025 mm grid (23 segments); its long run is already on B.Cu
DIO1:         already connected on the committed board and DRC-clean -- leave it alone
Two vias must be >= 0.700 mm apart (0.500 dia + 0.200 clearance). This is the constraint that
  broke runs 4/5/6/7 and it is easy to violate by eye. Check it explicitly.
```

## Refuted claims, recorded so they are not repeated

**1. "U4.18 is NOT ESCAPABLE"** — from the delegated escape-feasibility card
(`docs/fab/FCU-ESCAPE-FEASIBILITY.md`, branch `pr/fcu-escape`). **False.** Run 1 routed SCK out of
`U4.18` and DRC reported **zero violations at that pad**. The card assumed a track must run on the pad
centreline; it may offset within the pad's own height. **The card's U4.18 verdict must be corrected
before that branch merges.**

**2. "the B.Cu escape is clear — 12 mm, 7 directions"** — measured on a layer SMD pads cannot reach
without a via. Wrong object.

**3. `pad_reachability.py`'s "PAD ESCAPE CLEAR (nearest 0.970 mm >= 0.300 mm)"** while listing four
`[BLOCKING]` obstacles at that same threshold — the card already records this: line 105 compared
millimetres against nanometres (`0.300 × 10⁶`), so **every** obstacle was tagged BLOCKING.

## What this does NOT establish

Routing a board is not the same as a fab-ready board. Even with both nets routed, the board still has
`holes_co_located 2` (a via drilled inside `C_CAP2`'s pad-2 hole), `via_dangling 7..9`, and the two
`GND` zone-to-zone breaks (D7). **`fab_grade.sh` will say `NOT ORDERABLE` until those are addressed,
and no amount of signal routing changes that.**

## Next action

**One GUI session**, following the proven numbers above: shove `/SX1280_DIO1` off `U4.18`'s escape,
place MOSI's via at `(55.850, 25.250)`, route MOSI on B.Cu, route SCK out at `y = 24.700`, check the
two-via spacing, refill, DRC. **Not another router iteration.**

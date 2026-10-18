# F.Cu escape feasibility — hub_board_v9, the four unrouted SX1280 pads

**Measurement, not a route.** This document records what is geometrically possible for four pads at the
board's own design rules. It selects no route. See [What this measurement CANNOT establish](#what-this-measurement-cannot-establish).

| | |
|---|---|
| Board | `tracker/hardware/hub_board_v9.kicad_pcb` — 70.15 × 71.65 mm, 59 footprints, 834 traces / 286 vias, 4 copper layers |
| Pads | `U1.8`, `U4.17` (net `/SX1280_MOSI`) and `U1.22`, `U4.18` (net `/SX1280_SCK`) |
| Tool | `tracker/hardware/fcu_escape_feasibility.py` |
| Reproduce | `~/venvs/kicad/bin/python tracker/hardware/fcu_escape_feasibility.py` |
| Measured | 2026-10-18, branch `pr/fcu-escape`, off `origin/master` 84fd968ef |

## Rules in force (read from the board, never assumed)

| Rule | Value | Source |
|---|---|---|
| Clearance | **0.200 mm** | `max(m_MinClearance, GetSmallestClearanceValue())` — `m_MinClearance` is 0 (unset floor), so the netclass value rules |
| Track width | **0.200 mm** | `GetCurrentTrackWidth()` |
| Via | **0.600 mm / drill 0.300 mm** | `GetCurrentViaSize()` / `GetCurrentViaDrill()` |
| Via floor (min allowed) | **0.500 mm / drill 0.300 mm** | `m_ViasMinSize` / `m_ViasMinDrill` |
| Hole clearance | **0.200 mm** | `m_HoleClearance` |
| Hole-to-hole | **0.250 mm** | `m_HoleToHoleMin` |

Two different thresholds are needed, and conflating them is the defect this document exists to fix:

- A **trace centreline** must stay `track_w/2 + clearance` = **0.300 mm** from other-net copper.
- A **pad** does not escape from its centreline. Its escape-ring radius is `half-diagonal + clearance`,
  because the pad's own corner already occupies `half-diagonal`.

| Pad | Size (mm) | Half-diagonal | **Escape-ring radius** |
|---|---|---|---|
| U1.8 | 1.50 × 0.90 | 0.8746 | **1.0746 mm** |
| U1.22 | 1.50 × 0.90 | 0.8746 | **1.0746 mm** |
| U4.17 | 0.80 × 0.30 | 0.4272 | **0.6272 mm** |
| U4.18 | 0.80 × 0.30 | 0.4272 | **0.6272 mm** |

All four are **F.Cu-only SMD** — `layers = ['F.Cu','F.Mask','F.Paste']`, no drill, no `B.Cu`, `through-hole:
False`. That single fact invalidates the project's long-standing claim *"B.Cu escape is clear, 12 mm in 7
directions"*: it was measured on a layer these pads cannot reach without a via.

## Verdict table

| Pad | Net | Ring | F.Cu obstacles in ring | F.Cu flood fill | Legal dogbone via | **Verdict** |
|---|---|---|---|---|---|---|
| **U1.8** | MOSI | 1.0746 mm | 5 | **escapes**, reaches 3.54 mm from centre | 350 @ ⌀0.60 (nearest R=1.10 mm) | **ESCAPABLE on F.Cu** — and the existing in-pad via is a *stub*, not an escape |
| **U1.22** | SCK | 1.0746 mm | 4 | **escapes**, reaches 3.54 mm from centre | 364 @ ⌀0.60 (nearest R=1.05 mm) | **ESCAPABLE on F.Cu** — and the existing in-pad via is a *stub*, not an escape |
| **U4.17** | MOSI | 0.6272 mm | 11 | no exit — stalls 1.41 mm from centre | 3 @ ⌀0.50 only; **none** at ⌀0.60 | **ESCAPABLE only via layer transition** (F.Cu → In1/In2/B.Cu) |
| **U4.18** | SCK | 0.6272 mm | 7 | no exit — stalls 0.78 mm from centre | **none** at ⌀0.60 or ⌀0.50 | **NOT ESCAPABLE at current rules** — bound by pad-to-copper clearance, short by 0.0655 mm |

### U1.8 — ESCAPABLE on F.Cu

Obstacles inside the 1.0746 mm ring (distance from pad **edge**):

| Distance | Kind | Net |
|---|---|---|
| +0.3700 mm | pad U1.7 | adjacent pin |
| +0.3700 mm | pad U1.9 | adjacent pin |
| +0.5200 mm | via | `/SX1280_MISO` |
| +0.6900 mm | trace | `/F33_CS_N` |
| +0.7100 mm | via | `/F33_CS_N` |

The flood fill leaves the pad field and reaches the sampling-window edge (3.54 mm). Widest single-direction
run without touching other-net copper: **5.0 mm** at 348–358°.

**Existing copper on this net:** one ⌀0.60/0.30 through via at (49.950, 11.840) — *exactly the pad centre*,
0.0000 mm away. It re-checks **LEGAL**: worst-case copper clearance 0.5200 mm (F.Cu pads U1.7/U1.9),
hole-to-hole 0.9700 mm. But **no own-net copper continues on In1/In2/B.Cu beyond it** — the via is a stub:
a hole through every layer with nothing on the far side. It is a legal hole, not an escape.

### U1.22 — ESCAPABLE on F.Cu

| Distance | Kind | Net |
|---|---|---|
| +0.2500 mm | trace | `/F33_VSENSE` |
| +0.3700 mm | pad U1.23 | adjacent pin |
| +0.3700 mm | pad U1.21 | adjacent pin |
| +0.7450 mm | via | `/GNSS_PPS` |

Escapes toward 270–300°; reaches the window edge (3.54 mm). Widest run **5.0 mm** at 290–300°.

**Existing copper:** one ⌀0.60/0.30 through via at (60.400, 20.300), 0.4584 mm from pad centre — inside the
1.50 × 0.90 land, so via-in-pad. Re-checks **LEGAL**: worst copper 0.3071 mm (In1.Cu trace `/SX1280_BUSY`),
hole-to-hole 1.4117 mm. Again **no continuation** on any inner or back layer — a stub.

### U4.17 — ESCAPABLE only via a layer transition

U4 is a 0.5 mm-pitch QFN24: pads 13–18 form a column at x = 55.15 with 0.50 mm pitch and 0.30 mm pad
height, so **adjacent pad edges are exactly 0.200 mm apart — identical to the clearance rule.** There is no
slack between neighbours, so no trace can run between them.

| Distance | Kind | Net |
|---|---|---|
| +0.2000 mm | trace | `/SX1280_MISO` |
| +0.2000 mm | pad U4.16 | adjacent pin |
| +0.2000 mm | pad U4.18 | adjacent pin |
| +0.2132 mm | trace ×3 | `/SX1280_MISO` |
| +0.2182 mm | trace | `/SX1280_MISO` |
| +0.2500 mm | trace | `/SX1280_MISO` |
| +0.5459 mm | via | `/SX1280_MISO` |
| +0.5718 mm | trace | `+3V3` |
| +0.6159 mm | trace ×2 | `/SX1280_DIO1` |

F.Cu flood fill stalls — the longest legal run in any direction is **1.00 mm at 356°**, straight out of the
package in +X, immediately stopped by `+3V3`.

A via *is* legal here, but only at the board's 0.50 mm floor:

| Via ⌀ | Legal dogbone spots | Nearest | Worst-case copper | Hole-to-hole | F.Cu approach |
|---|---|---|---|---|---|
| **0.50 mm** | **3** | R = 0.70 mm @ 0° | **0.2110 mm** (F.Cu pads U4.16/U4.18) | 0.9816 mm | 0.2500 mm |
| 0.60 mm | 0 | R = 0.85 mm @ 351° | 0.1610 mm ✗ | 1.0686 mm | 0.1831 mm ✗ |

The ⌀0.50 candidate was re-verified by direct measurement against every item on every layer, no
prefiltering: F.Cu 0.2110, In1.Cu 0.4000, In2.Cu 0.4278, B.Cu 0.5000, hole-to-hole 0.9816 — all ≥ rule.
The via sits 0.70 mm from pad centre, i.e. outside the 0.40 mm pad half-length but still against the
package: a dogbone, not via-in-pad.

**Existing copper on this net:** the only via on `/SX1280_MOSI` is the U1.8 one, 14.38 mm away. U4.17 has
no copper of its own.

### U4.18 — NOT ESCAPABLE at current rules

| Distance | Kind | Net |
|---|---|---|
| +0.2000 mm | trace | `/SX1280_MISO` |
| +0.2000 mm | pad U4.17 | adjacent pin, **other net** |
| +0.2154 mm | via | `/SX1280_MISO` |
| +0.2182 mm | trace | `/SX1280_DIO1` |
| +0.2354 mm | trace | `/SX1280_DIO1` |
| +0.5933 / +0.6058 mm | trace ×2 | `/SX1280_MISO` |

F.Cu flood fill stalls at **0.78 mm** from centre — the shortest reach of the four. No legal via at either
size:

| Via ⌀ | Best near-miss | Copper | Hole-to-hole | F.Cu approach | Short by |
|---|---|---|---|---|---|
| 0.60 mm | R = 0.85 mm @ 18° | 0.1176 ✗ | 1.1774 | 0.1093 ✗ | 0.0824 mm |
| 0.50 mm | R = 0.80 mm @ 15° | 0.1492 ✗ | 1.2399 | 0.1345 ✗ | **0.0655 mm** |

**Binding rule: pad-to-copper clearance, 0.200 mm. Tightest neighbour: pad U4.17** — the pad on the *other*
net that must also escape. Two 0.80 × 0.30 pads sit 0.50 mm apart centre-to-centre, leaving 0.200 mm
between their edges. A 0.50 mm via needs its own edge 0.200 mm clear of U4.17's copper, so its centre must
be ≥ 0.45 mm from U4.17's edge — the local geometry admits no such point at any angle. Best achievable is
0.1345 mm of the 0.200 mm required: **short by 0.0655 mm.**

This is a placement fact, not a search failure, and **no rule was relaxed to produce it.** It also means
`/SX1280_SCK` cannot be completed while U4.18 stays where it is — its U1 end is escapable, its U4 end is not.

## Method

1. **Rules** are read from the loaded board's `BOARD_DESIGN_SETTINGS`: `m_MinClearance` (0),
   `GetSmallestClearanceValue()` (0.200), `GetCurrentTrackWidth()`, `GetCurrentViaSize/Drill()`,
   `m_ViasMinSize`, `m_HoleClearance`, `m_HoleToHoleMin`. `BOARD_DESIGN_SETTINGS` has **no `GetDefault()`**
   in KiCad 9.
2. **Pad geometry** comes from `pad.GetEffectivePolygon(layer)` — KiCad's exact copper outline, correct for
   the rotated 1.50 × 0.90 land of U1.22. Half-diagonal is `hypot(w/2, h/2)`.
3. **Escape ring** = every other-net item on that layer whose nearest approach to the pad is within
   `half-diagonal + clearance`, reported as distance from the pad **edge**.
4. **Copper gap kernel** models each item as a convex core inflated by a radius (trace = segment + w/2,
   via = point + ⌀/2, pad = its polygon + 0) and computes exact edge-to-edge distance. Validated against
   KiCad: **3 nm** agreement on trace/via point-probes, **exact** on pad-vs-pad against `SHAPE::Collide`.
   (`GetEffectiveShape().Distance()` was *not* used: on the `SH_COMPOUND` a roundrect pad returns it reports
   0.275 mm where the true gap is 0.025 mm.)
5. **F.Cu reachability** is a DRC-legal flood fill — 0.05 mm grid, a cell legal only if a trace centreline
   there keeps `track_w/2 + clearance` from every other-net F.Cu item, 8-connected with no corner-cutting,
   seeded from legal cells inside the pad's own polygon. It answers "can the pad's copper leave?", not
   "where does the route go?".
6. **Via candidates** are searched on a 0.05 mm radial × 3° angular grid out to 2.0 mm, and must satisfy
   copper clearance on **all four** copper layers, hole-to-hole clearance, and a legal F.Cu approach trace
   from pad centre to via. Via-in-pad placements are counted separately (they need filled/plugged vias and
   are a different process from a dogbone).
7. **Existing own-net copper** is audited separately, because a pad that already has a legal via-in-pad is
   already transitioned — but only if copper continues on the far side. A via with nothing beyond it is
   recorded as a **stub** and explicitly not credited as an escape.
8. **Self-check before any verdict is printed:** each verdict is re-derived from the same threshold that
   produced the obstacle list, in the same units. A verdict contradicting its own data makes the script
   exit non-zero.

The **GND pour is deliberately excluded** from the obstacle set. It is re-poured around new copper, and
measured zone-to-pad gaps are uniformly **0.2005 mm** across all 215 pads — exactly the zone clearance,
which is what a re-poured clearance looks like. Counting it as an obstacle would report every pad on this
board as blocked. It is reported separately per pad, as *re-pourable*.

## The defect that was fixed

`tracker/hardware/pad_reachability.py` (worktree `wing-fix`) printed:

```
       via    at 0.970 mm  [BLOCKING]
       ...
     => PAD ESCAPE CLEAR (nearest 0.970 mm >= 0.300 mm)
```

The verdict contradicts the list four lines above it. Three distinct defects overlapped; the first alone
guarantees the contradiction:

| # | Line | Defect |
|---|---|---|
| **D1** | **line 105** — `blocked = "BLOCKING" if d < need * UM else "clear"` | **Unit mismatch.** `d` is millimetres; `need * UM` is nanometres (0.300 × 10⁶ = 300000). `d < 300000` is true for every obstacle, so every obstacle was tagged `[BLOCKING]` regardless of geometry. |
| **D2** | **line 113** — `PAD ESCAPE CLEAR (nearest … >= 0.300 mm)` | **Wrong threshold, and a comparison never reconciled with the tags above it.** `need` (line 47: `track_w/2 + clearance` = 0.300 mm) is the requirement for a *trace centreline*. A pad escapes from its own edge, so the threshold is `half-diagonal + clearance` = **1.0746 mm** for a 1.50 × 0.90 pad. Against the correct threshold a nearest obstacle at 0.970 mm is **inside** the ring — the opposite of the printed verdict. |
| **D3** | lines 60–70 | **Wrong layer.** Obstacles were collected from `B.Cu` only, but all four pads are F.Cu-only SMD. That measured a layer the pads cannot reach without a via — the same error that made five routing attempts fail. |

**The wrong line is line 105**, the `blocked` tag: it compared millimetres to nanometres and so labelled
every obstacle `[BLOCKING]` indiscriminately, destroying exactly the information the verdict line then
ignored. Line 113 is wrong twice over — the 0.300 mm trace threshold instead of the 1.0746 mm pad ring, and
a `min()`-based verdict never reconciled with the tags printed above it.

`fcu_escape_feasibility.py` fixes all three: every threshold is derived from the object being judged, all
distances are millimetres throughout, F.Cu is measured for F.Cu pads, and `self_check()` refuses to emit a
verdict that disagrees with the obstacles that produced it.

## What this measurement CANNOT establish

Explicitly, and these are load-bearing:

- **It does not prove a route exists** — to the destination, or anywhere. *Escapable* means a pad's own
  copper can legally leave its local pad field, and nothing more. It says nothing about whether a corridor
  continues to the other endpoint, or whether the remaining SX1280 nets that share that corridor leave room.
  **Escapable ≠ routable.**
- **It does not select or validate a route.** Astra's ruling stands: *"algorithmic search should own detailed
  route selection."* No router was run; the flood fill answers yes/no on local exit only.
- **Two escapable pads do not make a net.** Both nets have both endpoints unrouted, so `/SX1280_MOSI` and
  `/SX1280_SCK` each need a path joining two pads. U4.18 is not escapable, so `/SX1280_SCK` cannot be
  completed as placed regardless of what the U1 end permits.
- **It is a static snapshot, and it excludes the pour.** Results assume the GND pour re-flows around new
  copper. If the pour is frozen, or an island cannot re-pour, every pad here becomes blocked. Any new copper
  changes the numbers.
- **It does not run KiCad's DRC.** The clearance model is my own exact geometry, validated to 3 nm against
  KiCad's primitives — but it is not the DRC engine. A `WriteDRCReport` pass on the *routed* board is still
  required before fab.
- **It says nothing about manufacturability or signal integrity.** No impedance, no length matching, no
  annular-ring-versus-drill check against the fab's capability, no current-carrying check on `+3V3`.
- **The grid is finite** — 0.05 mm × 3° for vias, 0.05 mm for the flood fill, 2.0 mm radius. A legal
  placement between grid points is not excluded in principle; for U4.18 the best near-miss misses by
  0.0655 mm, far more than the 0.05 mm grid could hide.
- **U4.17's via is legal, not endorsed.** It meets every rule at ⌀0.50 mm, the board minimum. Whether a
  minimum-spec via on a 0.5 mm-pitch QFN is *desirable* is a fab and yield question, not a geometry one.
- **"NOT ESCAPABLE" is about the current rules and placement**, not a claim the board is unfixable. Moving
  U4, rotating the QFN, narrowing the clearance scope for this pad class, or permitting via-in-pad all
  change the premise. **No rule was changed to reach any verdict here.**

## Reproduce

```
cd ~/worktrees/escape
~/venvs/kicad/bin/python tracker/hardware/fcu_escape_feasibility.py
```

Runs in ~80 s, no arguments, reads only the board, writes nothing, modifies nothing. Exit code 0 when all
four self-checks pass. Output is deterministic — two consecutive runs are byte-identical.

Environment: `pcbnew` exists **only** in `~/venvs/kicad/bin/python`. `BOARD_DESIGN_SETTINGS` has no
`GetDefault()` in KiCad 9. `pcbnew.LoadBoard` returns `None` (does not raise) for a path without a
`.kicad_pcb` extension.

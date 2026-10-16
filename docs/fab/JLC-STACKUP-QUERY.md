# JLC FAB QUERY — hub_board_v9 stackup and controlled impedance

**Status:** DRAFT — needs operator approval before sending. Nothing here has been sent or ordered.

## Why this query exists

`tracker/hardware/hub_board_v9.kicad_pcb` declares **0.6 mm thickness, 4 copper layers**, and **no
stackup at all**. Because the dielectric height between L1 and L2 is undeclared, the 50-ohm trace width
for the 2.4 GHz RF path is unknown by a **factor of 3.7**:

| assumed L1–L2 dielectric | 50-ohm width | Z0 of a 0.20 mm trace |
|---|---|---|
| 0.0752 mm (JLCPCB 0.6 mm 4L, 7628×1 prepreg) | 0.099 mm | 30.4 Ω |
| 0.1000 mm | 0.146 mm | 40.8 Ω |
| 0.1088 mm | 0.162 mm | 43.9 Ω |
| 0.1300 mm | 0.202 mm | 50.4 Ω |
| 0.2100 mm (a 1.6 mm board) | 0.364 mm | 69.0 Ω |

The repo already carries a stale number derived from the wrong row: `PCB-EXECUTION-PLAN.md` §3.1 gives
**"RF width 0.76 mm on 1.6 mm FR4"** while the board exported is **0.6 mm**. `C3-SIGNOFF.md` flagged this
on **2026-08-05** as unreconciled, and it still is. This query is what closes it.

## Questions for JLCPCB (or any fab quoting this board)

1. **What is the standard build for a 0.6 mm, 4-layer, 1 oz outer copper board?** Specifically the
   **prepreg thickness and Dk between L1 and L2**.
2. **Is 0.6 mm available as a standard 4-layer stack, or is it a special build?** If special, what is
   the lead time and surcharge?
3. **Does the stackup table include a controlled-impedance option**, and if so what impedance tolerance
   is offered (e.g. ±10%)?
4. **What trace width does your calculator give for 50 ohm single-ended on F.Cu over that L1–L2
   dielectric**, at the board's minimum trace width of 0.20 mm? (We need to know whether 0.20 mm is
   already close to 50 ohm or needs widening.)
5. **Minimum trace width / spacing** for this build (the board currently assumes 0.20 mm both).
6. **Is 0.20 mm reliably manufacturable on 0.6 mm 4-layer**, or is there a recommended minimum for
   impedance-controlled traces?

## What this unblocks

- the RF net class and its trace width (currently the route is at the board's default 0.20 mm, chosen
  deliberately rather than guessed)
- `PCB-EXECUTION-PLAN.md` §3.1/§4.2, which currently contradict the board
- the final fab-readiness verdict for the hub board, and by extension the same question for the other
  boards in the system as they reach this stage

## Notes for the operator

- The board is **not** ready to order yet: the full route is in progress, and the 24 remaining
  `copper_edge_clearance` items are the `J_W*` wing-socket edge interface awaiting a ruling.
- **No order has been placed and none should be placed until this query is answered**, because the RF
  width cannot be finalised without it.

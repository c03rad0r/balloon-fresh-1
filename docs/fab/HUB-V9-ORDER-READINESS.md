# HUB v9 — ORDER READINESS (measured 2026-10-15)

**Board:** `tracker/hardware/hub_board_v9.kicad_pcb` (70.0 × 70.0 mm, 4-layer, 0.6 mm)
**Method:** `tracker/hardware/fab_grade.sh` — route (STRICT frozen floor, escalation OFF)
→ stitch GND → **refill zones** → DRC against `jlcpcb-s1-frozen.kicad_dru`.
**Reproduce:** `bash tracker/hardware/fab_grade.sh tracker/hardware/hub_board_v9.kicad_pcb tracker/hardware/output/fabgrade_u4`

## Verdict

**NOT ORDERABLE.** 10 unconnected items, 165 DRC entries (29 error / 136 warning).
The chain is fully reproducible and every item below is read from its JSON, not eyeballed.

## What changed this session (progress, measured)

| gate | before | after |
|---|---|---|
| board components | 44 | **59** (all 15 U4 SX1280 support/RF parts placed) |
| `test_netlist_integrity.py` | 9 pass / 7 FAIL | **12 pass / 4 FAIL** |
| section C — "THE ORDER BLOCKER" | **FAIL** | **PASS** |

## Remaining blockers, each named with its links

### 1. Two nets the router CANNOT complete at the frozen floor (real)

The router ran with `--escalation off`, whose contract is *"sizes and clearances are exact; a net
that cannot complete at them FAILS AND IS REPORTED; nothing is narrowed or shrunk."* Measured
`"escalations": 0` — **nothing was narrowed**, which is the point of the strict mode.

| net | links | state |
|---|---|---|
| `/SX1280_MOSI` | `Pad 8 of U1` ↔ `Pad 17 of U4` | **unrouted** (0 of 1 pad pairs connected) |
| `/SX1280_VBAT_IO` | `Pad 11 of U4` ↔ a B.Cu track | **partial** (1 of 2) |
| `/GNSS_VCC` | `Pad 8 of U5` ↔ a B.Cu track | **partial** (1 of 2) |

`/SX1280_MOSI` is the MCU↔radio SPI trace — **a genuine signal-integrity blocker**, and it is new
work created by the U4 rewire. The other two are partials, not new nets.

Also measured: `Multi-point 188/190 pads connected (2 FAILED)`, `vias 306`,
`min_clearance_used 0.2` (the frozen floor, honoured exactly).

### 2. GND wing-pad stitching (5 of the 10 unconnected items)

`Pad 2 [GND] of J_W1 / J_W2 / J_W3` is unconnected **F.Cu ↔ B.Cu** (its own two layers), and the
F.Cu pad is not reached by `Zone 'GND_PLANE_F.Cu'`. The stitcher reported
`pads already stitched: 18` but `UNRESOLVABLE: 55`, naming `U1.41` repeated, `C0.2`, `C10.2`,
`C_CAP2.2`, `R_BAL2.2`, `D_BP4.2`, `U_CUT1.2`, `C4.2`, …

**`U1.41` appearing 15 times is itself suspicious** — one pad reported repeatedly suggests the
stitcher is iterating a pad list it cannot resolve, not that 15 distinct pads are blocked. Worth
checking before treating "UNRESOLVABLE: 55" as 55 real defects. *(This is the same shape as the
false FAILs found earlier this session: an instrument reporting a number that does not survive
scrutiny.)*

### 3. DRC errors: 29

| type | count | status |
|---|---|---|
| `copper_edge_clearance` | **27** | the **documented counted delta** (43 → 31 → 28 → 27). The operator-approved scoped `Reference` exemption is **MEASURED INERT** for copper-vs-Edge.Cuts pairs — see BLOCKER 4. |
| `starved_thermal` | **2** | real and fixable — `fix_starved_thermal.py` exists and previously took this 3 → 0 |

Warnings (136) are not order blockers but do carry information: `silk_overlap` 77,
`silk_over_copper` 34, `silk_edge_clearance` 12, **`lib_footprint_issues` 7**,
`via_dangling` 6.

**The 7 `lib_footprint_issues` are on `U2, U3, U4, J_W1..J_W4`** — i.e. the custom-symbol parts.
`U4` is in that list, so the SX1280 footprint/library link should be checked before the order even
though it is graded a warning.

### 4. The inert edge exemption — NEEDS AN OPERATOR RULING (unchanged this session)

`fail G` of `test_netlist_integrity.py`. The scoped exemption keys on `A.Reference == 'J_W1' || …`
and **was measured inert**: all eight Reference-based forms left the edge-clearance count at 28 while
a blanket rule took it to 16. **An inert exemption is worse than none** — it reads as though the
class is handled, so nobody looks again. Two honest options:

1. remove it and record the 27 items as an **explicit counted delta**, or
2. find a condition that actually fires.

## ROUTING: the U1/U4 channel is OVER-SUBSCRIBED -- proved by controlled test

Three attempts, all measured, all with `--escalation off` (nothing narrowed) and
`min_clearance_used = 0.2` (the frozen floor honoured exactly):

| attempt | unconnected | errors | failed nets |
|---|---|---|---|
| single-phase, default rip metric | 10 | **29** | `/SX1280_MOSI`, `/SX1280_VBAT_IO` |
| single-phase, `--ripup-abandon-metric weighted-probe` | 10 | 29 | **identical** -- 55/59, same 2, same 306 vias |
| **two-phase** (route the 2 problem nets FIRST, then the rest) | **13** | **36** | MOSI/VBAT_IO **now connect**, but `/SX1280_MISO`, `/SX1280_VDD`, `/SX1280_RF` open |

**Conclusion: routing ORDER relocates the failure, it does not fix it.** A stronger rip metric changes
nothing; routing the congested nets first fixes those two and breaks three others.

**The isolation test is MISLEADING and this is the trap worth recording.** Routing ONLY
`/SX1280_MOSI` on the placed board succeeds (`Single-ended 1/1 routed`, via the router's own rescue
path) -- which looks like proof of routability. It is not: an isolated net is handed the entire board.
`/SX1280_VBAT_IO` behaves the same way (2/2 routed in isolation, fails in the full run). **"It routes
alone" does not imply "it routes".**

**Where that leaves it:** the channel between `U1` (ESP32-S3, 53 pads of which 13 are ground) and
`U4` (SX1280, 25 pads) plus `U2` (the 39.0 x 21.0 mm LoRa2021F33-2G4) is over-subscribed at the frozen
floor. **The fix is a PLACEMENT change -- spread the U4 support/RF parts, or move U4 -- not another
routing pass.** That is consistent with `HUB-LAST-NET-DIO1.md`, which recorded the same region as
"a placement decision, not a routing one" (`U2` courtyard x = 46.670 vs `U1` x = 47.099).

### Rejected: `stitch_gnd_planes.py --offset` (measured trap, DO NOT ENABLE)

The v3 stitcher's offset mode is opt-in and `fab_grade.sh` never passes it -- which is why 55 pads
report UNRESOLVABLE. Enabling it looks like a win and is not:

| | centre-only | `--offset` |
|---|---|---|
| unresolvable pads | 55 | **12** |
| unconnected items | 10 | **6** |
| **errors** | **29** | **56** |
| new classes | -- | `hole_to_hole` 34, **`shorting_items` 5 (real shorts)**, `clearance` 4, `solder_mask_bridge` 3, `tracks_crossing` 2, `holes_co_located` 2 |

**Root cause: `free()` tests pad/via clearance only** -- it never checks hole-to-hole spacing or
whether the stub crosses an existing track. Vias land in ring positions free of *pads* but colliding
with *holes and traces*. **The metric it optimises (unresolvable pads) is not the metric that matters.**

### A self-grading hazard to preserve

The router prints `FAB FLOOR RELAXED` and writes its own project, warning that *"every checker
(check_drc, board_score, KiCad's own DRC) grades against the NEW value, so this copper will read
clean."* **`fab_grade.sh` avoids this by copying the FROZEN project over the router's before DRC** --
which is why its numbers are trustworthy and a raw router output is not.

## What is NOT blocking the order (say it explicitly)

- **Schematic / netlist integrity**: section C passes — the board carries all 59 components.
- **Footprint resolution**: both `v9_flight.net` and `base_station_v1.net` now resolve fully.
- **The 15 new U4 parts**: present on the board, all on stock KiCad libraries.

## Next steps, in order

1. **Fix the 2 starved thermals** (`fix_starved_thermal.py`) — cheap, and it removes 2 errors.
2. **Resolve `/SX1280_MOSI` and `/SX1280_VBAT_IO`** — hand-route or re-place. `/SX1280_MOSI` was
   previously blocked by the same U1/U4 channel congestion recorded in `HUB-LAST-NET-DIO1.md`
   (`U2` courtyard x = 46.670 vs `U1` x = 47.099): **a placement decision, not a routing one.**
3. **Stitch the J_W1..J_W3 GND pads**, after checking whether `UNRESOLVABLE: 55` is 55 real pads or
   a repeated-pad artifact.
4. **Get the BLOCKER-4 ruling**, then re-run the chain and record the final delta.
5. **Only then** rebuild the derived order package (`docs/fab/hub-v9/gerbers/`): it is **STALE**
   (`fail C2` — lacks the 15 U4 parts + `U_CUT1-4` + `U_HUB_CVT`). Route → re-emit BOM/CPL/gerbers
   → copy the routed board in.

## Two generator traps that MUST be respected by anyone re-running a builder

Both measured this session. **Re-running a generator silently reverts ratified hand work:**

| builder | reverts |
|---|---|
| `build_flight_sch.py` | the `ANT_SW` removal (`96d219b3`) and the `U_HUB_CVT`/`U_CUT*` part-number pass |
| `build_hub_board_v9.py` | **`min_through_hole_diameter` 0.2 → 0.3** in `hub_board_v9.kicad_pro`, deleting the comment that records the operator's 2026-10-14 decision |

**After any builder run, `git diff` the `.kicad_pro` / `.kicad_prl` / schematic and restore the
operator work before committing.** This was caught and restored once already; it will recur.

## Honest limits of this record

- Every number here is read from `fab_grade.sh` output or its JSON — not estimated.
- The `copper_edge_clearance` delta is **carried, not fixed**; 27 is a count, not a clearance.
- **No claim is made that the board will work.** This grades *geometry and connectivity*, not RF
  performance, thermal margin under load, or flight behaviour.

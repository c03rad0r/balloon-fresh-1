# BOARD READINESS REGISTER — JLCPCB order gate

**Purpose:** the single answer to *"are all the boards required for the
end-to-end system ready to order?"* Every row is **machine-measured**
(`kicad-cli pcb drc`, KiCad 9.0.8), not asserted.
**Author:** manager (Felix) · **Date:** 2026-10-13
**Rule:** a board may be ordered only with (a) copper-rule families at zero or
documented, (b) an LLM spatial review verdict on file, (c) a fab packet
generated from the exact reviewed board.

---

## The required board set (verified, not assumed)

Per `tracker/hardware/FLIGHT-BOARD-PLAN.md` (flight set) and
`docs/BASE-STATION-BOARD-CHECKLIST.md` (ground set):

| # | Board | Role | Needed? |
|---|---|---|---|
| 1 | **Hub board v9** | balloon payload: MCU + FLRC radios + GPS + power, wing sockets | YES |
| 2 | **Wing / solar carrier v9** | 3× solar cells, plugs into the hub's castellated wing sockets | YES |
| 3 | **Base-station board** | ground side: 433 RX chain + 2.4 GHz TX chain + control | YES |
| 4 | ~~Bench-rig console~~ | range-test console | **NO — see §4** |

---

## 1. Hub board v9 — ✅ ORDER-READY

| Field | Value |
|---|---|
| Board | `tracker/hardware/hub_board_v9_d1c_routed.kicad_pcb` |
| Board md5 | `a5e0cca3211eafdc4bd9de7795ac0901` |
| DRC | **shorts 0 · crossings 0 · via_diameter 0 · annular 0 · hole_clearance 0 · drill_out_of_range 0 · copper_sliver 0 · clearance 3 · total 104** |
| Unconnected | 25 — all classified intentional (22 external wing-board interface pads, 2 same-net pour pairs, 1 tracked residual) |
| Spatial review | **`docs/CONSULT-astra-final3-APPROVED-2026-10-13.txt` → VERDICT: APPROVED** |
| Fab packet | `docs/fab/hub-v9/` — STEP 893 KB, 14 gerbers, PTH drill 153 holes (T0.200/0.250/0.300/1.000), NPTH 2×1.500, job file, centroid, `PROVENANCE.txt` (board md5 + commit) |
| Fab process | 4-layer · **Via-in-Pad = Filled & Capped (IPC-4761 Type VII)** · file minimums aligned to JLCPCB 4L standard (min via 0.40 / drill 0.20) |
| Exceptions | `docs/CONTROLLED-EXCEPTION-TABLE-hub-v9.md` — 3 items, **all above** JLCPCB's 0.15 mm published standard (0.1750/0.1750/0.1648 vs our stricter 0.20 rule) |
| Commit | `1ff5c572` (branch `feat/hub-routing-v9`, both remotes) |

**Verdict: orderable now.**

---

## 2. Wing / solar carrier v9 — ✅ ORDER-READY

| Field | Value |
|---|---|
| Board | `tracker/hardware/wing_board/wing_board_v9.kicad_pcb` |
| Board sha256 | `62e00d43e0c7d3be8a293f431e6d1110587791d7be6127a4763017702953f715` |
| Order gate | `wing_v9-GATE-RECORD.json` → **`"status": "PASS", "errors": 0, "unconnected": 0`** (tool `pcb_order_gate`, kicad 9.0.8) |
| DRC (independent re-run) | **unconnected 0**, 37 violations — all cosmetic/metadata: `lib_footprint_issues 15`, `silk_edge_clearance 9`, `nonmirrored_text_on_back_layer 6`, `silk_overlap 2`, `text_height 2`, `track_dangling 2`, `silk_over_copper 1` |
| Fab packet | `tracker/hardware/output/gerbers_wing_v9` — fab sha256 `d0bcd707caea321b022624b3589b0d5f5941b5d18f13c77b665871257ae69df9` |
| Spatial review | **`docs/CONSULT-astra-wing-APPROVED-2026-10-13.txt` → VERDICT: APPROVED** (on `renders/wing_v9_top.png` + `wing_v9_iso.png`, 1768×1376) |
| Release caveats | **both closed** — `docs/WING-RELEASE-CAVEATS.md`: (1) castellated edge plating **N/A**, measured 0 edge-adjacent pads (plain rectangle, 184.10×25.10 mm, outline 418.00 mm = bbox perimeter; interface is the J1 4-pin connector); (2) solar net mapping **verified** — 2 parallel strings × 3 series cells, all terminals assigned, no polarity inversion. Residual = physical cell tab orientation, a build-time check. |

**Verdict: ORDER-READY.** Gate PASS, zero unconnected, APPROVED, gerbers
present, both caveats closed with measurement. *Note:* the hub — not the wing —
carries the castellation requirement (its wing sockets).

---

## 3. Flight board (ESP32-C3 lineage) — ❌ NOT ORDERABLE

Multiple variants exist; **none is manufacturable.** Measured:

| Variant | Unconnected | Violations | Notable |
|---|---|---|---|
| `v_c3_flight_v4b` (best) | **20** | 10 | 1 short (`LR_RST` → un-netted U2 pad 7), 1 clearance (SPI_NSS vs GND via 0.16 vs 0.20), 2 keepout (`SPI_MISO` through a keepout), 5 dangling vias, 1 mask bridge |
| `v_c3_flight_final_clean` | 20 | 15 | 4 shorts, 1 track crossing, 4 keepout |
| `v_c3_flight_v7_routed` | 40 | 69 | 17 shorts, 19 mask bridges, 9 clearance |

**The 20 unconnected are REAL unrouted nets**, not interface pads:
`SOLAR_IN`, `VDIV_MID`, `EN`, `GPS_TX`, `GPS_RX`, `SPI_SCK`, `SPI_MOSI`,
`LR_BUSY`, `LR_DIO0`, `I2C_SDA`, `I2C_SCL`, `LED_A`, `UART0_TX`.

**Prior independent sign-off:** `tracker/hardware/C3-SIGNOFF.md` (2026-09-29,
worker-inspector) → **VERDICT: REJECT** — *"DRC fails the P5 gate (1 short, 12
track crossings, 3 clearance, 4 keepout, 49 unconnected); ERC fails (159
violations); **GPIO18/GPIO19 are wired on the board** — the exact rule this
sign-off exists to enforce is violated on U1 pads 13 and 14; the netlist does
not match the firmware."*

**Blocker:** this board is placed-but-largely-unrouted, plus the GPIO18/19 rule
violation is a **functional** defect, not cosmetic.

---

## 4. Bench-rig console — ➖ NO BOARD REQUIRED

Measured refutation of the premise (see `docs/PLAN-bench-rig-board.md`):
- `firmware/e80-stm32-bench/FLASHING.md`: *"Target: onboard STM32F103C8T6 of the E80-900MBL-02"*
- `firmware/rp2040/README.md`: *"Firmware for the RP2040-Zero coprocessor…"*
- `docs/HARMONIZED-BENCH-PACKAGE.md` (HARM-T9): bench **delivered and already run**, with results

The bench is satisfied by owned off-the-shelf modules. **Dropped from the order.**
Remaining need: the **LiteVNA 62** (€166.99) as the RF measurement instrument.

---

## 5. Base-station board — ⏳ NOT STARTED (blocked on decisions)

No schematic, netlist, board or gerbers. Plan: `docs/PLAN-base-station-board.md`
(ADR-051 Stage 1–2, stopped at the operator approval gate).

Open decisions: masthead topology · layer count · first-flight population ·
TQP3M9037 433 MHz dispute · enclosure.
Sub-board implied by ADR-079 INV-1: a small **masthead LNA board** may be a
separate, second board in this family.

---

## ORDER SUMMARY

| Board | State | Can order today? |
|---|---|---|
| Hub v9 | APPROVED, fab packet with provenance | **YES** |
| Wing v9 | APPROVED, gate PASS, 0 unconnected, caveats closed | **YES** |
| Base-station | plan only | NO — needs decisions + Stage 1–2 |
| Flight (C3 lineage) | REJECTED, 20 unrouted nets, GPIO18/19 violation | NO |
| Bench-rig | not needed | — |

**Net:** the **balloon side is orderable now** (hub + wing). The **ground side
(base-station) has not been designed**, and the legacy C3 flight board remains
rejected.

---

## Flagged for the operator

1. **C3 flight board vs hub v9 — MEASURED (2026-10-13): hub v9 is a strict
   functional superset.** Component-set comparison:

   | Function | Flight C3 v4b (20 parts) | Hub v9 (44 parts) |
   |---|---|---|
   | MCU | ESP32-**C3**-WROOM-02 | ESP32-**S3**-WROOM-1U-N8R8 |
   | FLRC radio | 1× LR2021F33 | 2× (LoRa2021F33-2G4 + LoRa2021_Castellated) **+ SX1280** |
   | GNSS | MAX-M10S | MAX-M10S ✓ |
   | Barometer | BMP280 | **MS5611-01BA** (better) |
   | Antennas | 1× U.FL | 4× U.FL (433 TX, 2G4 range, 2G4 RX, GNSS) |
   | Solar/storage | 1F 5.5V cap + SOLAR_In | 2× 3.3F SCC + 4× wing sockets + supervisor/dividers + NTC |
   | Wing interface | — | J_W1..J_W4 ✓ |

   **Every function the C3 board provides exists on hub v9 with equal or better
   parts, plus dual radios, 4 wings, and more storage.** The C3 board's rejected
   lineage (REJECT sign-off: 20 unrouted nets, GPIO18/19 wired against the
   explicit rule) is therefore **historical** — re-routing it would duplicate a
   board the hub already supersedes. **Recommendation ACCEPTED — OPERATOR
   CONFIRMED RETIREMENT 2026-10-13.** The C3 flight lineage is retired; the
   balloon payload = **hub v9 + wing v9**. No further C3 board work; its 20
   unrouted nets and the GPIO18/19 violation are closed as historical.
2. ~~Wing board spatial review~~ — **DONE 2026-10-13: APPROVED**, both release
   caveats closed (`docs/WING-RELEASE-CAVEATS.md`). Remaining human step: confirm
   the physical solar-cell tab orientation at assembly.
3. **Consolidation route** for the hub work (separate scoped PR vs the existing
   10-PR queue) — asked, not yet answered.
4. **Base-station decisions** (listed above).

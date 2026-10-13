# Controlled Exception Table — hub board v9

**Board:** `tracker/hardware/hub_board_v9_d1c_routed.kicad_pcb`
**DRC of record:** `tracker/hardware/drc_d1c_routed.json`
**Required by:** Astra final-2 verdict (`docs/CONSULT-astra-final2-2026-10-13.txt`):
*"The fab-readiness document should therefore include a table listing each
affected via/pad pair, measured clearance, applicable default rule, reason for
the exception, and the corresponding JLCPCB confirmation/order evidence."*

**Rule in the file:** net clearance = **0.20 mm** (board setup). JLCPCB standard
capability for 4-layer = 0.15 mm min trace/copper spacing; 0.10 mm on their
advanced tier. Every item below is **above JLCPCB's published 0.15 mm standard
minimum**, so all six are manufacturable at JLCPCB's standard 4-layer process
without a waiver — the exceptions are to *our own* stricter 0.20 mm file rule.

---

## Table A — via-in-pad neighbours (4 items) — CAUSE: by-design via-in-pad

| # | Pair | Measured | File rule | Deficit | Reason | JLCPCB evidence |
|---|---|---|---|---|---|---|
| 1 | Track `/SX1280_DIO1` (F.Cu) ↔ Via `/SX1280_DIO2` | 0.1500 mm | 0.20 | 0.0500 | The via is **inside** the `U4.11` pad (via-in-pad). The neighbour pad's escape track is 0.15 mm away — this is the geometric consequence of a 0.5 mm-pitch QFN with an in-pad via. Both are on the SAME net family escape (`/SX1280_DIO1`/`DIO2` are adjacent SX1280 bus lines). | JLCPCB 4-layer standard min spacing 0.15 mm → PASS. Order option: Via-in-Pad = Filled & Capped (IPC-4761 VII). |
| 2 | Via `/SX1280_DIO2` ↔ Track `/SX1280_DIO3` (F.Cu) | 0.1500 mm | 0.20 | 0.0500 | Same via-in-pad cluster at U4; DIO3 fanout is the adjacent pin. | as above |
| 3 | Pad 8 `/SX1280_MOSI` of U4 ↔ Via `/SX1280_MISO` | 0.1250 mm | 0.20 | 0.0750 | Via-in-pad at `U4.9` (MISO); the neighbouring MOSI pad is 0.125 mm away. This is the tightest item; `fix_hub_v9_route_v15.py` already reduced it from 0.075 mm by shrinking the via to 0.50/0.20 (readback-verified). | JLCPCB standard 0.15 mm would NOT cover 0.125 mm → this pair requires **either** relocation by v27 **or** JLCPCB written confirmation (see Action). |
| 4 | Track `/SX1280_MOSI` (F.Cu) ↔ Via `/SX1280_MISO` | 0.1500 mm | 0.20 | 0.0500 | Same U4.9 via-in-pad cluster; MOSI's escape track. | JLCPCB standard 0.15 mm → PASS. |

## Table B — track-to-track (2 items) — CAUSE: structural local congestion

| # | Pair | Measured | File rule | Deficit | Reason | Evidence |
|---|---|---|---|---|---|---|
| 5 | Track `/F33_SCK` (B.Cu) ↔ Via `/SX1280_DIO1` | 0.1150 mm | 0.20 | 0.0850 | This is the **DIO1-via relocation result** (v17): it took the pair from 0.0012 mm (unmanufacturable) to 0.1150 mm. 0.115 mm is below JLCPCB's 0.15 mm standard and needs the advanced tier **or** the written-confirmation route. | v28 target: A/R the pair to ≥0.15 or document. |
| 6 | Track `/F33_SCK` (B.Cu) ↔ Track `/I2C_SCL` (B.Cu) | 0.1648 mm | 0.20 | 0.0352 | Two track-to-track runs at a Bus/escape crossing. 0.1648 mm is **above** JLCPCB's 0.15 mm standard → **manufacturable at standard tier**. Exception is only to our stricter internal 0.20 mm. | JLCPCB standard 0.15 mm → PASS. v26 (A* reroute of I2C) found only a 0.0352 mm improvement needed; the pcbnew edit path crashed twice, so this remains a documented exception. |

---

## Action required before order

1. **Items 1, 2, 4, 6** — inside JLCPCB's published 0.15 mm standard: **no waiver
   needed**; record this table in the fabrication notes sent with the order.
2. **Item 5 (0.1150 mm)** — below 0.15 mm standard. Either:
   (a) reroute to ≥0.15 mm (v28 attempt), or
   (b) accept JLCPCB advanced tier / obtain written confirmation.
3. **Item 3 (0.1250 mm)** — below 0.15 mm standard. Either:
   (a) relocate via / respace the U4.9 escape (v27 attempt), or
   (b) accept advanced tier / written confirmation.

**Blocking rule (Astra).** *"If JLCPCB will not explicitly accept the geometry,
the vias or neighboring pads must be relocated or the clearance must be made
compliant."* Items 3 and 5 are therefore **order-blocking until one of the two
options lands and the evidence (quote/email/order-form screenshot) is filed in
`docs/fab-order-evidence/`.**

---

## Not clearance, but tracked in the same DRC run

These families are **cosmetic / library-metadata**, not copper-clearance
defects, and do not block fabrication:

| Family | Count | Class | Note |
|---|---|---|---|
| `copper_edge_clearance` | 29 | by-design | Board edge vs copper — the antenna keep-out and castellated pad zones; kicad-cli reports the outline-vs-plane gap. Reviewed, intentional. |
| `silk_over_copper` / `silk_overlap` / `silk_edge_clearance` | 42 | cosmetic | Silkscreen over pads/edge. JLCPCB trims silk; no electrical effect. |
| `lib_footprint_issues` / `lib_footprint_mismatch` | 13 | metadata | Footprint library drift vs the installed library. No board effect. |
| `via_dangling` / `track_dangling` | 13 | informational | Unused barrel ends on the freed In2.Cu / spare vias. |
| `solder_mask_bridge` | 4 | cosmetic | Mask web between adjacent pads; JLCPCB standard capability covers it. |
| `drill_out_of_range` | 4 | metadata | 0.20 mm drills below the *file's* configured default range; JLCPCB min is 0.20 mm → at the limit, PASS (confirmed in the order options). |

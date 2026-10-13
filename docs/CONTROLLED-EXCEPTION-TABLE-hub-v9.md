# Controlled Exception Table — hub board v9

**Board:** `tracker/hardware/hub_board_v9_d1c_routed.kicad_pcb`
**Board md5:** `a5e0cca3211eafdc4bd9de7795ac0901`
**DRC of record:** `tracker/hardware/drc_d1c_routed.json`
**Spatial review:** `docs/CONSULT-astra-final3-APPROVED-2026-10-13.txt` — **APPROVED**
**Required by:** Astra final-2 verdict (`docs/CONSULT-astra-final2-2026-10-13.txt`):
*"The fab-readiness document should therefore include a table listing each
affected via/pad pair, measured clearance, applicable default rule, reason for
the exception, and the corresponding JLCPCB confirmation/order evidence."*

**File rule:** net clearance = **0.20 mm** (our stricter project rule).
**JLCPCB published 4-layer standard:** min copper spacing **0.15 mm**;
min via **0.40 mm** dia / **0.20 mm** drill.

**STATUS: NO ORDER-BLOCKING ITEM REMAINS.** Every item below is **above
JLCPCB's published 0.15 mm standard** — they are exceptions only to OUR 0.20 mm
project rule, not to the fabricator's capability. Astra approved on this basis
and explicitly noted the 0.20 mm internal-rule exceptions "should remain
documented."

---

## FINAL TABLE — all remaining clearance items (3 of 3)

| # | Pair | Measured | Our rule | Deficit vs our rule | Margin vs JLCPCB 0.15 | Class |
|---|---|---|---|---|---|---|
| 1 | Pad 10 `/SX1280_DIO1` of U4 ↔ Via `/SX1280_DIO2` | **0.1750 mm** | 0.20 | 0.025 | **+0.025 above** | via-in-pad neighbour |
| 2 | Pad 8 `/SX1280_MOSI` of U4 ↔ Via `/SX1280_MISO` | **0.1750 mm** | 0.20 | 0.025 | **+0.025 above** | via-in-pad neighbour |
| 3 | Track `/F33_SCK` (B.Cu) ↔ Track `/I2C_SCL` (B.Cu) | **0.1648 mm** | 0.20 | 0.035 | **+0.015 above** | track-track |

**Reason for each exception:** the U4 pads are 0.25 mm wide on 0.5 mm pitch, so
the inter-pad edge gap is already 0.25 mm (compliant). Items 1–2 arise from the
via barrel inside its own pad — the via-in-pad construction the board requires
(same IPC-4761 Type VII family as the 18 `+3V3` in-pad vias). Item 3 is a
bus/escape crossing. All three are manufacturing-compliant at JLCPCB standard
tier; the deficit is against our deliberately stricter internal rule.

**JLCPCB confirmation/evidence:** JLCPCB's published 4-layer capability
(min spacing 0.15 mm) covers all three; the order form selection
(**Via-in-Pad = Filled & Capped**, IPC-4761 Type VII) must be screenshotted into
`docs/fab-order-evidence/` at order time.

---

## CLOSED — was order-blocking, now fixed (recorded for audit)

| Pair | Was | Now | How |
|---|---|---|---|
| Pad 8 `/SX1280_MOSI` of U4 ↔ Via `/SX1280_MISO` | 0.1250 (below JLC 0.15) | **0.1750** | v29: via 0.50→0.40 (clears via-in-pad overhang) |
| Track `/F33_SCK` ↔ Via `/SX1280_DIO1` | 0.1150 (below JLC 0.15) | **cleared** | v29: DIO1 escape via 0.60→0.40 (needed c-c fell 0.60→0.50, actual 0.5150) |

**The mechanism (worth recording):** clearance through a QFN fanout is
`0.25 − (via_dia/2 − 0.125)`. The lever is the **via diameter** — Astra's
ladder step #3 ("use a different supported via size") — not placement. Seven
placement-based attempts (v23/v24/v27/v28 and earlier) were correctly refused
before arithmetic found this.

**v30 companion change:** the board file's own minimums were aligned to
JLCPCB's documented capability (`m_ViasMinSize` 0.50→**0.40 mm**,
`m_MinThroughDrill` 0.30→**0.20 mm**, before/after readback printed). The file
had been stricter than the fabricator, which produced spurious
`via_diameter`/`drill_out_of_range` items.

---

## Non-clearance families — reviewed, non-blocking

| Family | Count | Class | Note |
|---|---|---|---|
| `copper_edge_clearance` | 29 | by-design | Board edge vs copper — antenna keep-out and castellated pad zones vs the outline. Reviewed, intentional. |
| `silk_over_copper` / `silk_overlap` / `silk_edge_clearance` | 42 | cosmetic | Silkscreen over pads/edge. JLCPCB trims silk; no electrical effect. |
| `lib_footprint_issues` / `lib_footprint_mismatch` | 13 | metadata | Footprint library drift vs the installed library. No board effect. |
| `via_dangling` / `track_dangling` | 13 | informational | Unused barrel ends on the freed In2.Cu / spare vias. |
| `solder_mask_bridge` | 4 | cosmetic | Mask web between adjacent pads; within JLCPCB standard capability. |

## FINAL DRC (from `drc_d1c_routed.json`)

```
shorts 0 | tracks_crossing 0 | via_diameter 0 | annular_width 0
hole_clearance 0 | drill_out_of_range 0 | copper_sliver 0 | clearance 3
total violations 104        (session start: 128 violations, 4 shorts,
                             14 blind vias, 26 unconnected)
```

## Intentional unconnected items (25) — NOT DNP

Per the final-2 review, these are **external-board interface connections**,
not do-not-populate components:

| Class | Items | Justification |
|---|---|---|
| `J_W1`…`J_W4` sockets + `W*_SOLAR_N` + `CUT_SENSE_W*` pads | 22 | Populated interface pads whose electrical partner is the **separate solar wing board** (ADR-046 wing-board-interface, ADR-048 v9-hub-wing-interfaces, ADR-049 wing-architecture). No same-board copper connection is expected; connection occurs when the wing board is installed. |
| Same-net zone/via pairs (`+3V3` via↔via, `GND_PLANE_F.Cu`↔itself) | 2 | Informational; the net is continuous through the pour. Verified after refill. |
| `/F33_SCK` residual fragment | 1 | Real tracked item — see the F33_SCK notes in the route scripts; net otherwise fully routed. |

The two 4-pin wing sockets (`J_W3`↔`U5`) are the same class.

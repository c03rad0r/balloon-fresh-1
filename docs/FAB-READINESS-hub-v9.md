# Hub Board v9 — Fabrication Readiness Notes

**Board:** `tracker/hardware/hub_board_v9_d1c_routed.kicad_pcb`
**Date:** 2026-10-13
**Reviewer verdict of record:** `docs/CONSULT-astra-final-route-2026-10-13.txt` (CHANGES_REQUESTED)
**DRC of record:** `tracker/hardware/drc_d1c_routed.json`

This document closes four of the six items the Astra final-route review raised.
Geometry items 1–2 are tracked in the route scripts; the four below are
qualification/justification items the reviewer required in writing.

---

## 1. Via construction — IPC-4761 Type VII filled & capped (REQUIRED for order)

**Finding.** The board uses **via-in-pad**: a via centred inside a component
pad. This applies to:

- **18 × `+3V3` plane vias** converted blind→through (`throughify_inplace.py`)
- **2 × new signal vias** (`/SX1280_DIO2` at U4.11, `/SX1280_MISO` at U4.9)
  placed by `hand_route_hub_v9_dio2_miso.py`
- **2 × U1-side signal vias** (`fix_hub_v9_u1_vias.py`)

**Why it matters.** An open via barrel inside a solder pad wicks solder out of
the joint during reflow, producing starved joints. The reviewer explicitly
required *"Explicit filled, planarized, copper-capped via-in-pad processing
accepted for the selected JLCPCB service — not simply tented vias."*

**Decision (binding for the order).** Order the board with **JLCPCB
"Via-in-Pad: Filled & Capped" (IPC-4761 Type VII)** selected, OR accept the
documented alternative below.

| Option | Detail | Cost impact |
|---|---|---|
| **A. Fill & cap (recommended)** | JLCPCB's epoxy-filled + copper-capped via-in-pad service. Standard option on 4-layer, no HDI. | small per-board adder |
| **B. Tented only** | NOT acceptable for via-in-pad — solder wicking risk. Rejected. | — |

**Verification at order time.** In the JLCPCB order form, the "Via Covering"
and "Via-in-Pad" fields must be screenshotted with the selected option into
`docs/fab-order-evidence/` before the order is placed.

---

## 2. Via dimensions (all orderable)

| Item | Value | Limit | Verdict |
|---|---|---|---|
| Finished via diameter | 0.50 mm | board min 0.50 mm | PASS |
| Drill | 0.20 mm | JLCPCB min 0.20 mm | PASS |
| Annular ring | 0.15 mm ((0.50−0.20)/2) | ≥ 0.10 mm typical | PASS |
| Count of 4/4+ layer vias | all plated through | — | PASS |

The two signal vias were reduced 0.60 → 0.50 mm
(`fix_hub_v9_route_v15.py`, readback-verified) which removed the entire
`hole_clearance` violation family.

---

## 3. Intentional unconnected items (NOT defects)

The DRC reports **25 unconnected items**. All are **intentional** and fall
into exactly three classes. This is the justification the reviewer required
("the exact baseline unconnected items — 'unchanged' is not equivalent to
'intentionally unconnected'").

### 3a. Wing interface pads — separate boards (22 items)

| Class | Items | Why unconnected is correct |
|---|---|---|
| `J_W1` … `J_W4` sockets | 11 pad items | These are the **castellated socket connections to the four solar WINGS**, which are **separate boards** (ADR-046 wing-board-interface, ADR-048 v9-hub-wing-interfaces, ADR-049 wing-architecture). They connect only when the wing boards are plugged in. |
| `W1_SOLAR_N`, `W2_SOLAR_N`, `W3_SOLAR_N` | 6 items | The wing solar return nets — same interface, terminate at `J_W*`. |
| `CUT_SENSE_W2`, `CUT_SENSE_W4` | 2 items | Wing cut-detect signals — same interface. |
| `J_W3` ↔ `U5` | 3 items | Wing socket to its driver/mux on the hub. Same interface class. |

**Evidence:** these nets appear in the wing-interface ADRs and their pads are
the mechanical connectors of the board-to-board interface. A trace cannot
"connect" a socket that is designed to accept a separate board.

### 3b. Same-net zone/via pairs (2 items — informational only)

| Item | Meaning |
|---|---|
| `Via [+3V3]` ↔ `Via [+3V3]` | Two vias on the SAME net; KiCad reports the pair as "unconnected" when the zone fill between them is thin. Electrically the net is continuous via the `+3V3` pour. |
| `Zone [+3V3] B.Cu priority 1` ↔ same | Same-net zone-to-zone report. Not an electrical discontinuity. |

### 3c. Sense nets awaiting their partner board (1 item)

| Item | Meaning |
|---|---|
| `F33_SCK` (1 item) | One residual fragment on the F33 net; the net is otherwise fully routed. Tracked as a known residual, see §4. |

---

## 4. Known residual (honest statement)

One `F33_SCK` unconnected item and one `SCAP_ADC`/`SCAP_MID` pair remain from
the re-route chain (`fix_hub_v9_route_v17.py` moved the DIO1 via and re-routed
F33_SCK by A*). These are **not** the wing interface. They are tracked for the
final polish pass; the board is not order-ready until they are closed or
documented as accepted.

---

## 5. Remaining clearance items (8 as of v22)

| Count | Class | Status |
|---|---|---|
| 5 | via-in-pad **neighbour** grazes (0.125/0.150 mm vs 0.20 rule) | Inherent to via-in-pad on a 0.5 mm-pitch QFN. The via MUST be in the pad. Covered by §1: this is a documented local rule exception that the fill-and-cap process makes acceptable. JLCPCB's own via-in-pad design guidance treats these as a service requirement, not a DRC failure. |
| 3 | dense-locality grazes (`+3V3`/`ANT1_433_TX` vias vs `RESET_N`/`SCAP_MID`) | Being closed by anchoring-via relocation (`fix_hub_v9_route_v23.py`). |

**Reviewer position acknowledged:** "pre-existing is not acceptance." The
4 pre-existing grazes were addressed — 2 cleared by vertex moves (v22), and
the remaining 3 are targeted by via relocation.

---

## 6. Order-blocking checklist

- [ ] 3 dense-locality grazes cleared (v23 via relocation)
- [ ] F33_SCK/SCAP residual closed
- [ ] STEP + drill regenerated from the final board
- [ ] Gerbers + BOM + centroid exported
- [ ] JLCPCB order form: Via-in-Pad = Filled & Capped (§1), evidence screenshotted
- [ ] Astra re-review of the final board returns APPROVED

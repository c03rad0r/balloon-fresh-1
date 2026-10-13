# PLAN — Base-Station Board (ground side)

**ADR of record:** ADR-051 (canonical board-production order of operations)
**Status:** STAGE 1–2 DRAFT — **AWAITING OPERATOR APPROVAL before any placement**
**Author:** manager (Felix)
**Date:** 2026-10-13
**Inputs:** `docs/BASE-STATION-BOARD-CHECKLIST.md` (living component checklist,
2026-10-08), `docs/BASE-STATION-PCBA-D14-FREEZE.md`, ADR-071 (gateway basis),
ADR-072 (band-split duplex, BPF-before-LNA), ADR-079 (owned LNA), ADR-080
(XR-613), ADR-083 (2.4 GHz dish), ADR-084 (level control / AGC)

---

## Stage 0 — what exists today (honest inventory)

| Artifact | State |
|---|---|
| Component checklist | ✅ `BASE-STATION-BOARD-CHECKLIST.md` — 18 rows, OWNED/TO-BUY/OPT/TODO(unverified), ≈€274.58 to-buy (€441.57 incl. the LiteVNA 62) |
| Architecture ADRs | ✅ 071/072/079/080/083/084 |
| Schematic (.kicad_sch) | ❌ **does not exist** |
| Netlist / SKiDL source | ❌ **does not exist** |
| Board / placement / routing | ❌ **does not exist** |
| Gerbers | ❌ |

**Gate statement:** no board work begins until Stage 1's netlist is reviewed and
accepted. Per ADR-051, placement (Stage 3) may not start before the operator's
Stage-2 form-factor approval.

---

## Stage 1 — Logical definition (SKiDL netlist) — ADR-054

Deliverable: `tracker/hardware/base-station/netlist.py` written in **SKiDL**,
compiling to a netlist, ERC-clean (this would be the project's **first ever
ERC run** — ADR-054 context).

### Sub-circuits to express (from the checklist, by block)

| Block | Components (checklist rows) | Notes for the netlist |
|---|---|---|
| **433 RX chain** | Diamond A-430S15R Yagi (1), 433 MHz BPF (2), TQP3M9037 LNA (3, OWNED), PIN limiter (4), ADL5240 VGA (5) | **Order is normative (ADR-072 INV-3): antenna → BPF → LNA → limiter → VGA.** The BPF must be FIRST; the LNA would otherwise amplify 2.4 GHz TX leakage. |
| **2.4 GHz TX chain** | XR-613 (16), DSA level control (6), PA/FEM (closed DNP under D9/ADR-072) | Band-split duplex: **nothing in the duplex path may pass both bands through one element** (ADR-072 INV-1). 2.4 GHz latching circulator: **explicitly NOT used** (band-split instead). |
| **Level control** | AGC detector + ADC + MCU (7, 8), DSA (6) | Rows 5–6 are **separate physical instances** when both directions are automated: one AGC element in the 433 RX path, one DSA in the 2.4 GHz TX path. First-flight build: **qty 1 on TX only**; RX then runs manual/commanded gain. |
| **Bias / PSU** | row 14 (TODO(unverified)) | Power budget to be declared in the netlist; over-provision per Felix's design doctrine. |
| **Control / host** | MCU (row 8), interfaces | UART/USB to the host; must expose the level-control SPI/parallel bus for ADL5240. |
| **Antenna/coax** | Yagi (1) + PL→SMA adapter (12), 2.4 GHz dish (in scope of ADR-083, mechanical) | Connector placement is a **Stage-2** constraint, not Stage-1. |

### Stage-1 verification gate
- SKiDL compiles the netlist without error.
- **ERC runs clean** (first in project history).
- Every checklist row that is `TODO(unverified)` is either resolved or explicitly
  marked DNP/absent in the netlist with a comment.
- **Spec disputes must be resolved or flagged as blockers before layout:**
  - **Dispute A (checklist row 3):** TQP3M9037 433 MHz coverage — operator says
    0.1 MHz–6 GHz, Qorvo says 0.7–6 GHz. If 0.7 GHz is authoritative the part
    **does not cover the 433 downlink at all** and ADR-079 must be reopened.
    **Bench verification required** (S21 400–500 MHz on the LiteVNA 62) — this is
    a *measurement* task, not a layout task, and it gates the 433 RX chain.
  - **Dispute B (row 2):** the 68 dB duplex isolation figure is a composite of
    norms, not a measurement. Acceptance = BPF rejection ≥40 dB at 2.45 GHz +
    the end-to-end desense test.

---

## Stage 2 — Form factor / envelope

Deliverable: `docs/PLAN-base-station-form-factor.md` + a dimensioned drawing.

### Locked-by-constraint items (cannot be decided freely)
| Constraint | Source | Consequence |
|---|---|---|
| Mast-head LNA position | ADR-079 INV-1 — LNA **must be at the masthead** | The board likely **splits**: a small masthead LNA module + the shack board, OR one board with an explicit masthead feed. **This is a form-factor question for the operator.** |
| Band-split duplex, no circulator | ADR-072 INV-1 | Two physically separate RF paths with a hard band split; keep 433 and 2.4 GHz copper apart. |
| 2.4 GHz reflector | ADR-083 (bought Ku offset dish) | A 2.4 GHz feed point + connector; dish is mechanical/out-of-scope for the PCBA. |
| Positioning / stow | ADR-076/077/078 — **out of scope** of this board | No rotator/stow hardware on the PCBA. |
| Enclosure | checklist row 18 — external mechanical | Board outline must fit the enclosure, but the enclosure is not a PCBA part. |

### Proposed envelope (for operator approval)
- Board class: **2-layer or 4-layer** (decision point — 4-layer recommended if
  the 433 RX + 2.4 GHz TX co-existence needs a solid ground plane between them;
  this is exactly the class of decision the hub board taught us to make EARLY).
- RF section separated from DC/control by a ground-stitched boundary.
- All antenna connectors on one edge, castellated or SMA per the RF plan.
- Mounting holes at the enclosure pattern.

### Proposed Stage-2 gate (per ADR-052)
1. Dimensioned drawing + (if practical) a cardboard/3D-print mockup.
2. **Operator review in Signal** of the drawing.
3. **Astra spatial review** of the same drawing + the planned RF separation.
4. Only then: Stage 3 (deterministic placement) → Stage 4 (placement gate) →
   Stage 5 (routing) → Stage 6 (DRC gate + STEP/Gerbers).

---

## OPEN DECISIONS REQUIRED FROM THE OPERATOR (do not proceed without these)

1. **Masthead topology** — single shack board with a masthead LNA module, or a
   split masthead+shack design? (ADR-079 INV-1 forces the LNA to the masthead.)
2. **Layer count** — 2-layer (cheaper, harder RF co-existence) vs 4-layer
   (solid inner ground between 433 and 2.4 GHz).
3. **First-flight population** — full AGC+DSA (qty 2 level-control elements) or
   the sufficient first-flight build (qty 1, TX only)?
4. **TQP3M9037 dispute** — do we bench-measure S21 before building, or design
   with a placeholder 433-capable LNA and swap later?
5. **Enclosure** — which enclosure (drives the board outline)?

**Nothing is placed, routed, or ordered until these are answered and Stage 1–2
are approved.**

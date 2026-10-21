# ADR-118 — Flight board v10: two-sided population, three LR2021 sites, E28-2G4M27SX ranging module, minimal outline, human placement gate, visual-first reporting

- **Status:** **ACCEPTED — operator instruction, 2026-10-20** (verbatim directives below; this ADR records them as binding design rules for the next flight-board revision, `v10`).
- **Decision owner:** Felix (operator)
- **Supersedes (in part):** the v9 single-sided placement posture and the bare-chip SX1280 site (`docs/fab/SX1280-MODULE-DECISION.md`, PR #251 — its recommendation is hereby adopted); does **not** supersede ADR-034 (band split), ADR-035 (TDM), ADR-040 (site optionality — extended by the three-slot ruling), or the three-slot consolidation ruling (`docs/fab/V9-RADIO-SLOT-CONSOLIDATION.md`, 2026-10-14).
- **Split into:** ADR-119 (radio sites decision), ADR-120 (placement process + gates). This file remains the umbrella record of the operator's verbatim directives.
- **Reference:** `docs/modules/e28-2g4m27sx/E28-2G4M27SX_UserManual_v1.0.pdf` (merged to the default branch as the qualification source for the ranging module).

## The operator's directives, verbatim in substance (2026-10-20)

1. **Both sides of the board.** "parts are distributed on both sides of the circuitboard to make better / more efficient use of the available surface area."
2. **Three LR2021 boards total: two small (LP) + one F33.**
3. **The ranging radio is the whole E28-2G4M27SX board** — "the whole E28 board with the matching network included so that we don't need to design that ourselves." The bare QFN SX1280 + our own scattered 7-part network is abandoned (measured fatal: `SX1280-MODULE-DECISION.md`).
4. **Minimal outline.** "reduce the surface area of the board down to the surface that's required to hold the parts once you have placed them on both sides of the board."
5. **HUMAN PLACEMENT GATE — mandatory, not skippable.** "Show me the placement of the parts on the board before you start routing, so that I can verify that we are not wasting space. This human gate is important and not to be skipped."
6. **Visual-first reporting.** "I want regular visual updates … here in signal … No more talking about something on the circuit board without showing me what you're talking about."

## Consequences

### Placement (v10)

- **Two-sided population** is now the default. Per-module keep-outs still apply: the E28 manual §4.1 forbids routing under the module except in the digital corner, and requires the module kept away from interfering sources — on a two-sided board this constrains what sits **behind** each radio module site.
- **Radio count: four RF sites total.**
  - `U_A` — LoRa2021F33-2G4 (HP, 433 TX + optional 2G4) — Site A (exists in v9 as U2).
  - `U_B` — bare LoRa2021 LP (2G4 RX) — Site B (v9 U3).
  - `U_C` — **NEW** bare LoRa2021 LP — Site C (the missing third slot; may sit on the back side).
  - `U_D` — **E28-2G4M27SX** (ranging: SX1280 + PA + LNA + matching + 52 MHz crystal, 15×20 mm, 16 pads, 1.27 mm castellated pitch) replacing the bare-chip SX1280.
- The **E28 adds two control pins** vs the bare chip (`RX_EN`, `TX_EN` for its PA/LNA) and draws **580 mA TX peak** — the power entry/decoupling and the ESP32 GPIO budget (ADR-108 pin plan) must be re-derived.

### Sizing

- The outline shrinks to what the two-sided placement needs. The 70×70 mm v9 outline is **not** a constraint for v10. Wing sockets (4 edge seats, ADR-085) constrain the outline shape, not a fixed size.

### Process (binding on every session, v10 and after)

- **GATE:** placement is frozen for review by the operator BEFORE any routing begins. Routing before gate sign-off is a defect, not initiative.
- **VISUAL:** every substantive board claim made to the operator must come with a rendered image (3D view, copper plot, or annotated crop) delivered in Signal. Text-only board reports are a process violation.
- The image-freshness pre-commit hook (PR #250) enforces that committed renders match the board.

## Risks recorded (not blockers; the operator has decided)

- Two-sided assembly raises cost slightly at JLC (two stencils) — hand assembly by the operator remains the default for optional parts.
- Back-side RF sites sit over the front-side ground stitching; the E28 manual's keep-out rules must be honoured per site.
- 580 mA TX peak on a solar-harvester board: the energy budget (ADR-036) must be re-checked; likely constrains ranging to burst operation (already the ADR-035 posture).

## Reproduce

```
ls docs/modules/e28-2g4m27sx/          # the module datasheet, merged
git log --oneline -- docs/adr/118-*    # this ADR
```

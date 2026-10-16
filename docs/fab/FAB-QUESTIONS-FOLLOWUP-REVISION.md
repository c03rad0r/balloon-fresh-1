# FAB QUESTIONS FOR A FOLLOW-UP BOARD REVISION

**Status:** PERSISTED FOR LATER — deliberately NOT blocking the current board iteration.
**Decision (operator, 2026-10-16):** use conservative, non-unusual assumptions for this board revision;
get these answered for a follow-up revision.

## Why this document exists

`tracker/hardware/hub_board_v9.kicad_pcb` is **0.6 mm, 4-layer**. The project file declares **no
stackup**, so the dielectric height between L1 and L2 is unknown and the 50-ohm microstrip width is
unknown by a **factor of 3.7**:

| assumed L1–L2 dielectric | width for 50 Ω | what a 0.20 mm trace gives |
|---|---|---|
| 0.0752 mm | 0.099 mm | 30.4 Ω |
| 0.1000 mm | 0.146 mm | 40.8 Ω |
| 0.1088 mm | 0.162 mm | 43.9 Ω |
| 0.1300 mm | 0.202 mm | 50.4 Ω |
| 0.2100 mm (a 1.6 mm board) | 0.364 mm | 69.0 Ω |

## Why this is NOT reverted to a "standard" 1.6 mm board

**0.6 mm is deliberate and recorded:**
- `docs/adr/028-schematic-first-three-variants.md:107` — *"Board thickness must be 0.6mm (pico balloon
  weight constraint)"*
- `tracker/hardware/PCB-TWO-STAGE-PLAN.md:612` — *"Thickness revised to 0.6mm for pico-balloon weight
  budget."*

Reverting to 1.6 mm would break a weight budget, so the unusual element here is **required**, not
accidental. JLCPCB does offer 0.6 mm as a standard 4-layer thickness; what varies is the **L1–L2
dielectric**, which is the number that actually matters.

## The contradiction this has to close

`tracker/hardware/PCB-EXECUTION-PLAN.md` §3.1 states an RF width of **0.76 mm "on 1.6mm FR4"**, and §4.2
tabulates **"Thickness | 1.6mm"**. The board that was exported is **0.6 mm**. `tracker/hardware/C3-SIGNOFF.md`
flagged this on **2026-08-05** as unreconciled, and it remains so. **The same question will hit every
remaining board in the system as it reaches this stage**, so answering it once unblocks the end-to-end goal.

## The six questions

1. **Prepreg thickness and Dk between L1 and L2** for the standard 0.6 mm 4-layer build.
   *This single number sets the RF width; everything else follows from it.*
2. **Is 0.6 mm a standard 4-layer build, or a special one?** *Affects lead time and cost, and the range
   of available dielectrics.*
3. **Is controlled impedance offered, and at what tolerance** (e.g. ±10%)? *Determines whether the RF
   width is guaranteed or only nominal.*
4. **What trace width does your calculator give for 50 Ω single-ended on F.Cu** over that L1–L2
   dielectric at 0.20 mm minimum width? *Cross-checks in-repo arithmetic against the fab's own model.*
5. **Minimum trace width and spacing for this build** — the board currently assumes 0.20 mm both.
6. **Is 0.20 mm reliable at 0.6 mm 4-layer** for impedance-controlled traces, or is there a recommended
   minimum?

## Conservative assumptions used for THIS board revision

Recorded so the follow-up revision has a baseline to correct:

- **Stackup:** not declared; the board is graded against its own design rules, not against an assumed
  dielectric.
- **RF route:** laid at **0.20 mm**, the board's declared default, **deliberately not a 50-ohm figure.**
  This establishes connectivity. Impedance is left open rather than guessed — committing an unjustified
  width would repeat the error `PCB-EXECUTION-PLAN.md` already made.
- **Everything else:** the board's own frozen JLCPCB rules (0.20 mm track/clearance, 0.60 mm via,
  0.30 mm drill, 0.25 mm hole-to-hole).

## Not to be sent without the operator's approval

Nothing here has been sent to any fab, and no order has been placed or authorised.

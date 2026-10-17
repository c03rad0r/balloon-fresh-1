# The ERC errors and "U1.41" — classified, measured 2026-10-16

**Both items were described wrongly in the working record. Corrected here from measurement.**
Nothing in this file was fixed by adding a connection, and that is deliberate — see the reasoning.

## 1. "U1.41 — the SX1280's exposed ground pad has no net" — WRONG on every clause

Measured by `tracker/hardware/diagnose_u1_41.py` and `inspect_u1_pads.py`:

| claim in the record | measured |
|---|---|
| "U1 is the SX1280" | **U1 is the ESP32-S3-WROOM-1U-N8R8.** The SX1280 is **U4** |
| "pad 41 has no net" | **all thirteen pad-`41` objects are on GND** |
| "the footprint is `SX1280_QFN24.kicad_mod` pads 1..24 + 25" | that footprint belongs to **U4**; it declares `1..24` + `0`, and is irrelevant here |

**What the defect actually is.** A WROOM-1U has **41 pads** (1..40 + one exposed ground pad). This
board's `U1` carries **62 pad objects across 42 distinct numbers**:

```
pad '41' : 13 objects at 13 DISTINCT positions, ALL net=GND
           twelve 0.6×0.6 mm + ONE 3.9×3.9 mm (the central thermal pad)
           => NUMBER COLLISION on distinct copper; KiCad cannot address them separately
pad ''   :  9 objects at  9 DISTINCT positions, ALL net=(none), 0.9×0.9 mm
           => NINE FLOATING PADS CONNECTED TO NOTHING  (the genuine electrical gap)
```

The 0.6×0.6 grid plus the 3.9×3.9 centre is the signature of a **footprint built by replicating a pad
without renumbering**. This is also why the stitcher reported `U1.41` twelve times as UNRESOLVABLE: it
was trying to stitch pads already on the plane.

## 2. The 20 ERC errors — classified by `classify_erc_errors.py`

| count | class | action |
|---|---|---|
| **12** | `U_CUT1–4` pins 4/5/6 (`ARM`, `CTRL`, `SENSE`) — **expected-open provisioning stubs** | **do NOT wire** |
| **4** | `U1` pins 3/13/14/35 (`EN`, `USB_D−`, `USB_D+`, `IO42`) — plausible intentional no-connects | confirm, then **exclude from ERC** (a no-connect marker is the correct schematic form) |
| **2** | `U4` pins 2/11 (`VDD_IN`, `VBAT_IO`) — `power_pin_not_driven` | **settle against pin types first**; this may be a modelling error, not missing copper |
| **1** | a 0.0508 mm dangling wire | **delete it** — the only unambiguous artefact in the set |
| **1** | `U_HUB_CVT` pin 4 (`VOUT`) | classify before touching |

### Why the twelve `U_CUT` pins must NOT be wired

The netlist's own description of `U_CUT1` states the circuit is undecided *and why*:

> "THE DRIVE MUST BE A LATCHED ONE-SHOT: cutting is irreversible and a level-sensitive driver can re-fire
> on a reset, a brown-out, a firmware retry or a floating gate (ADR-051 §2.5.1). **Exact part, the sense
> divider and the GPIO assignment are all `TODO(unverified)`**"

And `docs/analysis/ADC-PIN-RESOLUTION-OPEN17-OPEN25.md` says the sense path **cannot** currently be built:

> "One GPIO + 4:1 mux / resistor-ladder for cut-sense — **the only workable shape** ... But it still needs
> **ONE ADC input, and none is spare.**"

**So these twelve pins are unconnected for two independent reasons** — an undecided drive topology and an
exhausted pin budget. **Wiring them would invent an undecided circuit and bury an open item.**

## 3. A live contradiction found while classifying

`docs/analysis/ADC-PIN-RESOLUTION-OPEN17-OPEN25.md` is titled
**"ADC / analog-sense pin resolution on the ESP32-S3 — OPEN-17 and OPEN-25 CLOSED"**.

The netlist's `U_CUT1` description **still says "see OPEN-25 and OPEN-28"**.

**Two live records disagree and nothing surfaces it** — the same defect class as the stale inventory
(2026-10-14), the stale order-readiness counts (2026-10-15), and ADR-046 §4.2 vs the built board.
This is the **fourth** instance found in one pass. Not resolved here: which record owns `OPEN-25` is a
decision, and the closing analysis adds a constraint (no spare ADC) that whoever resolves it must see.

## 4. What this means for "the one real electrical defect"

**There are arguably two, and neither is the one the record named:**

1. ~~**nine unnamed pads on `U1` with no net** — real floating copper~~ **CORRECTED 2026-10-17:** they are
   `F.Paste`-only stencil apertures — **no copper layer at all**, so they cannot be "floating copper" and
   have nothing to connect. They are the standard idiom for controlling paste coverage over a large
   thermal pad. See `U1-FOOTPRINT-DIAGNOSIS.md`.
2. **thirteen pads sharing number `41`** — duplicated numbering on distinct copper

Plus one genuine but small artefact: the 2-mil dangling wire.

**Neither of the first two is a wiring omission, and both are FOOTPRINT edits** — which this repo forbids
by hand (`build_hub_board_v9.py` rule R2: positions come from parametric rules; a change is a *rule*
change, and a builder re-run must restore the project files). So the fix must go through the builder or
an ADR, not a script that nudges pads.

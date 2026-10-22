# v10 connectivity OPEN ITEMS

Every pin whose connection is NOT decided yet, or whose decision is UNVERIFIED.
This file is the companion to `v10_pinmap.reg`: the registry says what IS, this says
what is NOT YET DECIDED and what evidence would close it.

Rule: a pin may be `UNASSIGNED` only if it is listed here. The registry check prints
the UNASSIGNED list every run; if a pin appears there and not here, that is a defect.

---

## OPEN-16 — ESP32-S3 GPIO0 (J_PROG pin 6)
- **State:** unverified. The WROOM-1U's GPIO0 pad number is not named by any in-repo
  source. An earlier guess (pad 25) was WRONG — pad 25 is IO48 and already carries
  `/U3_RESET_N`; the guess had clobbered that net and was reverted (PR #266).
- **Blocked on:** Espressif ESP32-S3-WROOM-1 datasheet pin table (not in repo).
- **Workaround in force:** J_PROG pin 6 dangles. Flashing still works over
  USB-Serial-JTAG (EN + USB D± are connected), which needs no GPIO0.
- **Closes when:** datasheet table pasted in, or GPIO0 read off a physical module.

## OPEN-E28-EN — E28 RX_EN (pin 8) / TX_EN (pin 9)
- **State:** unassigned. ADR-123 budgeted two spare GPIOs for them but named no pads.
- **Note:** these are NEW versus the bare SX1280 (which had no PA/LNA enables), so no
  v9 pin carried over.
- **Closes when:** the ESP32-S3-WROOM-1 pad numbers for two free GPIOs are verified
  from the datasheet (same blocker as OPEN-16).

## OPEN-17 / OPEN-25 (merged) — the LAST ADC INPUT on the board

**State:** unresolved, and now BLOCKING two functions that are both in the design.

Two things compete for one ADC-capable pin:

1. **`/SCAP_ADC` — the supercap-rail monitor** (`R_DIV1`/`R_DIV2`, 2× 1 M, ADR-006).
2. **`/CUT_SENSE_W1..W4` — the cut-sense lines** (ADR-051 §2.6), which the operator has now
   confirmed are IN the design (ADR-129 D5).

**Measured in the v9 netlist: `/SCAP_ADC` connects to NOTHING but its own divider.** In v9 the
node was a net between `R_DIV1.2` and `R_DIV2.1` and had **no ESP32 pin at all** — the rail
monitor was never actually readable. So this is not a regression v10 introduced; v10 inherited it
by carrying the divider across. It is recorded here because ADR-129 restores the divider and
therefore makes the gap explicit.

**The arithmetic** (`docs/analysis/ADC-PIN-RESOLUTION-OPEN17-OPEN25.md`): there is **no spare ADC
input**. `IO13` is spent on the F33 rail monitor (ADR-047 §6, `F33_VSENSE`). ADR-029 §4 forbids
GPIO0 for the supercap divider (it is a strap), and ADR-069 forbids dividers on straps generally.

**The three shapes the analysis allows, in its own order of preference:**

1. **Give the cut-sense the one-GPIO + resistor-ladder/mux shape** ADR-051 §2.6 already allows.
2. **Free an ADC-capable pin** by relocating one *digital* assignment onto the free IO22–IO34
   block (currently `U1.26..U1.30`), rather than sharing IO13's analog node. This preserves
   rail-monitor accuracy.
3. **Only if no digital line can move**, share IO13 — and then the divider network must be
   designed and *measured* for burden and post-cut interpretability before flight.

**Not decided here.** `U_CUT1..4` pin 3 is landed on `/CUT_SENSE_W<n>` and the divider is landed
on `/SCAP_ADC`; **neither has a U1 pin.** Closing this item is what gives them one.

**Closes when:** a shape is chosen and a U1 pad is assigned to `/SCAP_ADC` and to the cut-sense
encoding. **`/SCAP_ADC` and `/CUT_SENSE_W1..W4` will remain single-ended nets until then** — they
are a deliberate, documented open item, not an omission.

## OPEN-26 (amended) — the hub panel connector pin count is DECIDED

**Closed for the connector:** `J_HUB_PV` is a **5-pin** connector (operator, 2026-10-22):
`PV_P`, `PV_MID1`, `PV_N`, `GND` (Option B) **plus a spare `PV_MID2`** pin to future-proof the
3-cell H3 sizing at ~one extra contact. `J_HUB_PV.3` is `UNASSIGNED` until/unless H3 is chosen.

**Still OPEN:** the hub array's **cell count** (H2 2-cell recommended vs H3 3-cell fallback vs
M5/M6 5–6 cell), its **mounting plane**, and the **harvester part** (ADR-051 §4 items 3/5/6).
The panel is an **external panel like the wing boards** — no board area is reserved for cells
(ADR-129 D3).

## OPEN-31 — `U_CUT1..4` driver part, sense divider and latch topology

**State:** the cut CHANNELS are IN the design (ADR-129 D5), but the part is `TODO(unverified)`.
`U_CUT<n>` is a 3-pin provision: `VSCAP` / `GND` / `CUT_SENSE_W<n>`.

**The drive is mandated to be a LATCHED ONE-SHOT** (ADR-051 §2.5.1). Cutting is irreversible and
a level-sensitive driver can re-fire on reset, brown-out, retry or a floating gate — each fire
costing ~2.59 J of the bank's 16.63 J, at the exact moment the bank matters. Firmware must
serialise cuts: 4 simultaneous fires = 9.9 A = **2.4× the IRLML2502 class rating**.

**Closes when:** the driver part, the sense divider and the latch topology are chosen (OPEN-25).

## CLOSED 2026-10-21
- **E28 GND pads 2/7/10/16** were floating metal (the netlist only carried the pins
  that existed on the bare QFN24). Found by the registry on its first run; fixed in
  `build_hub_board_v10.py`; authority = `footprints/e28/E28-2G4M27SX.md`.
- **U_C.9 hit by a track at 0.000 mm** — the pad has no net, and the clearance checker
  skipped unnamed pads (bug B5). Both fixed: the pad is now a modelled obstacle and the
  checker treats unnamed pads as metal. Regression test: `tests/test_v10_connectivity.py`.

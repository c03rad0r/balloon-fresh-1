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

## CLOSED 2026-10-21
- **E28 GND pads 2/7/10/16** were floating metal (the netlist only carried the pins
  that existed on the bare QFN24). Found by the registry on its first run; fixed in
  `build_hub_board_v10.py`; authority = `footprints/e28/E28-2G4M27SX.md`.
- **U_C.9 hit by a track at 0.000 mm** — the pad has no net, and the clearance checker
  skipped unnamed pads (bug B5). Both fixed: the pad is now a modelled obstacle and the
  checker treats unnamed pads as metal. Regression test: `tests/test_v10_connectivity.py`.

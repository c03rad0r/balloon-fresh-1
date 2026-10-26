# Provenance — E28-2G4M27SX_UserManual_v1.0.pdf

Recorded 2026-10-26 so this datasheet's identity and origin are checkable, not assumed.

## The file

| | |
|---|---|
| path | `docs/modules/e28-2g4m27sx/E28-2G4M27SX_UserManual_v1.0.pdf` |
| **sha256** | `0a8bc8afb33bc4ed47edb9e52af2f55b1e87c9adbbbc27e859a6944f70e45af3` |
| size | 948 204 bytes |
| pages | 14 |
| PDF version | 1.7 |
| first added to this repo | commit `a9626dd4` (feat(v10): two-sided board, 3x LR2021 + E28-2G4M27SX module, …) |

## Origin (verified 2026-10-26)

- **Official source:** <https://www.cdebyte.com/pdf-down.aspx?id=1671> — Chengdu Ebyte Electronic Technology Co., Ltd.
- **Product page:** <https://www.cdebyte.com/products/E28-2G4M27SX/1>
- The copy fetched from that URL on 2026-10-26 is **byte-identical** to the file already in this
  repository (same sha256 above). So the in-repo datasheet is the current official document and no
  newer revision has been substituted.

To re-verify at any time:

```bash
curl -sL -o /tmp/e28.pdf "https://www.cdebyte.com/pdf-down.aspx?id=1671"
sha256sum /tmp/e28.pdf docs/modules/e28-2g4m27sx/E28-2G4M27SX_UserManual_v1.0.pdf
```

If the hashes differ, Ebyte has published a revision — re-read §3 (pin table), §4.1 (hardware
design) and the Chapter 3 drawing before relying on anything recorded elsewhere, and update this file.

## Facts this document is cited as owning

Extracted with `pdftotext -layout`; the mechanical drawing read from a 200 dpi render (the drawing is
an image, so it has no text layer).

| fact | location | value |
|---|---|---|
| antenna interface | §2.2 p.4 | **"IPEX/PCB", equivalent impedance about 50 Ω** |
| module is SX1280 + amplifiers | §1.1 p.3 | **"SX1280+PA+LNA"** — PA and LNA are inside the module |
| pin 8 | §3 p.5 | `RX_EN` — "LNA control pin, **active high**" |
| pin 9 | §3 p.5 | `TX_EN` — "PA control pin, **active high**" |
| pin 11 | §3 p.5 | `NRESET` — "built-in pull-up resistor **50K**" (the ONLY documented pull-up) |
| logic level | §2.2 p.4 + §4.1 p.6 | 3.3 V; series resistor 1k–5.1k **only for 5 V** lines |
| current | §2.2 p.4 | emission **580 mA**, receive **14.5 mA**, sleep **2.0 µA** |
| rated power | §4.2 p.7 | set the SX1280 to **0 dBm**; module outputs **27 dBm** |
| sensitivity | §2.2 p.4 | −130 / −131 / −132 dBm, "high sensitivity mode **enabled**" |

## Two discrepancies inside the document itself — do not silently "fix" either

1. **Mechanical size.** The Chapter 3 **drawing** dimensions the module at
   **16.0 × 20.0 × 2.90 mm**, while the specification **table** (§2.2) says **15 × 20 mm**.
   This repository's footprint `tracker/hardware/footprints/e28/E28-2G4M27SX.kicad_mod` has pad rows
   **15.0 mm** apart, which matches the **drawing** (16.0 mm outline, pads inset ≈0.5 mm per side) —
   **not** the table. Treat the drawing as the land-pattern reference. Anyone "correcting" the
   footprint to the table's 15 mm would shrink the pad spacing by 1 mm.

2. **Chip name.** This manual and the repo's BOM say **SX1280**; the product page calls it **SX1281**.
   They are the same family and driver-compatible; the board and firmware assume SX1280. Recorded so
   the mismatch is not mistaken for a wrong part later.

## What this document does NOT answer

Verified absent — see `docs/fab/status/EBYTE-QUESTION-e28-enables.md`:

- whether `TX_EN` and `RX_EN` may be asserted **simultaneously**;
- what the module does while those pins are **floating** (which is the state during an ESP32 reset);
- any **sequencing** requirement between VCC / `NRESET` / `TX_EN` / `RX_EN`.

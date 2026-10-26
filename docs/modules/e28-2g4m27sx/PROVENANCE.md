# Provenance — E28-2G4M27SX User Manual

Recorded 2026-10-26 so this datasheet's identity and origin are checkable, not assumed.
**Two revisions are held deliberately.** Both are Ebyte's own; neither is a fork or a mirror.

## Revision history (from the manual's own Revise History table)

| version | date | note | operator |
|---|---|---|---|
| 1.0 | 2021-11-15 | Initial Version | Linson |
| 1.0 | 2022-10-13 | Bug fixes | Yan |
| 1.1 | 2024-02-23 | Bug fixes · **Modified ranging description** | Hao |
| **1.2** | **2024-04-18** | Bug fixes | Hao |

## The two files

| | v1.2 — **CANONICAL** | v1.0 — retained |
|---|---|---|
| path | `E28-2G4M27SX_UserManual_v1.2.pdf` | `E28-2G4M27SX_UserManual_v1.0.pdf` |
| sha256 | `4fc67a87cea1dbf5bb18487745681df35982bdd68a9c6f517b2c1012e0f7cf9d` | `0a8bc8afb33bc4ed47edb9e52af2f55b1e87c9adbbbc27e859a6944f70e45af3` |
| size | 946 412 bytes | 948 204 bytes |
| pages | 14 | 14 |
| source | supplied by the operator 2026-10-26 (downloaded from Ebyte) | `cdebyte.com/pdf-down.aspx?id=1671`, added in `a9626dd4` |

Note: the v1.2 file's **PDF metadata Title field reads `E01-2G4M27D_产品规格书_v1.0`** — a stale template
field left by the vendor. The *content* is the E28-2G4M27SX manual (verified by extracting the text and
reading the revise-history table). Do not identify this document by its metadata title.

## What changed between them — 82 substantive lines

1. **The chip is SX1281, not SX1280.** v1.0 says `SX1280` on the cover, in §1.1, in the §3 pin-table
   cross-references, and throughout §4.1. **v1.2 says `SX1281` in every one of those places.** The
   vendor corrected it. **Discrepancy resolved — the repo's BOM (which always said SX1281) was right
   and the older manual was the stale side.**
2. **Ranging / time-of-flight claims were removed.** v1.0 carried a "Ranging, with Time-of-flight
   function" feature bullet and stated the chip "also integrates time of flight, which is suitable
   for ranging". v1.2 deletes both. This matches silicon: **SX1281 has no ranging**; only SX1280
   does. Any plan that expects this module to range is wrong — ranging needs a bare SX1280.
3. Page numbering and layout shifted (TOC entries move by one page). No electrical, pinout or
   mechanical value changed.

## The mechanical drawing is UNCHANGED between revisions

Re-rendered v1.2 at 400 dpi and re-read: still **16.0** (width) × **20.0** (length) × **2.90**
(thickness), pin pitch **1.27**, first pad centre **2.69** from the upper edge, pads numbered 1–8
down one long edge and 16–9 down the other, `IPX` in the lower-right recess. The §2.2 table still
says `Dimensions 15*20mm`. So the internal inconsistency survives the revision — it is a vendor
convention, not a typo that got fixed.

**Pad geometry, read from the drawing this time in full:**

| item | value |
|---|---|
| pad quantity | 16 |
| pad width (along the edge) | **0.80 mm** |
| castellated opening | **0.65 mm** |
| pad depth, top side | 0.50 mm |
| pad depth, bottom side | 1.00 mm |
| tolerance | **X.X ± 0.1 mm** |
| unit | mm |

### Against our footprint, measured from `tracker/hardware/hub_board_v10.kicad_pcb`

```
U_E28 orientation  -90 deg
pad size (local)    2.20 x 1.00 mm
board-space extent  x 1.00 mm  (along the row / pitch direction)
                    y 2.20 mm  (radial)
pad 1..8 x          48.555 .. 57.445, pitch measured 1.27 across all 7 gaps
rows y              59.10 and 74.10  ->  row separation 15.0 mm
gap between adjacent pads = 1.27 - 1.00 = 0.27 mm
```

- **Row separation 15.0 mm.** The governing dimension. Both readings of the drawing (15.0 body
  with pads straddling the edge, or 16.0 body with pads inset 0.5) put the **pad centres** 15.0 mm
  apart, so the footprint is correct either way. **Do not "correct" this toward a 14 mm figure.**
- **Along-edge pad is 1.00 mm; the vendor draws 0.80 mm.** Consequence: our inter-pad gap is
  **0.27 mm** where the vendor intends **0.47 mm**. It is legal (board rule is 0.20 mm) and no DRC
  violation results, but it is 0.10 mm tighter than the vendor's intent and just outside the
  vendor's ±0.1 mm tolerance. **Recorded as a candidate change for the next board revision, not
  applied now** — narrowing it would invalidate the routed radio link and the DRC baseline for a
  cosmetic gain on a board that already passes.
- **Radial pad is 2.20 mm; the vendor draws 1.00 mm (bottom side).** Ours extends further past the
  body edge, which buys more solder fillet. Harmless.

## Facts this document is cited as owning (v1.2 wording)

| fact | location | value |
|---|---|---|
| antenna interface | §2.2 | **"IPEX/PCB", equivalent impedance about 50 Ω** |
| module is SX1281 + amplifiers | §1.1 | **"SX1281+PA+LNA"** — PA and LNA are inside the module |
| pin 8 | §3 | `RX_EN` — "LNA control pin, **active high**" |
| pin 9 | §3 | `TX_EN` — "PA control pin, **active high**" |
| pin 11 | §3 | `NRESET` — "built-in pull-up resistor **50K**" (the ONLY documented pull-up) |
| logic level | §2.2 + §4.1 | 3.3 V; series resistor 1k–5.1k **only for 5 V** lines |
| current | §2.2 | emission **580 mA**, receive **14.5 mA**, sleep **2.0 µA** |
| rated power | §4.2 | set the SX1281 to **0 dBm**; module outputs **27 dBm** |
| sensitivity | §2.2 | −130 / −131 / −132 dBm, "high sensitivity mode **enabled**" |
| no ranging | v1.2 revision note + absent feature bullet | SX1281 has no time-of-flight |

## Re-verify

```bash
# canonical revision on disk is the vendor's current one
sha256sum docs/modules/e28-2g4m27sx/E28-2G4M27SX_UserManual_v1.2.pdf
pdftotext -layout docs/modules/e28-2g4m27sx/E28-2G4M27SX_UserManual_v1.2.pdf - | grep -A6 -i "Revise History"

# the drawing has no text layer — render it
pdftoppm -png -r 400 -f 6 -l 6 docs/modules/e28-2g4m27sx/E28-2G4M27SX_UserManual_v1.2.pdf /tmp/e28
```

If Ebyte publishes a v1.3, diff its extracted text against `E28-2G4M27SX_UserManual_v1.2.pdf` before
relying on anything recorded elsewhere, and update this file.

## What this document does NOT answer

Verified absent from **both** revisions — see `docs/fab/status/EBYTE-QUESTION-e28-enables.md`:

- whether `TX_EN` and `RX_EN` may be asserted **simultaneously**;
- what the module does while those pins are **floating** (the state during an ESP32 reset);
- any **sequencing** requirement between VCC / `NRESET` / `TX_EN` / `RX_EN`.

Only `NRESET` documents a 50 K internal pull-up. The enables have no documented default, in either
revision. This is not a document gap that a newer revision closed.

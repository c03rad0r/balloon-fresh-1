# E28-2G4M27SX — dimensions resolved without buying one

Status: **RESOLVED for body, pads, pitch, thickness. ESTIMATE for IPEX position.**
Written 2026-10-26 in response to "can you reliably get the dimensions out of the datasheet or
some other source?"

The operator cannot wait for the Amazon part (slow delivery) and needs the outline before placing
the board. So: triangulate the published sources instead of measuring.

## Answer in one line

**Body 15.0 × 20.0 mm, castellation envelope 16.0 × 20.0 mm, thickness 2.90 mm, pin pitch 1.27 mm.**
The "15 vs 16" contradiction is not a contradiction — it is **body vs pad envelope**.

## The apparent conflict

| source | says | kind |
|---|---|---|
| manual §2.2 main-parameters table | `Dimensions 15*20mm` | body |
| manual Ch.3 **drawing**, page 5 | `16.0` × `20.0`, thickness `2.90` | envelope |
| Chinese 产品规格书 (xonlink mirror) | `外形尺寸 15*20mm` | body |
| ebyte.com product page (EN + CN) | `15*20mm` | body |
| ebyte.com E28 family table | `E28-2G4M27SX … 15*20` | body |
| JLCPCB C5333988 package field | `SMD, 20x16mm` | envelope |
| RobotShop / Flash Army / Hubtronics | `15*20mm` | body (re-published) |
| cirkitdesigner | `16 × 24 × 2.2` | **wrong — ignore** |

Six independent sources say 15. Two say 16.0, and they are the two that describe **metal extent**:
Ebyte's own mechanical drawing and JLCPCB's package field (which JLCPCB derives from manufacturer
CAD, not from marketing copy).

## Why both numbers are correct

The drawing prints, on the same page, both the `16.0` outline **and** the pad geometry:

- `Bottom-pad horizontal depth 1.00 mm`
- `Top-pad horizontal depth 0.50 mm`
- `Castellated opening 0.65 mm`

A castellation **straddles** the moulded edge. A 1.00 mm deep pad on a 15.0 mm body protrudes
0.50 mm each side:

```
body            15.0 mm
+ 2 x 0.50 mm   1.0  mm   (pad overhang, one each side)
= envelope      16.0 mm   <- the number the drawing dimensions
```

**15.0 is the body. 16.0 is the pad envelope. Both printed values are right; they measure
different things.** This is the same class of defect the repo already names — two records
asserting different values for one parameter with nothing saying they are different quantities.

## What this means for our footprint — and a correction to my last message

The governing dimension for solderability is the **pad-centre row separation**, not the body width.
Our footprint has pad centres at **x = ±7.5 mm → 15.0 mm apart** (`footprints/e28/E28-2G4M27SX.md`).

```
interpretation A: body 15.0, pads straddle the edge, centres at ±7.5   -> 15.0 mm
interpretation B: body 16.0, pads inset 0.5 mm,     centres at ±7.5   -> 15.0 mm
```

**Both give 15.0 mm.** So the footprint is correct under either reading.

**CORRECTION.** In `E28-BENCH-MEASUREMENT-PLAN.md` I ranked "body width 15 or 16 mm" as
*board-scrapping-class, test this first*. That was **too strong**. The pad spacing is 15.0 mm
either way, so the 15-vs-16 question cannot scrap the board. What it actually moves is:

- the **courtyard** (currently 17.2 × 22.1 mm, built as 15×20 + pad overhang) — self-consistent
- the **3D body/keep-out envelope**, by 1.0 mm in width
- the **collision check** against neighbouring parts

Real, but a 1 mm mechanical-envelope question, not a solderability one. A caliper is still the
cheapest confirmation, but it is **no longer a reason to delay placing the board.**

## Thickness and pitch

- **2.90 mm** — drawing only; no table gives it. Single source, but it is a dimensioned
  mechanical drawing, and it agrees with the 1.5 ± 0.1 g mass at this size.
- **1.27 mm** pitch — table, drawing, product page, and the module is described as
  "SMD type (pin spacing 1.27 mm)" in prose. Four sources. Solid.

## IPEX position — ESTIMATE, not a dimension

No published source dimensions the connector. So it was measured **in the drawing**: 400 dpi
render, outline used as the scale reference (16.0 × 20.0).

| quantity | value |
|---|---|
| centre across the outline width | **≈ 78 %** (0 % = pin-1 edge) |
| centre down the outline length | **≈ 88 %** (0 % = pin-1 end) |
| connector land size | ≈ 0.18 × width ≈ **2.9 mm** |
| uncertainty | **±1.5 mm** — raster measurement, no dimension line |

Two useful consequences:

1. **It is a U.FL / IPEX-1 / MHF1 connector, not MHF4.** The ~2.9 mm land matches a U.FL land
   pattern (≈3.0 × 3.1 mm); MHF4 is ≈1.2 mm. **This decides which pigtail we buy** — an MHF4
   cable will not mate a U.FL jack. Worth pinning before the order, independent of the module.
2. It is in the **lower-right recess, diagonally opposite pin 1** — consistent with the Ch.3
   drawing and with the pin-16 corner the antenna volume is currently anchored at.

Board-mapped estimate (module body x 43.0–63.0, y 59.1–74.1; drawing width axis → board y,
length axis → board x, pin 1 at (48.555, 59.10)):

```
IPEX centre ≈ (60.6, 70.8) mm  +/- 1.5 mm
```

The antenna volume extends 32 mm, so a 1.5 mm anchor error is inside its margin. It is recorded as
an estimate so a later exact figure can replace it without anyone having to guess which number was
measured and which was inferred.

## Do not order the wrong variant

```
E28-2G4M27SX   15 x 20.0   IPEX        <- ours
E28-2G4M27S    15 x 26.5   PCB antenna <- 6.5 mm longer, no connector
E28-2G4M20SX   20 x 15     IPEX, 20 dBm
E28-2G4M12SX   17.8 x 15   IPEX, 12 dBm
```

The `-S` is **6.5 mm longer**. Substituting it silently breaks the layout.

## What is still not obtainable from any public source

- Simultaneous `TX_EN` + `RX_EN` (Q2)
- Behaviour while both float during ESP32 boot (Q4)
- Sequencing VCC / NRESET / TX_EN / RX_EN (Q5)

These are electrical, not mechanical. No amount of drawing measurement reaches them, and they do
not block placing the board — they block **first power-on** and decide whether an interlock is
needed.

## Pad geometry — read in full from the rev 1.2 drawing

| item | value |
|---|---|
| pad quantity | 16 |
| pad width (along the edge) | **0.80 mm** |
| castellated opening | **0.65 mm** |
| pad depth, top side | 0.50 mm |
| pad depth, bottom side | 1.00 mm |
| tolerance | **X.X ± 0.1 mm** |
| unit | mm |

Measured against `tracker/hardware/hub_board_v10.kicad_pcb` (footprint rotated −90°):

```
pad size (local)     2.20 x 1.00 mm
board-space extent   x 1.00 mm  along the row (pitch direction)
                     y 2.20 mm  radial
pad 1..8 x           48.555 .. 57.445, pitch measured 1.27 across all 7 gaps
rows y               59.10 / 74.10  ->  row separation 15.0 mm
gap adjacent pads    1.27 - 1.00 = 0.27 mm   (vendor's 0.80 pad gives 0.47 mm)
```

- **Row separation 15.0 mm — correct, leave it alone.** Both readings put the pad *centres* 15.0 mm
  apart: 15.0 body with pads straddling the edge, or 16.0 body with pads inset 0.5 mm. Do not
  "correct" this toward a 14 mm figure.
- **Along-edge pad is 1.00 mm vs the vendor's 0.80 mm** → inter-pad gap 0.27 mm instead of 0.47 mm.
  Legal (rule is 0.20 mm) and no DRC violation, but 0.10 mm tighter than intent and just outside the
  vendor's ±0.1 mm tolerance. **Candidate for the next revision; deliberately NOT applied now** —
  narrowing it would invalidate the routed radio link and the DRC baseline for a cosmetic gain on a
  board that already passes.
- **Radial pad is 2.20 mm vs the vendor's 1.00 mm** — more solder fillet. Harmless.

## Rejected source — a pasted AI summary of this same part

An AI-assistant summary was supplied 2026-10-26. What it got right it did not add value on, and what
it added was wrong. Recorded so it is not re-adopted later.

**Wrong, and it would have changed the board:**

- *"Row Spacing (X-span): 15.0 mm between the outer module edges (center-to-center pad row span is
  typically **14.2 mm**…)"* — internally contradictory, and the 14.2 mm figure is **invented**. Our
  footprint is 15.0 mm and that is correct. Adopting 14.2 would put every pad 0.4 mm off and shorten
  the module's effective span by 0.8 mm.
- *"Pad Size: 0.8 mm width × **1.8 mm length**"* — the 0.8 matches the drawing; the 1.8 appears
  nowhere in it (depths are 0.50 and 1.00 mm).

**Correct, but already held from the primary source:** the 16-pin pinout (all 16 rows match Ebyte
exactly), 15 × 20 mm, 1.27 mm pitch, 1.5 ± 0.1 g. Nothing here was new.

**Correct but not applicable:** the "antenna keep-out for the integrated PCB antenna variant" — we
use the IPEX variant, so that rule does not apply to us.

**Filler:** "premade CAD files on SnapMagic or GitHub" — no links. SnapEDA carries only the `-S`
(PCB-antenna) variant and lists no 2D model for it.

The lesson is the repo's existing rule: an AI summary of a document is not the document. Cite the
drawing.

## Reproduce

```bash
pdftoppm -png -r 400 -f 6 -l 6 docs/modules/e28-2g4m27sx/E28-2G4M27SX_UserManual_v1.2.pdf /tmp/hi
# page 5 of the PDF = Ch.3 (pdftoppm -f 6 accounts for the cover offset)
```

Sources beyond the committed PDF: `jlcpcb.com/partdetail/…C5333988` (package `20x16mm`),
`ebyte.com/product/1920.html` (family table), `cdebyte.com/products/E28-2G4M27SX`
(`Dimensions 20 * 15 mm`), and the Chinese 产品规格书 mirrored at `xonstorage`.

No free STEP model exists for this part. Ebyte's download index carries footprint files for
related variants and a 3D ZIP for `E280-2G4T12S` only; PartGenie/SnapEDA hold CAD behind a login.

# LoRa1280 — footprint specification

Status: **spec written; 3 dimensions await a caliper before the `.kicad_mod` is cut.**
Part decided in ADR-139: **`LoRa1280` (plain, 10 ppm crystal, 12.5 dBm, ranging Yes).**
Source: `LoRa128X_Series_Datasheet_Rev2.2.pdf` (sha256 `9a23b241…`), §7 pin definition and
§9 mechanical dimensions. Both sections are images, so they were rendered at 400 dpi and read —
not inferred from marketing pages.

## 1. What is settled, and why it is trustworthy

### 1.1 Self-consistency proof for the pad row

The drawing gives four numbers that must agree, and they do:

```
8 pads per side, pitch 2.00 mm       -> 7 x 2.00 = 14.00 mm span
first pad centre 1.00 mm from end    -> 1.00 before the first, 1.00 after the last
                                        1.00 + 14.00 + 1.00 = 16.00 mm
outline length                       -> 16.00 mm   ✔ agrees exactly
```

That is not a coincidence that can be faked by a misread: a wrong pitch or a wrong end-offset would
break the identity. **Pitch 2.00 mm and a 1.00 mm end offset are therefore confirmed by the outline
dimension itself.**

### 1.2 Pad centres

| item | value | source |
|---|---|---|
| outline | 16.00 ± 0.2 × 16.00 ± 0.1 mm | §9 |
| thickness | 2.10 ± 0.15 mm (shield 1.10 ± 0.1 above PCB) | §9 |
| pads per side | 8, castellated, 16 total | §9 |
| pad pitch | **2.00 ± 0.1 mm** | §9, corroborated by §1.1 |
| pad centre offset from end edge | **1.00 ± 0.1 mm** | §9 |
| row centre offset from side edge | **1.00 ± 0.1 mm** | §9 ("1.00 inward from the side board edge to the centre of the circular hole") |
| **pad row separation (centre-to-centre)** | **14.00 mm** = 2 × (16.00 − 1.00 − 1.00)/2 … i.e. 16.00 − 1.00 − 1.00 | derived |
| plated hole in each land | Ø0.70 ± 0.1 mm | §9 |
| antenna | `ANT` pad, **no connector** | §7, §8 |
| shield | yes — chip is not readable | §9 |

Pad centres in module coordinates, origin at the pin-1 end corner, X along the pad row:

```
row A (pins 1-8):   x = 1.00, 3.00, 5.00, 7.00, 9.00, 11.00, 13.00, 15.00   at y = 1.00
row B (pins 16-9):  same x positions                                        at y = 15.00
```

## 2. Pin numbering — read from the §7 drawing

The numbered drawing on the shield side is printed with the pin rows horizontal:

```
            16   15   14   13   12   11   10    9        <- top edge, numbering right-to-left
          +--------------------------------------+
          |            shield (CE / FCC)         |
          +--------------------------------------+
             1    2    3    4    5    6    7    8        <- bottom edge, left-to-right
                    ^ white triangle marks pin 1
```

- **Pin 1 is at one corner of the lower row**, with a **white triangle** marker beside it (not a dot,
  not a chamfer).
- Numbering is **opposite-direction on the two rows**: 1→8 left-to-right, then 16→9 left-to-right
  (equivalently 9→16 right-to-left).
- **`ANT` (pin 9) is the pad opposite pin 8**, i.e. the far corner of the other row.

Rotated 90° clockwise — the conventional footprint orientation used here:
**pin 1 top-left, 1→8 down the left edge, 9→16 up the right edge, `ANT` at bottom-right.**

| pin | name | | pin | name |
|---|---|---|---|---|
| 1 | DIO2 | | 9 | **ANT** |
| 2 | DIO3 | | 10 | GND |
| 3 | VCC (1.8–3.7 V) | | 11 | GND |
| 4 | GND | | 12 | GND |
| 5 | MISO | | 13 | NRESET (active low) |
| 6 | MOSI | | 14 | **GND** on `LoRa1280` (TCXOEN on `-TCXO`) |
| 7 | SCK | | 15 | BUSY |
| 8 | NSS | | 16 | DIO1 |

**No `TX_EN`, no `RX_EN`.** Confirmed against the pin table — this is the whole point of the part.

## 3. The three numbers to confirm with a caliper

The pad *land* geometry is where the drawing needs care, because two readings are both defensible:

- **Reading A:** "1.70 inward extent from the outer board edge" → copper spans edge→1.70, centre 0.85.
- **Reading B:** the 1.70 is the land size and the Ø0.70 hole sits at 1.00 (which is what §9's
  separate "1.00 inward … to the centre of the circular hole" callout implies) → centre 1.00.

They differ by 0.15 mm, which is inside the drawing's own ±0.1 mm tolerance band, so the drawing
cannot settle it. **Measure an actual module:**

| # | measure | expected |
|---|---|---|
| 1 | **overall body** L × W | 16.00 × 16.00 mm |
| 2 | **pad-pitch**, hole-centre to hole-centre along a row | 2.00 mm |
| 3 | **pad land depth**, from the outer body edge to the inner edge of the copper | 1.70 mm |
| 4 | **pad land width** along the edge | 1.20 mm |
| 5 | thickness | 2.10 mm |

Also worth a photo: **the shield marking**. If it reads `LORA1280` the part is right. The shield makes
the chip itself unreadable, so the marking plus the order paperwork is the only provenance — see
ADR-139 §8.2.

## 4. Footprint construction rules for this part

- Pad: oblong/rounded rectangle, `1.70 × 1.20 mm`, Ø0.70 plated hole at its centre, **extended
  0.30 mm outboard past the module edge** for a solder fillet (standard castellation practice; the
  module's own land stops at the body edge, the host pad must not).
- Row separation centre-to-centre: **14.00 mm**.
- Courtyard: body + 0.25 mm on all sides, so **16.50 × 16.50 mm**.
- Silkscreen: pin-1 triangle at the pin-1 corner, and `ANT` marked — humans assemble this board.
- **No copper under the module** beyond the pad lands, and **no matching network anywhere** — ADR-137.
  The antenna is soldered directly to the `ANT` pad.

## 5. What changes on the board versus `U_E28`

```
                 E28-2G4M27SX        LoRa1280
outline          15.0 x 20.0         16.0 x 16.0
thickness        2.90                2.10
pads             16                  16
pad pitch        1.27                2.00
row separation   15.0                14.00
enables          TX_EN, RX_EN        none  (2 nets deleted)
nets to route    9 SPI/ctrl          9 SPI/ctrl, different pin order
current          580 mA TX peak      28 mA TX
```

The 9 SPI/control nets survive but **change pins**, so the radio link routed at 4 layers must be
re-routed. `TX_EN` and `RX_EN` disappear, freeing two GPIOs (`IO42`, `IO46` per ADR-138) back to the
spare pool.

## 6. Re-run

```bash
pdftoppm -png -r 400 -f 7 -l 7 docs/modules/lora128x/LoRa128X_Series_Datasheet_Rev2.2.pdf /tmp/pin
pdftoppm -png -r 400 -f 8 -l 8 docs/modules/lora128x/LoRa128X_Series_Datasheet_Rev2.2.pdf /tmp/mech
```

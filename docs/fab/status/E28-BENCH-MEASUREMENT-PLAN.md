# E28-2G4M27SX — bench measurement plan (what a caliper can and cannot settle)

Status: **plan only.** Written 2026-10-26 in response to "would it help if I buy one and measure it
with a caliper?"

**Short answer: yes, and it is worth it — but for GEOMETRY, not for the electrical questions.**
The caliper's highest-value job is ruling out a wrong land pattern, which is a scrapped-boards-class
error and costs almost nothing to check.

---

## 0. You probably do not own this part yet

Verified in `docs/sx1280/E28-SX1280-SKU-AUTODETECT-2026-09-23.md` line 3: the two LILYGO T3S3 V1.3
boards you already have are **"SX1280, plain +13 dBm SKU, no PA"**.

That is a *different part* from the E28-2G4M27SX:

| | your T3S3 module | E28-2G4M27SX |
|---|---|---|
| power amplifier | **none** | yes, 27 dBm / 500 mW |
| `RX_EN` / `TX_EN` pins | **do not exist** | pins 8 and 9 |
| antenna | PCB or IPEX depending on SKU | IPEX |

So the boards you own **cannot answer the enable questions** — there are no enables to measure. This
is the same point `OPEN-ITEMS.md` makes: *"these are NEW versus the bare SX1280 (which had no PA/LNA
enables), so no v9 pin carried over."*

**Buy exactly `E28-2G4M27SX`** — the `-SX` suffix is the IPEX variant. `E28-2G4M27S` is the same
silicon with a **PCB antenna** and would not validate our IPEX geometry.

---

## 1. Tier A — caliper. Do these, in this order.

### A1. Body width across the pad rows — **the single most valuable measurement**

The datasheet contradicts itself: the Chapter 3 **drawing** says the outline is **16.0 × 20.0 ×
2.90 mm**; the specification **table** says **15 × 20 mm**.

Our footprint (`tracker/hardware/footprints/e28/E28-2G4M27SX.kicad_mod`) has pad rows **15.0 mm**
apart, 8 pads per side on 1.27 mm pitch.

- If the body is **16.0 mm** (pads inset ≈0.5 mm per side) → row separation 15.0 mm → **our footprint
  is correct**, the table is wrong.
- If the body is **15.0 mm** → row separation should be ≈14.0 mm → **our footprint is 1.0 mm too
  wide**, every pad lands ≈0.5 mm off, and no board built from it will solder correctly.

*Why this is #1:* it is a yes/no on whether the board is orderable at all, it takes ten seconds, and
nothing else in this list can substitute for it. Also record length (**20.0**) and thickness
(**2.90**), which feed the 3D keep-out.

### A2. IPEX connector position — closes Q6 exactly

Measure from the **pin-1 corner** to the **centre of the IPEX connector**: x offset and y offset, in
mm. The drawing places the connector in the **lower-right corner, diagonally opposite pin 1**, but
dimensions nothing — this is the only way to get a real number.

While you have it, measure the connector body: centre-pad pitch and overall footprint size identify
**MHF1 / U.FL (≈2.0 mm)** versus **MHF4 (≈1.2 mm)**. That decides which pigtail we buy — it is a BOM
item, not a detail. A MHF4 pigtail will not mate a U.FL jack.

*Why:* the antenna keep-out volume is currently anchored on the corner as a proxy. A real offset makes
it exact, and it is the number the mechanical/enclosure work needs.

### A3. One castellation pad + pitch

Pad length along the edge, pad depth into the module, and pitch (expect **1.27 mm**). The drawing
gives pad depth **0.50 mm** (top view) / **1.00 mm** (bottom pad) and a **0.65 mm** opening. Our pad is
**2.20 × 1.00 mm**. Checking one pad validates all sixteen.

### A4. Pin-1 marking, photographed

Which corner carries the pin-1 marker, and confirm numbering runs **1→8 down one long edge, then 9→16
up the other** (counter-clockwise from the component side).

*Why:* the entire enable assignment rests on the pad→GPIO map derived in
`docs/analysis/E28-ENABLES-DRIVE-FROM-ESP32.md`. That map was corroborated 20 ways against the
registry, but it assumes this numbering direction. Ten seconds to confirm.

### A5. Photos — worth as much as the caliper to me

A sharp top-down and bottom photo **with a ruler or the caliper jaws in frame** lets me measure pixel
ratios against a known dimension and cross-check your numbers. It also shows the silkscreen markings,
which may name the variant.

---

## 2. Tier B — multimeter. Answers one of the three open questions (Q4), partially.

### B1. Control first: `NRESET` (pin 11)

The manual documents **"built-in pull-up resistor 50K"** on pin 11. On an **unpowered** module,
measure resistance **pin 11 → VCC** and **pin 11 → GND**. You should see ≈50 kΩ to one rail.

**This is the control experiment**: it proves your method can detect an internal pull at all. Without
it, a reading on pins 8/9 means nothing.

### B2. Then the enables — pins 8 and 9

Same measurement: resistance to VCC and to GND.

| reading | conclusion |
|---|---|
| ≈50 kΩ to VCC, open to GND | internal **pull-up** exists → the floating boot window is benign, Q4 answered |
| ≈50 kΩ to GND | internal **pull-down** → enables default OFF, Q4 answered |
| open both ways | **no internal pull** → the boot window is genuinely undefined, Q4 answered (badly) |
| hundreds of kΩ, or asymmetric | **inconclusive** — protection diodes. Say so; do not call it "no pull" |

**Caveat, stated plainly:** on-chip protection diodes make unpowered resistance readings unreliable.
A mid-scale or lopsided number is *not* evidence of absence.

### B3. Better alternative if B2 is inconclusive — measure the voltage

Power the module at 3.3 V with `NRESET` released and the ESP32 **disconnected**, then measure **DC
voltage at pins 8 and 9** with a high-impedance meter:

- near **3.3 V** → pulled up (and therefore already enabled)
- near **0 V** → pulled down
- **mid-rail / wandering** → undefined, i.e. **not safe to leave floating** — which is itself the
  answer and justifies the ESP32 drive we have already assigned

---

## 3. Tier C — a caliper and a DMM cannot answer these

| question | why not | how it gets answered |
|---|---|---|
| **Q2** — `TX_EN` + `RX_EN` high **simultaneously** | needs the module *in a circuit*, driven | bench test: assert both, watch supply current, confirm TX and RX both still work and nothing heats. Ebyte if they will say. |
| **Q5** — sequencing VCC / `NRESET` / `TX_EN` / `RX_EN` | chip-internal behaviour | Ebyte only |
| RF port truly matched to 50 Ω | needs a VNA | Ebyte in writing, or trust the inference in `EBYTE-QUESTION-e28-enables.md` |

**Do not** try to identify the chip as SX1280 vs SX1281 by appearance. The manual and the product page
disagree, the two are driver-compatible, and our firmware assumes SX1280 either way. Markings will not
settle it usefully.

---

## 4. What each result would change

| measurement | if it comes out | action |
|---|---|---|
| A1 body width | 16.0 mm | footprint stands; fix the spec table reference in `PROVENANCE.md` |
| A1 body width | 15.0 mm | **footprint is wrong** — re-derive the land pattern before any order |
| A2 IPEX offset | any number | replace the corner proxy in `reserve_antenna_volume.py` with the measured anchor |
| A2 connector size | MHF4 | buy MHF4 pigtails, not U.FL |
| A4 numbering | matches | enable assignment (`TX_EN→IO42`, `RX_EN→IO46`) stands |
| A4 numbering | differs | re-derive the whole pad→GPIO map before routing anything |
| B2/B3 | pull-up present | nothing to add; the boot window is safe |
| B2/B3 | no pull / undefined | keep the ESP32 drive, and consider a pull-down so the enables are defined during reset |

## 5. Order of work, cheapest first

1. Buy **one** `E28-2G4M27SX` (IPEX variant). One is enough — every measurement here is single-part.
2. **A1** — body width. If it is 15 mm, stop: the footprint is wrong and deserves attention before
   anything else.
3. **A2, A3, A4, A5** — geometry + photos.
4. **B1 control**, then **B2**; **B3** only if B2 is inconclusive.
5. Whatever is left after that is Ebyte's to answer, and by then the email is down to two questions.

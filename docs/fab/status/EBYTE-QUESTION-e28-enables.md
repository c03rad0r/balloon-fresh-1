# Question for Ebyte — E28-2G4M27SX: default state of RX_EN / TX_EN

Status: **DRAFT — for the operator to send.** Not a decision record.
Part: **E28-2G4M27SX** (Ebyte, SX1280-based, 2.4 GHz, 27 dBm)
Our document: `E28-2G4M27SX_UserManual_v1.0.pdf`, Chapter 3 pin table and Chapter 9 antenna guidelines.

---

## Why we are asking (context you can paste with the question)

We have designed this module onto a carrier board. Our design **drives pin 8 (`RX_EN`) and pin 9
(`TX_EN`) from two ESP32-S3 GPIOs** (our GPIO budget assigns exactly two lines to these enables). On
the current board revision they are still unconnected because the pad assignment was only just
resolved — the questions below are what we need before we commit that routing. Your manual's pin
table (§3) reads:

| Pin | Item | Type | Application |
|---|---|---|---|
| 8 | `RX_EN` | Input | **LNA control pin, active high** |
| 9 | `TX_EN` | Input | **PA control pin, active high** |

The manual does document an internal pull-up for one other pin — pin 11 `NRESET`, "built-in pull-up
resistor 50K" — but says nothing about a default state or internal pull for pins 8 and 9.

**Our concern:** with the enables under firmware control, the failure modes are (a) a boot window
where our GPIOs are still tri-stated and the pins float, and (b) a firmware or boot race asserting
both enables at once. Either could present as an RF fault rather than a control fault, so we want the
module's behaviour stated rather than inferred.

## The questions, numbered

Questions are ordered by **what would change our design**, not by pin number. Two of them could
force a board change; the rest are documentation.

## ANSWERS FOUND — from Ebyte's official manual and product page (2026-10-26)

The operator supplied a link; the Google redirect token would not resolve, but Ebyte's own PDF was
located and fetched: **`https://www.cdebyte.com/pdf-down.aspx?id=1671`** (14 pages, "E28-2G4M27SX User
Manual") plus the product page `cdebyte.com/products/E28-2G4M27SX/1`. Extracted with `pdftotext
-layout`, and the Chapter 3 mechanical drawing read from a 200 dpi render.

This section **supersedes the questions below where they overlap** — check here first.

### ANSWERED — Q3 (series resistor): no, 3.3 V direct is correct

Two independent statements in the manual:

> "Communication level | 3.3 V | Risk of burnout with 5 V TTL"

> §4.1: "If the communication line uses **5 V level**, a 1k–5.1k resistor must be connected in series
> (not recommended, there is still a risk of damage)"

A series resistor is specified **only for 5 V lines**, and even then is called "not recommended".
At 3.3 V there is no resistor requirement. **No BOM change needed** — drive both pins directly from
ESP32 GPIOs.

### ANSWERED — Q7 (current), module totals (the enable delta is still not given)

| parameter | typ | note |
|---|---|---|
| emission current | **580 mA** | instantaneous, during TX |
| receive current | **14.5 mA** | |
| sleep current | **2.0 µA** | software shutdown |

Receive sensitivity is quoted as **−130 / −131 / −132 dBm** "...with **high sensitivity mode
enabled**", i.e. the LNA enable is worth roughly the 2 dB between the un-enabled and enabled figures.
So `RX_EN` is not cosmetic for a weak-signal link, and `TX_EN` gates the 580 mA. The PA-on/off
*delta* specifically is still unstated.

### ANSWERED — Q1 (IPEX finished 50 Ω port): strongly implied YES, not stated verbatim

Never stated in one sentence, but the manual is unambiguous in aggregate:

- antenna interface is **"IPEX/PCB, equivalent impedance is about 50 Ω"**;
- the module is **"SX1280+PA+LNA"** — the amplifiers are **inside** the module;
- the only antenna interface offered is the IPEX (or a PCB antenna variant);
- §4.2: *"It is recommended to set the power output parameter of SX1280 to 0 dBm. At this time, the
  module can output power of 27 dBm"* — the gain is added on-module.

A module sold as a finished 27 dBm product, whose only RF port is an IPEX, must carry its own
matching. **ADR-137 stands on that basis**, but it remains an inference rather than a quoted
sentence, so it is still worth confirming in writing before a purchase order.

### PARTIALLY ANSWERED — Q6 (IPEX position): corner known, offset not

The Chapter 3 mechanical drawing shows the connector labelled **"IPX"** in the module's
**lower-right corner — diagonally opposite pin 1** (i.e. at the pin-16 corner), on the component
face. Pin 1 is on a long edge near the upper-left corner, numbering runs **1→8 down one long edge
then 9→16 up the other** (counter-clockwise from the component side).

**No numeric offset from either edge is dimensioned.** The `2.69 mm` callout locates the first pad
from the top edge, not the antenna.

Consequence applied: the `U_E28` antenna volume is now anchored at that corner `(57.0, 74.6)` rather
than at the module centre — previously it was centred at x≈53, about 4 mm too far left.

**A drawing-vs-table discrepancy worth recording:** the mechanical drawing is
**16.0 × 20.0 × 2.90 mm**, while the specification table says **15 × 20 mm**. Our footprint's
**15.0 mm** pad-row separation matches the **drawing** (16.0 mm outline, pads inset ~0.5 mm each
side), not the table. So the drawing is the correct reference for our land pattern.

### STILL OPEN — genuinely unanswered by the manual

| question | status |
|---|---|
| **Q2** — is `TX_EN` + `RX_EN` high **simultaneously** permitted? | **not addressed anywhere** in the manual or product page |
| **Q4** — behaviour while both pins **float** (our boot window) | **not addressed**; only `NRESET` documents a 50 K pull-up |
| **Q5** — sequencing between VCC / `NRESET` / `TX_EN` / `RX_EN` | **not addressed** |

These three are the ones actually worth sending now. Q2 in particular has a board consequence
(hardware interlock or not) and cannot be inferred from the documents.

---

## Original question set (kept for the record; see ANSWERS above first)

### Tier 1 — could change the board

**Q1. Is the antenna IPEX port a FINISHED 50 Ω interface, or is it the raw SX1280 RF pin?**
Your manual §2 says "Antenna Interface IPEX/PCB, equivalent impedance about 50 Ω". We need it stated
explicitly: **does the module already contain the PA/LNA matching, harmonic filtering and antenna
match**, so that an antenna can be connected to the IPEX with no external components?
*Why:* our design rule (ADR-137) forbids any RF design on our carrier board — no matching network, no
balun, no controlled-impedance feed. We attach at your IPEX and do nothing else. If the IPEX is
unmatched, that rule is violated and we would have to change part or re-open the decision.

**Q2. Is it permitted to hold `TX_EN` and `RX_EN` HIGH at the same time?**
*Why:* we will drive both from ESP32 GPIOs (your budget allows it). A firmware bug or a boot-time
race can assert both. If simultaneous PA+LNA enable is damaging or causes excessive current, we must
add a hardware interlock; if it is harmless, we only need firmware discipline. **We need to know
which.** If simultaneous assertion is simply "TX wins" or "undefined", say so.

**Q3. Can pins 8 and 9 be driven directly from a 3.3 V GPIO with no series resistor?**
If a series resistor is required or recommended, what value and on which side? Any maximum input
current or clamping requirement?
*Why:* a resistor is a BOM change. We would rather add it now than respin.

### Tier 2 — behaviour at power-up (still matters even though we drive them)

**Q4. What happens during the window when both pins are FLOATING?**
Our ESP32 tri-states its GPIOs during reset and early boot, so for some milliseconds pins 8 and 9
will be floating — our drive is not present yet. Do the module's internal pulls hold them low, high,
or is the state undefined? Are there internal pull resistors at all?
*Why:* this is the only period our control does not apply. If the PA or LNA is enabled in that window
while the SX1280 is unclocked or unconfigured, we want to know whether that is harmless.

**Q5. Any sequencing requirement** between VCC, `NRESET`, `TX_EN` and `RX_EN` — e.g. must the enables
be low while `NRESET` is asserted, or during VCC ramp?

### Tier 3 — documentation / budget

**Q6. Where exactly is the IPEX connector on the module body?**
Position relative to the pin-1 corner (x/y in mm), or which edge and what offset. Your Chapter 3
mechanical drawing has it; the text does not.
*Why:* we reserve a physical keep-out volume for the pigtail and its bend radius. Anchoring that
volume on a guessed position already produced a phantom collision in our own model, which we had to
withdraw — so this one we would rather not guess.

**Q7. Supply current difference** between LNA enabled/disabled (receive) and PA enabled/disabled
(idle), at 3.3 V.
*Why:* balloon payload power budget. We intend to gate the PA in firmware, so the PA-on delta is the
number we most want.

### What we no longer need to ask

The original question set led with "do the enables have internal pull-ups" and "what is the default
if floating", because we planned to strap them. **We are now driving both from the ESP32**, so the
steady-state default is irrelevant — only the brief boot window (Q4) still matters.

---

## What we will do with each answer

| if the answer is | we do |
|---|---|
| IPEX is already matched 50 Ω | ADR-137 stands unchanged; connect antenna at the IPEX |
| IPEX is the raw RF pin | **ADR-137 is violated** — re-open it; different part, or accept RF design |
| simultaneous TX_EN+RX_EN is harmful | add a hardware interlock (inverter/AND gate) between the two enables |
| simultaneous is harmless | firmware discipline only; record it in the bring-up notes |
| series resistor required | add two resistors — a BOM change, so we want it before ordering |
| floating window is dangerous | add pull-downs to hold the enables low until the ESP32 drives them |
| sequencing required | write it into the power-up sequence in the bring-up notes |
| IPEX position given | replace the guessed anchor in `reserve_antenna_volume.py` with the real coordinate |

## Our own measured facts (so Ebyte can check us)

- Board: 4-layer, 72 × 80 mm. Module `U_E28` on the bottom side, rotated −90°.
- Pin 1 (`VCC`) = `+3V3` net. Pins 2, 7, 10, 16 = `GND`.
- Pin 8 (`RX_EN`) = **unconnected**. Pin 9 (`TX_EN`) = **unconnected**.
- Pins 3–6 = SPI1 (`MISO`/`MOSI`/`SCK`/`CS`); pin 11 `NRESET`, pin 12 `BUSY`, pins 13–15 `DIO1..3`
  all connected.
- The other three radios on the board do **not** leave enables floating: the `LoRa2021F33-2G4` has its
  `CE` strapped to `+3V3`, which is also what ADR-108 specifies for it.

## Note: the strap attempt is withdrawn, not pending

We briefly planned to strap pins 8 and 9 to VCC. **That plan is withdrawn** — ADR-123 already budgets
two ESP32 GPIOs for these enables (`E28 extras (RX_EN, TX_EN) | 2`), so they are meant to be driven.
Our open item was only ever "which pads", which is now answered (`TX_EN` -> `U1.35 / IO42`,
`RX_EN` -> `U1.16 / IO46`; see `docs/analysis/E28-ENABLES-DRIVE-FROM-ESP32.md`).

A strap attempt was made and reverted because it produced three `track_dangling` reports we could not
explain. It is kept as `tracker/hardware/strap_e28_enables.py` for the record but is **superseded** by
the driving approach and should not be applied.

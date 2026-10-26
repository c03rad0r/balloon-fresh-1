# Question for Ebyte — E28-2G4M27SX: default state of RX_EN / TX_EN

Status: **DRAFT — for the operator to send.** Not a decision record.
Part: **E28-2G4M27SX** (Ebyte, SX1280-based, 2.4 GHz, 27 dBm)
Our document: `E28-2G4M27SX_UserManual_v1.0.pdf`, Chapter 3 pin table and Chapter 9 antenna guidelines.

---

## Why we are asking (context you can paste with the question)

We have designed this module onto a carrier board. Our carrier leaves **pin 8 (`RX_EN`) and pin 9
(`TX_EN`) unconnected**. Your manual's pin table (§3) reads:

| Pin | Item | Type | Application |
|---|---|---|---|
| 8 | `RX_EN` | Input | **LNA control pin, active high** |
| 9 | `TX_EN` | Input | **PA control pin, active high** |

The manual does document an internal pull-up for one other pin — pin 11 `NRESET`, "built-in pull-up
resistor 50K" — but says nothing about a default state or internal pull for pins 8 and 9.

**Our concern:** if the LNA and PA are not enabled, the module may transmit at reduced power or not at
all, and receive with poor sensitivity. That would look like an RF or firmware fault rather than a
pin-strapping problem, so we want to get it right before we build.

## The questions, numbered

1. **Do pins 8 (`RX_EN`) and 9 (`TX_EN`) have internal pull-up or pull-down resistors in the
   E28-2G4M27SX?** If yes, what value and to which rail?

2. **If both pins are left floating (no external connection), are the LNA and PA enabled or
   disabled?** Please state the resulting behaviour, not only the intent.

3. **What is the recommended connection for each pin if we do not need dynamic control**
   (i.e. we want the PA and LNA permanently on)? Tie directly to VCC, tie through a resistor, or
   leave floating? If a series resistor is recommended, what value, and on which side?

4. **What supply current difference should we expect** between LNA enabled and LNA disabled
   (receive mode), and between PA enabled and PA disabled (idle/standby)? We are power-budgeting a
   battery/balloon payload and need to know what permanent enable costs us.

5. **Is there any sequencing requirement** between VCC, `NRESET`, `TX_EN` and `RX_EN`? For example,
   must `TX_EN` be low during reset, or is any order safe?

6. **Are the two pins safe to drive from a 3.3 V GPIO directly,** or do they require series
   resistance / level shifting? (Datasheet implies 3.3 V logic, but we would like it stated.)

## Secondary question — antenna connector position

7. **Where exactly is the IPEX connector on the E28-2G4M27SX module body?** Your manual §2 lists the
   antenna interface as "IPEX/PCB, equivalent impedance about 50 Ω", and Chapter 3 has the mechanical
   drawing. We need the connector's position relative to the module's pin-1 corner (x/y offsets in mm),
   so we can reserve keep-out space for the mating pigtail and its bend radius on our board. A
   dimensioned drawing or a coordinate (or simply "which edge and what offset") would be enough.

---

## What we will do with each answer

| if the answer is | we do |
|---|---|
| internal pull-ups exist / floating = enabled | no board change; record it and close the item |
| floating = disabled, and tying to VCC is correct | add the strap: two tracks from pins 8 and 9 to the module's own VCC pin (pad 1) — **already scripted, `tracker/hardware/strap_e28_enables.py`, not applied** |
| floating = disabled, and a series resistor is required | add two resistors; a BOM change, so we would rather know now |
| sequencing required | add to the power-up sequence in firmware/board bring-up notes |

## Our own measured facts (so Ebyte can check us)

- Board: 4-layer, 72 × 80 mm. Module `U_E28` on the bottom side, rotated −90°.
- Pin 1 (`VCC`) = `+3V3` net. Pins 2, 7, 10, 16 = `GND`.
- Pin 8 (`RX_EN`) = **unconnected**. Pin 9 (`TX_EN`) = **unconnected**.
- Pins 3–6 = SPI1 (`MISO`/`MOSI`/`SCK`/`CS`); pin 11 `NRESET`, pin 12 `BUSY`, pins 13–15 `DIO1..3`
  all connected.
- The other three radios on the board do **not** leave enables floating: the `LoRa2021F33-2G4` has its
  `CE` strapped to `+3V3`, which is also what ADR-108 specifies for it.

## Note on what we already tried

We attempted an on-board strap from pins 8 and 9 to the module's VCC pin, routed around the module on
F.Cu. It produced three `track_dangling` DRC reports at the points where the tracks meet the pads, and
we could not explain or eliminate them, so **we reverted it rather than ship an unresolved violation**.
That attempt is committed as a script but **not applied to the board**. If Ebyte says the strap is
required, the fix should be done by someone with a KiCad GUI session, or after understanding why the
pad/track junction did not register as connected.

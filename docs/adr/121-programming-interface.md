# ADR-121 — Programming/debug interface: 6-pin J_PROG header on every flight board

- **Status:** ACCEPTED — operator question and direction, 2026-10-21 ("Do we also have connectors for flashing the ESP32S3?"); decision taken under standing authority and recorded here.
- **Decision owner:** Felix (operator) — question; design under standing authority.
- **Related:** ADR-108 OPEN-10 (which named the gap and the part), ADR-118/119/120 (v10), `docs/adr/108-f33-sx1280-pin-plan.md` line 312.

## The measured gap

The v9 hub board has **no programming connector at all**. Measured on the canonical board:

```
U1 pad  3 (EN)      -> NO NET
U1 pad 13 (USB_D-)  -> NO NET
U1 pad 14 (USB_D+)  -> NO NET
connectors present: J_VCC + 4x wing socket. Nothing else.
```

`ADR-108 OPEN-10` recorded this exactly — *"The ESP32-S3 console is USB-Serial-JTAG and has no fitted connector, and the reset RC is not in the BOM"* — and classified it as a **"fitting task" for "this revision"**. That revision shipped without it, so **a soldered hub can only be flashed by hand-soldering wires to the module pads**.

## Decision

Every flight board carries a **6-pin 2.54 mm programming header** (`J_PROG`), wired per ADR-108 OPEN-10 / the frozen v8i board's `J1 "Prog_Header"`:

| pin | signal |
|---|---|
| 1 | GND |
| 2 | +3V3 |
| 3 | EN |
| 4 | USB_D- |
| 5 | USB_D+ |
| 6 | IO0 |

Plus the **EN reset RC**: R = 10 kΩ, C = 1 µF, per Espressif ESP32-S3-WROOM-1/1U datasheet v1.8 §9 (*"it is advised to add an RC delay circuit at the EN pin … usually R = 10 kΩ and C = 1 µF"*).

USB is the ESP32-S3's **native USB-Serial-JTAG** — no USB-UART bridge chip needed; the header exposes D-/D+ directly.

Why a header and not a USB-C socket: the payload is a pico-balloon; a 2.54 mm header adds ~1.5 g and gives a positive-lock, hand-solderable, cheap interface with no connector-shell mass. Optional: leave it DNP-by-default like the radio sites, and flash via the header only on the bench before flight.

## Consequences

- v10 placement gains the header (5.0 × 15.2 mm courtyard) plus R/C; measured fits the front band without enlarging the outline beyond 53 × 62 mm.
- The v10 build must route: EN → header pin 3 (+ RC to GND), USB_D-/D+ → pins 4/5, IO0 → pin 6, GND/+3V3 rails.
- **The v9 board keeps the gap** (not retrofitted) — but any *flashable* hub now has the interface.
- `docs/fab/PCB-HANDOVER-FOR-JLCPCB.md` item list gains the header part (`Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical`).

## Reproduce

```
~/venvs/kicad/bin/python -c "import pcbnew; b=pcbnew.LoadBoard('tracker/hardware/hub_board_v9.kicad_pcb'); print([p.GetNetname() for p in b.FindFootprintByReference('U1').Pads() if p.GetNumber() in ('3','13','14')])"
```

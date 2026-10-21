# ADR-122 — v10 ESP32-S3 ↔ four-radio interconnect: one shared SPI bus, four CS, 29-GPIO budget

- **Status:** SUPERSEDED by **ADR-123** (2026-10-21, operator instruction: two buses partitioned by band for real-time bent pipe). The GPIO accounting and strapping-pin rules below CARRY FORWARD; the single-bus topology does not.
- *(Original status line: ACCEPTED — design under standing authority, answering the operator's 2026-10-21 question)* ("How is the ESP32-S3 going to connect to all three radios? Does it have enough SPI connections?"); recorded per ADR-first.
- **Decision owner:** Felix (operator) — question; topology decision under standing authority.
- **Related:** ADR-108 (v9 pin plan — 2-radio version of this same topology), ADR-119 (four RF sites), ADR-121 (J_PROG), ADR-035 (TDM — why bus sharing is safe).

## The answer to the operator's question

**One SPI bus is enough — that is the standard topology and v9 already runs it for two radios.**

The ESP32-S3 has two general-purpose SPI masters (GPSPI2, GPSPI3). SPI is a **multi-drop bus**: SCK/MOSI/MISO are shared; each slave gets a private **CS** (chip select). The v9 board already wires `U2` (F33) and `U3` (LP) on one shared bus — `/F33_SCK`, `/F33_MOSI`, `/F33_MISO` with separate `/F33_CS_N` and `/U3_CS_N` (measured in the v9 netlist). v10 extends the identical pattern to four slaves.

## Topology (v10)

```
ESP32-S3 GPSPI2 (one shared bus):
  SCK  ─┬─ F33 (Site A)   CS_N ──┐
  MOSI ─┼─ LP  (Site B)   CS_N ──┤        each radio also gets:
  MISO ─┼─ LP  (Site C)   CS_N ──┤        BUSY · IRQ · RESET_N
         └─ E28 (Site D)  CS_N ──┘        E28 adds: RX_EN · TX_EN
```

**GPIO budget (all four radios + everything else):**

| function | pins |
|---|---|
| shared SPI bus (SCK/MOSI/MISO) | 3 |
| CS per radio ×4 | 4 |
| BUSY ×4 · IRQ ×4 · RESET_N ×4 | 12 |
| E28 extras (RX_EN, TX_EN) | 2 |
| J_PROG (EN, IO0) | 2 |
| I2C (baro sensor) | 2 |
| GNSS (TX, RX, PPS) | 3 |
| F33_VSENSE | 1 |
| **total** | **29** |

**ESP32-S3 has ~33 usable GPIOs** (strapping pins and the USB/JTAG pins account for the rest). **29 < 33 — it fits, with 4 spare.** The WROOM-1U footprint exposes 41 pads; v9 used 26 signal nets, 11 numbered pads are free, and pads 3/13/14 are claimed by ADR-121's J_PROG.

## Why not two buses

Two SPI masters would "dedicate" GPSPI3 to the ranging radio — but ADR-035's TDM arbiter means **only one radio transmits at a time anyway**, so bus contention is never simultaneous; and a second bus buys nothing except 3 more spare pins at the cost of firmware complexity (two drivers, two DMA channels). One bus + four CS is simpler, proven on v9, and the arbiter already serialises access.

## Consequences

- ADR-108's pin table is superseded by this budget for v10 (108 remains the v9 record).
- The v10 netlist derives from this table; the build script names nets per site: `/F33_*`, `/U3_*`, `/UC_*`, `/E28_*`.
- Site C nets (`/UC_CS_N`, `/UC_IRQ`, `/UC_BUSY`, `/UC_RESET_N`) and `/E28_RX_EN`, `/E28_TX_EN` are NEW; pin numbers assigned at build from the free-pad list with strapping-pin avoidance (no GPIO0 for CS — it is the bootloader strap; the J_PROG header owns it).
- DNP semantics: an unpopulated site's CS/BUSY/IRQ/RESET nets are simply unused GPIOs — no firmware cost.

## Reproduce

```
~/venvs/kicad/bin/python -c "import pcbnew; b=pcbnew.LoadBoard('tracker/hardware/hub_board_v9.kicad_pcb'); print(sorted({p.GetNetname() for p in b.FindFootprintByReference('U1').Pads() if p.GetNetname()}))"
```

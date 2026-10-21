# ADR-123 — v10 radio interconnect v2: TWO SPI buses, partitioned by band (bent-pipe capable)

- **Status:** ACCEPTED — operator instruction, 2026-10-21: *"make sure that one of the low power LR2021 is on one SPI bus and the F33 … on the other SPI bus so that we can have a real time bent pipe without being forced to do TDMA if we want to."*
- **Supersedes:** **ADR-122** (single shared bus) — superseded the same day it landed; ADR-122's GPIO accounting and strapping-pin rules carry forward, its topology does not.
- **Decision owner:** Felix (operator).
- **Related:** ADR-034 (band split 433 TX / 2.4 RX — the bent pipe's two halves), ADR-035 (TDM — now an *option*, not a bus-forced necessity), ADR-119 (four RF sites), ADR-121 (J_PROG owns GPIO0, USB D±).

## The decision

Two SPI buses, **partitioned by band**:

```
SPI-1 (GPSPI2) — the 2.4 GHz bus          SPI-2 (GPSPI3) — the 433 MHz bus
  SCK/MOSI/MISO ─┬─ LP-B (Site B, 2.4 RX)    SCK/MOSI/MISO ── F33 (Site A, 433 TX)
                 ├─ LP-C (Site C, 2.4 spare)
                 └─ E28  (Site D, 2.4 ranging)
```

**Why band-partition is exactly right:** ADR-034 already guarantees only cross-band operation is ever simultaneous (433 ∥ 2.4). All three 2.4 GHz radios are mutually exclusive **by band rule R7** — they never contend for their shared bus at the same moment anyway. The F33 sits alone on the second bus.

**Result — the real-time bent pipe:** LP-B receives on SPI-1 **while** the F33 transmits on SPI-2 — two independent buses, zero bus arbitration, zero TDMA dependency. The ESP32 can stream received packets into the F33's FIFO while still servicing the RX radio. TDM (ADR-035) remains available as a power-management choice, not a bus-forced one.

## GPIO budget (updated — was 29, now 32)

| function | pins |
|---|---|
| SPI-1 bus (SCK/MOSI/MISO) | 3 |
| SPI-2 bus (SCK/MOSI/MISO) | 3 |
| CS per radio ×4 | 4 |
| BUSY ×4 · IRQ ×4 · RESET_N ×4 | 12 |
| E28 extras (RX_EN, TX_EN) | 2 |
| J_PROG (EN, IO0) — ADR-121 | 2 |
| I2C (baro) | 2 |
| GNSS (TX, RX, PPS) | 3 |
| F33_VSENSE | 1 |
| **total** | **32** |

**Pin availability on ESP32-S3-WROOM-1U N8R8:** assignable GPIOs ≈ 34 (GPIO0–18, 21, 33, 34, 38–48; 26–32 are module flash — never available; **35–37 are consumed by the N8R8's octal PSRAM**; 19/20 are the native USB D± owned by J_PROG). **32 needed < 34 assignable → fits with 2 spare.**

Caveats carried forward from ADR-122: CS assignment avoids strapping pins (GPIO0 = J_PROG; 3/45/46 usable with care); unpopulated DNP sites cost zero firmware.

## Consequences

- v10 netlist: bus-1 nets `/U3_*`, `/UC_*`, `/E28_*` share `/SPI1_*`; `/F33_*` moves to `/SPI2_*` — **the F33 no longer shares SCK/MOSI/MISO with anything**.
- ADR-035's TDM schedule becomes optional per-operation, not load-bearing for bus access.
- Firmware: two SPI host drivers (GPSPI2 + GPSPI3), each with its own DMA channel — the exact price ADR-122 refused to pay, now bought deliberately for bent-pipe parallelism.
- If a future variant needs >34 GPIOs, the pressure valve is BUSY polling (each BUSY line dropped saves 1 GPIO at a small firmware cost).

## Reproduce

```
grep -n 'GPSPI' docs/adr/122-v10-esp32-radio-bus.md docs/adr/123-v10-two-spi-buses.md
```

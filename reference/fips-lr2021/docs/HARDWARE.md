# Hardware

## Supported targets

1. **E80-900MBL-02 STM32 bridge** — the event hardware. The STM32F103 runs the
   bridge mode added to `firmware/e80-stm32-bench`; the CH340 is the USB serial
   link. See `docs/E80-STM32-BRIDGE.md`.
2. **RP2040 + E80 SPI bypass** — the reference target. The RP2040 drives the
   LR2021 directly using the proven E80 SPI-bypass pin map.

Both speak the same host protocol.

## E80 STM32 bridge

```bash
cd firmware/e80-stm32-bench && make firmware
PROBE=<cmsis-dap-serial> ./reference/fips-lr2021/scripts/flash-e80-bridge.sh
fips-lr2021ctl --serial /dev/ttyUSB6 --baud 115200 bridge
fips-lr2021ctl --serial /dev/ttyUSB6 --baud 115200 cfg --band us915
```

The STM32 bridge starts at 115200 (the bench console rate). At 115200 the host
side is the throughput limit; 2 Mbaud is the next step.

## Wiring

From `firmware/e80-bypass/common/e80_pinmap.h`:

| RP2040 | E80 J2 | Signal |
|---:|---:|---|
| GP2 | J2-13 | SCK |
| GP3 | J2-11 | MOSI |
| GP4 | J2-9 | MISO |
| GP5 | J2-15 | NSS |
| GP6 | J2-7 | BUSY |
| GP7 | J2-10 | DIO8 / IRQ |
| GP8 | J2-5 | NRST |
| GND | GND | ground |

Do not connect 3V3 from the RP2040 to the E80 unless the E80 is powered
correctly and the current budget is understood. The E80 has its own supply path
on the eval board.

## First power-up

1. Continuity-check ground and each SPI line.
2. Power the E80 with an antenna or a 50 Ω load on the selected port.
3. Flash the bridge with `scripts/flash-bridge.sh`.
4. Run `fips-lr2021ctl hello`. A missing HELLO_ACK means the serial port is
   wrong or the firmware is not running.
5. Run `fips-lr2021ctl cfg --band us2400` at low power on the bench, then
   `status`.
6. Only then connect the second board.

## Serial port

The RP2040 exposes USB CDC. On Linux it is `/dev/ttyACM0` or similar. The
protocol ignores the baud rate, but the host opens at 2,000,000 by default to
match the E80 console convention.

## 2.4 GHz

The E80-900 module is primarily a sub-GHz board. Before using `eu2400` or
`us2400`:

- confirm the module has a 2.4 GHz path and which SMA jack it uses;
- confirm the HF PA configuration works on this board;
- measure output power and harmonics.

If the HF path is not populated, use 868/915.

## Flashing

RP2040 uses BOOTSEL/picotool. Pre-flash all event boards before travel. The
ESP32 porting guide is in `PORTING-ESP32.md`; that is the recommended path if
BOOTSEL becomes the operational bottleneck.

## Power and thermal

FLRC at +22 dBm is not free. Check the E80 regulator temperature during a
30-minute soak. Do not leave a board transmitting into an unmatched antenna.

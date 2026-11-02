# Porting the bridge to ESP32-C3/S3

The host protocol and link layer do not change. Only the firmware target changes.

## Why

The RP2040 needs BOOTSEL for flashing. ESP32-C3/S3 has auto-reset over USB and
more RAM. The event plan already lists ESP32-C3 boards in inventory.

## Pin map

From `firmware/e80-bypass/common/e80_pinmap.h`:

| ESP32-C3 | E80 J2 | Signal |
|---:|---:|---|
| GPIO6 | J2-13 | SCK |
| GPIO7 | J2-11 | MOSI |
| GPIO2 | J2-9 | MISO |
| GPIO10 | J2-15 | NSS |
| GPIO4 | J2-7 | BUSY |
| GPIO5 | J2-10 | DIO8 / IRQ |
| GPIO3 | J2-5 | NRST |

That is the same wiring the proven `firmware/esp32-c3-flrc` and
`tracker/firmware/components/lr2021_transport` use.

## Port checklist

- [ ] Reuse the C++ bridge protocol from `firmware/rp2040-bridge/src`.
- [ ] Replace Arduino `SPI`/`digitalWrite` with ESP-IDF `spi_master`/`gpio`.
- [ ] Keep the single radio-owner task and TX queue.
- [ ] Keep USB CDC (or UART0) as the binary host link; use the other UART for logs.
- [ ] Port the `bridgeInit` sequence:
  - LF path for 868/915: `SET_RX_PATH=0`, LF PA `{00 76 10}`.
  - HF path for 2.4 GHz: `SET_RX_PATH=1`, HF PA `{80 00 60 07 10}`.
  - FLRC mod/packet/sync/DIO/IRQ as in the RP2040 firmware.
- [ ] Verify the 16–20 MHz SPI clock; the ESP32-C3 is proven at 20 MHz, the
  RP2040 is safer at 4–12 MHz.
- [ ] Run `fips-lr2021ctl hello/cfg/status/per` against the new board.
- [ ] Add a `firmware/esp32-bridge/` PlatformIO or ESP-IDF project.
- [ ] Update the pin map doc and the hardware test matrix.

## Host compatibility

The host does not care which MCU is behind USB CDC, as long as the bridge
protocol and radio packet size match. A mixed fleet (RP2040 on one end, ESP32 on
the other) is a useful early test.

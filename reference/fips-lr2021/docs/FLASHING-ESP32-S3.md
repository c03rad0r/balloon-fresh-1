# Flashing an E80 with an ESP32-S3 CMSIS-DAP probe

This replaces the Raspberry Pi Pico probe with an ESP32-S3 running Espressif's
`esp-usb-bridge` firmware. The S3 is only the programmer; the E80's STM32 is the
FIPS bridge.

## Hardware

- ESP32-S3 DevKitC-1 N8R2 or N16R8 with **native USB** (`303a:1001` / `303a:1002`)
- E80-900MBL-02 debug header, labeled **C D G V**
- 3 dupont wires
- Two USB-C data cables (S3 and E80)

## Wiring

| E80 | Signal | ESP32-S3 | DevKitC-1 header pin |
|---|---|---|---|
| C | SWCLK | GPIO10 | **J1 pin 16** |
| D | SWDIO | GPIO8 | **J1 pin 12** |
| G | GND | GND | **J1 pin 22** or **J3 pin 1** |
| V | 3V3 | **leave open** | — |

The physical header pin numbers matter on the DevKitC-1. J1 is the header with
3V3/RST/GPIO4…GPIO14; J3 is the header with G/TX/RX/GPIO1…GPIO21. GPIO10 is
**not** pin 10 of the header — it is J1 pin 16.

The E80 is powered by its own USB. The S3 is powered by its own USB. Only GND is
shared. Do not connect V to the S3.

Verify before powering:

- G has continuity to the E80 USB-C shell.
- V is 3.3 V when the E80 is powered.
- No short between 3V3 and GND, or between GPIO8/GPIO10 and GND.
- If OpenOCD cannot read IDR, swap C and D.

## Build `esp-usb-bridge`

The firmware is built for ESP32-S3 with the SWD interface:

```bash
git clone --recursive https://github.com/espressif/esp-usb-bridge
cd esp-usb-bridge
docker run --rm -v "$PWD":/project -w /project \
  -e SDKCONFIG_DEFAULTS='sdkconfig.defaults;sdkconfig.defaults.esp32s3;sdkconfig.swd.defaults' \
  espressif/idf:release-v5.5 \
  bash -lc 'idf.py set-target esp32s3 && idf.py build'
```

Build output:

```text
build/bootloader/bootloader.bin
build/partition_table/partition-table.bin
build/bridge.bin
```

## Flash the S3

Use the S3's native USB port and `esptool` (the ROM USB-JTAG interface works
even if the application is reset-looping):

```bash
esptool.py --chip esp32s3 -p /dev/ttyACM1 -b 460800 \
  --before default_reset --after hard_reset \
  write_flash 0x0 bootloader/bootloader.bin \
              0x8000 partition_table/partition-table.bin \
              0x10000 bridge.bin
```

After reset the S3 should enumerate as:

```text
303a:1002  Espressif Systems Co. Ltd. CMSIS-DAP
```

The old `303a:1001` USB JTAG/serial device is the blank/default firmware; it is
not the probe.

## Pin verification with a meter (do this before blaming the probe)

Flash a tiny image that drives one pin as a slow square wave, then measure the
E80 pad. This separates "is the wire right?" from "is the protocol right?" and
needs no working probe.

```c
gpio_set_level(10, level);          /* SWCLK */
vTaskDelay(pdMS_TO_TICKS(2000));    /* 2 s high, 2 s low */
```

Measured 2026-11-03 on S3 serial `94A9902E9484`:

| Build | E80 C | E80 D | Conclusion |
|---|---|---|---|
| GPIO10 toggles | 3.3 V ↔ 0 V | steady 3.3 V | GPIO10 → C **confirmed** |
| GPIO8 toggles, GPIO10 held low | steady 0 V | 3.3 V ↔ 0 V | GPIO8 → D **confirmed** |
| idle | — | — | V = 3.3 V, so the E80 is powered |

Both signal wires are proven. After this, a `cannot read IDR` is **not** a
wiring, soldering or pin-numbering fault.

Note: the app and the ROM bootloader both enumerate as `303a:1001`, so the USB
ID alone cannot tell them apart. Probe with `esptool ... chip-id` before
flashing, and use `--after watchdog-reset` — the "hard reset via RTS" path does
not reset a chip running over USB-Serial/JTAG.

## Test the probe

Espressif's own documentation for the SWD bridge gives this invocation:

```bash
openocd -s tcl -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg \
  -c 'adapter speed 5000'
```

Two details matter:

- Use a **current** OpenOCD. Espressif syncs CMSIS-DAP fixes from mainline
  continuously; Ubuntu 24.04's `openocd 0.12.0-1build2` predates them.
- The documented speed is **5000 kHz**, not a conservative 100 kHz. The
  bit-banged SWD path was developed against that speed.

Expected on a good target:

```text
Info : SWD DPIDR 0x1ba01477
Info : [stm32f1x.cpu] Cortex-M3 r1p1 processor detected
```

Build a current OpenOCD (needs `libusb-1.0-0-dev`, `libjim-dev`,
`libhidapi-dev`, `libtool`):

```bash
git clone --depth 1 https://github.com/openocd-org/openocd
cd openocd && ./bootstrap
./configure --enable-cmsis-dap --disable-werror --prefix=/opt/openocd
make -j"$(nproc)" && sudo make install
```

The ESP USB Bridge supports **USB bulk (v2) only**; the HID backend is not
implemented.

## Flash the E80

```bash
openocd -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg \
  -c "adapter speed 5000; program e80_bench.elf verify reset exit"
```

## Current status (2026-11-03)

- S3 bridge build: success.
- S3 flash: success.
- S3 enumerates as `303a:1002` CMSIS-DAP, serial `94A9902E9484`.
- GPIO10 → E80 C and GPIO8 → E80 D **verified with a multimeter**.
- OpenOCD 0.12.0 (Ubuntu) still reports `cannot read IDR`.
- The Pico probe `203584200D2D0D42` reads `DPIDR 0x1ba01477` on the same board,
  so the target and the SWD header are healthy.
- OpenOCD master (`0.12.0+dev-g8443233`, built 2026-11-03) is available for the
  speed sweep; `adapter speed 5000` is the documented setting.
- Do not connect V.

## Checklist

- [x] S3 native USB enumerates (`303a:1001`)
- [x] `esp-usb-bridge` SWD build
- [x] S3 flashed with bridge
- [x] S3 enumerates as `303a:1002` CMSIS-DAP
- [x] OpenOCD sees the CMSIS-DAP probe
- [x] GPIO10 → E80 C verified by meter
- [x] GPIO8 → E80 D verified by meter
- [ ] OpenOCD reads DPIDR through the S3 on a known-good E80
- [ ] E80 flashed with the bridge firmware
- [ ] E80 `hello`/`status` over USB
- [ ] Two-node FIPS test

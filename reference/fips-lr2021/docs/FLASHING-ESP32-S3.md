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

| E80 | Signal | ESP32-S3 |
|---|---|---|
| C | SWCLK | GPIO10 |
| D | SWDIO | GPIO8 |
| G | GND | GND |
| V | 3V3 | **leave open** |

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

## Test the probe

```bash
openocd -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg \
  -c "adapter speed 100; init; exit"
```

Expected on a good target:

```text
Info : SWD DPIDR 0x1ba01477
Info : [stm32f1x.cpu] Cortex-M3 r1p1 processor detected
```

## Flash the E80

```bash
openocd -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg \
  -c "adapter speed 100; program e80_bench.elf verify reset exit"
```

## Current status (2026-11-03)

- S3 bridge build: success.
- S3 flash: success.
- S3 enumerates as `303a:1002` CMSIS-DAP, serial `94A9902E9484`.
- OpenOCD sees the probe.
- OpenOCD still reports `cannot read IDR` on the E80 that previously had the
  dead Pico probe.
- Next control: move C/D/G to the known-good E80. If that reads DPIDR, the S3
  probe is good and the other E80's SWD path is damaged. If it still fails,
  swap C/D and recheck GND.

## Checklist

- [x] S3 native USB enumerates (`303a:1001`)
- [x] `esp-usb-bridge` SWD build
- [x] S3 flashed with bridge
- [x] S3 enumerates as `303a:1002` CMSIS-DAP
- [x] OpenOCD sees the CMSIS-DAP probe
- [ ] OpenOCD reads DPIDR on a known-good E80
- [ ] E80 flashed with the bridge firmware
- [ ] E80 `hello`/`status` over USB
- [ ] Two-node FIPS test

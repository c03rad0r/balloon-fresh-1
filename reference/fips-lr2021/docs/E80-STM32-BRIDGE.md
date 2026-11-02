# E80 STM32 bridge mode

The actual event hardware is the E80-900MBL-02: STM32F103C8T6 + LR2021 + CH340.
The `firmware/e80-stm32-bench` image now has a `BRIDGE` mode that speaks the same
host protocol as the RP2040 reference. It reuses the proven `radio_bench` driver,
including its LF/HF selection, so 868/915/2.4 GHz all go through one path.

## Build

```bash
cd firmware/e80-stm32-bench
make firmware
```

Current size: **37 KB flash / 15.9 KB RAM** of the 64 KB / 20 KB budget.

## Flash

The working probe on x280 is `203584200D2D0D42`:

```bash
openocd -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg \
  -c 'adapter speed 100; cmsis_dap_serial 203584200D2D0D42; \
      reset_config none separate; init; \
      program firmware/e80-stm32-bench/build-fw/e80_bench verify reset exit'
```

Or:

```bash
PROBE=203584200D2D0D42 ./scripts/flash-e80-bridge.sh
```

## Enter bridge mode

The bench console is 115200 8N1. Send the line command once:

```bash
fips-lr2021ctl --serial /dev/ttyUSB6 --baud 115200 bridge
```

Expected: `OK BRIDGE 115200`. The firmware then speaks the binary protocol until
the next reset.

Then:

```bash
fips-lr2021ctl --serial /dev/ttyUSB6 --baud 115200 hello
fips-lr2021ctl --serial /dev/ttyUSB6 --baud 115200 cfg --band us915
fips-lr2021ctl --serial /dev/ttyUSB6 --baud 115200 status
```

## Verified on hardware

2026-11-02, board on `/dev/ttyUSB6`, probe `203584200D2D0D42`:

```text
OK BRIDGE 115200
protocol=1 firmware=0.1.0 chip=0x1801 capabilities=0x0007
configured band=us915 freq=915000000 Hz flrc=1300 kbps power=22 dBm payload=255B relay=false
pong
tx=0 rx=0 crc=0 drops=0 timeouts=0 resets=0
```

That proves the binary protocol, CFG/CFG_ACK and STAT path on the real board.
Two-node RF is still blocked: the second board's SWD probe (`148757…`) cannot
read IDR, and the CH340 ROM-bootloader path fails as documented.

## Baud rate

The current bridge runs at 115200 because that is the bench console rate. At
115200 the host link caps around 11.5 kB/s, enough for FIPS handshake, ping and
low-rate telemetry but not for the full FLRC throughput. The next step is a
`BAUD 2000000` switch after entering bridge mode (the E80 console hardware
supports 2 Mbaud).

## Relay

Same protocol: add `--relay` to `cfg`. The STM32 bridge repeats unique packets
for 2 s to stop an immediate loop. Single relay only in this cut.

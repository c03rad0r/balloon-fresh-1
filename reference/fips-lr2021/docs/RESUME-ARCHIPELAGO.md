# Resume on the archipelago node

Written 2026-11-05. The bench moved to a different machine and network; this is
the state to pick up from.

## Access

| | |
|---|---|
| Host | `archipelago.local` (10.2.5.37, WiFi) / `192.168.1.166` (USB Ethernet) |
| Account | `archipelago` (key auth; `root` and `c08r4d0r` do not work) |
| Note | Both addresses are the same machine — verified by interface list |

## Device map on that host

| Port | Device | State |
|---|---|---|
| `/dev/ttyACM0` | Pico `E663B035977F242D` | RP2040 bridge, carrier init, TX works |
| `/dev/ttyACM1` | ESP32-C3 `70:AF:09:21:FB:18` | GPS carrier ESP32 |
| `/dev/ttyACM2` | Pico debugprobe `203584200D2D0D42` | SWD probe |
| `/dev/ttyACM3` | ESP32-C3 `B0:A6:04:00:96:DC` | NiceRF |
| `/dev/ttyACM4` | `123456` | does not answer `usb_reset` |
| `/dev/ttyACM5` | ESP32-C3 `88:56:A6:7B:C6:98` | NiceRF |
| `/dev/ttyUSB1` | CH340 | E80 (STM32 bridge) |

## Tooling

| Tool | Status |
|---|---|
| python3 + pyserial | yes |
| esptool | **yes** — `usb_reset` flashing works, no button needed |
| fips-lr2021ctl | **missing, must be copied** |
| openocd / picotool / stm32flash | no |

## Checklist

- [ ] Copy `fips-lr2021ctl` to the host
- [ ] `hello` on each port; record which are bridges
- [ ] Flash the **refactored** ESP32 bridge (proven driver) to `88:56` via `usb_reset`
- [ ] `hello` → `HELLO_ACK`
- [ ] `cfg --band us2400` → `CFG_ACK`
- [ ] `per` at 2440 MHz → `timeouts` stays 0
- [ ] `cfg --band eu868` → `CFG_ACK`
- [ ] `per` at 868.1 MHz → `timeouts` stays 0
- [ ] `per`/`echo` against the E80 (`ttyUSB1`)
- [ ] Record results in `docs/RESULTS.md`

## Why the refactor matters

The ESP32 bridge now links `tracker/firmware/components/lr2021_transport`
(`EspIdfLr2021Radio`), which is proven on this exact hardware. Six
reimplementation bugs were fixed one at a time before abandoning that approach:

| Symptom | Cause |
|---|---|
| boot loop | 2 KB buffer on a 3.5 KB main-task stack |
| `chip=0` | RC standby instead of `SET_STANDBY_XOSC` |
| SPI reads empty | manual GPIO CS, full duplex |
| TX never completes | IRQ status register reads 0; only the DIO pin works |
| wrong bitrate | 650 kbps is `0x03`, not `0x04` |
| version gate | the proven driver never reads the version at all |

## Regulatory

Bench is in the EU: `eu868` or `eu2400` only. Never `us915`. 868.0–868.6 MHz has a
1% duty cycle — keep bursts short.

## If something is unreachable

`usb_reset` gets an ESP32-C3 into download mode without a button. It fails on
firmware that owns the USB PHY (the `123456` device). RP2040 and STM32 need
BOOTSEL and SWD respectively, so those still require hands-on access.

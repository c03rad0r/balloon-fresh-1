# Proving an over-the-air frame on archipelago — staged plan

Written 2026-11-05. Goal: prove two LR2021 radios exchange frames **before**
asking for a manual test. Everything here is doable without physical access,
except where noted.

## Prerequisites for a manual SSH-over-FIPS test

| # | Prerequisite | Status |
|---|---|---|
| 1 | Two radios exchange a frame over the air | **not demonstrated** |
| 2 | FIPS peer addressing over `lr2021` (peer addr = 4-byte link id) | code exists, never exercised |
| 3 | Two FIPS instances with TUN, matching radio config | not attempted |
| 4 | FIPS handshake over the radio | blocked by 1 |
| 5 | SSH over the FIPS IPv6 address | blocked by 1–4 |

## Stage 1 — can a radio transmit at all?

The DIO line never asserts on the ESP32 carrier, so `timeouts` is ambiguous. Two
possible causes: the IRQ pin is not wired, or the radio is not transmitting.

**Finding while preparing this stage:** the two firmware families use *different
FLRC packet framing*, so they could never have interoperated regardless of IRQ:

| Family | Packet params |
|---|---|
| E80 driver (RP2040 carrier, STM32) | `{0x0C, 0x4C, len}` |
| Proven NiceRF driver (ESP32) | `{0x0E, 0x4D, len}` |

Byte 1 differs in the CRC bit, byte 0 in the sync/preamble field. **Both ends must
use the same framing.** Since the ESP32 can be reflashed remotely and the RP2040
cannot (BOOTSEL), alignment must be applied to the ESP32 side.

- [x] Add a compile-time packet-framing override to the shared driver
- [x] Build the ESP32 bridge with the E80-compatible framing `{0x0C, 0x4C}`
- [x] Flash remotely via `usb_reset`
- [ ] `per` from the ESP32, `echo` on the RP2040 → **still `rx=0`**

### Result 2026-11-05

Framing aligned, still nothing:

```
esp32: tx=40 rx=0 crc=0 timeouts=40
pico : tx=0  rx=0 crc=0 timeouts=0 resets=3
```

The ESP32 never sees the DIO line assert, so it never reports TX completion. Two
possibilities remain, and they need a measurement rather than another guess:

1. **GPIO5 is not wired to the radio's IRQ on this carrier.** Then `timeouts` is a
   false alarm and the radio may be transmitting perfectly.
2. **The radio is not entering TX at all.**

The decisive measurement is the **FLRC packet status register (0x024B)** read over
SPI immediately after `SET_TX`, which reports TX progress without depending on the
DIO pin. The current driver does not expose it for TX, so this needs a small
addition.

Equally unresolved: **the RP2040 has never been shown to receive anything.** Its
TX is confirmed, its RX is not. Until one node demonstrably receives, a null
result from it proves nothing about the other side.

## Stage 2 — does a radio receive?

The RP2040's TX is confirmed (`timeouts=0`); its RX has **never** been shown to
work. One successful `per`/`echo` proves both directions of one pair.

- [ ] RP2040 → ESP32 frames received
- [ ] ESP32 → RP2040 frames received

## Stage 3 — two independent pairs

- [ ] RP2040 ↔ ESP32 (`ttyACM0` ↔ ESP32)
- [ ] E80 (`ttyUSB1`) ↔ RP2040 (`ttyACM0`)

Both pairs must pass before believing the transport is sound.

## Stage 4 — FIPS over the radio, same host

- [ ] Two network namespaces on archipelago
- [ ] `fips` in each, `transports.lr2021` on a different bridge, same band/sync,
      distinct `local_id`
- [ ] Peer configured with the other node's 4-byte link id
- [ ] Handshake completes
- [ ] `ping6` between namespaces
- [ ] `ssh` between namespaces over the FIPS address

## Stage 5 — only then the manual test

- [ ] One radio on the T14, one on archipelago
- [ ] `fips` on both, handshake, `ping6`, `ssh`

## Constraints

- Bench is in the EU: `eu868` or `eu2400` only, never `us915`.
- ESP32 flashing works remotely (`esptool --before usb_reset`).
- RP2040 reflashing needs BOOTSEL — physical access.
- E80 reflashing needs SWD — physical access.
- Prefer 2440 MHz for sustained testing; 868.0–868.6 MHz has a 1% duty cycle.

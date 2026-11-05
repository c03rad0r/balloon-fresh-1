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

## Three distinct problems, only one of which is interop

| # | Problem | Evidence | Nature |
|---|---|---|---|
| 1 | Is anything transmitted at all? | ESP32 `timeouts=40` | instrumentation or TX fault |
| 2 | Do the radio parameters match? | framing, bitrate table, encoding | interop |
| 3 | Can any node receive? | no frame ever observed | RX unproven |

Problems 1 and 3 must be settled before 2 is testable: a link that does not exist
cannot be tuned.

## Stage 0 — self-reception (settles problems 1 and 3, one board)

Configure one node, transmit, and check whether its **own** bridge `rx` counter
increments. Self-reception means the radio demonstrably transmits *and* receives,
with no peer involved.

- [ ] RP2040: `cfg`, `per`, then `status` → `rx > 0`?
- [ ] ESP32: same

If a node hears itself, the fault is purely parameter interop. If it does not,
the parameter question is premature.

## Parameter table — what must match exactly

| Parameter | RP2040 carrier | ESP32 driver | E80 STM32 |
|---|---|---|---|
| Frequency encoding | FRF | FRF | **plain Hz** |
| Bitrate code @650 | 0x04 | 0x03 | 0x04 |
| Bitrate code @2600 | 0x00 | 0x00 | 0x00 |
| Framing byte0/byte1 | 0x0C/0x4C | 0x0E/0x4D → now 0x0C/0x4C | 0x0C/0x4C |
| CRC | off | now off | off |
| Sync word | cfg | cfg | hardcoded 0x2DD4D4B2 |

Two consequences:

- **At FLRC-2600 both bitrate tables agree (0x00).** At 650 they do not. Test at
  2440 MHz / FLRC-2600 where the discrepancy disappears.
- **RP2040 and ESP32 now agree on everything** (FRF, 0x00, aligned framing, CRC
  off, same sync), so a null result from that pair is meaningful.
- **The E80 is the odd one out** (plain Hz). Mixing it with the NiceRF modules is
  the hardest case and goes last.

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

## Stage 3 — two independent pairs, easiest first

- [ ] RP2040 ↔ ESP32 at 2440 MHz / FLRC-2600 (same encoding, same bitrate code,
      aligned framing) — the most likely pair to work
- [ ] E80 (`ttyUSB1`) ↔ RP2040 (`ttyACM0`) — cross-family, expect the frequency
      encoding to fight back

Both pairs must pass before believing the transport is sound.

## Structural fix (prevents recurrence)

The bench has three firmware families, each carrying its own copy of "the air
configuration", and they drifted. The durable fix is a **single canonical
air-config definition** — frequency, bitrate, framing, CRC, sync — shared by all
three bridges, plus a self-test that transmits and confirms reception. Worth
writing down even if the event build stays pragmatic.

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

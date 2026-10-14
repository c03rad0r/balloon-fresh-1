# REPORT — L4 `mesh_meshtastic` transport layer

> **Note on this file's location.** `REPORT.md` in this worktree root already
> contained the deliverable of an **unrelated** task (a PCB wing-board
> double-sided-cell report, `t_8657bd7f`). That text has been preserved verbatim
> as `REPORT-wing-board-t_8657bd7f.md` in the same directory rather than deleted,
> and this report was written in its place. If the wing-board task expected to
> still find its report at `REPORT.md`, this is the change to revisit.

**Branch:** `feat/lib-meshtastic`
**Worktree:** `/home/c03rad0r/worktrees/lib-meshtastic`
**Date:** 2026-10-14
**Scope:** deterministic, host-only. **NO RADIO WAS INVOLVED.**

---

## 1. What this is, and what it is NOT

This is a **Meshtastic-*style*** transport layer for the pico-balloon flight
computer's long-range fallback path. It is **not** an interoperable Meshtastic
implementation, and the difference matters:

| Part of the frame | Status |
|---|---|
| 16-byte `PacketHeader` (layout, endianness, flag bit packing) | **byte-compatible** with Meshtastic, reproduced from upstream source |
| Channel key expansion (single-byte PSK aliases, default key) | **reproduced** from upstream source + published docs |
| 8-bit channel hash (XOR of name bytes with XOR of key bytes) | **reproduced** from upstream docs + source |
| AES-128/256-CTR with the documented nonce construction | **reproduced**; anchored to FIPS-197 and an independent OpenSSL vector |
| Hop-limit decrement + SNR-weighted contention-window delay | **reproduced** from upstream source |
| **Payload + position + telemetry encoding** | **NOT Meshtastic.** A TLV container of our own design |
| **4-byte CRC-32 trailer on the payload** | **NOT Meshtastic.** An addition of ours (upstream has no integrity check) |

Upstream carries the payload as a protobuf `Data` message and position/telemetry
as separate protobuf `PortNum` messages. There is no protobuf on this path (and
adding one would put a third-party dependency in the flight build), so a
maximum-size frame from this layer **will not decode on a real Meshtastic node**.
The header half will; the payload half will not. A real interoperability attempt
needs protobuf (or a hand-rolled minimal protobuf writer for the handful of
fields involved). This is the single most important caveat in this report.

---

## 2. Deliverables

```
firmware/lib/meshtastic/
  README-API.md?                 (no — the headers carry the documentation)
  fake_radio_hal.h               test double implementing the FROZEN contract
  mesh_aes.{h,cpp}               AES-128/256 block cipher (generated S-box) + CTR
  mesh_packet.{h,cpp}            in-memory packet + 16-byte wire header + flags
  mesh_tlv.{h,cpp}               TLV codec (our container) with 7 stated rules
  mesh_channel.{h,cpp}           PSK expansion + 8-bit channel hash
  mesh_crypto.{h,cpp}            nonce construction + seal/open + CRC-32
  mesh_flood.{h,cpp}             hop-limit policy + injectable-jitter delay + dupe suppression
  mesh_transport.{h,cpp}         the layer that binds all of the above to the HAL
  test_mesh.cpp                  4610 assertions
  tools/gen_aes_ctr_kat.py       provenance for the AES-CTR KAT
REPORT.md                        (this file, worktree root)
```

`firmware/lib/radio_core/radio_hal.h` was **read only**; `radio_core.cpp` was
**not linked**; `make_radio_hal` is **never defined** here (the fake implements the
abstract class directly). The shared `firmware/lib/Makefile` was **not edited** —
the module was auto-discovered, which is exactly what the auto-discovery commit
was for.

---

## 3. TDD evidence — real observed RED

### 3.1 RED: test first, implementation absent

`test_mesh.cpp` was committed **before** any implementation existed (commit
`9d207f35`). Real output of `make -C firmware/lib test`:

```
== meshtastic ==
meshtastic/test_mesh.cpp:21:10: fatal error: fake_radio_hal.h: No such file or directory
   21 | #include "fake_radio_hal.h"
      |          ^~~~~~~~~~~~~~~~~~
compilation terminated.
== resetlog ==
  ok   23 checks passed
== ringstore ==
  ok   193 checks passed
...
RESULT: FAILURES
make: *** [Makefile:16: test] Error 1
```

Two further RED cycles happened during implementation, and both were **real**
failures found by the tests rather than by inspection:

* **RED 2 — a genuine encoder bug.** `tlv_encode` produced a **30-byte** frame
  where 77 were needed, and decoding it returned `Truncated`. Cause: the
  `Writer` value-copy helper never advanced its write offset, so each record
  emitted its 3-byte header and **no value**. The header byte-order assertions
  also failed (`out.relay_node = 8, expected 34`). Fixed by making `Writer::record`
  atomic (whole record or nothing) — that shape makes the bug unrepresentable.
* **RED 3 — three failing checks, all three were bugs in MY TEST, not in the
  implementation.** `4610` checks ran, `3` failed. Reporting them distinguishes
  "the test found a bug" from "the test was wrong", and these were the latter:

  * **A hash collision I asserted that does not exist.** I wrote
    `CHECK_EQ(a.channel_hash(), b.channel_hash())` for PSK alias 1 vs alias 2 on
    `LongFast`. Observed: `a.channel_hash() = 8, expected b.channel_hash() = 11`.
    The implementation was right — alias 2 shifts the key's last byte, which
    changes the key's byte-XOR and therefore the hash. Independently confirmed
    with `python3`: `xor("LongFast") ^ xor(psk_alias1) = 0x08`, `... ^ xor(psk_alias2) = 0x0B`.
    Replaced with (i) an explicit **non**-collision test (aliases 1 vs 2, `0x08`
    vs `0x0B`) and (ii) a real collision built from raw key bytes with equal
    byte-XOR (`"0123456789abcdef"` and `"fedcba9876543210"`, both XOR `0x06`,
    verified with `python3`; both hash to `0x0a ^ 0x06 = 0x0c`), which is the
    case that proves the 8-bit filter can be defeated while the cipher check
    still catches it.

  * **A TLV counter-test that was measuring the wrong rule.** The overrun case
    declared a 32-byte value inside a 6-byte buffer and expected `Truncated`.
    Observed: `= 2` (`Oversized`), not `1`. The cause is genuinely interesting:
    because the declared length (32) was inside the size limit, the unknown
    record was *skipped* — which consumed 35 bytes of a 35-byte buffer, leaving a
    misaligned stream whose later garbage records happened to declare an oversize
    length. So the assertion failed while the implementation was arguably
    behaving correctly, and my test was asserting the wrong rule. Rewritten as a
    standalone 6-byte buffer declaring 32 bytes: now the declared length is
    inside the size limit (`≤ 64`) **and** beyond the buffer, so the availability
    check fires first and the rule the test claims to exercise is the one it
    actually exercises.

  * **Two more order/arith slips in the assertions**, both corrected and
    re-derived rather than "fixed until green": the exact loopback wire size
    (independently derived as 73 bytes: `16 + (3+4)*3 + (3+1)*4 + (3+13) + 4`) is
    now pinned as a literal so a layout change cannot pass silently, and the
    `kMaxPayloadLen` budget comment was recomputed exactly
    (`7*3 + 12 + 4 + (3+12) + (3+9) + 4 + 16 = 84`; `84 + 3*ceil(L/64) + L ≤ 255`
    ⇒ `L ≤ 162`).

### 3.2 GREEN

```
== meshtastic ==
  ok   4610 checks passed
== resetlog ==
  ok   23 checks passed
== ringstore ==
  ok   193 checks passed
RESULT: all module tests green
```

Clean rebuild from scratch: **0 warnings** with `-Wall -Wextra`.

### 3.3 Sabotage counter-tests — the suite PROVABLY fails

The brief requires sabotage. Four independent mutations were applied, the suite
run, and the mutation reverted. All four were caught.

| # | Sabotage | Result | Checks failed |
|---|---|---|---|
| 1 | no-op the **channel-hash filter** (`if (hdr.channel != channel_hash())` → `if (false && ...)`) | `RESULT: FAILURES` | 2 |
| 2 | break the **CTR counter increment** (counter never advances) | `RESULT: FAILURES` | 2 |
| 3 | **preserve** the hop limit instead of decrementing (the broadcast-storm bug) | `RESULT: FAILURES` | 5 |
| 4 | disable the **CRC integrity check** (wrong key silently accepted) | `RESULT: FAILURES` | 7 |

Real output samples:

```
#1  FAIL test_mesh.cpp:1079 [transport: wrong-alias B comes up]
      (int)b.last_rx().action = 4, expected (int)RxAction::FilterChannelHash = 1
    FAIL test_mesh.cpp:1099 [transport: other-channel B comes up]
      (int)b.receive(&in, 100) = 0, expected (int)Result::BadArgument = 5

#2  FAIL test_mesh.cpp:518 [AES-CTR KAT: an independent OpenSSL vector over 200 bytes]
      std::memcmp(buf.data(), want.data(), buf.size()) == 0
    FAIL test_mesh.cpp:535 [AES-CTR KAT: ...]  (chunked path)
      std::memcmp(split.data(), want.data(), 200) == 0

#3  FAIL test_mesh.cpp:766 [flood: rebroadcast only while hop limit remains]
      f.hop_limit() = 3, expected 2 = 2
    FAIL test_mesh.cpp:775 [...]  !should_rebroadcast(f1, false)

#4  FAIL test_mesh.cpp:588 [sealed payload: ... a wrong key is DETECTED not accepted]
      (int)open_payload(wrong, ...) = 0, expected (int)SealStatus::IntegrityFailure = 1
    FAIL test_mesh.cpp:591 [...]  garbage.size() = 39, expected 0u = 0
```

Sabotage 1's second failure is the one worth reading: with the hash filter
disabled, a packet from a **different channel that shares the key** was accepted
and decoded (`receive() = 0`, i.e. `Ok`) where the test requires a rejection.
Sabotage 4 shows a wrong key being accepted **with no error at all** — precisely
the failure mode the CRC trailer exists to prevent.

All four mutations were reverted (`grep -c SABOTAGE` on the three touched files
returns `0` for each) and the suite is green again in the same session.

---

## 4. Source verification — what was checked, and where

Everything claimed as "reproduced" was read from public sources fetched during
this task. No constant is from memory.

| Source | Used for |
|---|---|
| `meshtastic/firmware` `src/mesh/RadioInterface.h` | `MESHTASTIC_HEADER_LENGTH 16`, `MAX_LORA_PAYLOAD_LEN 255`, `struct PacketHeader`, `PACKET_FLAGS_*` masks, `CWmin 3` / `CWmax 8` |
| `meshtastic/firmware` `src/mesh/Channels.h` | `defaultpsk[]` (16 bytes, `d4 f1 bb 3a 20 29 07 59 f0 bc ff ab cf 4e 69 01`), `ChannelHash` typedef, "16 bytes of random PSK … (AES128)" |
| `meshtastic/firmware` `src/mesh/Channels.cpp` | `xorHash()`, `generateHash()`, single-byte PSK expansion (`*last = *last + pskIndex - 1`), short-key padding |
| `meshtastic/firmware` `src/mesh/CryptoEngine.cpp` | `initNonce()`, `setCounterSize(4)`, "For CTR, the implementation is the same" |
| `meshtastic/firmware` `src/mesh/RadioInterface.cpp` | `getCWsize()`, `getTxDelayMsecWeighted()`, `getTxDelayMsec()` |
| `meshtastic/firmware` `src/mesh/Router.cpp` | `shouldDecrementHopLimit()`, `p->hop_start = p->hop_limit`, channel index→hash substitution |
| `meshtastic/firmware` `src/mesh/NextHopRouter.cpp` | `tosend->hop_limit--` |
| `meshtastic/firmware` `src/mesh/FloodingRouter.h` | the flooding rules in prose; the `(from,id)` history; "random delay between 0 and 10 seconds"; `perhapsCancelDupe` |
| `meshtastic/firmware` `src/mesh/PacketHistory.h` | hop-limit bit masks in the history record |
| `meshtastic/meshtastic` `docs/development/reference/encryption-technical.mdx` | nonce layout, single-byte PSK alias rule, channel-hash definition, "AES-CTR adds no bytes and has no integrity check", default-key-is-public |
| `meshtastic/meshtastic` `docs/configuration/radio/channels.mdx` | `0x01` for the default channel; key must be 0, 16 or 32 bytes |
| `meshtastic/meshtastic` `docs/configuration/radio/lora.mdx` | "Maximum number of hops. This can't be greater than 7. Default is 3" |
| `rweather/arduinolibs` `CTR.h` / `CTR.cpp` | counter increment algorithm and `setCounterSize()` semantics |
| FIPS-197 (`AES`, App. C) | the AES block KATs, printed in the standard itself |

**Independently computed constants** (not copied) were derived with `python3` on
the target host and are listed in the test as their arithmetic, e.g.
`xor("LongFast") = 0x0a`, `xor(defaultpsk) = 0x02` ⇒ hash `0x08`;
`xor(eventpsk) = 0xc8` ⇒ hash `0xc2`; alias `n` ⇒ `bytes[15] = 0x01 + n - 1`.

---

## 5. DESIGN DECISIONS

**The header is cleartext.** Upstream encrypts only the payload; the channel hash
and hop fields are visible to every relay, which is how a relay knows to relay at
all. Reproduced deliberately.

**Key length is the security parameter, not buffer size.** `CryptoKey.length`
(0/16/32) selects AES-off / AES-128 / AES-256. A 16-byte key zero-padded into a
32-byte buffer is **AES-128**. Getting this wrong silently promotes the default
channel to AES-256 and breaks interoperability; the test asserts
`aes_bits_for()` returns 128 for the default alias.

**The channel hash is a routing hint, not a MAC.** It is 8 bits, so two keys
collide roughly one time in 256. The suite *proves* the collision (two distinct
keys, same hash) rather than pretending otherwise. The filter exists to avoid
running AES for every frame in earshot.

**A CRC-32 trailer is added, and it is not a MAC.** Upstream AES-CTR has no
integrity check by design. On a balloon a relay must not forward garbage and must
not act on a garbled command, so this layer trails the ciphertext with
`LE32(crc32(plaintext))` — 4 bytes. This is an **addition to the wire format**,
detects wrong keys / truncation / corruption, and does **not** stop a forger who
holds the channel key (they can recompute the CRC). It is not authentication and
must not be described as such. Cost: 4 bytes per frame.

**Always decrement, never preserve.** Upstream has a role-dependent exception
where a favourite ROUTER-to-ROUTER first hop *preserves* the hop limit. That is
**not** implemented: a preserved hop limit on a link with no duty-cycle headroom
is a broadcast storm waiting to happen, and this node is a plain client.

**Jitter randomness is injected.** `RandomSource` is an interface;
`ScriptedRandom` gives a test an exact draw. `XorshiftRandom` is the production
generator (deterministic and non-cryptographic — it schedules delays, it does not
make keys). A test asserts the generator actually *varies*, because a constant
would satisfy every bound and still be a broken jitter source.

**`receive()` distinguishes three outcomes** that are easy to collapse and must
not be: `Ok` + empty payload = *nothing pending* (per the frozen contract);
`Timeout` = the radio is not listening; `BadArgument` = a frame arrived and was
rejected, with `last_rx().action` carrying the reason. A filter that silently
drops everything and a filter that works look identical from outside otherwise.

---

## 6. UNCERTAINTIES — every one, honestly

Every item below is marked `UNVERIFIED` at its definition site in the source too.

1. **The `slot_time_ms` default is not verified.** This is the most significant
   gap. Upstream computes the slot time from the LoRa preamble/airtime at the
   configured bandwidth (`slotTimeMsec = computeSlotTimeMsec()`), so it is a
   function of radio config, not a constant. Two public sources disagree on the
   resulting window: the `FloodingRouter.h` prose says "a random delay between 0
   and 10 seconds"; the code path with `2*CWmax*slot + random(0,2^CW)*slot` at a
   slot time of ~1 s yields tens to hundreds of seconds. This module defaults
   `slot_time_ms = 1000` and exposes it as a constructor parameter with a named
   constant so it can be set from **measured airtime on the real link**. The
   *structure* (SNR-dependent contention window scaled by a slot time) is
   verified; the *number* is not.
2. **CTR counter width cannot be proven by a round-trip test.** Upstream uses
   `setCounterSize(4)`. For any frame shorter than ~64 GiB the increment never
   carries past the low four bytes, so 4 bytes and 16 bytes are indistinguishable
   in the output. `kCtrCounterBytes = 4` is sourced from the upstream call site,
   not proven here. The 200-byte KAT *does* catch a counter that fails to advance
   or advances the wrong end (sabotage 2 confirms this).
3. **Position and telemetry scaling is our invention.** `lat_1e7 / lon_1e7 /
   alt_mm` and the selected telemetry fields are a compact local representation,
   not a verified wire-format detail. If these ever need to interoperate, the
   scaling must be checked against `mesh.proto` (`sfixed32 latitude_i`, etc.).
4. **AES implementation is not side-channel hardened.** The S-box is *generated*
   from the GF(2^8) definition (a hand-copied 256-entry table is unverifiable) and
   the inverse S-box from it. The key schedule and rounds are FIPS-197. It is a
   correct AES by construction and by KAT, and it is **not** a hardened crypto
   library: no constant-time guarantees, no padding oracle resistance, no AEAD.
   The data is broadcast on a licence-free band with a key that ships in every
   node's firmware, so the threat model does not warrant more — but the file says
   so rather than leaving a reviewer to assume otherwise.
5. **`kTlvMaxValueLen = 64` and the split-payload rule are arbitrary.** A single
   record's length byte is one byte; 64 was chosen so the worst case fits one
   LoRa frame with room to spare. A payload longer than 64 bytes is split across
   several `Payload` records and concatenated on decode — the one deliberate
   exception to the no-duplicate-fields rule (R5), and it is stated as such.
6. **`kMaxPayloadLen = 160` is derived, not measured.** Derivation is in
   `mesh_packet.h`: `84 + 3*ceil(L/64) + L <= 255` ⇒ largest `L` is 162; 160
   leaves explicit margin. A test asserts a 160-byte payload encodes, seals and
   fits one frame, so the constant cannot silently drift from the encoder.
7. **Hop-limit semantics on receipt.** Upstream's `getHopsAway()` and the
   `hop_start > 0 && hop_start == hop_limit` "repeated reliable tx" special case
   (used for implicit ACKs) are **not** implemented. This layer implements the
   plain flooding path only: decrement, rebroadcast while budget remains,
   suppress duplicates. ACK/retransmission handling is out of scope.
8. **No `ReliableRouter`, no next-hop routing, no PKI.** Upstream's
   `NextHopRouter` (which can *raise* a hop limit back to 2) and its Curve25519
   direct-message path are not implemented. Unicast here is the encrypted-channel
   broadcast addressing a `to` node; relays carry it because they cannot read it,
   and only the addressee delivers it upward.

---

## 7. What is NOT claimed

* **No over-the-air result.** There is no radio attached to this host. A compile
  is not a flash; a host fake is not an SX1280 or an LR2021. No timing, RSSI,
  SNR, TCXO, SPI or range behaviour was measured.
* **No interoperability result.** No frame from this layer was fed to a real
  Meshtastic node, and per §1 the payload half would not decode if it were.
* **No flight-readiness claim.** This is a host-tested library on a branch.
* **No security certification.** The CRC trailer is not a MAC; the channel hash
  is not a MAC; the AES is not hardened; the default channel key is public.

---

## 8. Verification commands (reproduce all of it)

```sh
# the whole host suite
make -C firmware/lib test

# only this module, with sanitizers
cd firmware/lib && g++ -std=c++17 -Wall -Wextra -g \
    -fsanitize=address,undefined -I. -Imeshtastic \
    -o /tmp/meshtastic.test meshtastic/*.cpp && /tmp/meshtastic.test

# regenerate the AES-CTR KAT and diff it against test_mesh.cpp
python3 firmware/lib/meshtastic/tools/gen_aes_ctr_kat.py
```

The generator refuses to emit a vector unless OpenSSL and
`python-cryptography` **agree** and the decrypt round-trip returns the original
plaintext. Its output matches the hex block in `test_mesh.cpp` byte for byte.

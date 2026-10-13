# PLAN — Bench-Rig Board (range-test console)

**ADR of record:** ADR-051 (canonical board-production order of operations)
**Status:** STAGE 1–2 DRAFT — **AWAITING OPERATOR APPROVAL before any placement**
**Author:** manager (Felix)
**Date:** 2026-10-13
**Inputs:** `docs/BENCH-CONSOLE-SPEC.md` v1.0 (NORMATIVE cross-board protocol),
`firmware/e80-stm32-bench/src/{bench_cmd.c,bench_pkt.c,prbs.c,bench_payload.c}`

---

## What the bench-rig board is

The **ground-side RF range-test console**. It is what proves the balloon link
before flight: it streams PRBS test packets over the sub-GHz/FLRC radio and
measures **PER / RSSI / SNR** so a link budget claim is a measurement, not an
estimate. Three firmware variants already exist for three MCU platforms — **no
bench PCB exists for any of them.**

From `BENCH-CONSOLE-SPEC.md` (normative; the spec wins over a board's firmware
where they disagree):

| Property | Value |
|---|---|
| Transport | UART 115200 baud, 8N1 (E80: USART1); USB-CDC consoles must sustain an equivalent line rate |
| Framing | newline-terminated ASCII; `\r` tolerated/stripped |
| Tokenisation | space-separated; commands case-INSENSITIVE; ≤8 tokens, ≤24 chars/token, line ≤96 chars |
| Replies | `OK [...]` / `ERR <REASON>` (`SYNTAX`, `ARG`, `RANGE`, `UNKNOWN`) |
| Async lines | `PKT,...`, `CONFIG_START,...`, `TX DONE (RADIO ASLEEP)`, boot banner, `WDG RESET (...)`, `NOTE ...` — hosts MUST ignore unrecognised lines |
| Identity | `ID <BOARD> v<maj.min> fw=<sha7> role=<TX\|RX\|NONE> armed=<0\|1> mod=lora sf=<sf> bw=<hz>\|mod=flrc br=<bps> freq=<hz> band=<label> pa=<dbm> pcap=<label> chip=<maj.min> radio=<asleep\|awake> boot=<label> buf=<n>` |
| Units | `rssi_dbm`/`snr_db` signed ints (half-dBm / quarter-dB values truncated); `ts_ms` u32 since boot; `per_x1e6` = PER×10⁶; `bw_khz` = Hz/1000 |

**Consumers (must all work against ONE board design):**
- E80 bench fw (STM32F103C8 + LR2021)
- RP2040 bench fw
- ESP32-C3 bench fw

---

## Stage 0 — what exists today (honest inventory)

| Artifact | State |
|---|---|
| Console protocol | ✅ NORMATIVE `BENCH-CONSOLE-SPEC.md` v1.0 |
| Firmware (3 variants) | ✅ `firmware/e80-stm32-bench/`, RP2040, ESP32-C3 bench fw |
| Schematic | ❌ does not exist |
| Netlist / SKiDL | ❌ does not exist |
| Board / placement / routing | ❌ does not exist |
| Gerbers | ❌ |

---

## Stage 1 — Logical definition (SKiDL netlist) — ADR-054

Deliverable: `tracker/hardware/bench-rig/netlist.py` in SKiDL, compiling to a
netlist, ERC-clean.

### Functional blocks (derived from the spec + the three firmware ports)

| Block | Requirement | Candidate part |
|---|---|---|
| **Radio** | sub-GHz + FLRC capable; must expose the `ID?` fields (`mod`, `br`, `freq`, `band`, `pa`, `pcap`, `chip`, `radio`) | LR2021 (ADR-002/ADR-110 lineage) **or** SX1280 (ADR-108 pin plan) — **decision required** |
| **MCU** | must run the console at 115200 8N1 while streaming PRBS at the target bitrate; USB-CDC option | ESP32-C3 (ADR-001) or RP2040 or STM32F103C8 (the three existing firmware targets) — **decision required: one board or three?** |
| **Console UART** | USART1 at 115200 8N1, line buffer ≥96 chars | MCU native UART + USB-UART bridge or native USB-CDC |
| **PA / power control** | `pa=<dbm>`, `pcap=<label>`, `radio=<asleep\|awake>` imply switchable PA + a power-capture path | from the RF shopping list; **TODO(unverified)** |
| **Watchdog** | `WDG RESET (...)` async line → hardware watchdog required | MCU WDT or external |
| **Power** | bench-supplied; over-provision per design doctrine | USB or barrel + LDO |
| **Timing** | `ts_ms` since boot, u32 | MCU timer |

### Stage-1 verification gate
- SKiDL compiles; **ERC clean**.
- The netlist must be able to satisfy **every** `ID?` field and every async line
  in the spec — i.e. the hardware must be able to *produce the protocol*, not
  just run firmware that emits constants.
- **Protocol conformance test plan** written alongside: `ID?` round-trip, the
  command set minimum, `PKT,...` emission under PRBS, PER/RSSI/SNR numbers
  produced from real RF.

---

## Stage 2 — Form factor / envelope

### Design question that dominates the form factor
**One board or three?** The spec covers three MCU platforms. Two shapes:

| Option | Pros | Cons |
|---|---|---|
| **A. One board, one MCU** (the spec's "consumers" are then reduced to one) | simplest, smallest-first, one BOM | breaks the other two firmware variants |
| **B. One board with a pluggable MCU daughterboard** (MCU on a socket/module) | serves all three firmwares with one RF/console base | more mechanical complexity |
| **C. Three boards** | each firmware gets a native board | 3× layout work, 3× BOM, against "smallest-first" |

**Recommendation: B** — one RF+console base board with the MCU as a mode
(populated option), so the three firmware variants share one design. Requires
operator approval.

### Other Stage-2 constraints
- Console must be reachable with the board in an enclosure (test-point access).
- **Arming switch** (`armed=<0|1>`) must be a physical, deliberate input —
  a jumper or latching switch, not a firmware flag (safety: this board keys a
  transmitter).
- Antenna connector matched to whoever runs the range test (SMA, castellated, or
  per Felix's castellated-antenna-pad convention).
- Board must be a bench instrument: provisions for probes on the RF path.

### Proposed Stage-2 gate (per ADR-052)
1. Dimensioned drawing + one-board/three-board decision recorded.
2. **Operator review in Signal**.
3. **Astra spatial review** (RF path separation; arming-switch placement).
4. Then Stage 3 → 4 (placement gate) → 5 (routing) → 6 (DRC + fab files).

---

## OPEN DECISIONS REQUIRED FROM THE OPERATOR (do not proceed without these)

1. **Radio part** — LR2021 or SX1280?
2. **One board / pluggable-MCU base / three boards?** (Recommendation: B)
3. **MCU** — ESP32-C3, RP2040, or STM32F103C8 as the primary?
4. **PA provision** — populate a switchable PA now, or leave a pad for later?
5. **Enclosure / bench form** — handheld, benchtop box, or bare board?

**Nothing is placed, routed, or ordered until these are answered and Stage 1–2
are approved.**

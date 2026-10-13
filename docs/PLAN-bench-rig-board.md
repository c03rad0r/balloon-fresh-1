# PLAN — Bench-Rig Board — **SUPERSEDED: NO BOARD IS NEEDED**

**ADR of record:** ADR-051 (canonical board-production order of operations)
**Status:** **CLOSED — NOT REQUIRED.** This plan was written from
`BENCH-CONSOLE-SPEC.md` without first checking how that spec is actually
satisfied. That check was done on 2026-10-13 and it **refuted the premise**.
**Author of the correction:** manager (Felix)
**Date:** 2026-10-13

---

## Why the premise was wrong (measured evidence)

The bench console is a **firmware + off-the-shelf-module capability that
already exists and has already run**. No custom PCB is involved or required:

| Bench family | Physical target (from the repo) | Evidence |
|---|---|---|
| E80 / STM32 | **onboard STM32F103C8T6 of the E80-900MBL-02 module** | `firmware/e80-stm32-bench/FLASHING.md`: *"Target: onboard STM32F103C8T6 (64K flash / 20K RAM) of the E80-900MBL-02."* |
| RP2040 | **off-the-shelf RP2040-Zero** driving an LR2021 over hardware SPI | `firmware/rp2040/README.md`: *"Firmware for the RP2040-Zero coprocessor that drives the LR2021 radio via hardware SPI"*; UART pins GP20/GP21 verified 2026-07-15 |
| ESP32 | off-the-shelf ESP32-C3 dev boards (RadioLib LR2021) | `firmware/esp32-c3-flrc/`, `firmware/esp32-e28-range/` |

`docs/HARMONIZED-BENCH-PACKAGE.md` (HARM-T9) describes the cross-board bench as
**delivered**, with a results table (`HARMONIZED-RESULTS.md`), a run-report
template, and RCA notes for the LR2021/FLRC quirks. The bench rig has been
*run*, not merely specified.

**Conclusion:** the bench capability is satisfied by modules already owned.
A bench PCB would add a new RF board, a new enclosure, and new bring-up risk to
**replace hardware that already works and already has published results.**

---

## What this means for the JLCPCB order

**The order is hub + base-station, not three boards.** The bench-rig board is
dropped. This supersedes the earlier `docs/PLAN-bench-rig-board.md` scope
(radio choice, one/pluggable/three boards, MCU, PA provision, enclosure — all
moot; there is no board).

---

## What the bench rig still actually needs

| Item | Why | Cost |
|---|---|---|
| **LiteVNA 62** | The instrument that turns bench numbers into RF measurements: S21 sweeps for the TQP3M9037 433 MHz dispute gate, the 433 BPF rejection at 2.45 GHz, the XR-613 insertion loss. Also the base-station checkout instrument. | €166.99 (TO-BUY, checklist row 13) |
| Updated bench README | Record the physical stack + pin map per family (the RP2040-Zero GP20/21 backside note is a known trap) | docs work only |
| (nothing else) | | |

---

## Lesson recorded (ADR-051/053 relevance)

A spec document defines a **protocol**; it does not imply a **board**. Before
writing a board plan, verify how the spec's requirements are physically
satisfied today. This plan was authored from the spec alone and was wrong for
exactly that reason — the same class of error as assuming a DRC "unconnected"
item is a defect without checking whether the partner is off-board.

## If the premise ever changes

The bench-rig board would only be justified if: (a) an enclosure/handheld form
factor becomes a requirement, (b) a family needs an integrated PA not present on
any owned module, or (c) the modular stack proves unreliable in the field. None
of those hold today. Should one arise, re-open this file and start at ADR-051
Stage 1.

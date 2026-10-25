# ADR-136 — The flight wing interface is TWO lands; cut-sense is deferred DNP; routing is sequenced AFTER the interface

> Numbered **136** on 2026-10-25. Verified free with `scripts/adr_next_number.py --number 136`.

**Status:** Accepted (operator direction, 2026-10-25)
**Amends:** ADR-046 §2 (4-land tab), ADR-134 (already removed `GND`/`RF_FEED` as *names*)
**Corrects:** a claim made in conversation that the hub's pad 3 was *dead* `RF_FEED` — it is not
**Relates:** ADR-129 D5 (cut channels), ADR-051 §2.5 (nichrome topology), ADR-131 (release)

---

## 1. Context — and a correction

ADR-134 removed `GND` and `RF_FEED` from the **wing** tab as dead copper. That was correct for
the wing: the wing has no Yagi, and `GND` was never a solar return.

**What I then said in conversation was wrong.** I stated that the hub's corresponding pad 3
carried dead `RF_FEED`. Measured off `hub_board_v10.kicad_pcb`:

```
J_W1 pad 3 = /CUT_SENSE_W1     J_W2 pad 3 = /CUT_SENSE_W2
J_W3 pad 3 = /CUT_SENSE_W3     J_W4 pad 3 = /CUT_SENSE_W4
```

ADR-129 §D5 line 138 states it explicitly:

> `pin 3 = /CUT_SENSE_W<n> = J_W<n> pad 3 (RF_FEED)`

So the hub **repurposed** the old RF provision as the **sense leg of each wing's nichrome
cutter**, fed from `VSCAP` pre-LDO so a cut still works with the converter dead. The `(RF_FEED)`
in that line is a historical note about the PAD, not a statement that the net is unused.

**Consequence:** `RF_FEED` is not dead on the hub. It is load-bearing for the cut channel. The
ADR-134 change to the wing was still right; my description of the hub side was not.

## 2. Decision

### 2.1 The FLIGHT interface is two lands

```
J_W<n> pad 1 = W<n>_SOLAR_P
J_W<n> pad 4 = W<n>_SOLAR_N
```

Pins 2 and 3 are **not part of the flight interface**:

- **pad 2 (`GND`)** — the wing has no ground plane to reference (ADR-134 removed it), so on the
  flight build this land carries nothing. It stays on the hub as an unused pad.
- **pad 3 (`CUT_SENSE_W<n>`)** — retained as a **land and a net**, but **DNP / deferred**. See §2.2.

### 2.2 Cut-sense is deferred, not deleted

ADR-129 §D5 already records the cut channel as partly undecided:

> **Still `TODO(unverified)`:** the driver part, the sense divider and the latch's exact topology
> (OPEN-25, OPEN-28). Restoring the channel lands the **net and the pads**; the part is chosen
> when OPEN-25/OPEN-28 close.

And `docs/analysis/wing-jettison.md` recommends **not building the cutter at all** (§Recommendation:
"do not build it"), because there is no trigger that gains anything before burst.

So the sense leg cannot be used on the first flight regardless of how many pads the tab has.
**Keep the net and pad; do not route it as flight-critical, do not fit a part, and do not let it
gate the flight.** Deleting it would destroy the work ADR-129 landed and force a respin when
OPEN-25/OPEN-28 close.

### 2.3 Routing is sequenced AFTER the interface

**The hub's remaining nets must not be routed against the 4-land assumption.** Order:

1. Interface: confirm pads 1 and 4 only on the wing side (§2.1).
2. Parity: `check_schematic_parity.py` on the hub with its registry.
3. Route the remaining signal nets.
4. Re-check the 16 `copper_edge_clearance` at the **J_W2 slot** (`x≈35.75–36.25, y≈74–80`).

Routing 147 nets first means the wing seat geometry is re-done later — the work twice.

## 3. What the hub needs for the FIRST FLIGHT (operator's actual requirement)

Operator: *"I need the board as a way to connect the LR2021 boards to the ESP32 for the first
flight."*

Measured nets with **zero copper** on `hub_board_v10.kicad_pcb` that this requirement needs:

| net group | nets | pads | purpose |
|---|---|---|---|
| `SPI1_SCK/MOSI/MISO` | 3 | 12 | ESP32 ↔ radio SPI bus |
| `E28_CS_N`, `E28_BUSY`, `E28_DIO1..3`, `E28_RESET_N` | 7 | 14 | E28/LR2021 control + IRQ |
| `U3_*` (CS_N/RESET_N/IRQ) | 3 | 6 | second radio select |
| `SPI2_SCK` | 1 | 2 | second bus |
| `F33_*` (RESET_N, IRQ, VSENSE) | 3 | 8 | F33 module |

**Total ≈ 17 nets / 42 pads** for the radio link — not 147. The 147 divides as:

- **82 `GND` + 16 `+3V3`** → the board has **0 pour zones**. These are pour nets; the router
  skips rails by design (`RAILS = ("GND", "+3V3")`). They need **two copper pours**, not tracks.
- **~32 signal nets** with zero copper, of which ~17 are the radio link above.
- **11 `/VSCAP`** — the raw supercap rail, also a pour candidate.
- remaining: solar wing nets, PV nets, misc.

**So "finish the wiring" is: two pours + the signal nets.** The 147 figure overstates the track
work by ~6×; most of it is plane copper.

## 4. What this ADR does NOT decide

- **The cut-sense sense-divider topology and driver part** — OPEN-25 / OPEN-28, unchanged.
- **Whether the cutter is built at all** — `wing-jettison.md` still recommends against it. This
  ADR only guarantees the pads survive so that decision stays open.
- **The hub's final outline** (ADR-068 reconciles 72×80 mm).

## 5. For future sessions

- The wing tab is 2 pins (`SOLAR_P`, `SOLAR_N`). Verify on the board, never from this text:
  `kicad-cli pcb drc ... tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb`
- The hub's J_W pads 1/4 are the flight interface; pads 2/3 are retained-unused.
- **Do not describe hub pad 3 as dead `RF_FEED`.** It is `/CUT_SENSE_W<n>` (ADR-129 §D5).
- Rails are pours: `GND` (82 pads), `+3V3` (16), `/VSCAP` (11). There are currently **0 zones**.

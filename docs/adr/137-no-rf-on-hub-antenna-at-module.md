# ADR-137 — No RF on the hub: antennas connect at the radio module, never on our PCB

> Numbered **137** on 2026-10-25. Verified free with `scripts/adr_next_number.py --number 137`.

**Status:** Accepted (operator decision, 2026-10-25)
**Supersedes:** ADR-004 §Yagi-on-wing (already V2), ADR-034/040 RF provisioning remnants,
and the `ANT*` copper on `hub_board_v10.kicad_pcb`
**Relates:** ADR-136 (hub interface/routing sequence), ADR-129 D5 (old `RF_FEED` repurposed)

---

## 1. The decision, in the operator's words

> *"I would like to avoid doing RF engineering with AI because it's bound to go wrong. The
> LR2021 and SX1280 boards that we solder onto our circuit board handle all the RF & matching
> stuff. I want to connect antennas straight to the pin of those correctly built boards or
> straight to their UFL ports so that we don't need to do any RF design here on our circuit
> board."*

**Rule: the hub carries NO RF design.** No controlled-impedance traces, no matching networks, no
baluns, no antenna feed runs on our PCB. The radio module owns all of it. An antenna (or a U.FL
pigtail) attaches **at the module**:
1. directly to the module's own antenna pin/castellation, or
2. to the module's own U.FL connector, or
3. to a module that already integrates an antenna.

Anything that would put RF on our copper is rejected by this ADR.

## 2. Why — and what the risk actually was

### 2.1 The risk is NOT "the radio nets need 50 Ω"

The 12 blocked nets are `SPI1_*`, `E28_*`, `SPI2_SCK`, `F33_RESET_N`, `F33_IRQ`. **None are RF.**
Impedance control is irrelevant to them; they are ordinary digital signals at a few MHz.

**Measured** — the nets actually occupying U1's blocked escape columns (x 11–16, y 47–56):

```
/F33_BUSY   F.Cu
/GNSS_PPS   F.Cu, B.Cu
/GNSS_RX    F.Cu, B.Cu
/GNSS_TX    F.Cu, B.Cu
/USB_DN     F.Cu
/USB_DP     F.Cu, B.Cu
```

Every one is digital (GNSS UART, USB, a radio-busy line). **Not one is an RF net.**

### 2.2 But there IS real RF on the board today, and that is the actual risk

**Measured** on `hub_board_v10.kicad_pcb`:

| net | length | note |
|---|---|---|
| `/ANT1_433_TX` | **98.7 mm** | from `ANT1` U.FL at (12.5, 69.1) to `U2.9` at (45.5, 30.6) |
| `/ANT4_GNSS_L1` | 12.6 mm | 1.575 GHz |
| `/ANT3_2G4_RX` | 10.6 mm | 2.4 GHz |
| **total** | **121.9 mm / 90 segments** | hand-routed on a mixed-signal board |

That 98.7 mm 433 MHz run crosses a 72×80 mm board packed with a switching converter, an ESP32
and USB. It is the single most likely place for this design to fail for reasons nobody will be
able to diagnose from a flight log. **This ADR deletes exactly that risk** — not by tuning it, but
by not having it.

### 2.3 Why "avoid doing RF engineering" is the correct engineering position here

- RF layout is not verifiable by the gates this repo has. DRC checks clearance, not impedance,
  not return-path continuity, not radiation. A 98.7 mm feed can pass every gate and still be
  wrong.
- The modules are already characterised, matched and (usually) certified by their vendor. Their
  antenna port is the one place where RF is known-good.
- The operator has stated he does not want AI-authored RF design. That is a **sound** boundary:
  the failure mode of subtly-wrong RF is silent and expensive, and no automated gate here would
  catch it. Recording it as a rule prevents a future session from "helpfully" adding a matching
  network.

## 3. What this changes on the hub

### 3.1 Delete

- `ANT1..ANT4` U.FL connectors — **if** their module offers its own antenna port or U.FL. Verified
  per module before deletion; a module whose only antenna access is a castellated pin still gets
  the pigtail soldered at the module, not routed across the board.
- The `ANT*` nets and their 121.9 mm of copper.
- `ANT_C_2G4` (0 pads routed, 0 tracks — already vestigial).

### 3.2 Keep

- Anything the **module** needs at its own pin: DC supply, ground, and (if the module exposes them)
  control lines. These are not RF.

### 3.3 Do NOT do

- Do not add a matching network, balun, or controlled-impedance trace "to be safe".
- Do not route an antenna feed across the board even if DRC is happy.
- Do not infer that a module's antenna pin is 50 Ω and design for it — the vendor did that.

## 4. Effects on the routing problem (ADR-136), stated honestly

The operator asked how this bears on the blocked radio link. Measured answer:

| expectation | measured |
|---|---|
| RF nets are what block U1's escape | **false** — the blockers are GNSS/USB/F33, all digital |
| deleting RF frees the corridor | **mostly false** — only **2 of 90** RF segments are inside the blocked corridor box |
| deleting RF reduces board congestion | **true but modest** — 121.9 mm of copper and up to 4 connectors leave the board |

**So: this ADR does not, by itself, unblock the 12 radio nets.** It removes a real RF risk and
some congestion, and it is the right decision on its own merits. But the placement problem in
ADR-136 §4/§5 stands, and options A (move `U_E28`) and B (re-assign U1 pins) are still the fix.

**This matters:** adopting this ADR should not create the expectation that routing suddenly works.
It does not. Two separate problems were being conflated because both involve "antennas".

## 5. Consequences

- The hub no longer needs RF-aware layout review — one whole class of review disappears.
- Board area and congestion improve slightly (measured above), which *helps* options A/B.
- The physical build gets simpler: antennas attach at the module, where the vendor's own reference
  design applies.
- If a module later proves to have no usable on-module antenna access, the answer is a **different
  module** or a vendor pigtail — not a trace on our board.

## 6. For future sessions

- **Rule:** no `ANT*` net, no matching network, no RF trace on any of our boards. Antenna at the
  module.
- Verify the modules' antenna access from their datasheets before deleting `ANT1..ANT4`; record
  which access each module has (pin / U.FL / integrated).
- Reproduce the measurements above:
  ```bash
  /usr/bin/python3 -c "import pcbnew,math;b=pcbnew.LoadBoard('tracker/hardware/hub_board_v10.kicad_pcb');\
  print([(t.GetNetname(),round(math.dist((t.GetStart().x,t.GetStart().y),(t.GetEnd().x,t.GetEnd().y))/1e6,1)) \
  for t in b.GetTracks() if t.GetNetname().startswith('/ANT')][:5])"
  ```
- A stale note: ADR-046 §2.4 and ADR-004 still describe an `RF_FEED` on the wing tab. ADR-134
  removed it from the wing and ADR-129 D5 repurposed the hub pad as `CUT_SENSE_W<n>`. This ADR
  closes the last of that thread.

# SX1280 chip-vs-module + the third LR2021 slot — consultant-reviewed findings (2026-10-20)

**Trigger:** operator questions after reviewing the board renders: (1) what is `U5`?
(2) what happened to the three-LR2021-slots plan? (3) does a bare QFN SX1280 contain the PA
and everything needed to drive an antenna, or should we leave pads for an SX1280 *module*
(example: AliExpress item `32946774361`, an E28-style castellated SX1280 module)?

**Consultation:** `tracker/hardware/ask_astra.py`, served model **`gpt-6-astra`** (read back),
on the annotated RF-scatter render `docs/fab/jlc-query/`-style evidence
(`/tmp/boardviews/95-SX1280-RF-scatter.png`). Verdict: **FATAL as laid out — not a tuning
problem.** Full answer preserved in `SX1280-MODULE-DECISION.md` appendix.

## 1. What the parts are (measured from the canonical board)

| ref | value | role |
|---|---|---|
| `U4` | `SX1280` | QFN-25, **2.4 GHz ranging radio**, centre (52.8, 26.8) |
| `U5` | `MAX-M10S` | **u-blox GNSS module**, centre (41.9, 35.3) — **not a radio** |
| `U2` | `LoRa2021F33-2G4` | Site A (HP, nested pad field), 433 TX via `ANT1` |
| `U3` | `LoRa2021_Castellated` | Site B (bare LP), 2.4 RX via `ANT3` |

`U5` is the GPS. Its `VIO_SEL` pin 15 is correctly left open (3.3 V I/O).

## 2. The three-LR2021-slot ruling: NOT implemented — one site short

`docs/fab/V9-RADIO-SLOT-CONSOLIDATION.md` records the operator ruling (2026-10-14):
**three LR2021 slots total — two LP + one F33.** Measured now: the board carries **two**
(`U2` F33 + `U3` LP). **Site C (second LP slot) does not exist.** The consistency gate
`tracker/hardware/tests/test_order_package_consistency.py` fails on exactly this
(pre-existing, known). Nothing since 2026-10-14 added Site C; the slot-consolidation doc's
own warning — "a real area add on a 70 mm board already at the seat-probe limit" — is why.

## 3. The SX1280 RF section is REAL but SCATTERED — measured

The full vendor reference network (Table 15-1 BOM) is present with correct values/MPNs
(`C0` 0.8 pF, `L1` 3 nH, `C1`/`C2` 1.2 pF, `C7`=C4 0.5 pF, `L2` 2.5 nH, `C3` 100 pF,
`Q1` 52 MHz ±10 pF load). **The schematic is right. The placement is not:**

```
U4 RF pin 22 (52.5,29.2)  C0 (52.1,30.7) + L1 (55.5,30.7)   adjacent — GOOD
C1  ( 2.0,39.5)   52 mm from U4   PI shunt element
C7  (20.0,48.5)   39 mm           PI shunt element
C2  (56.0,40.5)   14 mm           PI shunt element
C3  (68.0,39.5)   20 mm           DC block (feeds ANT2 U.FL)
L2  (67.0,27.5)   14 mm           PI series element
Q1  (44.1, 2.8)   25 mm from XTA/XTB, 27 mm + 38 mm of track
/SX1280_RF_MATCH net: 83 mm of 0.2 mm track spanning x 1.5..66.5
/SX1280_RF_FILT  net: 66 mm            /ANT2 feed: 68 mm     total ≈ 220 mm
```

## 4. Does the bare chip contain "everything"? — consultant answers

- **The SX1280 integrates its own PA and RX front-end** (nominal max TX ≈ **+12.5 dBm**).
  It has **no external PA/LNA** — and needs none for the ranging role.
- **But the RF pin is NOT an antenna connector.** It requires the external
  matching/filter network — which we have, **by value**. At 2.4 GHz the reference design
  includes **placement, interconnect geometry and grounding**, not just values. A 52 mm
  trace to a 1.2 pF shunt element is not that element anymore — at ~220 mm total chain
  (several guided wavelengths in FR-4) the network becomes a distributed mess.
- The 52 MHz crystal 25 mm away on XTA/XTB is an independent oscillator-integrity risk.

## 5. Recommendation (consultant's, adopted, pending operator confirmation)

> **Replace the bare-chip SX1280 with ONE qualified, castellated SX1280 module site, and
> add the missing LP Site C — in ONE placement revision.**

Reasoning, condensed:
- **Hand-assembly:** a QFN with exposed pad + 0201-class RF parts + layout-sensitive
  oscillator is the worst possible *optional* population job; a castellated module is the
  best. Felix hand-solders optional parts by ruling.
- **Optionality:** an unpopulated module footprint weighs nothing; the bare-chip site
  offers no advantage once a module site exists.
- **Weight:** bare chip wins on paper; module-with-castellations directly soldered is
  close, and far cheaper than a flight failure.
- **The module must be qualified before the footprint freezes** (pinout, PA/LNA presence —
  **not all SX1280 modules add a PA; verify the exact item's datasheet**, supply, antenna
  port, mass). The AliExpress listing alone is NOT qualification.
- **Do not piecemeal:** slot ruling + RF consolidation + wing-slot seat fix are all
  placement-level changes; one revision beats three reflows of the layout.

## 6. What this changes about "fit to order"

The wing-slot seat fix, Site C, and the SX1280 module-site swap are **one coordinated
placement revision** — not independent DRC cleanups. The current board remains
**fit to show, not to order**; the JLC query (§2A castellations, 4A via-in-pad) stays valid
as-is because those questions are unchanged by this revision.

# HUB v9 FLIGHT GAP ANALYSIS — boards + flight readiness

**Date:** 2026-10-14
**Trigger:** operator — "verify these things and do a gap analysis… work with the
visual consultants… so that we don't waste resources on boards that have an issue."
**Method:** datasheet verification (WROOM-1U v1.3 PDF from LCSC), board-file
parsing (pads, footprints, drills, thickness, outline), JLC fab-zip inspection,
and two Astra visual-consultant rounds on 3-D renders (top + bottom). Every
consultant claim below was then CHECKED against the board file — two of their
seven findings were wrong, and that is recorded too.

---

## CORRECTION TO MY OWN FLASHING ANSWER

I previously said UART0 = pads 32/33 and called it "closed". **Wrong.** The
module pinout (datasheet table 3) is: **RXD0 = pin 36, TXD0 = pin 37** (pads
32/33 are IO40/IO41). Both 36 and 37 are **(no net)** on our board — **UART0 is
free**. So you have BOTH flashing paths: native USB (GPIO19/20, pads 13/14) and
UART0 (pins 36/37). GPIO0 (pad 27) no-net is fine — datasheet strapping table 4:
GPIO0 default **pull-up = 1** (SPI boot) at reset; only GPIO45/46 pull down. EN
(pad 3): the strapping section does NOT list EN among internally-pulled pins and
the reference circuit shows R1/C2 as TBD — **EN floating is a real, if
low-probability, intermittent-reset risk. Verify on first power-up; if erratic,
tack 10 kΩ EN→3V3.** Rev-10 should carry it properly.

---

## FINDINGS, ranked by order-wasting potential

### GAP 1 — CRITICAL: the mass budget is for a different board
`docs/PAYLOAD-WEIGHT-ESTIMATES.md` targets **< 14 g** for "Mesh V1: ESP32-C3,
50 × 40 mm, 0.6 mm". The hub v9 is **115 × 103 mm**. Bare laminate alone at
0.6 mm ≈ 13.2 g; at 0.8 mm ≈ 17.5 g; populated (ESP32 3.5 g + SX1280 + 4× U.FL +
solder) ≈ **21–25 g**; plus two wings (25 × 184 mm each) + solar cells → the
flying assembly plausibly **40–55 g**. Nobody has reconciled this against the
envelope's lift. **Ordering 10 boards before the mass budget is re-derived for
hub v9 + wings risks a fleet that cannot fly.** This is the single biggest
resource-waster found.

### GAP 2 — CRITICAL: 0.6 mm 4-layer is not a JLC standard stackup
The board file says `(thickness 0.6)`. JLC's 4-layer offerings are
0.8/1.0/1.2/1.6/2.0 mm — **0.6 mm is 2-layer-only**. The $32.30 quote priced the
page default (likely 1.6 mm). Consequences: (a) the board you receive will be
thicker/heavier than the file says unless you pick 0.8 mm at order time; (b) the
mass estimate must use the REAL thickness; (c) via-in-pad epoxy-fill options vary
by stackup. **At order time, explicitly select 0.8 mm (lightest 4-layer) and
re-check the price.**

### GAP 3 — HIGH: all parts are rated −40 °C; float ambient is ≈ −55 °C
Verified from LCSC spec strings: ESP32-S3-WROOM-1U **−40…+65 °C**, SX1280
−40…+85 °C, MAX-M10S −40…+85 °C, TPS7A02 −40…+125 °C. Tropopause ambient at
11–13.7 km is −55…−60 °C. This is **out-of-spec operation** — standard community
practice (no convective cooling aloft, self-heating + solar keep the stack
warmer), but it must be a KNOWN accepted risk, not an accident. First boards:
log temperature (we kept NTC + R_MON sense lines) and validate the margin before
committing flights.

### GAP 4 — MEDIUM: supercap DNP leaves the cold-start story untested
C_CAP1/2 (THT, 10 mm radial) are correctly DNP in the order BOM. But their
absence means: no energy buffer for TX bursts at dawn/dusk, and cold-start on
weak sun is unproven. Bench rig must measure brownout during SX1280 TX with only
the 100 µF bulk cap. (Consultant raised the same point unprompted.)

### GAP 5 — MEDIUM: U.FL connectors are tight to the board edge
ANT1 sits 2.5 mm from the left edge, ANT2/ANT4 at y = 100.5 with the outline at
103 — ~2.5 mm pad-center-to-edge. A mated U.FL plug (~Ø5 mm) will overhang the
edge; that works, but verify against the Hirose mate drawing and add coax strain
relief (consultant flagged this; the geometry check confirms it is real).

### GAP 6 — MEDIUM: mechanical load path rests on 0.6 mm FR4 tabs
The wing-interface tabs (J_W1..4) extend the outline to 115 mm and carry the
solar wings; there are only 2 × 1.5 mm NPTH holes (both on the left edge, x≈9.4)
— no symmetric mounting. At the real thickness (0.8 mm min, GAP 2) the tabs bend
under launch loads. Felix's doctrine already says castellated antenna pads +
iterate after flights — but note it here so the first launch uses a soft
attachment (zip-tie loop, not hard soldered tab).

### Consultant claims CHECKED and REFUTED (for the record)
- "J_VCC looks like a through-hole jumper" — **wrong**: footprint
  `Jumper:SolderJumper-3_P1.3mm_Open`, pads `smd`, 3 pads. It is a DNP-class
  solder jumper. No assembly impact.
- "C_CAP1/2 shown populated" — render artifact: KiCad renders 3-D models for
  THT footprints regardless of DNP; the order BOM correctly excludes them
  (verified: no C_CAP rows).
- Their remaining findings (strain relief, −55 °C, copper-pour continuity not
  provable from a render, insufficient evidence to approve) are upheld above.

### Verified fine (no action)
- **No unintended THT anywhere**: the only `thru_hole` pads are the two DNP
  supercaps and U1's pad-41 grounding vias (0.6 mm — by design, 6 of them).
- Drill files present and sane: NPTH 2 × 1.5 mm; PTH 153 hits (vias 0.2–0.3 mm
  + supercap 1.0 mm + castellations).
- Edge.Cuts: one clean rect 0,0→103,103; tabs extend to 115 mm as footprint
  graphics (known; JLC detected 115 × 103 correctly).

---

## Astra verdicts (both rounds)
Top and bottom renders both returned **VERDICT: PARTIAL** — "no demonstrated
unmanufacturable feature, but insufficient evidence to approve a ten-board
flight order without BOM/stackup/DRC/power-path checks." Full texts:
`docs/fab/hub-v9/consult-top.md`, `consult-bottom.md` (committed with this doc).

## RECOMMENDED ORDER SEQUENCE
1. Re-derive the mass budget for hub v9 + 2 wings (GAP 1) — **before** paying.
2. Pick 0.8 mm 4-layer explicitly at order time; re-verify price (GAP 2).
3. Accept −40 °C parts at −55 °C ambient as a documented risk; validate with
   first-board temperature logs (GAP 3).
4. Order the 10 boards (the electronic design itself survived every check).
5. Bench: cold-start/brownout test without supercaps (GAP 4); U.FL mate check
   (GAP 5); soft attachment for first launch (GAP 6).

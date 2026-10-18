> **Location note (2026-10-18).** This file was moved from the repo root to
> `docs/reports/REPORT.md` in the root-tidy pass. Source comments elsewhere in the repo
> that say "see REPORT.md" refer to THIS file.

# REPORT — U4 (SX1280) WIRING REBUILD  ·  card t_5c5937f9

**Branch:** `pr/u4-rewire` · **Commit:** `322f37b5` · **Date:** 2026-10-15
**File of record:** `tracker/hardware/schematics/flight_board/v9_flight.kicad_sch`
**Derived netlist:** `tracker/hardware/schematics/flight_board/v9_flight.net`
**Transform script:** `tracker/hardware/rewrite_sch_u4_wiring.py`

---

## 1. What was done (every claim below is a tool observation)

| # | Claim | Evidence |
|---|---|---|
| 1 | `kicad-cli sch export netlist` succeeds on the modified schematic | `rc=0`, 94,051-byte netlist written |
| 2 | EVERY U4 pin is on its target net — **25/25, zero mismatches** | asserted pin-by-pin in the transform script, and re-dumped independently |
| 3 | The 7 dead connections are gone | U4 pin→net dump below |
| 4 | 8 support parts + the 7-part RF network present and wired | 32 pin→net assertions, 0 mismatches; 59 comps in the netlist (was 44) |
| 5 | `test_netlist_integrity.py` | 9 pass / 7 FAIL — see §5 for the exact delta and why |
| 6 | Committed + pushed to BOTH remotes | GitHub `refs/heads/pr/u4-rewire` @ `322f37b5` (`git ls-remote`); ngit **open PR `f25e0137…`** (`ngit pr list`) |
| 7 | `REPORT.md` written | this file |

### The measured U4 pin→net result (from the exported netlist)

```
pin  0 GND      -> GND                pin  1 VR_PA    -> /SX1280_VR_PA
pin  2 VDD_IN   -> /SX1280_VDD        pin  3 NRESET   -> /SX1280_RESET_N
pin  4 XTA      -> /SX1280_XTA        pin  5 GND      -> GND
pin  6 XTB      -> /SX1280_XTB        pin  7 BUSY     -> /SX1280_BUSY
pin  8 DIO1     -> /SX1280_DIO1       pin  9 DIO2     -> /SX1280_DIO2
pin 10 DIO3     -> /SX1280_DIO3       pin 11 VBAT_IO  -> /SX1280_VBAT_IO
pin 12 DCC_FB   -> /SX1280_VDD        pin 13 GND      -> GND
pin 14 DCC_SW   -> /SX1280_DCC_SW     pin 15 VBAT     -> +3V3
pin 16 MISO_TX  -> /SX1280_MISO       pin 17 MOSI_RX  -> /SX1280_MOSI
pin 18 SCK_RTSN -> /SX1280_SCK        pin 19 NSS_CTS  -> /SX1280_CS_N
pin 20 GND      -> GND                pin 21 GND      -> GND
pin 22 RFIO     -> /SX1280_RF         pin 23 GND      -> GND
pin 24 GND      -> GND
```

Before: **7** connected pins, on the wrong functions (`+3V3`, `/SX1280_RESET_N`, `/SX1280_CS_N`,
`/SX1280_MOSI`, `/SX1280_DIO1`, `/SX1280_DIO3`, `GND`). After: **25** connected pins, all correct.

### How the rebuild works

The old field is a **13-row stub grid at 2.54 mm pitch** (x = 314.96/320.04 and 350.52/355.60). The
real part is **6 LEFT / 3 BOTTOM / 9 RIGHT / 6 TOP at 5.08 mm pitch**, so the grid cannot be reused
and labels cannot be matched at the pin coordinate. `rewrite_sch_u4_wiring.py`:

* removes the old field — **25 wires, 10 labels, 14 power flags** (asserted counts, not a guess);
* rebuilds 25 stubs and their labels on the symbol's OWN absolute pin coordinates (5.08 mm),
  including the **exposed pad (pin 0)**, whose connectable end is the body centre and therefore
  needs a dedicated 25.4 mm run out to the left;
* adds the 15 parts and wires them by label + power flag (this sheet connects by NAME, not by drawn
  wire — a plain `GND` label would make `/GND`, a different net, so `power:GND` flags are used);
* embeds the `Device:L` and `Device:Crystal_GND24` symbols it needs.

Method rules from the brief are enforced in code, not by care: paren balance **and** minimum depth
are asserted before and after, the tab profile is asserted (0 lines starting with a space), and the
script **refuses to write** a document that does not balance. It is dry-run by default.

## 2. What was NOT done

* **The PCB (`hub_board_v9.kicad_pcb`) was NOT touched.** The 15 new parts exist in the schematic
  only. This is why gate C is red — see §5.
* **`build_flight_sch.py` was only PARTLY fixed** — its SX1280 pinout, side layout and U4 net
  numbers are corrected and it now regenerates a sheet with the right U4 pinout and the right
  digital/GND/rail/antenna connectivity, but it does **not** yet add the 15 support/RF parts, so it
  still cannot reproduce the sheet of record. See §4 — that is a real finding, not an omission.
* The jack/wing power tree, `/F33_VCC`, `J_VCC` and `D_CLAMP` were not touched (out of scope).
* No crystal load capacitors were added — **deliberate** (vendored Table 15-1: `Cload = 10 pF` is
  internally integrated).
* No `LCSC` property was added to the new symbols (the part numbers are recorded here instead).

## 3. Deviations from the brief — both measured, both flagged

**(a) Q1's padout. The brief is wrong; the vendor's own figure refutes it.**
The brief and `SX1280-WIRING-SPEC.json` say `p1→XTA, p2→XTB, p3→GND, p4→GND`. **Figure 15-1
(page 145 of the vendored PDF) shows pins 1 and 3 as the two crystal electrodes and pins 2 and 4 as
the package ground pads.** Wired as written, one electrode would have been grounded — a dead
oscillator, the same failure class as the 7 connections this card removes. Two independent reads
agree:

* `pdftotext -bbox` token coordinates on page 145: `'3' (88.97,239.20)`, `'1' (88.97,275.93)`,
  `'4' (107.15,252.15)`, `'2' (107.15,262.99)`, `'GND' (116.89,266.51)` — the ground net sits with
  4 and 2, the two electrodes with 1 and 3;
* a 3× zoomed visual read of the crystal (`/tmp/q1_zoom.png`), which returned the same grouping
  unprompted.

Implemented: **pin 1 → `/SX1280_XTA`, pin 3 → `/SX1280_XTB`, pins 2 & 4 → `GND`**
(`Device:Crystal_GND24`). The manager has since confirmed this correction. **The brief and
`SX1280-WIRING-SPEC.json` still need the same edit.**

**(b) The RF network's `C4` designator collides and was renamed `C7`.**
The vendor's parallel 0.5 pF cap is `C4`, but **`C4` is already a populated 10 µF `/GNSS_VCC`
decoupling cap on this sheet**. Adding a second `C4` would produce a duplicate designator (gate D
would fail, and one part would be silently lost). The RF part is therefore added as **`C7`** —
value, MPN and topology unchanged. Vendor-designator mapping: `C0→C0, C1→C1, C2→C2, C3→C3,
C4→C7, L1→L1, L2→L2`.

**(c) Two internal RF nodes needed names** because this sheet connects by label: `/SX1280_RF_MATCH`
(the RFIO–C0–L1–C1 node) and `/SX1280_RF_FILT` (the L2‖C7–C2 node). The antenna-side node is the
**existing** `/ANT2_2G4_RANGE` net — ADR-108 R1 re-points ANT2 at the SX1280 RFIO, and **there is
no `ANT5` part on this sheet** (the brief's "ANT5 (U.FL)" has no counterpart in the design).

## 4. The generator: what was fixed, and what is still open

The card's guidance said the schematic is generated and a hand edit is not durable. **That premise
does not hold for this file any more, and this was measured, not assumed.** Before this card,
`python3 build_flight_sch.py v9` produced a **75-hunk diff** against the committed sheet — i.e.
**regenerating would REGRESS it**. The divergences are all deliberate hand work the generator never
learned:

* `V9_SX1280_PINS` still held the **placeholder** pinout (`VDD_IN/VDD_IO/NSS/SCK/MOSI/MISO/ANT_SW`),
  so regenerating reverted STEP 1 (`b7b47df7`) and put the 7 dead connections back;
* `U_HUB_CVT` / `U_CUT1..4` regressed from their real values, footprints and `LCSC` properties back
  to `TODO(unverified)` and an empty footprint (the part-number pass);
* the `SX1280_ANT_SW` labels that commit `96d219b3` removed were re-added;
* `in_bom` / `on_board` flags flipped.

### What WAS fixed in the generator (this card)

1. **`V9_SX1280_PINS` replaced with the REAL 24+EP pinout** — names, numbers and electrical types
   from Table 2-1, cross-checked against `docs/fab/SX1280-WIRING-SPEC.json`. The placeholder's
   `ANT_SW` pin is gone (the real part has none).
2. **A per-pin SIDE spec** (a 4th field: LEFT / BOTTOM / RIGHT / TOP / centre) and a side-aware
   placement path in `_v9_symbol()`. The old 50/50 half-split put 25 pins as 13 left / 12 right at
   2.54 mm — structurally unable to represent a 6/3/9/6 part, and that is precisely the geometry
   that re-landed the wiring on the wrong pins. The new geometry reproduces `rewrite_sch_sx1280.py`
   (STEP 1) pin for pin, so generator and sheet of record agree. **The legacy 3-tuple path is
   untouched**, so every other custom symbol is unchanged.
3. **`V9_NETS` U4 pin numbers corrected** — the SPI/DIO nets were still on the placeholder numbers
   (4/5/6/7/8/9/10/11/12), which is what re-created the dead connections. Now: `SCK→18, MOSI→17,
   MISO→16, CS_N→19, BUSY→7, RESET_N→3, DIO1→8, DIO2→9, DIO3→10`; `SX1280_ANT_SW` deleted.
4. **The GND and `+3V3` nets corrected for U4** — GND now lists the real ground pads
   (`0, 5, 13, 20, 21, 23, 24`); the rail now lists **pin 15 (VBAT)** and no longer pins 1/2
   (`VR_PA` is a regulator OUTPUT and `VDD_IN` is the regulator's own output node — neither may sit
   on a rail; that was the original defect). `ANT2_2G4_RANGE` moved from placeholder pin 14 to the
   real RFIO, **pin 22**.
5. **`V9_COL_TITLES` no longer claims `*** PINOUT UNVERIFIED ***`** for U4.

### Measured on the regenerated sheet (into a scratch path; the sheet of record was restored)

```
python3 build_flight_sch.py v9                        -> rc=0  (it REFUSED with rc=3 before step 4)
kicad-cli sch export netlist <generated>              -> rc=0
generated SX1280 symbol: 25 pins, sides {LEFT: 6, BOTTOM: 3, RIGHT: 9, TOP: 6, CENTRE: 1}
                         LEFT-side pitch 5.08 mm
                         pin name/side MISMATCHES vs the datasheet pinout: 0
generated U4 pin->net:   18 pins connected, all on their correct nets
                         (GND 0/5/13/20/21/23/24; +3V3 15; SPI 16/17/18/19; DIO 7/8/9/10;
                          RESET_N 3; ANT2 22)
```

### What is STILL open in the generator

**The 15 support/RF parts are not in `V9_COMPONENTS` yet**, so the regenerated sheet leaves U4 pins
**1 (VR_PA), 2 (VDD_IN), 4 (XTA), 6 (XTB), 11 (VBAT_IO), 12 (DCC_FB), 14 (DCC_SW)** open and wires
RFIO straight to `ANT2_2G4_RANGE` with no matching network. **The generator is therefore NOT yet a
substitute for the sheet of record** — and because its own validation is fail-closed, it cannot
silently emit the old wrong pinout either. That is the honest state: strictly better than before,
still incomplete.

**Until the parts are added to the generator, do NOT run it over the sheet of record** — it would
still revert the `U_HUB_CVT`/`U_CUT*` part-number pass and re-add the `SX1280_ANT_SW` labels.


## 5. Gate results, stated honestly

```
test_netlist_integrity.py    BASELINE (bd47f514): 10 pass / 6 FAIL
                             AFTER    (322f37b5):  9 pass / 7 FAIL
```

**Exactly one new failure, and it is the correct signal:**

```
FAIL  C. v9 hub (netlist -> committed board): the board carries every netlist component
      v9 hub (netlist -> committed board): netlist declares 59, board carries 44
      MISSING FROM THE BOARD (15): C0 C1 C2 C3 C5 C6 C7 C8 C9 C10 L1 L2 L4 Q1 R15
```

The schematic now declares the 15 reference-design parts; `hub_board_v9.kicad_pcb` has not been
placed yet. **A red gate with a named, actionable cause is the system working.** It is not hidden
and it is not faked green.

No other gate changed class: gate **A** still passes (0 empty footprints), gate **D** still passes
(no duplicate designators — the `C7` rename is what keeps it passing), and gate **B** fails on
exactly the same pre-existing items as before (`J_W1..J_W4 → Tracker_Mechanical`, plus
`base_station_lib`); **every footprint added by this card resolves** against the installed libraries.

The committed `v9_flight.net` had been **stale since STEP 1** — it still carried the placeholder
pinout and the 7 dead connections. It is regenerated here so the derived netlist matches the sheet
of record.

### Disclosure: the push used `--no-verify`

The pre-push credential gate blocked the first push with retired literals in
`AGENTS.md`, `docs/handovers/HANDOVER-PROMPT.md`, `mesh-stack/tollgate/main/config.c` and two
`tracker/ground-station/antenna-tracker/` files. **Those are pre-existing and already published** —
they are present in `bd47f514`, which is an ancestor of the current `origin/master` (`a05588d1`).
The pushed change introduces **no** literal, proved with the gate itself:

```
cred_gate.sh --text <each of the 3 changed files>   -> rc=0, rc=0, rc=0
cred_gate.sh --range bd47f514..HEAD                 -> rc=0
```

`cred-gate.conf` documents `git push --no-verify` as the override for a TREE_SCAN block that the
pushed range does not cause. **The 5 carrier files still need a scrub** — that is a repo-wide job,
not this card's, and it blocks every future branch push from this checkout.

## 6. REMAINING STEPS (numbered, in dependency order)

1. **Place the 15 new parts on `hub_board_v9.kicad_pcb`** (C0 C1 C2 C3 C5 C6 C7 C8 C9 C10 L1 L2 L4
   Q1 R15) so gate C goes green. Then route them. This is the immediate next card.
2. **Finish the generator** so the sheet is reproducible again. Done in this card: real
   `V9_SX1280_PINS`, the per-pin SIDE spec, the U4 SPI/DIO/GND/+3V3/ANT2 net numbers, and the U4
   column title. **Still to do: add the 15 parts to `V9_COMPONENTS` (+ a `V9_COLUMNS` entry) and
   their nets**, and re-apply the `U_HUB_CVT`/`U_CUT*` part-number pass to the generator so a
   regeneration stops reverting it. Until then the generator must not be run over the sheet of
   record.
3. **Correct `SX1280-WIRING-SPEC.json` / the brief for Q1's padout** (1 & 3 electrodes, 2 & 4
   ground) and for the `C4 → C7` designator collision.
4. **Scrub the 5 retired-credential carrier files** repo-wide so branch pushes stop requiring
   `--no-verify`.
5. **Vendor the crystal datasheet** (`C7502106` / `L327S520H11L`) and confirm its pad↔function table
   against the implemented 1/3-electrode mapping before the fab order. `C0_XTAL` and `R_S_XTAL` are
   still UNVERIFIED for the selected part (already flagged in
   `docs/fab/SX1280-SUPPORT-PARTS-SELECTION.md`).
6. **Confirm the L4 land pattern.** The selected part is `DMBJ CD32-150M 15UH` (LCSC `C2826623`,
   package **SMD 3.5×3 mm** per the live LCSC page), but `Inductor_SMD` has no 3.5×3 footprint; the
   nearest standard one, `L_1210_3225Metric` (3.2×2.5 mm), is used. Confirm or supply a land pattern.
7. Cold cross-family review of the netlist diff (Gate 2.5) — see the card handoff.

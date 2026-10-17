# ERC disposition — v9 flight board

**Date:** 2026-10-17 · **Branch:** `pr/erc-classification` · **Status:** reviewable disposition, no design decision taken.

Gate: `bash tracker/hardware/run_erc.sh` (ERC + netlist regeneration + schematic-to-board parity).

| | before | after |
|---|---:|---:|
| ERC **errors** | **20** | **19** |
| ERC warnings | 37 | 36 |
| parity | PASS (266 nodes, 0 mismatches) | PASS (266 nodes, 0 mismatches) |
| gate exit | 1 | 1 (explained — see §5) |

**Nothing here was fixed by adding a connection.** That is the whole point of the file: thirteen of the
twenty errors are pins on circuits that the design records *explicitly leave undecided*, and wiring them
would **invent a design decision and hide an open item**. Exactly one error was a drawing artefact and it
was deleted (§3).

Reproduce:

```bash
python3 tracker/hardware/classify_erc_errors.py     # the existing classifier, re-run
bash    tracker/hardware/run_erc.sh                 # the gate (prints the waiver)
```

---

## 1. The classifier, re-run and confirmed — with five corrections

`tracker/hardware/classify_erc_errors.py` was re-run and its list is **confirmed**: 12 / 4 / 2 / 1 / 1 is
the right shape, and its rule — *only a genuine omission should be fixed by adding a connection* — is the
rule this disposition follows. Five corrections/additions, each with the measurement that shows it:

| # | classifier said | measured | effect |
|---|---|---|---|
| 1 | "a 0.0508 mm horizontal wire" | the wire is **5.08 mm**, at schematic coords `(121.92, 63.5) → (127, 63.5)`, uuid `c66d7c6a-8a27-5e69-b728-bf87702bb4f6`. ERC's JSON reports position `(1.2192, 0.635)` and length `0.0508` — i.e. the schematic value **÷ 100**. It is a units artefact, not a 2-mil stub. | **the fix target is confirmed, its size is corrected** (§3) |
| 2 | group B `U_HUB_CVT` VOUT — "needs checking" | the part's own netlist description covers **pins 1–3 only**; pin 4 (`VOUT`) has no net, and the description states the **part choice itself is OPEN** (ADR-051 §2.2/§4 items 3/5/6, `OPEN-26`) | resolved → **AWAITING-DECISION `OPEN-26`** |
| 3 | group C `U4` — "UNRESOLVED, could be a pin-type modelling issue" | checked against the symbol: `VDD_IN` and `VBAT_IO` **are** `power_in`, which is correct for the SX1280. Both nets **exist and carry their passives** (`/SX1280_VDD`: `C6.1, C9.1, L4.2, U4.12, U4.2`; `/SX1280_VBAT_IO`: `C8.1, R15.2, U4.11`) — so it is **not** missing copper and **not** a pin-type error: the sheet is missing a *driver declaration* | resolved → **AWAITING-DECISION: declare the rails driven (PWR_FLAG)** |
| 4 | group D `U1` — "likely INTENTIONAL … should be confirmed" | confirmed against the **board**, not just the sheet: `hub_board_v9.kicad_pcb` leaves `U1` pads **3, 13, 14, 35 on no net at all**, exactly as the sheet does | confirmed → **EXCLUDED-with-reason** |
| 5 | group A `U_CUT` — 12 expected-open pins | confirmed against the netlist description *and* the pin arithmetic | confirmed → **AWAITING-DECISION `OPEN-25` + `OPEN-28`** |

The classifier's own summary line ("ZERO of the twelve `U_CUT` pins should be connected by us") is
**confirmed**.

---

## 2. The 20 errors, one row each

Class vocabulary: `FIXED` · `EXCLUDED-with-reason` (a deliberate non-connection; the correct schematic form
is a `no_connect` marker) · `AWAITING-DECISION` (an open design question — **not** ours to close here).

| # | error | ref / pin | class | disposition | who must decide |
|---|---|---|---|---|---|
| 1 | `pin_not_connected` | `U_CUT1.4` ARM | expected-open provisioning stub | **AWAITING-DECISION** — `OPEN-25` (cut-sense GPIO/divider) + `OPEN-28` (the latched one-shot part, ADR-051 §2.5.1) | the `OPEN-25`/`OPEN-28` owner (ADR-051 §2.6; ADR-108) |
| 2 | `pin_not_connected` | `U_CUT1.5` CTRL | expected-open provisioning stub | **AWAITING-DECISION** — same as #1 | as #1 |
| 3 | `pin_not_connected` | `U_CUT1.6` SENSE | expected-open provisioning stub | **AWAITING-DECISION** — same as #1 (the SENSE leg additionally needs an ADC input; §4) | as #1 |
| 4 | `pin_not_connected` | `U_CUT2.4` ARM | expected-open provisioning stub | **AWAITING-DECISION** — same as #1 | as #1 |
| 5 | `pin_not_connected` | `U_CUT2.5` CTRL | expected-open provisioning stub | **AWAITING-DECISION** — same as #1 | as #1 |
| 6 | `pin_not_connected` | `U_CUT2.6` SENSE | expected-open provisioning stub | **AWAITING-DECISION** — same as #1 | as #1 |
| 7 | `pin_not_connected` | `U_CUT3.4` ARM | expected-open provisioning stub | **AWAITING-DECISION** — same as #1 | as #1 |
| 8 | `pin_not_connected` | `U_CUT3.5` CTRL | expected-open provisioning stub | **AWAITING-DECISION** — same as #1 | as #1 |
| 9 | `pin_not_connected` | `U_CUT3.6` SENSE | expected-open provisioning stub | **AWAITING-DECISION** — same as #1 | as #1 |
| 10 | `pin_not_connected` | `U_CUT4.4` ARM | expected-open provisioning stub | **AWAITING-DECISION** — same as #1 | as #1 |
| 11 | `pin_not_connected` | `U_CUT4.5` CTRL | expected-open provisioning stub | **AWAITING-DECISION** — same as #1 | as #1 |
| 12 | `pin_not_connected` | `U_CUT4.6` SENSE | expected-open provisioning stub | **AWAITING-DECISION** — same as #1 | as #1 |
| 13 | `pin_not_connected` | `U_HUB_CVT.4` VOUT | provisioning stub on an undecided part | **AWAITING-DECISION** — `OPEN-26`: the harvester part and the H2/H3 vs M5/M6 string fork (ADR-051 §2.2, §4 items 3/5/6). The part's own description defines pins 1–3 only | the `OPEN-26` owner (ADR-051 §4) |
| 14 | `power_pin_not_driven` | `U4.2` VDD_IN | power-model declaration missing | **AWAITING-DECISION** — whether `/SX1280_VDD` is declared driven (a `PWR_FLAG`, the generator's own idiom) or the sheet accepts the error. Pin type is correct; the net is real and driven by the SX1280's own DC-DC via `L4` (`DCC_SW`→`L4`→`VDD_IN`), which KiCad's power model cannot see | the sheet-of-record owner (REPORT.md §4 / ADR-108) |
| 15 | `power_pin_not_driven` | `U4.11` VBAT_IO | power-model declaration missing | **AWAITING-DECISION** — same as #14, for `/SX1280_VBAT_IO` | as #14 |
| 16 | `pin_not_connected` | `U1.3` EN | deliberate non-connection | **EXCLUDED-with-reason** — the **board** leaves `U1` pad 3 on no net too; the module relies on the ESP32-S3's internal `CHIP_EN` pull-up. Correct schematic form is a `no_connect` marker (the sheet already carries 19 such markers) | sheet-of-record owner (follow-up: add the marker) |
| 17 | `pin_not_connected` | `U1.13` USB_D− | deliberate non-connection | **EXCLUDED-with-reason** — board leaves pad 13 unnetted; GPIO19/20 are repurposed (`U1.19`→`/U3_IRQ`, `U1.20`→`/U3_CS_N`), so the USB PHY is not used | sheet-of-record owner (follow-up: add the marker) |
| 18 | `pin_not_connected` | `U1.14` USB_D+ | deliberate non-connection | **EXCLUDED-with-reason** — same as #17 | as #17 |
| 19 | `pin_not_connected` | `U1.35` IO42 | deliberate non-connection | **EXCLUDED-with-reason** — board leaves pad 35 unnetted; a spare IO in the free IO22–IO34 block's neighbourhood | sheet-of-record owner (follow-up: add the marker) |
| 20 | `wire_dangling` | `(121.92, 63.5)→(127, 63.5)`, uuid `c66d7c6a…` | drawing artefact (orphan stub) | **FIXED** — deleted from the sheet of record (§3). It is the only error in the set that is an artefact rather than a decision | — |

Twelve of the twenty (#1–#12) are `U_CUT1..4` provisioning pins on a circuit the records state is
**undecided**; #13 is the same condition on the hub harvester. **Thirteen pins are awaiting a design
decision and none of them was wired.**

---

## 3. The one fix, and *where its source is*

**FIXED in the committed schematic file, not in the generator — and that is a measured finding, not a
shortcut.**

`build_flight_sch.py` **does** generate this schematic (`v9_emit()` → `v9_flight.kicad_sch`; run as
`python3 build_flight_sch.py v9`). But it **does not generate the committed file**, and it **does not
emit the dangling wire**:

```bash
# regenerate into an isolated scratch dir (every output global overridden)
python3 build_flight_sch.py v9            # -> 195 wire segments
kicad-cli sch erc <generated> …           # -> 11 errors, 0 wire_dangling, 0 power_pin_not_driven

# the committed sheet of record
grep -c '(wire' tracker/hardware/schematics/flight_board/v9_flight.kicad_sch   # 234 (233 after the fix)
kicad-cli sch erc <committed> …           # -> 20 errors (19 after the fix), 1 wire_dangling
```

- committed sheet: **234** wire segments; regenerated: **195** — **40** exist only in the committed file,
  and `(121.92, 63.5)→(127, 63.5)` is one of them.
- the regenerated sheet has **0** `wire_dangling`, so **there is no generator code to fix** for this wire.
- the reason is recorded in the repo: `REPORT.md` §4 and `docs/fab/SX1280-WIRING-SPEC.json`
  (`"build_flight_sch.py was NOT made to reproduce this sheet -- it is 75 hunks stale and re-running it
  REVERTS step 1 plus the part-number pass"`). The generator was changed in `7055495a7` **without**
  regenerating the sheet, and the sheet was then surgically rewritten in `57d1ee1f4`
  (`rewrite_sch_u4_wiring.py`). Regenerating over the sheet of record is **forbidden by the repo's own
  record** and would revert landed work — it was not done.

So the source of *this* wire is the sheet of record. The fix is the deletion of that one 6-line `(wire …)`
block (uuid `c66d7c6a-8a27-5e69-b728-bf87702bb4f6`), verified afterwards:

```
wire segments   234 -> 233        paren balance  12495 / 12495 (balanced)
all wire blocks well-formed: 233/233 malformed: 0
uuid pairing preserved (the neighbouring (121.92,30.48) wire keeps its own uuid)
ERC errors      20 -> 19   (its companion unconnected_wire_endpoint warning also cleared: 37 -> 36)
parity          PASS (266 nodes, 0 mismatches)
```

The board, the netlist, the DRC rules and the generator were **not** touched.

**Separate defect surfaced by this measurement (not fixed here):** the committed
`v9_flight.kicad_sch` is **not reproducible** from its generator of record — the same defect class as the
stale inventory and ADR-046 §4.2 vs the built board. Whoever next regenerates it must reconcile the 40
divergent segments first.

---

## 4. A live contradiction: `OPEN-25` is "CLOSED" in one record and "open" in four others

The classifier found it; it is recorded here, and **neither record was edited.**

| record | says about `OPEN-25` |
|---|---|
| `docs/analysis/ADC-PIN-RESOLUTION-OPEN17-OPEN25.md` (2026-10-14) | **title: "… OPEN-17 and OPEN-25 CLOSED"**. Self-declared *"Status: analysis + pin decision input. **No freeze**."* |
| `tracker/hardware/schematics/flight_board/v9_flight.net` — the `U_CUT1` description | *"Exact part, the sense divider and the GPIO assignment are all `TODO(unverified)` — **see OPEN-25 and OPEN-28**"* |
| `docs/adr/069-…strap-contradiction-resolved.md` §4 (numbered **2026-10-14**, the same day) | *"**NOT CLOSED.** `OPEN-25` / `OPEN-14` remain open."* |
| `docs/adr/108-f33-sx1280-pin-plan.md` (`OPEN-25` row) | *"… the choice and the divider values **remain open**"* |
| `docs/adr/068-hub-v9-outline-60x60.md` | *"`OPEN-25` — the cut-sense GPIO/divider choice and values — **stays open**"* |

**Which is stale: `docs/analysis/ADC-PIN-RESOLUTION-OPEN17-OPEN25.md` — on its status claim, not on its
finding.** Why, with the evidence:

1. **It is an analysis, and this repo's own rule says analyses cannot close decisions.** `AGENTS.md`:
   *"`docs/analysis/` — findings and measurements, **not decisions**"*, and *"a design change without a
   landed ADR is a draft, not a decision."* The file itself says *"No freeze."*
2. **An ADR dated the same day says the opposite, explicitly.** `ADR-069` (numbered 2026-10-14) states
   `OPEN-25` is **NOT CLOSED**. An ADR outranks an analysis on a status question.
3. **Two more ADRs and the netlist agree with ADR-069** (`ADR-108`, `ADR-068`, and the `U_CUT1`
   description the design itself carries).
4. **The generator agrees too** — `build_flight_sch.py` says *"The GPIO/divider assignment is OPEN
   (OPEN-25)"* (its own `TODO(unverified)` block).

What the analysis genuinely established is a **finding** and it is *not* stale: there is **no free
ADC-capable pin** on the v9 S3 (`GPIO1–GPIO10` all spent; `GPIO11–GPIO20` spent; the 13 free IO22–IO34 are
digital-only), so the cut-sense can only take the one-GPIO + mux/ladder shape. That finding is *why*
`OPEN-25` is hard, and it is a constraint the `OPEN-25` owner must see. **The defect is the word
"CLOSED" in the title, not the arithmetic under it.** The correction belongs to whoever owns `OPEN-25`
(edit the title/status of the analysis, or land the ADR that actually closes it) — picking a side here
silently would be worse than the conflict.

---

## 5. Can ERC reach exit 0 honestly? **No.**

The 19 remaining errors can only be cleared by doing one of two things, and the first is forbidden:

| to clear | you would have to | verdict |
|---|---|---|
| 12 `U_CUT1..4` pins + 1 `U_HUB_CVT.4` | **connect 13 pins on circuits the records explicitly leave undecided** | **FORBIDDEN** — invents a design decision (`OPEN-25`/`OPEN-28`/`OPEN-26`) and hides an open item |
| 4 `U1` pins | add `no_connect` markers to pins that are deliberately unconnected | allowed, but a **sheet edit** asserting intent — not this card's single unambiguous fix; recorded as a named follow-up |
| 2 `U4` power pins | declare `/SX1280_VDD` and `/SX1280_VBAT_IO` driven (`PWR_FLAG`) | allowed, but a **sheet edit** (a power-topology declaration) — recorded as a named follow-up |
| 1 dangling wire | delete it | **DONE** |

So the honest answer is: **ERC cannot reach exit 0 without inventing a connection or making six further
schematic decisions.** The gate therefore keeps exiting **1** — but it now **explains itself**. A printed
WAIVER block was added to `run_erc.sh`, computed from the ERC report at run time (so it cannot go stale):

```
WAIVER -- ERC cannot reach exit 0 honestly. This non-zero exit is EXPLAINED, not ignored.
  19 ERC error(s) remain. Every one is a DISPOSITION, not a repair:
     12  pin_not_connected      U_CUT1, U_CUT2, U_CUT3, U_CUT4 pin(s) 4/5/6
         AWAITING-DECISION: OPEN-25 + OPEN-28 -- cut-sense GPIO/divider and the latched one-shot part (ADR-051 2.5.1 / 2.6)
      4  pin_not_connected      U1 pin(s) 13/14/3/35
         EXCLUDED-with-reason: deliberate non-connection; the board leaves the same pads unnetted (a no_connect marker is the correct schematic form)
      2  power_pin_not_driven   U4 pin(s) 11/2
         AWAITING-DECISION: declare the SX1280 rails driven (PWR_FLAG) -- the generator's own idiom, not a wiring change
      1  pin_not_connected      U_HUB_CVT pin(s) 4
         AWAITING-DECISION: OPEN-26 -- harvester part and H2/H3 vs M5/M6 topology (ADR-051 4 items 3/5/6)
  13 of these are pins on circuits that are EXPLICITLY UNDECIDED (the U_CUT1..4
  provisioning pins and the U_HUB_CVT harvester output): wiring them would INVENT a
  design decision and HIDE an open item. ERC cannot reach exit 0 without doing so.
  Full table, evidence and decision owners: docs/fab/ERC-DISPOSITION.md
```

The gate is **not** made green. Its non-zero exit is now **explained at the point of failure** rather than
left to be guessed at or ignored.

---

## 6. Follow-ups this disposition names (none done here)

1. `OPEN-25` / `OPEN-28` — decide the cut-sense GPIO/divider and the latched one-shot part. Owner: ADR-051
   §2.6 / ADR-108. Must see the pin-exhaustion finding in §4.
2. `OPEN-26` — decide the hub harvester part and the H2/H3 vs M5/M6 fork; then `U_HUB_CVT.4` (VOUT) has a
   destination. Owner: ADR-051 §4 items 3/5/6.
3. Reconcile the two `OPEN-25` records (§4) — edit the analysis's status claim or land the ADR that closes
   the item. Do **not** edit both to agree by guesswork.
4. Sheet of record: add the four `no_connect` markers (`U1.3/13/14/35`) and the two `PWR_FLAG`s
   (`/SX1280_VDD`, `/SX1280_VBAT_IO`) — six declared-intent edits, in one reviewed pass, by the sheet owner.
5. Make `build_flight_sch.py` reproduce the sheet of record again (40 divergent segments; `REPORT.md` §4).
   Until then, **do not run it over the sheet of record.**

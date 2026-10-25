# Wing interconnect — FIRST-ARTICLE TEST PROCEDURE

**Board:** `tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb`
**Records:** ADR-132 (per-cell bypass), ADR-134 (2-pin tab), ADR-135 (schematic), ADR-054 §2.3(b)
**Status:** REQUIRED before any wing is flown. Not optional, not a spot check.

---

## 1. Why this procedure exists

Every automated gate on this board is green — ERC 0, DRC 0, schematic↔board parity 0
failures, 34 tracks fully routed. **None of them can detect a diode soldered in backwards.**
The board is electrically correct on paper and can still be silently broken on the bench.

ADR-054 §2.3(b) states the failure mode exactly:

> A single reversed diode is forward-biased by its own cell's 0.5 V and **silently shorts out
> that cell by construction — i.e. it creates the hard-short failure mode it was fitted to
> prevent.** Install it the other way round and it is forward-biased by the cell's own 0.5 V:
> it clamps the cell to ≈ 0.35 V and shunts it, so the cell produces ≈ 0 V while the diode
> carries the full 1.2 A continuously.

And the reason a lazy test misses it:

> Nothing in the topology catches it — **it is invisible to a string-voltage check, because
> the loss is only 0.85 V of 6.0 V.**

### The consequence for HOW this must be tested

A four-wing string losing one diode loses ≈0.5 V of ≈6.0 V — **8 %**, which hides inside
normal irradiance variation. **A string-level measurement will not find it.**

The same fault measured **at one wing** (3 cells ≈1.5 V, losing ≈0.5 V) is a **33 % drop** —
unmissable.

> **RULE: test per wing at the tab. Never accept a string-level reading as evidence of
> correct diode orientation.**

---

## 2. Test A — Diode orientation, BARE BOARD (definitive)

**Do this BEFORE any solar cell is soldered.** Once the cells are attached, each diode is in
parallel with a live 0.5 V source and the direct measurement is gone. This is the only
unambiguous test in the procedure; it costs about a minute per board.

**Setup:** board bare, 3 × SS24 fitted, no cells, no power, nothing else connected.
DMM in **diode-test** mode.

**Polarity reference (from the ADR-132 netlist and the silkscreen `D1`–`D3` marks):**

| pad | net role | symbol pin |
|---|---|---|
| pad 1 | the cell's **HIGH** side | **K** (cathode) |
| pad 2 | the cell's **LOW** side | **A** (anode) |

**Procedure — repeat for D1, D2, D3:**

1. Red probe on **pad 2 (A)**, black probe on **pad 1 (K)**.
   → **EXPECT** a forward drop of roughly **0.15–0.30 V** (SS24 Schottky at meter test current).
2. Swap the probes: red on **pad 1 (K)**, black on **pad 2 (A)**.
   → **EXPECT** **OL / open** (no conduction).

**Acceptance:**

| step 1 reading | step 2 reading | verdict |
|---|---|---|
| 0.15–0.30 V | OL | **PASS** |
| OL | 0.15–0.30 V | **FAIL — diode reversed** |
| short / ≈0 V both ways | — | **FAIL — diode damaged or wrong part** |
| OL both ways | — | **FAIL — open joint or missing part** |

A reversed diode is caught at step 1 as OL and at step 2 as a forward drop. There is no
ambiguity and no dependence on lighting.

**Also verify while the board is bare:** pad 1 of `D1` is electrically continuous with pad 1
of `SC1` and pad 1 of `J1` (that net is `SOLAR_P`). Continuity, not resistance — the trace
runs are milliohms.

---

## 3. Test B — Assembled wing open-circuit voltage (per wing)

**Setup:** one wing assembled (3 cells soldered to `SC1`–`SC3`), at the tab, **not** connected
to the hub, **not** connected to the other wings. Illuminated at the intended test irradiance
(or a stable bench source — record which).

**Measure:** `J1` pin 1 (`SOLAR_P`) to `J1` pin 2 (`SOLAR_N`), open circuit.

**Expected:** 3 cells in series ≈ **1.5 V** (0.5 V/cell) under good light.

**Acceptance:**

| reading | verdict |
|---|---|
| ≈1.5 V, and all three cells warm/active | **PASS** |
| ≈1.0 V (one cell contributing ≈0 V) | **FAIL — suspect a reversed diode on that wing** → go to Test C |
| ≈0 V | **FAIL — open string**; check cell tails and `SOLAR_P`/`SOLAR_N` continuity |
| one cell visibly shadowed / cold | **inconclusive** — re-test under uniform illumination |

Do **not** accept "close enough to 1.5 V". The whole point is that this is a 33 % signature;
if it reads 1.0 V, one diode is almost certainly reversed.

---

## 4. Test C — Per-cell voltages, assembled and loaded (localises the fault)

Only needed if Test B fails, or as a second-article sample. Purpose: identify **which** of the
three cells is being shunted, so the right diode is reworked.

**Setup:** wing under uniform illumination, loaded into a resistor drawing approximately the
wing's operating current.

**Measure each cell separately** across its own two tail pads (`SC1`, `SC2`, `SC3`).

**Acceptance:**

| per-cell reading | interpretation |
|---|---|
| all three ≈equal (≈0.45–0.5 V) | **PASS** |
| one cell ≈0.30–0.35 V, others normal | **FAIL — that cell's bypass diode is forward-biased (reversed)** |
| one cell ≈0 V, others normal, diode hot | **FAIL — reversed diode carrying ≈1.2 A** |
| one cell low, its diode **cold** | **not** a reversed diode — suspect a bad cell or joint |

The **temperature** discriminator is the useful one: a reversed diode carries the full string
current continuously, so it runs warm while a correctly-installed reverse-biased diode does
not. Touch-safe check only — do not probe a live 1.2 A path with fingers; use a thermal probe
or an IR camera.

---

## 5. Rework rule

A board failing Test A is **not** fixed by "flipping it in software" or by documenting the
reversal. **Desolder and refit the diode**, then re-run Test A from step 1 on that board.

Do not scrap a board for one reversed diode — the joints are accessible by design (SMA pads,
no underfill).

Record the rework against the board serial in §7.

---

## 6. Why a continuity/voltage check alone is not enough

Written down because it is the mistake that makes this procedure look optional:

- **"Continuity across the diode"** passes for a reversed diode — it is a diode either way.
- **"String voltage looks fine"** passes for a reversed diode — 0.85 V of 6.0 V is inside
  normal variation (ADR-054 §2.3(b), quoted in §1).
- **DRC/ERC/parity** pass for a reversed diode — the netlist is the same; only the physical
  part orientation is wrong. This is precisely the class of defect that **no** automated gate
  in this repo can catch.

The only checks that discriminate are **Test A** (bare board, probe polarity) and the
**per-wing** numbers in Test B/C.

---

## 7. Record sheet — copy one per wing

```
Board serial: ................   Assembler: ..............   Date: ..........

TEST A  (bare board, before cells)
  D1   step1 = ....... V   step2 = OL / ....... V   PASS / FAIL
  D2   step1 = ....... V   step2 = OL / ....... V   PASS / FAIL
  D3   step1 = ....... V   step2 = OL / ....... V   PASS / FAIL
  SOLAR_P continuity  D1.1 - SC1.1 - J1.1 ............  PASS / FAIL

TEST B  (assembled, at the tab, not in the string)
  irradiance / source: ...............................
  J1 pin1 - J1 pin2 open-circuit = ....... V     (expect ~1.5 V)   PASS / FAIL

TEST C  (only if B failed)
  SC1 = ....... V   SC2 = ....... V   SC3 = ....... V
  warm diode: D1 / D2 / D3 / none
  conclusion: ................................

REWORK (if any): diode ..... desoldered and refitted; Test A re-run: PASS / FAIL
FINAL VERDICT:  PASS  /  FAIL        Signed: ..............
```

---

## 8. Reproduce the automated side

The gates below are all green and prove the **design**, not the assembly. Run them before
first-article work so the comparison is against a known-good board.

```bash
kicad-cli pcb drc --exit-code-violations tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb
#   expect: Found 0 violations / Found 0 unconnected items, rc 0

python3 tracker/hardware/check_schematic_parity.py \
  --board tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb \
  --sch  tracker/hardware/schematics/wing_interconnect/wing_interconnect.kicad_sch
#   expect: G1-G4 PASS, PARITY: 0 failure(s)

PYTHONPATH=/usr/lib/python3/dist-packages python3 -m pytest tests/test_wing_board_gates.py \
    tests/test_wing_sch_gates.py tests/test_wing_schematic_board_sync.py -q
#   expect: all pass
```

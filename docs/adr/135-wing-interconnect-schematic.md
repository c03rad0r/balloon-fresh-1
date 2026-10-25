# ADR-135 — The wing interconnect has a schematic, and forward-generation is the direction of truth for a board that has no netlist

> Numbered **135** on 2026-10-25. Verified free with `scripts/adr_next_number.py --number 135`.

**Status:** Accepted
**Supersedes:** nothing. **Confirms:** ADR-132 (per-cell bypass), ADR-134 (2-pin tab).
**Amends:** the direction-of-truth convention recorded by `build_flight_sch.py`.

---

## 1. Context

`tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb` was merged as a
**placement-stage** artifact: 44 × 20 mm, 2-pin tab, 3 × SS24 per-cell bypass, DRC clean
except `lib_footprint_issues` and 10 `unconnected_items`. Its true state was recorded in
`docs/fab/wing-3d/ROUTING-STATUS.md`.

Routing it failed **six times**. Every attempt fixed the previous defect and introduced
another (5 crossings + 2 shorts → 1 crossing → clearance + short + dangling via → …).
The root cause was not the board: **the board had no schematic, so it had no netlist**, and
`route_v10_astar.py` (ADR-126) consumes a netlist rather than a pad list. AGENTS.md §19–21
puts schematic → ERC → netlist → board → DRC → routes before routing, for exactly this reason.

## 2. Decision

### 2.1 The wing interconnect gets a schematic, generated from a spec

`tracker/hardware/build_wing_sch.py` emits
`tracker/hardware/schematics/wing_interconnect/wing_interconnect.kicad_sch` plus its
`sym-lib-table`. It is a **pure function of its spec**: two runs are byte-identical, and
`--check` fails if the committed file differs from what the generator produces.

**Measured:** `kicad-cli sch erc --exit-code-violations` → **0 violations, exit 0**.
The netlist exports to exactly four nets:

| net | nodes |
|---|---|
| `SOLAR_P` | `D1.K`, `J1.1`, `SC1.+` |
| `SOLAR_MID1` | `D1.A`, `D2.K`, `SC1.-`, `SC2.+` |
| `SOLAR_MID2` | `D2.A`, `D3.K`, `SC2.-`, `SC3.+` |
| `SOLAR_N` | `D3.A`, `J1.2`, `SC3.-` |

Each bypass diode spans **exactly one cell** — D1 across SC1, D2 across SC2, D3 across SC3.
That is the substance of ADR-132: a per-wing diode cannot clamp a single failing cell
(ADR-054 §2.3), so the topology, not just the part count, is what has to be right.

### 2.2 The series chain needs no jumper wires — and that is a design constraint, not luck

The cells are placed so that cell *k*'s `-` pin lands **exactly** on cell *k+1*'s `+` pin
(step 7.62 mm = one cell's pin span). Each diode's own K–A span is also 7.62 mm, so it
bridges its cell with no jumper either.

This is deliberate: jumper wires on a symbol-dense sheet are where crossings and
`label_multiple_wires` come from. **Any future edit that needs a jumper to keep the chain
contiguous should be treated as a placement error, not solved with wire.**

### 2.3 Direction of truth: FORWARD for a board with no netlist; MIRROR for a frozen board

The repo already had `build_flight_sch.py`, which is **PCB → schematic**: it mirrors a
frozen, routed PCB and states "nothing here invents connectivity". That is correct for a
board that is already authoritative.

This ADR records that the opposite direction is correct — and required — when the board has
**no** netlist yet. A mirror-generator cannot be used there, because there is nothing to
mirror. So:

- **board frozen / routed → mirror** (existing `build_flight_sch.py` rule: PCB wins);
- **board has no netlist → forward-generate** (this ADR: the schematic is the spec).

Neither contradicts the other. What must never happen is a *second* source of truth for a
board that already has one. `test_wing_sch_gates.py` pins this board to the forward path.

## 3. Gates

`tests/test_wing_sch_gates.py` — 7 tests, all passing:

1. `--check` matches disk (a hand edit cannot silently diverge);
2. two builds byte-identical;
3. **ERC 0 violations**, via `--exit-code-violations` (a schematic that loads but has
   dangling pins still yields a wrong netlist, so "loads" is not the gate);
4. exactly the four ADR-134 nets, no others;
5. **`GND` and `RF_FEED` absent** — ADR-134 removed them as dead copper, so their
   reappearance is a regression;
6. full per-net node membership (catches a chain wired in the wrong order);
7. the tab is 2 pins, `J1.1` = `SOLAR_P`, `J1.2` = `SOLAR_N`.

If `kicad-cli` is absent the tests **skip loudly** rather than passing (AGENTS.md §23: a
gate that cannot run must not look green).

**Mutation-tested both ways** — a gate proven only by passing is not proven:

- hand-editing `SOLAR_MID1` → `GND` in the `.kicad_sch` → tests 1 and 2 **fail**;
- flipping `DIODE_ROT` 270 → 90 (which swaps K and A, putting the diode backwards) →
  test 6 **fails** with `{'D1.2', 'J1.1', 'SC1.1'} != {'D1.1', 'J1.1', 'SC1.1'}`.
  A backwards bypass diode is the documented silent-short hazard of ADR-054 §2.3, so this
  is the single most important test in the file.

## 4. What this does NOT do

- **The board is still not routed.** This ADR removes the *blocker*; the router pass is the
  next task and has not been run. `ROUTING-STATUS.md` remains accurate.
- **No schematic-to-board sync has been run.** The PCB still carries its own net table from
  the generator. Reconciling the two (import netlist → assign footprints → route) is work
  that follows this ADR, and until it is done the board must not be ordered.
- **No footprints are assigned in the schematic.** `Footprint` fields are empty; the PCB's
  land patterns are the ones the board generator defines. Footprint assignment belongs to
  the netlist-import step, not here.

## 5. For future sessions

- Rule: a board with no netlist cannot be routed — generate the schematic first.
- Generate: `python3 tracker/hardware/build_wing_sch.py`
- Verify: `python3 -m pytest tests/test_wing_sch_gates.py -q` (7 passed)
- Board gates: `kicad-cli pcb drc --exit-code-violations tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb`
  → expect `lib_footprint_issues` + `unconnected_items` only, until routing lands.
- Pin transforms in KiCad schematics are **measured, not derived**: read the coordinates
  `kicad-cli sch erc` reports. Deriving them from the transform matrix produced four
  consecutive wrong attempts (recorded in the generator's comments).

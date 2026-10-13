# Wing / Solar Carrier v9 — Release Caveat Closure

**Board:** `tracker/hardware/wing_board/wing_board_v9.kicad_pcb`
**sha256:** `62e00d43e0c7d3be8a293f431e6d1110587791d7be6127a4763017702953f715`
**Verdict of record:** `docs/CONSULT-astra-wing-APPROVED-2026-10-13.txt` → **APPROVED**
**Date:** 2026-10-13

Astra approved the board and attached two pre-release checks. Both are closed
below with measured evidence.

---

## Caveat 1 — "confirm the final Gerber preview for the castellated edge plating/profile"

**Finding: NOT APPLICABLE — the wing board has NO castellated pads.**

Measured with pcbnew (edge-proximity scan of every pad's bounding box against
the board outline):

| Measurement | Value |
|---|---|
| Board extents | `(-8.05, -0.05)` – `(176.05, 25.05)` = **184.10 × 25.10 mm** |
| Edge-adjacent pads (within 0.3 mm of any edge) | **0** |
| Edge.Cuts segments | 8 |
| Total outline length | **418.00 mm** |
| bbox perimeter `2×(184.10+25.10)` | **418.40 mm** → matches ⇒ plain rectangle |

**Conclusion:** the wing outline is a plain rectangle with **no castellation
profile**. The wing-to-hub electrical interface is the **J1 4-pin connector**
(pads at x = −5.0 mm, i.e. 3.05 mm inside the left edge — a normal connector,
not an edge-plated pattern). Therefore **no "castellated edge plating" option is
required on the wing order**, and the reviewer's caveat does not apply to this
board. It applies to the **hub**, whose wing sockets are the castellated side —
the hub order carries that requirement (see
`docs/FAB-READINESS-hub-v9.md`).

*Note for the operator:* the rendered view that suggested a "castellated/finger
interface at the left end" is the J1 connector's footprint at the left end. The
measurement above is authoritative.

---

## Caveat 2 — "verify the solar-cell tab polarity/net mapping against the schematic or connectivity report"

**Finding: VERIFIED CORRECT — complete and coherent series/parallel topology.**

Measured pad→net mapping:

| Net | Pads | Role |
|---|---|---|
| `SOLAR_P` | `SC1.1`, `SC4.1`, `J1.1` | string **positive** terminal → hub |
| `SOLAR_MID1` | `SC1.2`, `SC2.1`, `SC4.2`, `SC5.1` | interconnect, cell 1→2 (×2 strings) |
| `SOLAR_MID2` | `SC2.2`, `SC3.1`, `SC5.2`, `SC6.1` | interconnect, cell 2→3 (×2 strings) |
| `SOLAR_N` | `SC3.2`, `SC6.2`, `J1.4` | string **negative** terminal → hub |
| `GND` | `J1.2` | connector ground |

**Topology:** six cell instances `SC1…SC6` wired as **2 parallel strings ×
3 series cells**:

```
        SC1      SC2      SC3
SOLAR_P ──►├──MID1──►├──MID2──►├── SOLAR_N
        SC4      SC5      SC6
SOLAR_P ──►├──MID1──►├──MID2──►├── SOLAR_N
```

Each net carries exactly the pads its role requires; every cell has both
terminals assigned; there is **no floating tab and no polarity inversion**
(positive terminals reach `SOLAR_P`, negative terminals reach `SOLAR_N`).
The DRC's **zero unconnected items** independently confirms the chain is
electrically complete.

⚠️ **RESIDUAL NOTE (needs a human/electrical eye, not a geometric one):**
the DRC proves the *connectivity*, not the *physical polarity of the cells as
soldered*. Confirm that the **cell tab polarity orientation** (which physical tab
of each 52×19 mm cell lands on `SCn.1` vs `SCn.2`) matches this net map before
population. That is a build-time/assembly check on the physical parts, outside
what a board file can assert.

---

## Result

| Caveat | State |
|---|---|
| 1. Castellated edge plating/preview | **N/A** — no castellated pads on this board; interface is J1 |
| 2. Solar tab polarity / net mapping | **VERIFIED** — 2 strings × 3 series cells, all terminals assigned; residual = physical cell tab orientation at build |

Wing board v9: **spatial review APPROVED, order gate PASS, 0 unconnected,
gerbers present** ⇒ orderable, with the assembly-side polarity check due at
build time.

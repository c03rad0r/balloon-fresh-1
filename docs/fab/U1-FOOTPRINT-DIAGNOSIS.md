# U1 footprint — measured diagnosis

**Board:** `tracker/hardware/hub_board_v9.kicad_pcb`, sha256 `90a8aeaa17a199ba8f2cebd6…`
**Reproduce:** `~/venvs/kicad/bin/python tracker/hardware/diagnose_u1_footprint.py`

## The component

`U1` = **ESP32-S3-WROOM-1U-N8R8**, at (58.700, 11.360) mm, **62 pad objects across 42 distinct numbers**.

A WROOM-1U has **41 pads** — 40 perimeter lands plus one exposed ground pad. This board instance carries
**62**, and the excess is not random.

## Defect 1 — thirteen pads share the number `41`

```
number '41'  x13   nets=['GND']   sizes=['0.60x0.60', '3.90x3.90']
```

**Thirteen distinct positions**, all on `GND`, of two sizes: **twelve 0.6 × 0.6 mm** and **one
3.9 × 3.9 mm**. The 3.9 mm pad is the exposed thermal pad; the twelve small ones form a grid around it.

**This is a number collision on distinct copper.** KiCad addresses pads by number, so thirteen pads
answering to `41` cannot be distinguished by any tool — and any consumer that counts pads or enumerates
connections is misled by construction.

The 3 × 3 grid of small ground pads plus the central thermal pad is the signature of a footprint **built
by replicating a pad without renumbering**.

## Defect 2 — nine pads have no number and no net

```
number ''    x9    nets=['(none)']   sizes=['0.90x0.90']
```

**Nine 0.9 × 0.9 mm pads, each at a distinct position, with an empty number and no net.** This is
**floating copper**: it belongs to no net, so it connects nothing.

**These nine are the genuine electrical gap.** Thirteen pads sharing a number is a modelling fault; nine
pads on no net is copper that does nothing.

## Defect 3 — a library-nickname inconsistency, and it is NOT on U1

```
footprints with NO library nickname: 1
   U4         SX1280_QFN24
```

**I expected this to be U1's problem and it is U4's.** Corrected here rather than carried forward: the
netlist gives `U4` the footprint `balloon_flight_v9:SX1280_QFN24`, but the board instance stores a bare
`SX1280_QFN24` with no library nickname. **U1's fpid carries `RF_Module` correctly.**

So the nickname defect is a **separate U4 issue**, and this file records it because it was found while
looking for U1's — not because it belongs in this PR's fix.

**One method note:** the first version of `diagnose_u1_footprint.py` printed both `lib` and `item` as
`pcbnew.UTF8` proxy objects, because the SWIG bindings return an object rather than a string. The
per-footprint loop (which calls `str()` first) is correct; the raw U1 dump is not. The nickname finding
above comes from the loop, which is the trustworthy one.

## What is NOT a defect

- **duplicated references: 0** — no footprint appears twice under the same designator, so the 62 pad
  objects are not an artefact of duplication.
- **duplicated footprint IDs are normal**: `C_0402_1005Metric ×13`, `R_0402_1005Metric ×10`,
  `D_SMA ×6` etc. are simply many instances of a common part.

## Why nothing has caught this

`test_netlist_integrity.py`'s "empty footprint" and "declared vs placed" checks operate on **footprint
counts and reference designators**, not on **pad numbers**. A footprint with 62 pads where 41 are`expected
passes every count-based check: it is present, its reference resolves, and its pads all carry a net or
`(none)` — which no check currently interrogates.

**The check that would have caught it** is a per-footprint pad audit asserting that no number repeats and
that no pad is unnamed. That is a candidate for the gate set, and is recorded here rather than added
silently.

## Status

**Not fixed in this PR.** The repair is a footprint edit, and this repo forbids hand-typed geometry:
`build_hub_board_v9.py` rule R2 requires positions to come from parametric rules, and a builder re-run
must restore `hub_board_v9.kicad_pro`/`.kicad_prl`. Two candidate repairs, both needing a decision:

- **(a) renumber** the twelve colliding `41`s so each is addressable, and either number or delete the nine
  unnamed pads; or
- **(b) replace the footprint** with a correct WROOM-1U that has 41 pads, deriving the placement from the
  existing footprint's own geometry so no coordinate is hand-typed.

The second is cleaner and is what this PR will implement, subject to confirming it against the board's
existing pad positions.

# U1 footprint — CORRECTED diagnosis: it was a false alarm

**Board:** `tracker/hardware/hub_board_v9.kicad_pcb`, sha256 `90a8aeaa17a199ba8f2cebd6…`
**Reproduce:** `~/venvs/kicad/bin/python tracker/hardware/pad_audit.py`
**Net-group test:** `~/venvs/kicad/bin/python tracker/hardware/repeated_number_nets.py`

> ## CORRECTION — read this first
>
> An earlier version of this file claimed **two defects on U1**: thirteen pads sharing the number `41`, and
> nine pads with no number and no net. **Both claims are WRONG.**
>
> Measured against the source of truth, **seven of the eight defects first reported on this board do not
> exist.** They are correct, standard KiCad footprint design — and the "excess" pad count on U1 is the
> stock library part's own structure, not something this project authored.
>
> The mistake is recorded rather than deleted, because the way it was made is the useful part: a rule was
> inferred from a *shape* ("numbers repeat, therefore numbers are wrong") instead of being read from the
> **library that defines the convention**. The measurements below are the ones that settle it, and they are
> reproducible.
>
> **One genuine defect remains, and it is not on U1: `U4`'s footprint ID carries no library nickname.**

## What was claimed, and what disproved it

The original text read, of U1:

```
number '41'  x13   nets=['GND']   -> "a number collision on distinct copper"
number ''    x9    nets=[(none)] -> "floating copper: it belongs to no net, so it connects nothing"
```

Both readings are wrong. Here is the evidence, in the order that settles it.

### 1. The stock KiCad library ships the same structure

```
/usr/share/kicad/footprints/RF_Module.pretty/ESP32-S3-WROOM-1U.kicad_mod
    13 pads numbered '41'   (thru_hole circle)
     9 pads with NO number  (smd rect)
    62 pad lines total
```

**This project did not author the thirteen `41`s or the nine unnamed pads.** The official footprint
carries exactly the same counts. A library footprint contains **zero** `(net …)` lines — nets are assigned
by the designer — so a repeated number in a library part cannot be a defect in the *library*. It is the
convention.

Reproduce:

```bash
F=/usr/share/kicad/footprints/RF_Module.pretty/ESP32-S3-WROOM-1U.kicad_mod
grep -c '(pad "41"' "$F"      # 13
grep -cE '\(pad ""'  "$F"     # 9
grep -c '^.*(net '   "$F"     # 0
```

### 2. Thirteen pads numbered `41` are a THERMAL-VIA ARRAY

They are `thru_hole circle` pads, and on our board **all thirteen sit on one net, `GND`.** That is the
standard KiCad idiom for *several physical pads, one net*: the exposed thermal pad of a module, plus a
field of plated through-holes that carry heat and ground into the plane below.

**A repeated number is a defect only when its pads DISAGREE ON A NET** — because one number can carry
only one net, and that is the one case KiCad genuinely cannot express. Measured on the hub board:

```
~/venvs/kicad/bin/python tracker/hardware/repeated_number_nets.py

IDIOM     (repeated number, ALL pads on ONE net)  : 20 groups   <- correct by design
COLLISION (repeated number, pads on DIFFERENT nets):  0 groups
```

Examples of the idiom, all correct: `U1 '41' ×13 all GND`, and `ANT1..ANT4 '2' ×3 all GND` — a U.FL
connector is one signal pad plus three ground tabs, which the stock
`Connector_Coaxial.pretty/U.FL_Molex_MCRF_73412-0110_Vertical.kicad_mod` also ships as `'1'` plus three
`'2'`s.

### 3. The nine unnamed pads are PASTE APERTURES — they carry no copper

```
U1          9 unnamed pad(s)  nets=['(none)']
            layers=['F.Paste']   -> no copper layer at all
```

**`F.Paste` only.** A pad that exists solely on the paste layer is a *solder-paste aperture* — an opening
in the stencil. It has no copper, so nothing can be "floating", and there is nothing to connect. This is
the KiCad idiom for controlling paste coverage over a large thermal pad (a paste grid rather than one
sheet), and it is why the stack of small apertures appears inside the thermal-pad outline.

The spatial arrangement confirms the intent: rendered to scale and reviewed, the nine sit in a **regular
3 × 3 grid at ≈1.4 mm pitch** inside the 3.9 mm thermal pad, with the twelve small numbered pads at the
**midpoints between** grid positions. Regular geometry at a round pitch is design intent, not corruption.
See `docs/fab/reviews/U1-PAD-FIELD-FINDINGS.md`.

## The one genuine defect — and it is on U4, not U1

```
footprints with NO library nickname: 1
   U4         SX1280_QFN24
```

The netlist names `balloon_flight_v9:SX1280_QFN24`; the board stores a bare `SX1280_QFN24` with **no
library nickname**, while **every other part on the board carries one.** That is a real netlist/board
disagreement. `U1`'s fpid carries `RF_Module` correctly.

Reproduce:

```bash
grep -oE '\(footprint "[^"]*"' tracker/hardware/hub_board_v9.kicad_pcb | sort | uniq -c | sort -rn
# ... every line has 'lib:item' except:  1 (footprint "SX1280_QFN24"
```

## What the gate now checks, and what it deliberately does not

`tracker/hardware/pad_audit.py` — the first check in this repo that looks at pad **numbers and layers**,
because `test_netlist_integrity.py` looks only at footprint **counts** and reference designators.

**Reported as a defect (exit 1):**

- a repeated pad number whose pads **disagree on a net** — the unexpressible case
- an **unnamed pad that is on copper** — copper connected to nothing
- a **model reference that does not resolve**
- a **footprint ID with no library nickname**

**Reported as a warning, not a defect:**

- a repeated number whose pads all share one net — the *thermal-via / ground-tab* idiom
- an unnamed pad that is **paste-only** — a stencil aperture, correct by design

That distinction is the whole point of the tool, and getting it wrong is exactly how this file came to
claim eight defects where there is one.

## Method notes worth keeping

- **The count-based check was never going to catch this, in either direction.** A footprint with 62 pads
  where the part has 41 passes every existing check; and after the rule was written, the *same* pad
  structure passes the new check for the right reason. Neither outcome is visible to a footprint count.
- **`LayerSet.FmtHex()` is not stable across calls.** An early version of the audit used it in the pad
  signature; two IDENTICAL pads then compared as *different*, and the audit reported "overlapping copper"
  for a coincident duplicate. The audit now compares raw internal integers only.
- **The SWIG bindings return objects, not strings.** The first `diagnose_u1_footprint.py` printed `lib`
  and `item` as `pcbnew.UTF8` proxies; only a `str()`-ing loop is trustworthy. The nickname finding comes
  from that loop.
- **Read the source that defines the convention before writing a rule about it.** Every wrong finding
  above came from inferring a rule from the board alone. The stock library and
  `tests/test_model_resolution_census.py` (for `${KIPRJMOD}` / `${KICAD<n>_3DMODEL_DIR}` expansion) each
  already documented the truth.

## Status

**Nothing to fix on the board.** The single defect is a footprint-ID string on `U4`
(`SX1280_QFN24` → `balloon_flight_v9:SX1280_QFN24`), which is a builder-path change under rule R2 (no
hand-typed geometry), not a board repair.

An earlier version of this file said *"Not fixed in this PR — the repair is a footprint edit"* and proposed
renumbering U1's pads. **That plan is withdrawn: renumbering a thermal-via array would break correct
design.**

# docs/fab — START HERE (for the JLCPCB reviewer)

This directory exists for one purpose: **to let a fabricator see exactly what we are asking, and answer
it**, before any order is placed.

**No order has been placed. Nothing here authorises one.**

![system](../boards/system-diagram.png)

---

## Read in this order

### 1. What we are asking you — `JLC-QUERY-DRAFT-MESSAGE.md`

The question itself. Concise, three sections, ordered by what blocks us:

- **Section 2 is the blocking question** — the edge-launched connector pads. Copper **deliberately
  terminates at the routed board edge** so a mating tab contacts it. We need to know whether you can
  build that, and whether it implies edge plating or castellation (**we want neither**).
- **Section 1 is deferrable** — the 0.6 mm 4-layer stackup and controlled impedance.
- **Section 3** — thin-board handling.

**Its drawing:** `jlc-query/edge-launch-cross-section.svg` (`.png` alongside).

### 2. Why we are asking — `EDGE-EXEMPTION-MECHANISM.md`

The measurement behind section 2. A conditionless edge rule takes the DRC count **24 → 16**, and
**8 of the 24 original pairs cannot be reached by any rule at all** (`A.Reference` does not match for
copper-vs-`Edge.Cuts` pairs — proven with a control). The 16 residual is a **rule-applicability
artifact, not 16 defects.**

### 3. What the board actually is — `../boards/GALLERY.md`

**Generated** per-board table with a render each. Read the `nets routed` column, **not the amount of
red**: a copper pour is not routing.

### 4. Where everything stands — `GATE-RESULTS.md`

All three gates, with reproduce commands. Headline: **DRC has 16 errors and all 16 are the intentional
`J_W*` edge lands — zero real electrical errors.** 137 warnings are silkscreen or library metadata.

### 5. What is still missing — `ASTRA-GAP-ANALYSIS.md`

Dependency-ordered gap list across all three boards, from an independent visual/engineering review.
**Largest risk: the base station**, which is placed-only with **0 of 44 nets routed**.

---

## ⚠️ What is NOT ready, stated plainly

| item | state |
|---|---|
| **`U1.41` — the radio's exposed ground pad** | **has no net** (pad-number mismatch); an electrical defect |
| **Schematic ERC** | **20 errors** — 12 floating `U_CUT1–4` pins, `U4`'s two power pins undriven |
| **Wing joint geometry** | **OPEN** — ADR-046 §4.2.1; the board is Option B, the ADR recommends Option A |
| **Interface drawing** | **HELD** — no interface drawing goes to a fabricator while the geometry is undecided |
| **Base station** | placed only, **0/44 nets routed**, no editable schematic |
| **Wing board** | **2 of 6 nets** unrouted |

**The interface drawing is deliberately withheld.** Issuing it would depict a geometry that is not
decided. Everything else above can proceed in parallel with your answers.

---

## Status vocabulary used in this directory

- **ORDERABLE** — every gate passes and the artifacts match the design. Nothing here qualifies.
- **fit to show, not to order** — the current target. Reviewable, with open items named.
- **PENDING** — a check that cannot run yet. Not a pass; a stated gap.
- **WAIVED** — a check whose artifact does not exist and is deliberately not fabricated, with a reason
  that **prints at run time** from a committed record (`base_station/FR-CHECK-WAIVER.md`). Stronger than
  PENDING: deleting the record does not make the gap green — an absent artifact with no `WAIVER:` entry
  is reported **FAIL**. `--strict-waivers` turns every waiver into a failure for a release gate.
  See `BASE-STATION-F-CHECKS.md`.
- **measured** — read from the board or the tool, with the path and sha256 recorded.
- **assumed** — an explicit assumption, flagged wherever it appears, never silently folded into a result.

## The rule this directory is built on

**A gate that cannot run must not look green.** Every check here either passes, fails, or prints
`PENDING`/`WAIVED` with its reason. A check that prints nothing is the failure mode the whole set exists
to catch. A waiver is never a pass: it is countable, it prints, and it cannot be retired by deleting its
record.

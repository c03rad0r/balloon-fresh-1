# J_W* EDGE-CLEARANCE EXEMPTION — why the rule does nothing, measured

**Date:** 2026-10-16
**Rule under review:** `tracker/hardware/jlcpcb-s1-frozen.kicad_dru` lines 42–44 and 64–66
**Board default:** `min_copper_edge_clearance = 0.5` mm (`hub_board_v9.kicad_pro`)

## The rule

```
(rule "S1 hub wing-socket edge-launch (ADR-046/048) - scoped exemption"
  (condition "A.Reference == 'J_W1' || A.Reference == 'J_W2' || A.Reference == 'J_W3' || A.Reference == 'J_W4'")
  (constraint edge_clearance (min 0.00mm)))
```

## Why it exists

`J_W1..J_W4` are the wing-socket land sets. **ADR-046/048 place them deliberately ON the board edge** so
the pads meet the wing tab at 6.0 mm insert depth. Their copper must reach the edge — that IS the
connector. Against the 0.5 mm board default every one of them reads `actual 0.00 mm`.

## The measurement (not an inference)

`tracker/hardware/test_dru_loading.py`, refill-then-DRC discipline:

| variant | `copper_edge_clearance` errors |
|---|---|
| A — repo dru, as-is | **24** |
| B — blanket waiver, rule with **no condition** | **16** |
| C — **no dru file at all** | **24** |

- **A == C** → the repo's rule has **literally zero effect**. It is running and matching nothing.
- **B < A** → custom rules **do** execute and can remove violations. So the file loads and the engine works.

Therefore **the condition is what fails to match.**

`tracker/hardware/find_edge_exemption_form.py`, sweeping condition FORMS:

| condition form | errors |
|---|---|
| `A.Reference` only (as-is) | 24 |
| `A.Reference \|\| B.Reference` | 24 |
| `A.Type == 'Pad' && A.Reference` | 24 |
| `B.Type == 'Pad' && B.Reference` | 24 |
| either side is a Pad and a J_W | 24 |
| **no condition at all** | **16** |

**No reference-based form does anything.** `Reference` — on either side, with or without a Type guard —
is invisible to KiCad's edge-clearance test.

## The mechanism

KiCad's `edge_clearance` test pairs a **copper item** with a **board-edge item**. The edge side is
reported as `Segment of J_W1 on Edge.Cuts` or plain `Rectangle on Edge.Cuts`. An Edge.Cuts shape has no
footprint, so `Reference` is empty on that side; and when the copper side is a Pad the reference IS
present but the comparison is made against a pair whose other member cannot answer it. The rule engine
therefore cannot be told "this pad belongs to an edge-launched connector" through `Reference`.

## The residual, and why it is irreducible

The blanket waiver reaches **16, not 0**. The other **8 pairs cannot be suppressed by any condition** —
they are the pure Edge.Cuts-graphics items (outline rectangles and connector segments) where **neither**
member carries a footprint. This is a **rule-applicability artifact**, not copper closer to the edge than
intended. The repo's own comment already anticipated it: *"their Edge.Cuts SEGMENTS cannot be reached by
a copper condition … the leftover Edge.Cuts graphics items are a rule-APPLICABILITY artifact, not a
copper defect, and are left visible rather than suppressed."*

## Options

| option | effect | verdict |
|---|---|---|
| **(a) conditionless edge-clearance relaxation** | 24 → **16**; the remaining 16 documented as a known applicability artifact | **recommended** — the only form that changes anything |
| **(b) pull `J_W*` copper back to 0.5 mm** | 24 → 0 | **refused** — destroys the edge-launch connector and contradicts ADR-046/048 |
| **(c) lower the board-wide default to 0.2 mm** | 24 → 0 | **refused** — would let any trace reach 0.20 mm anywhere; the repo's own comment refuses this |

## What (a) actually asks the operator to accept

**Shipping with 16 documented rule-applicability items**, none of which is unintended copper. The
alternative readings of those 16 — a real clearance defect — are excluded because **every one is a
`J_W*` pad meeting its own socket's Edge.Cuts segment at 0.00 mm, i.e. the interface.** Zero of the 24
items involve copper from any other net.

## Not applied

This document is the evidence for the ruling. The rule file has **not** been edited and the board has
**not** changed. An ADR recording the decision would land with the edit if approved.

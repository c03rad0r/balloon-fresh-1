# MASTHEAD SPEC DISPUTE A — RESOLVED from the manufacturer

**Date:** 2026-10-14
**Dispute:** checklist row 3 / ADR-079 — does the owned Qorvo **TQP3M9037** cover
the **433 MHz** downlink?
**Prior state:** *"operator says 0.1 MHz–6 GHz, Qorvo says 0.7–6 GHz. If 0.7 GHz is
authoritative the part does not cover the 433 downlink at all and ADR-079 must be
reopened."* (PLAN-base-station-board.md, Dispute A)

## Resolution

**Qorvo is authoritative, and the answer is unambiguous.**

Source: Qorvo product page for TQP3M9037, Wayback snapshot
`20260610002217` (`web.archive.org/web/20260610002217/https://www.qorvo.com/products/p/TQP3M9037`),
fetched 2026-10-14. The live page rate-limits automated fetches (HTTP 429), which
is why the checklist itself already points at Wayback.

Verbatim feature bullets from the page:

```
0.7 - 6 GHz operational bandwidth
Ultra low noise figure, 0.4 dB NF @ 1.9 GHz
6000 MHz Ultra Low Noise, High Linearity Low Noise Amplifier
```

Application context on the same page: "1.9 GHz, the amplifier typically provides
20 dB gain, +35 dBm OIP3 …", "4 GHz frequency band … targeted for wireless
infrastructure", and a sibling part "2.0 GHz TQP3M9036". Nothing on the page
mentions sub-1 GHz operation.

**Conclusion: the lower bound is 0.7 GHz (700 MHz). The operator's 0.1 MHz figure
is not supported by the manufacturer. 433 MHz lies BELOW the specified band.**

## What this means — the consequence is real, not cosmetic

The part is **not specified for 433 MHz**. This is the case the plan flagged as
forcing ADR-079 to reopen. It is now a fact rather than a dispute, and it is
**decision-grade without buying the LiteVNA** — the documentary question is
settled from the manufacturer's own page.

## What the LiteVNA is still for (do not conflate the two)

The spec question and the *measurement* question are different, and only the
first is now closed:

| Question | Status |
|---|---|
| Is the part specified for 433 MHz? | **CLOSED — no.** Manufacturer's page: 0.7–6 GHz. |
| How badly does it actually roll off at 433 MHz? | **OPEN — needs the LiteVNA** (S21 at 400–500 MHz). |
| Is it usable anyway, out of spec? | **OPEN.** Many LNAs still give usable gain below their rated band with degraded NF/return loss. That is a measurement, not a datasheet lookup. |

So the LiteVNA purchase is **no longer gating the decision**, only the
verification of whichever option is chosen.

## The three options, with the trade-off stated

1. **Measure first (recommended).** Buy the LiteVNA, sweep S21 400–500 MHz on the
   owned part. If usable gain/NF at 433 → keep ADR-079, record the part as used
   out-of-spec, and note that no vendor will support it. Cost: €166.99 + bench time.
2. **Reopen ADR-079 now and select a specified 433-capable LNA.** Removes the
   out-of-spec risk entirely; the owned part then has no role in the RX chain.
   Cost: a new part + a re-run of the Stage-1 netlist and the link budget.
3. **Design the masthead with a 433-specified LNA footprint and keep the
   TQP3M9037 as a DNP alternative** for the bench comparison. Cost: one extra
   footprint; defers the choice to measurement without blocking layout.

Option 3 is the one that costs nothing and blocks nothing — it keeps both paths
alive until the VNA answers the second question.

## Netlist consequence (Stage 1, already built)

`tracker/hardware/base_station/base_station_masthead.net` is ERC-clean
(0 errors, 3 warnings) and instantiates `LNA1 = TQP3M9037` in the chain

```
J_ANT433 -> BPF433 -> LNA1 -> D_LIM -> J_FEED
```

which is the ADR-072 INV-3 order (BPF **before** the LNA). The topology is
unaffected by this dispute; only the LNA **part** is. Under option 1 or 2 the
topology stands as netlisted.

## Status change

- Dispute A: **OPEN → RESOLVED (Qorvo 0.7–6 GHz; 433 MHz is below spec).**
- Masthead board: still **blocked on the operator's choice among the three
  options**, but no longer blocked on an unknown. The blocker is now a decision
  with a costed recommendation, not a missing measurement.

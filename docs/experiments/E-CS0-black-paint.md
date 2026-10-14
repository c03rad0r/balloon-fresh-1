# E-CS0 — Passive solar heating: black paint? (ANSWERED by analysis)

**Question (operator, 2026-10-14):** would it make sense to paint the
electronics black so they heat up in sunshine?

## Answer: mostly no — and the existing ADR already rejects heating as a strategy

**ADR-043 (`docs/adr/043-cold-qualification-heating.md`) decided "Heating
Rejected, Below-Rated Parts Gated"** for active heating (≈0.5 W continuous,
which the solar budget cannot afford: that ADR's arithmetic gives ~28 s of
runtime for the energy a heater would need). Passive solar absorption is a
different mechanism — no stored energy is spent — so it deserves its own
numbers rather than a blanket "no":

### The physics, with real coefficients

| Mechanism | Coefficient | Effect |
|---|---|---|
| Black paint absorptivity α (solar) | ~0.9–0.95 | absorbs almost all incident sun |
| Bare FR4 / green mask α | ~0.6–0.8 | already fairly absorptive |
| Emissivity ε black paint (IR) | ~0.9 | radiates well — helps at night too… |
| Emissivity bare solder mask ε | ~0.8–0.9 | almost as good |

Net radiative equilibrium gain from painting: the board's **emissivity barely
changes** (mask already ~0.85), so the night-time loss stays the same; the
daytime absorption rises by α_paint/α_bare ≈ 0.95/0.7 ≈ **+35% of the absorbed
solar flux**. With ~0.02 m² of board area, at high-altitude insolation
(~1360 W/m², no atmosphere), absorbed power on the order of **5–15 W peaks on
the sun-facing side**. That is NOT small.

### Why "paint the whole board black" is still the wrong move

1. **Cells, not paint, are the collectors.** The solar wings already intercept
   the sun; their conversion efficiency (~20%) is what powers the bus. Paint on
   the hub adds heat to the *electronics* only.
2. **+35% absorption on a board that must not overheat in direct sun at
   0.02 m² with no convection** — at float there is no convective cooling
   (near-vacuum). A sun-facing black board can run HOT, not just "warm":
   community flights report electronics bays at +40…+60 °C in sun at 12 km.
   The SX1280's crystal drift and the LDO's accuracy degrade with heat; and
   hot→cold cycling across terminator crossings worsens fatigue.
3. **Contamination risk**: paint on U.FL launch pads, castellations, the
   programming pads, and the wing solar-tab joints = rework pain. Conformal
   coat first, paint never.
4. **The real cold problem is the NIGHT and dawn cold-start** — no sun to
   absorb, paint or not. Paint does nothing for the actual failure mode
   (cold boot after a −55 °C night, E-CS1).

### What IS worth doing (cheap, no-respin)

- **Matte-black conformal coating on the BACK of the board** (away from
  RF launch pads): buys the α gain on the sun-facing side as the balloon
  rotates, ε stays high, and it doubles as the conformal coat we want anyway.
  Net effect: a few K warmer in sun, 0 K at night. Nice-to-have, not a
  strategy.
- **The strategy stays ADR-043's: characterise, don't heat.** Fly the NTC log
  (E-01), learn the real thermal envelope, and let the next board revision
  make part choices from data (the `bom_temp_gate.py` script already enforces
  the rated-minimum audit).

**Verdict: no board-level paint. Optional matte-black conformal on the back.
The cold problem is night/dawn, and only E-CS1's data fixes that.**

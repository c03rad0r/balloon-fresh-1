# Wing cut-off and "turn-around" — what shedding a wing actually does

**STATUS: CONSULTANT ANALYSIS — NOT A DECISION RECORD.** No board, BOM, order or
flight procedure is authorised here. Every number is **CITED** to an in-repo source
or marked `TODO(unverified)`. Nothing is invented.

- **Date:** 2026-10-25 · **Branch:** `feat/foam-wing-3d`
- **Answers:** (a) does losing a wing leave the array survivable, and (b) is there
  yaw authority, and does shedding a wing help or hurt it?
- **Reads with:** ADR-129 D5 (four cut channels, restored), ADR-054 (array topology
  and the mandatory hub-side bypass), ADR-051 (cut ladder, corrected by ADR-054),
  `docs/analysis/wing-jettison.md`, `docs/analysis/wing-omnidirectional.md`.

---

## 0. The two answers, first

1. **A cut wing kills the array unless the hub-side bypass diode is populated.**
   ADR-054 §2.2 is explicit: *"Without it populated, a cutter-carrying flight is
   WORSE OFF THAN BASELINE: the first cut kills the array."* The socket lands go
   open, the string opens, **0.00 W**. With the diode populated, the cut bay is
   bypassed and the remaining string survives. **So survivability is not a property
   of the wing at all — it is a property of one hub-side part.**
2. **There is no yaw authority. Shedding a wing neither helps nor hurts it, because
   nothing controls yaw.** See §3.

---

## 1. Does losing a wing leave the array survivable?

**It depends on exactly one populated part, and the repo already decided it.**

ADR-054 §2.2: **one bypass diode per wing, on the HUB**, across the interface lands
`W<n>_SOLAR_P` ↔ `W<n>_SOLAR_N`. Populated, **not DNP**, on any cutter-carrying
flight. The reasoning it records is the whole answer:

- **A cut removes the wing and every diode soldered to it.** A per-cell or per-wing
  diode that lives on the wing **leaves with the wing** — so it cannot protect the
  cut it is there for.
- **Only a hub-side diode survives the cut.** It is *"the only protection a cut
  cannot jettison."*
- ADR-129 D5 restored **`U_CUT1..U_CUT4`** and, separately, **`D_BP1..D_BP4`**
  (hub-side bypass, 4× SMA footprints) — i.e. the channels **and** their protection
  are landed together.

**Verdict:** with `D_BP<n>` populated, cutting wing *n* costs **that wing's cells
only**; the remaining string continues. Without it, the first cut is a **100 % array
loss**. ADR-054 already made popularity mandatory for cutter flights; this analysis
confirms nothing about the *foam* wing changes that — the diode is hub-side and
survives the change of wing construction.

> **Note on the foam change specifically:** removing the wing PCB (ADR-130) removes
> the wing's own diode position, which ADR-117 consequence §2 already says is
> **unaffected** because `D_BP` is hub-side. The foam wing therefore does **not**
> weaken the cut story; if anything it removes a part that would have been jettisoned
> uselessly.

---

## 2. Is a cut worth it at all? — the repo's answer is no, for this flight

`docs/analysis/wing-jettison.md` §0 recommends **do not build it**:

- **No trigger gains anything.** Solar power *is* the science; cutting before burst
  or at apex is mission suicide. The only defensible trigger is **descent**, where
  the jettison buys **11 %** of a descent rate already ~0.45 m/s and removes **5.4 %**
  of the descent drag area.
- **Mass-negative.** ~0.5 g/channel (IRLML2502 + nichrome + nylon, `balloon-test-results.md`
  line 254) × 4 = **2.0 g carried all flight to shed ~3.2 g on descent**, plus **22 %
  of the 100 µW night budget in leakage**.

**But that study predates the operator's 2026-10-22 decision** (`ADR-129` D5, *"Yes
please include the nichrome cutoff"*). The channels are now **landed**. The honest
position: **the capability exists and is costed; whether to fly a cutter mission is
the operator's call, and the analysis above is the cost of exercising it.**

---

## 3. "Turn-around" and yaw authority

**The question contains a premise the vehicle does not satisfy: there is no yaw
authority, and no attitude control of any kind.**

`docs/analysis/wing-jettison.md` §1 (and `wing-omnidirectional.md`) state it:
*"The vehicle rotates slowly with no attitude control, so **rotation is not a sizing
case**."* The payload is a **passive, free-rotating** sphere-and-blades assembly. The
rotation numbers measured for sizing are:

```
1 rpm  -> 0.0003 g-f     6 rpm -> 0.012 g-f     30 rpm -> 0.31 g-f
```

Even at a fast 30 rpm the centrifugal load on a wing is **0.31 g-f**, ~10 % of the
1 g static case. So:

- **Yaw authority: none.** There is no actuator, no reaction wheel, no magnetorquer,
  no differential drag device. Nothing to size a control loop against.
- **Does shedding a wing help or hurt "turn-around"?** **Neither.** With no yaw
  authority, a wing cut removes a blade from a passive rotor. The only physical
  effects are: **mass down** (a few grams, good), **drag area down ~5.4 %** (from
  `wing-jettison.md` §7), and — if the cut is asymmetric (1 or 2 of 4 wings) — the
  **residual blade set becomes statically unbalanced**, which changes the free
  rotation's axis and rate. That is a **disturbance**, not a control input, and it is
  not characterised here. `TODO(unverified)`.

**If the operator means "does the payload self-orient / turn to face the sun":** the
answer is no — it rotates freely, and the array's energy is the **rotationally
averaged** figure (ADR-065's 2× double-sided argument is exactly this: front gets
`max(0, n·s)`, back gets `max(0, −n·s)`, sum `= |n·s|`). **That is why double-siding
helps and why a tilt is worth only ~+4.6 %/day** (`wing-omnidirectional.md` §0).

**What would change this answer:** a v10-era attitude system (none is in
`docs/adr/11x`–`12x` as of this writing), or a measured rotation/axis result after an
asymmetric cut.

---

## 4. What this analysis does NOT establish

- **No asymmetry characterisation.** The post-cut imbalance (§3) is named, not
  computed — it needs the as-built mass distribution.
- **No new cutter hardware.** ADR-129 D5 records the driver part, sense divider and
  latch topology as `TODO(unverified)` (OPEN-25/OPEN-28); this analysis adds nothing
  to that.
- **No flight recommendation beyond citing `wing-jettison.md`.** Whether to fly a
  cutter mission is the operator's.
- **No order, no BOM change, no flight procedure.**

---

*Analysis only. Nothing frozen, nothing ordered, no board touched.*

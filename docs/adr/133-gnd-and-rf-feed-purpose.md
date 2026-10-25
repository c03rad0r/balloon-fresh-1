# ADR-133 — What GND and RF_FEED are actually for, and what happens to them when the wing loses its Yagi

> Numbered **133** on 2026-10-25. Verified free with `scripts/adr_next_number.py --number 133`
> (exit 0) and across all refs.

- **Status:** **Proposed** — explanatory record; operator corrects pass 2.
- **Date:** 2026-10-25
- **Answers:** *"what are the GND and RF-Feed pins for? How is rf-feed related to the wing?"*
- **Reads with:** ADR-046 §2.1/§2.3/§2.4 (the tab), ADR-004 (the 4× Yagi 3D concept that
  created `RF_FEED`), ADR-009 (antenna strategy, SP4T), ADR-034/ADR-040 (v9 radios are all on
  the hub), ADR-132 (the interconnect board that carries these pins).

---

## 0. The short answers

- **`GND` is not a solar return.** It is the **system/ground-plane reference**. All solar
  current returns through `SOLAR_N` (the bottom of the 4-wing series string), **not** through
  `GND`. On v9 `GND` is the wing's mechanical/plane reference only.
- **`RF_FEED` is a leftover from the v1/v2 design where each wing carried a 2.4 GHz PCB Yagi.**
  On v9 it is **a copper land with no net** — an unconnected provision. It has **nothing to do
  with the solar function of the wing** and carries no current.

---

## 1. `GND` — what it is and what it is NOT

ADR-046 §2.3 states the rule plainly:

> *"There is **no per-wing solar ground return**. The single system `GND` return is the stack
> bottom (`W4.SOLAR_N`), which the hub ties to the ground plane. Each wing's `GND` pin is a
> *reference/plane* connection, not a solar return."*

The series stack:

```
W1.SOLAR_P  -> top of the array (+6.0 V)
W1.SOLAR_N == W2.SOLAR_P      (inter-wing link, hub side)
W2.SOLAR_N == W3.SOLAR_P
W3.SOLAR_N == W4.SOLAR_P
W4.SOLAR_N  -> system GND       <- THE ONLY solar return
```

**Why `GND` exists at all.** Historically it was the **ground plane of the wing's own 2.4 GHz
Yagi** — a coplanar-waveguide antenna needs a reference plane under and beside its feed. That is
the reason the pin is there and the reason it is called `GND` rather than something solar-ish.

**On v9 and on the foam wing it has no antenna to reference**, so it is reduced to a mechanical /
plane tie. **It is harmless and it costs one tab land; removing it would be a hub respin for no
gain** (ADR-131 D1 keeps the 4-pin row as the invariant).

> **A trap worth naming:** because the pin is labelled `GND`, it is tempting to use it as the
> solar return, or to tie `SOLAR_N` to it. **Do not.** Tying `SOLAR_N` to `GND` anywhere except
> at the stack bottom (`W4.SOLAR_N`) **short-circuits one or more wings** — it would bypass the
> series string. The two are different nets and must stay different.

---

## 2. `RF_FEED` — where it came from, and why it is dead copper on v9

### 2.1 The origin: 4 × Yagi 3D

**ADR-004** ("3D Yagi-Antennen-Struktur, 4 Wings + Hub") designed the vehicle as **4 identical
wing boards, each carrying a PCB Yagi**, pointing orthogonally, fed through a central hub via an
**SP4T RF switch** in a round-robin "lighthouse mode". In that design each wing genuinely needed
an **RF feed trace from its Yagi down the wing to the hub's switch**. **That is `RF_FEED`.**

### 2.2 Why it is unused today

**ADR-034 / ADR-040** moved **every v9 radio onto the hub**: TX 433 MHz on the F33-2G4, RX
2.4 GHz on a bare LoRa2021, both radio sites on the **back of the hub**. No v9 radio has a port
that reaches a wing. ADR-046 §2.4 records the consequence:

> *"on v9 the wing's pin 3 (`RF_FEED`) is a **copper land that is left electrically
> unconnected** (a provision). It carries no net on v9; the wing's RF_FEED net is a 1-pad net
> so there is no ratsnest and no DRC consequence."*

The wing's 2.4 GHz Yagi is **deferred to V2** and is **not etched** on the v9 wing, because with
no RF path it would be dead copper — and a 50 Ω coplanar waveguide would need the hub's SP4T,
which v9 does not carry.

### 2.3 So: how is `RF_FEED` related to the wing?

| Question | Answer |
|---|---|
| Does it carry solar power? | **No.** Zero current, ever. |
| Does the wing have an antenna? | **Not on v9.** The Yagi is a V2 provision. |
| Why keep the pin? | So a **V2 wing can be ordered with the same tab** — the tab is the one part that must not change, because the hub is routed against it. |
| What happens to it on the foam wing? | It becomes **an unconnected land on the interconnect board** (ADR-132). Copper, no net. |
| Could it be repurposed? | **Not without an ADR.** It is the only spare conductor in the wing interface. ADR-129 D5 already uses a `RF_FEED` conductor for **cut-sense** on the hub side, which is a hint that the pin has future value — but the wing side is not wired for that today. |

> **The one thing that would make `RF_FEED` live again:** a V2 wing with an etched Yagi and a
> hub that carries the SP4T. That is ADR-004's original design; v9 abandoned it (ADR-034/040)
> and nothing has reinstated it. `TODO(unverified)`: the V2 CPW geometry on 0.6 mm FR4 (ADR-046
> §2.4 records that no in-repo source derives the width).

---

## 3. What this means for the interconnect board (ADR-132)

The board carries all four tab lands, so it must carry `GND` and `RF_FEED` **as lands**:

- **`GND`** — land only; connect it to the board's copper if the board has a plane, but **never
  to `SOLAR_N`** except at the stack bottom on the hub.
- **`RF_FEED`** — land only; **no trace, no net** (a 1-pad net). Do not route it to anything.

Both are placeholders in a 4-land row whose geometry is fixed by the hub. **Neither adds a
component to the board.**

---

## 4. For future sessions

- **`GND` ≠ solar return.** The only solar return is `W4.SOLAR_N` at the stack bottom. Tying
  `SOLAR_N` to `GND` anywhere else shorts a wing out of the series string.
- **`RF_FEED` is dead copper on v9** — a V2 Yagi provision preserved only so the tab geometry
  never changes. It is not a signal you can use without a new ADR.
- **The tab is the invariant.** Both pins exist to keep the 4-land row identical to what the
  hub is already routed against.

---

*Proposed. Explanatory record only. No board, BOM or order change.*

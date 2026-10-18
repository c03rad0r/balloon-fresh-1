# DECISIONS — hub v9 unrouted nets (2026-10-18)

Standing authority per `AGENTS.md` § STANDING AUTHORITY. Consultant: **`gpt-6-astra`**, served id recorded
(not an alias). Every number below is from `pcbnew` on `tracker/hardware/hub_board_v9.kicad_pcb`
sha256 `e55a294628fd38a7…`, zone-refilled, or from `kicad-cli pcb drift --format json` on the same file.

---

## D1 — Do NOT move `U4`

**Decision:** `U4` stays exactly where it is.

**Evidence:**
- Body-clear placement search, every position on the 70 × 70 board at 1 mm steps with a 0.5 mm body margin:
  **only 3 positions exist** for a 6.15 × 6.15 mm part, and the best gives the two trapped pads **0.25 mm**
  of escape.
- The blockers are `U4`'s **own neighbouring escapes** — `/SX1280_MISO` (exits pad 16) walls in pad 17, and
  `/SX1280_DIO1` walls in pad 18. **They move with the part**, so relocation cannot free the pads.
- The originally proposed `dy = −2.0 mm` move **collides with `U1`** (`ESP32-S3-WROOM-1U`, bbox
  `y 1.49…21.68`; moved `U4` bbox starts at `y 21.68` — exact touch).
- Moving `U4` would disturb **12 of its 25 pads**, including `pad 22 /SX1280_RF` — the hand-matched
  `C0 0.8 pF + L1 3.0 nH` network.

**Alternatives rejected:** `+x` nudge (worse — drives pads into existing copper); `dy −2.0` (collides with
`U1`); any relocation (blocker moves with the part, RF at risk).

**What would change this:** an `U4` placement that frees the pads *and* leaves `pad 22`'s RF geometry intact.
None was found in the full-board search.

---

## D2 — Pin reassignment is NOT an option

**Decision:** rejected outright.

**Evidence (Astra, verbatim):** *"The SX1280's MOSI and SCK are **dedicated interface pins, not freely
assignable GPIOs**. Moving those nets to convenient U4 pads is not a routing solution; it changes the
circuit to an **invalid pinout**."*

**I offered this to the operator as a viable option. It was not.** Recorded so it is not re-proposed.

---

## D3 — Rip up `/SX1280_MISO` and `/SX1280_DIO1` escapes, re-route four nets together

**Decision:** yes, but it is **sufficient for `SCK` only**.

**Evidence** — post-rip-up ray sweep at 10° steps, `MISO` (net 34) and `DIO1` (net 37) F.Cu tracks removed:

| pad | best escape after rip-up | verdict |
|---|---|---|
| `U4.18` (SCK) | **0° and 350° open ≥ 6 mm** | ✅ fully escapable |
| `U4.17` (MOSI) | best 1.00 mm, then `+3V3`; 140° → 1.00 mm then `U4.0` (own thermal pad) | ❌ still blocked |

Astra predicted exactly this failure mode before it was measured: *"If a post-removal check truly shows no
legal exit at the permitted track width, (a) alone is insufficient."* **It was right, and the measurement
confirms it.**

**Note:** the rip-up is a routing change on two digital nets. **`pad 22 /SX1280_RF` is untouched.**

---

## D4 — `+3V3` shove by 0.2 mm, then a conventional via, then route `MOSI` on B.Cu

**Decision:** this is the fix for `MOSI`.

**Evidence:**

| `+3V3` shift in `y` | outcome |
|---|---|
| `+0.0 mm` | no legal via anywhere in the window |
| `+0.1 mm` | no legal via anywhere in the window |
| **`+0.2 mm`** | **via fits at offset 0.367 mm, clearance 0.207 mm** ✅ |
| `+0.3 / +0.4 / +0.5 mm` | same result (0.367 mm / 0.207 mm) — no further benefit |

The shove applies to the two short `+3V3` segments near `U4.17`:
`(55.650, 26.250) → (55.150, 26.250)` and `(56.700, 25.200) → (55.650, 26.250)`, both `0.20 mm` wide on
`F.Cu`.

**Via geometry, per Astra's derivation and verified against the board:** `0.60 mm` diameter, `0.30 mm` drill,
centre **0.367 mm outward from the pad's outer edge on the MOSI centreline**. Astra's interval bound was
`0.357 … 0.500`; the adjacent-pad corner tightens the *usable* bound to `0.367`. **This is NOT via-in-pad** —
the annulus does not overlap the component pad.

**Astra's ranking this satisfies:** option #1 *"reposition the ordinary via within the legal interval"* and
option #2 *"locally move/shove the obstructing non-RF track, such as +3V3 — usually the smallest layout change
if the normal via is genuinely blocked."*

**What would change this:** if a full four-layer DRC check shows the via obstructed on `In1.Cu` / `In2.Cu` /
`B.Cu` — the arithmetic proves the **F.Cu local geometry** only. Astra stated this limit explicitly:
*"a conventional through-via must clear foreign copper on all four layers… it does not certify unreported
geometry on the other layers."*

---

## D5 — The MOSI via sitting on `U1.8`'s centre is an unfinished routing feature, not a thermal via

**Decision:** incorporate it into the completed route if its net/layers are right; otherwise delete it.

**Evidence:** it is on net `/SX1280_MOSI`, exactly at `U1.8`'s centre `(49.950, 11.840)`, with **zero track
segments** on that net. Astra: *"On a MOSI pad, there is no basis for calling it a deliberate
ground-stitching or thermal via. A via centred on a pad can be electrically connected directly through copper
overlap; it does not need a track segment between itself and that pad."* So its presence is harmless
electrically — but it is a **routing stub**, not a design feature.

**⚠️ Fabrication flag (Astra, and this is a real one):** *"The existing via-in-pad on U1.8 is the immediate
flag. An ordinary open via can wick solder away from the joint, causing solder starvation or voiding. If
retained in the solderable pad, specify the appropriate filling, planarization and copper-capping process
with the fabricator and assembler — do not assume ordinary tenting is equivalent."*

**This is now a JLCPCB question, not a layout decision.** It goes in the query.

---

## D6 — SCK's via at `(60.400, 20.300)` is 0.47 mm off `U1.22` — connect it or remove it

**Decision:** connect it with a legal short track if it serves the route; else delete.

**Evidence:** `U1.22` is at `(60.605, 20.710)`; the via is at `(60.400, 20.300)` — **0.47 mm away**.
Astra: *"Its proximity alone does not establish connectivity."* DRC confirms it is unconnected to the pad.

---

## D7 — The two remaining GND unconnected items are zone-to-zone breaks, and must be fixed too

**Decision:** repair both, **away from the RF geometry**.

**Evidence:** DRC's 4 unconnected items are the 2 nets **plus**:

```
Zone 'GND_PLANE_F.Cu'  [GND] F.Cu   <->  Zone 'GND_PLANE_In1.Cu' [GND] In1.Cu
Zone 'GND_PLANE_F.Cu'  [GND] F.Cu   <->  Zone 'GND_PLANE_F.Cu'   [GND] F.Cu
```

**A board with the two signal nets routed would still be `NOT ORDERABLE` because the ground plane is split.**
This was not in the original RALPH queue and is a **new finding**.

---

## Standing risk flags for the fabricator

1. **Via-in-pad at `U1.8`** — needs filled/capped specification, or relocate the via outside the pad.
2. **0.6 mm 4-layer stackup** — through-via and drill capability unverified; the 50 Ω width varies 3.7× with
   the L1–L2 dielectric (`0.0752 → 0.099 mm` at 30 Ω; `0.1300 → 0.202 mm` at 50 Ω; `0.2100 → 0.364 mm` at
   69 Ω).
3. **`0.200 mm` inter-pad gap equals the `0.200 mm` clearance rule at `U4`** — no trace can pass between
   pads. Any future change that needs one must relax a rule or change the land pattern.

---

## What was NOT decided, and why

- **Whether to place the order.** Not authorised, and not satisfied: 4 unconnected items remain.
- **The stackup.** Still unknown; it is a JLCPCB question, not a design preference.
- **The two out-of-scope drawing defects** (slot-face construction, mating-fit spec) — both under the
  JLCPCB query (PR #215 §2A), and inventing numbers for them would be worse than stating them unresolved.

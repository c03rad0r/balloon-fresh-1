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

## D4 — A 0.50/0.25 mm via at 0.285 mm offset. **Do NOT move `+3V3`.**

**Decision (REVISED — version 1 was worse and is kept below rather than deleted):** place a
**0.50 mm diameter / 0.25 mm drill** via on the MOSI centreline, **0.285 mm outward from the pad's outer
edge**, then route MOSI on `B.Cu`. **`+3V3` is not touched.**

**Evidence — the via fits under the board's own rules, with no waiver:**

| via dia/drill | result in the outward window |
|---|---|
| `0.60/0.30` | does **not** fit |
| `0.50/0.25` | **FITS at offset 0.285 mm — worst gap 0.201 mm vs the 0.200 mm rule** ✅ |
| `0.45/0.20` | fits at 0.305 mm with 0.237 mm — but **violates `m_ViasMinSize`** |
| `0.40/0.20`, `0.35/0.15`, `0.30/0.15` | fit, all violate the minimum via size |

**Board design rules read directly (`GetDesignSettings()`):**

```
m_ViasMinSize      = 0.500 mm
m_MinThroughDrill  = 0.200 mm
```

**All four layers verified at `(55.855, 25.250)`** with `MISO`/`DIO1` ripped up:

```
F.Cu     +0.2371 mm to +3V3 track
In1.Cu   +0.4250 mm to /SX1280_VDD
In2.Cu   +0.4493 mm to /W3_SOLAR_N
B.Cu     +0.7549 mm to /SX1280_VDD via
```

**This is Astra's ranked option #1** — *"Local fine-feature escape at U4, using a qualified fabrication
rule… Implement it through a deliberate local/net-specific rule — not by waiving a DRC error."* The via
complies with `m_ViasMinSize` exactly, so **no rule change and no DRC waiver is needed.**

**⚠️ VERSION 1 OF THIS DECISION WAS WORSE.** It called for shoving `+3V3` by 0.2 mm so a `0.60/0.30` via
would fit. That works (0.207 mm clearance) but **moves a power track** when a compliant via size achieves
the same result. Astra ranked the fine-feature escape *above* moving a neighbour track, and it was right.
**I had not checked whether a smaller via already complied with the board's minimum via size** — it does,
and that is the whole answer. The mistake was assuming the existing 0.60 mm via was the only size to reason
about.

**What would change this:** if the fabricator's real minimum via exceeds `0.50 mm`, or if a `0.125 mm`
annular ring is below their capability. **That is a JLCPCB question and is now in the query.**

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

## D8 — Keep components single-sided. Do NOT move parts to `B.Cu`.

**Decision:** the board stays single-side assembled. All 59 footprints remain on `F.Cu`.

**This was asked directly** — *"would it help if we put components on both sides? It's a double-sided
4 layer board right? Maybe that would allow components to be packed more densely with less pressure on
surface area."*

**Evidence — the board is not area-constrained, and that is the whole point:**

```
all 59 footprints on F.Cu; zero on B.Cu          → 4-layer board, currently single-side populated
board area                5026 mm²  (70.2 × 71.7)
4-layer copper area      20105 mm²
routed copper length      3192 mm  (F 733 / In1 787 / In2 1209 / B 463)
copper length / Cu area    15.9%     → at 0.20 mm width, only 3.2% of copper area
footprint area total      2818 mm²  = 56% of one side
rule areas / keepouts        0
B.Cu track endpoints in the board's central 15 × 15 mm: 8   → bottom centre is nearly empty
```

**Astra's distinction, which is the reason to say no:** *"You have **global capacity** and lack **local
accessibility** at two U4 pads. Moving unrelated components underneath does not change that."*

**And the two premises I had to correct:**
- **Mass does not improve.** Astra: *"moving the same parts to the other face does not inherently add
  meaningful mass… it mostly redistributes mass."* The 57 g hub+wings target is unaffected either way.
- **Flipping `U4` itself does not help.** Astra: *"a pad escape forbidden by intrinsic pad geometry
  remains forbidden after flipping."* Pitch and inter-pad clearance do not change when the part is turned
  over. It would also force the 2.4 GHz path through a layer transition, and *"at values of 0.8 pF and
  3.0 nH, layout parasitics are significant enough that the existing match should not be assumed to
  survive unchanged."*

**Real cost if it were done anyway:** a second paste-print, placement and reflow pass; heavy-module
sequencing review; and `J_W1…J_W4` bottom-side solder access — their 4 `B.Cu` pads each mean *"edge
placement helps, but does not remove clearance requirements."*

**What would change this:** a genuine packaging constraint — a smaller outline, a shorter critical
interconnect, or an enclosure limit. **None is established.** Double-sided assembly is a valid future
option if the board must shrink; it is not a fix for two pads behind their own neighbours.

**Recorded as a real option the operator raised, and declined on measurement — not dismissed.**

## D9 — Do NOT shrink the outline. It is interface-constrained, not area-constrained.

**Decision:** the 70.15 × 71.65 mm outline stays. **No rectangular shrink.** If mass must come off the
board later, the option is **substrate cutouts inside the existing envelope**, and only after the mass
budget is corrected (see D10).

**This was asked directly** — *"shrinking the board would be great because it saves cost and makes the board
lighter. Please do this if it's low-hanging fruit and if it makes it easier to route."*

**Evidence — the parts already span the outline:**

```
bounding box of ALL 59 footprints:   69.96 × 74.95 mm
board outline:                       70.15 × 71.65 mm
slack:                               0.19 mm in x,   -3.30 mm in y
```

**Negative slack in `y`**: two wing connectors overhang the outline by 1.65 mm each — they are edge tabs, by
design. The six edge-locked parts pin all four sides:

```
J_W1 hugs LEFT    J_W2 hugs TOP (overhangs 1.65)    ANT1 hugs LEFT  (0.10 mm gap)
J_W3 hugs RIGHT   J_W4 hugs BOTTOM (overhangs 1.65) ANT2 hugs TOP   (0.95 mm gap)
```

**Astra's framing, which is the whole argument:** *"this board is **interface-constrained, not
routing-density-constrained**… low copper utilisation does not mean the outside dimensions are freely
reducible."*

**On cost, Astra refused to invent a number and that is correct:** *"the area saving is real; a material
reduction in the final fabrication bill is not guaranteed… at small prototype quantities, minimum-order and
setup charges and the four-layer process premium often dominate… Without those quotes, a dollar saving or a
firm claim that setup dominates would be invented."* **Action: compare otherwise-identical quotes at the
real quantity. Do not redesign mechanics on an assumed saving.**

**On routing, the premise is backwards:** *"Harder, or at best no better. It does not address the actual
blocker… MOSI/SCK are blocked by local escape geometry at the SX1280's 0.5 mm-pitch QFN pads. Reducing the
outline does not create more room between those pads."*

**What a shrink would cost:** a mechanical redesign of **four wing interfaces** (the balloon's structural
attachments at 90°) plus **two antenna placements**, for a substrate saving of `1.58 g` at 60 × 60 or
`2.80 g` at 50 × 50 — **2.8 % / 4.9 % of a 57 g payload.**

**What would change this:** a packaging requirement that the balloon's wing span or hub envelope must
shrink. Then the wing interfaces dominate and the board follows.

---

## D10 — 🔴 The mass budget's PCB figure is WRONG by 3.6×, and it has been driving design decisions

**Decision:** `docs/analysis/ALTITUDE-AND-MASS-REQUIREMENTS.md` line 15 is defective and must be corrected.
**The board is 5.58 g, not 20.2 g.**

**Evidence — same formula the budget itself cites (FR4 at 1.85 g/cm³):**

```
board area 50.26 cm²
@ 0.6 mm (the board file says (thickness 0.6)):  5.58 g
@ 0.8 mm (what the budget claims):               7.44 g
```

**To reach 20.2 g of FR4 at 0.8 mm you would need 136 cm² = 117 × 117 mm.** The board is 70 × 72. **The
budget's own row reads "PCB 20.2 @0.8 mm" and cites "board file + datasheet parts" as its source — but the
board file says 0.6 mm, and no reading of the board file yields 20.2 g.** It appears to have been derived
against an outline roughly 2.7× larger in area.

**Why this matters more than the routing work:** the row feeds `Hub v9 populated = 25.5 g`, which feeds the
`≈ 57 g` payload, which feeds envelope choice (**36–40 in latex**), which feeds the **≥ 13.5 km** altitude
target. **A 3.6× error in one term of a 4-term sum propagates into the envelope decision.** Every mass-based
design argument in this session inherited it — including "is the board worth shrinking": the honest answer is
that **the board is ~10 % of payload, not ~45 %**, so shrinking it was never the lever.

**Not corrected in place yet:** the corrected board figure must be paired with a re-check of the *parts*
figure in the same row (5.3 g of components is plausible but unverified), or the row is only half-fixed.
**That is the next task, and it must be done as one measurement, not two edits.**

## D11 — D7 (the GND breaks): measured. A stitching via does NOT fix it; the refuted hypothesis is recorded.

**Decision:** D7 needs a **zone/pour-rule change**, not a stitching via. The stitching attempt is
**refuted and withdrawn**, and the tooling that produced it is kept with its finding recorded.

### What the GND pour actually looks like (measured, `pcbnew`, board `/tmp/hub_refilled.kicad_pcb`)

```
GND_PLANE_F.Cu    6 filled islands
GND_PLANE_In1.Cu  2 filled islands
GND_PLANE_B.Cu    1 filled island
```

**F.Cu island areas (mm²):**

```
island 5: 3543.334   <- THE MAIN PLANE (98.7% of copper area)
island 0:    8.615   <- orphan, centroid (53.70, 31.23)
island 1:    1.428   <- orphan, centroid (53.35, 29.84)
island 2:   15.734   <- orphan, centroid (51.07, 26.64)   the U4 escape zone
island 3:    0.278   <- sliver, centroid (55.21, 27.26)
island 4:    0.445   <- sliver, centroid (25.77,  2.89)
```

**Orphans total 26.5 mm² = 0.74 % of the plane.** All five sit around `U4`/`U1` — the dense copper
where the routing work happened.

### The refuted hypothesis

**I hypothesised:** place a stitching via inside each orphan to tie it to `In1.Cu`, and DRC's
`F.Cu ↔ F.Cu` unconnected item would clear.

**Measured outcome — it does nothing:**

```
BEFORE:  F.Cu GND: 6 islands, areas=[3543.334, 15.734, 8.615, 1.428, 0.445, 0.278]
AFTER:   F.Cu GND: 6 islands, areas=[3543.334, 15.734, 8.615, 1.428, 0.445, 0.278]
DRC:     unconnected items 4 -> 4   (unchanged)
```

**Why:** a stitching via is a **vertical** connection. It does not merge two disjoint **same-layer**
outlines. The DRC `F.Cu ↔ F.Cu` item is about same-layer continuity, so a via cannot address it.

### And a second wrong assumption, also measured

I then hypothesised the orphans were **stale fill** (RALPH rule #1) because
`GetIslandRemovalMode = 0` = `ISLAND_REMOVAL_MODE_ALWAYS`.

**Refilling changes nothing:**

```
after refill: 6 islands, areas=[3543.334, 15.734, 8.615, 1.428, 0.445, 0.278]
```

**Why they survive a refill:** island removal drops islands with **no connection to the net anywhere in
the stack**. These five are each tied down to `In1.Cu`, so KiCad correctly keeps them. **The fill is not
stale.** Rule #1 was applied and cleared the fill as a suspect.

### Where that leaves D7

**Two candidate fixes, neither yet attempted:**

1. **Widen the pour's local clearance** so the fragments merge into the main plane. Costs copper
   clearance margin in the densest area of the board — needs a fab question if it crosses 0.20 mm.
2. **Add a short GND F.Cu track** across each fragment boundary, merging outlines on the same layer.
   This is what the vertical via could not do. Must be checked against the 0.20 mm rule and must not
   create a `tracks_crossing`.

**Option 2 is the direct fit for the DRC item and is the next step.** It is cheap: 4 fragments above
`0.20 mm²`, total copper 26 cm²… no — total **26.5 mm²**, i.e. a few short tracks.

### Tooling

`tracker/hardware/stitch_gnd_islands.py` is kept. Its **measurement** half (island enumeration, areas,
per-island legal-via search, and the two-via `0.800 mm` centre-to-centre check) is correct and reusable.
Its **remedy** half (place a via) is the refuted part and is marked as such in the header. It also
reports island 2/3/4 as `BLOCKED — no legal via site`, which was true and is now moot.

**Known-good via sites it found, if a vertical tie is ever wanted for return current:**
`island2 (51.501, 26.344)` clearance `0.232` · `island0 (53.339, 30.012)` clearance `0.288` ·
`island1 (53.478, 29.943)` clearance `0.212`. **But those first two are `0.155 mm` apart — ILLEGAL,
need `0.800 mm`. That is the exact trap that broke routing runs 4-7, and it was caught only because the
script checks new vias against previously placed ones.**

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

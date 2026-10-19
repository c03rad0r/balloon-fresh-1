# JLCPCB — DRAFT QUERY (send as a support message / web form)

**Status: DRAFT. Nothing has been sent. No order has been placed or authorised.**

To paste into JLCPCB's support chat or the "Engineering question" field of a quote.

---

**Subject: Fabrication query — 0.6 mm 4-layer board, edge-launched connector pads, controlled impedance**

Hello,

We are preparing a small-batch prototype order and have three questions we would like answered before we
submit, so we do not design something you cannot build. We would rather ask now than receive
non-conforming boards.

### 1. 0.6 mm 4-layer stackup and controlled impedance

The board is **0.6 mm thick, 4 copper layers**, ~70 × 72 mm, 1 oz outer copper. The 0.6 mm thickness is
a deliberate weight constraint (this is a high-altitude balloon payload), so we do not want to change it.

1.1 What is the standard build for 0.6 mm / 4-layer, specifically the **prepreg thickness and Dk between
L1 and L2**?

1.2 Is 0.6 mm a **standard** 4-layer thickness for you, or a special build? If special, what is the
lead time and any surcharge?

1.3 Do you offer **controlled impedance**, and to what tolerance (e.g. ±10%)?

1.4 **Using your own impedance calculator**, what trace width gives **50 ohm single-ended microstrip on
F.Cu** over that L1–L2 dielectric? Our minimum trace width is 0.20 mm.

1.5 What are your minimum **trace width and spacing** for this build? We currently assume 0.20 mm for
both.

1.6 Is **0.20 mm** reliably manufacturable on 0.6 mm 4-layer, in particular for an
impedance-controlled trace?

### 2. Edge-launched connector pads at the board edge — the main question

Four connectors (`J_W1`–`J_W4`) have their pads **deliberately flush with the routed board edge**, so
that a mating tab slides in and contacts them. This is a card-edge style interface, not a mistake.

Geometry of each connector:
- 4 pads per connector, **4.0 mm × 1.2 mm** each, **1.8 mm pitch** (0.6 mm between pad edges)
- SMD pads, no drill
- pads present on **both outer layers** (F.Cu and B.Cu) at the same coordinates
- copper reaches the board outline at **0.00 mm** — i.e. **copper terminates at the routed edge**
- the outline at these locations is a **routed edge**, and the pads are not separate fingers
- 4 connectors total, at three different board edges

Please confirm:

2.1 Can you **rout the board edge through these pads** so the copper is exposed at the edge? Does this
require a **special process**, or is it a standard routed edge?

2.2 Does this imply **edge plating or castellation**? We do **not** want either — we want exposed copper
on the pad, exposed at the board edge, with the edge simply being the finished cut. Please tell us which
of these we would actually get, and how we must specify it (i.e. what to draw/say on the fabrication
notes) to get plain exposed copper and **not** castellations.

2.3 What is the **positional tolerance** of the routed edge relative to the copper?

2.4 Will there be **burrs or copper peeling** at the edge? If so, is there a recommended finishing or
process note to reduce it?

2.5 Can you keep **panel tabs clear of these edges**? They are mating surfaces and a tab there would
ruin the contact.

2.6 For the solder mask and surface finish at the edge: please recommend what to specify so the pads
stay solderable after assembly.

### 2A. Copper on the INTERNAL FACES of a routed slot -- separate from 2.1/2.2

Questions 2.1-2.6 concern copper that terminates at the **board edge**. This is a different geometry and
we need it answered separately.

Per **ADR-048**, the hub carries a **routed slot 0.9 mm wide x 6.0 mm deep** in each of four board edges,
and the wing tab (0.6 mm) slides into it. The four electrical lands are intended to sit on the slot's
**opposing internal faces** -- i.e. the *walls of the cut*, not the board's outer edge.

2A.1 **How would copper be present on the internal faces of a routed slot at all?** Ordinary F.Cu/B.Cu is
     on the board's outer surfaces. A routed cut exposes the *substrate* on its walls, not copper. Please
     describe what process (if any) produces conductive surfaces on those internal faces, or state that it
     is not achievable by routing alone.

2A.2 If it **is** achievable, what must we specify on the fabrication drawing, and what is the resulting
     surface (bare copper? plated? which finish, and does it differ from the outer-surface finish)?

2A.3 If it is **not** achievable, what is the alternative you would recommend for a 0.6 mm tab that must
     make four connections inside a 0.9 x 6.0 mm slot -- and what would it cost to add?

2A.4 What is the **positional tolerance** of the slot's internal faces relative to the intended land
     positions, and the tolerance of the slot **width** (nominal 0.9 mm)?

2A.5 The slot is a **routed internal cut-out**, not an edge rout. Does that change the minimum slot width,
     the achievable depth-to-width ratio, or the tooling?

**We are not asking you to approve a design.** The slot-face land construction is currently recorded as
**UNVERIFIED** in our own drawing (`docs/fab/jlc-query/edge-launch-cross-section.svg`, row "Slot-face land
construction"). These questions exist to replace that assumption with your answer, or to learn that the
geometry needs revising -- which would be an ADR-046/048 change on our side.

### 3. Thin-board handling

3.1 For a **0.6 mm** board, is there anything you need from us on panelisation or handling, and any
minimum panel size?

3.2 With JLCPCB **assembly**, are there special handling or minimum quantity rules for a 0.6 mm board?

### 4. Via inside an SMD pad (solder-wicking risk)

Our design contains **one via located inside an SMD pad** — via centre to pad centre is **0.0000 mm**
(the via is drilled exactly at the pad centre; reference `U1.8`, net `/SX1280_MOSI` on an
ESP32-S3-WROOM module footprint). The board is hand-assembled (no JLC assembly planned for this pad).

4.1 Is an **open (un-filled, un-tented) via inside an SMD pad** within your standard capability, or does
it need a special note?

4.2 If it is buildable, what is the **solder-wicking risk** during hand soldering, and would you
recommend **via filling / capping** for this single via? What does that cost at prototype quantity?

4.3 If you recommend filling, please confirm the fill is **non-conductive** (epoxy capped and plated
over, or capped only), and whether the capped surface remains solderable.

### 4A. Via-in-pad in a 0.50 mm-pitch QFN GND pad — the blocking feasibility question

**This is the question that decides whether our current layout can be released at all.** It is not the
same feature as 4.x above: the `U1.8` via is in a **large module pad** and is **not** evidence that the
QFN case below is feasible.

**The feature we need:** a **ground via-in-pad inside `U4.13`**, a GND pin of the SX1280 2.4 GHz radio,
which is a **QFN24 at 0.50 mm pitch**. The pad is **0.80 mm × 0.30 mm**, on a **0.6 mm, 4-layer** board.
Adjacent pads (`U4.12` above, `U4.14` below) are at 0.500 mm pitch, so their pad edges leave a
**0.200 mm** gap, and our clearance rule is also 0.200 mm.

**Our own geometry calculation** (measured from the board, verified two independent ways):

| via copper Ø | clearance to adjacent pad | annular ring with 0.20 mm drill | meets our 0.20 mm rule? |
|---|---|---|---|
| 0.60 mm | 0.050 mm | 0.200 mm | **no** |
| 0.50 mm | 0.100 mm | 0.150 mm | **no** |
| 0.40 mm | 0.150 mm | 0.100 mm | **no** |
| 0.35 mm | 0.175 mm | 0.075 mm | **no** |
| **0.30 mm** | **0.200 mm** | **0.050 mm** | **yes, but ring is tiny** |
| 0.25 mm | 0.225 mm | 0.025 mm | yes |

So a compliant centred via here would be **≤ 0.30 mm copper diameter with a ≈ 0.050 mm annular ring** —
well below the **0.50 mm minimum via** our board's design rules currently specify, and far below the
0.125 mm ring of the 0.50/0.25 mm via asked about in question 5.

We are asking **what construction you can actually support**, not for permission to ignore a rule.

4A.1 On a **0.6 mm, 4-layer** board, can you manufacture a **ground via-in-pad in a 0.80 × 0.30 mm QFN
     pad at 0.50 mm pitch**, retaining **0.20 mm copper clearance** to the adjacent pads (top copper land
     no larger than **0.30 mm**)? Please specify an acceptable **through-via or microvia** construction,
     including: finished hole / drill definition, copper land diameters **on every relevant layer**
     (including internal lands), **minimum annular ring**, and any **stackup or layer-span restrictions**.

4A.2 What **filling, planarization and capping** treatment do you require or recommend for this pad?
     Please confirm the resulting **solderable pad surface**, and any **solder-mask or stencil**
     requirements. If assembly is handled by a third party, state what the assembler must approve.

4A.3 Is that construction available at **0.6 mm board thickness** through your **normal ordering
     process**? What **process tier, cost and lead-time impact** applies, and what explicit **CAD / DFM
     rules** should we enter? If it is **not** available, please state the **limiting requirement** so we
     can revise accordingly.

4A.4 If 4A.1 is not achievable, what is the **smallest via (copper Ø / drill) you would recommend we
     redesign to** for a GND escape from a 0.50 mm-pitch QFN pad in this position, keeping 0.20 mm
     clearance?

### 5. Minimum via size — 0.50 mm / 0.25 mm with 0.125 mm annular ring

The routing at a fine-pitch QFN requires one via at **0.50 mm finished diameter / 0.25 mm drilled**,
which gives a **0.125 mm annular ring**.

5.1 Is **0.50 / 0.25 mm** within your standard capability at no surcharge, or does it fall into an
advanced-drilling tier? Our board design rules record `m_ViasMinSize = 0.500 mm` and
`m_MinThroughDrill = 0.200 mm`, so we need to know where the real floor is.

5.2 If 0.50/0.25 is **not** standard, what is the smallest standard via (diameter/drill) we should
design to?

5.3 Is a **0.125 mm annular ring** acceptable, or do you require a larger ring on any layer of a
0.6 mm 4-layer build?

### 6. ENIG and copper newly exposed by routing

6.1 If we specify **ENIG**, is the finish applied to the **copper faces only** as drawn, or does the
process also plate the **routed edges / slot walls** where copper terminates at the cut?

6.2 For the edge-launch pads (question 2.1) whose copper **terminates at the routed edge**: after
routing, the copper at the cut face is **newly exposed bare copper**. What surface will it actually
have — will ENIG extend onto it, or does it remain bare?

6.3 If it remains bare, is that a **corrosion or contact-resistance concern** for a mating surface
that will see insertion cycles, and what would you recommend we specify instead?

---

**What we will supply with the order:** the KiCad project, gerbers (4 copper layers, mask, silkscreen,
outline, drill), a **cross-section drawing of the edge-launch connection** showing the pad, the routed
edge, the mating tab and the tolerances, and a note listing the four connector locations as
**intentional edge features**.

**What we are asking for in return:** written answers to **2.1 and 2.2** (the edge-located copper: is it
buildable as specified, and is it plain exposed copper or something else) and to **2A.1 and 2A.3** (how, if
at all, copper exists on the internal faces of a routed slot - and if it does not, what you would recommend
instead and what that would cost), plus the stackup numbers from 1.1, and answers to **4.1–4.3**
(via-in-pad), **5.1–5.3** (0.50/0.25 mm via and its 0.125 mm annular ring), and **6.1–6.3** (ENIG on
copper newly exposed by routing).

**4A is the single blocking question for release.** It decides whether our current layout can be
manufactured at all: a compliant via-in-pad in that QFN pad needs a copper diameter <= 0.300 mm with a
~0.050 mm annular ring, well below our 0.50 mm via minimum. Your answer decides between (i) a qualified
small via-in-pad, and (ii) us revising U4's local escape geometry. **2.1/2.2 and 2A are the blocking
questions for the wing interface.** If the edge interface cannot be built as drawn, or a routed
slot cannot carry the lands on its internal faces, the wing-tab design needs revising and that is an
ADR-046/048 change on our side. **4.x, 5.x and 6.x are blocking for the two unrouted nets and for the
mating surfaces** — 5.x decides whether the 0.50 mm via at the SX1280 escape is buildable (if not, the
fallback is a 0.2 mm shove of a +3V3 track, already designed and measured); 4.x decides whether the
existing U1.8 via must be filled; 6.x decides what the mating tabs will actually contact. **1.x is
deferrable** to a follow-up revision.

Thank you.

---

## Internal notes (do not send)

- The item this closes: Astra gap-analysis H5 / its section 2 — *"their fabrication disposition remains
  necessary... submit an annotated drawing and cross-section."*
- Order of importance: **2.1 and 2.2 are the blocking questions.** If JLCPCB cannot build the edge
  interface as drawn, the wing tab design needs revising and that is an ADR-046/048 change.
- **1.x is deferrable.** For this first revision we can order as a prototype at the 0.20 mm width and
  document the unverified impedance, per the operator decision of 2026-10-16. The 1.x answers feed a
  follow-up revision, and per Astra: *"neither '0.20 mm is wrong' nor '0.20 mm is 50 ohm' is justified
  without the stackup."*
- Full supporting measurements: `docs/fab/EDGE-EXEMPTION-MECHANISM.md` and
  `docs/fab/FAB-QUESTIONS-FOLLOWUP-REVISION.md`.
- Sections **4, 5, 6 added 2026-10-18** from the routing/escape work: the U1.8 via sits **exactly on the
  pad centre** (measured 0.0000 mm) — a solder-wicking risk that became visible only when the MOSI escape
  was analysed; the **0.50/0.25 mm via is the board's own `m_ViasMinSize`** and is the difference between
  routing MOSI legally and shoving a +3V3 power track (D4, `docs/fab/DECISIONS-UNROUTED-NETS.md`); ENIG
  on routed-edge copper was flagged by Astra as *"ENIG on pad faces doesn't establish a finish on copper
  newly exposed by routing."*
- The five items the operator confirmed on 2026-10-18 as the exact question list are **2A, mating fit
  (2A.4), 5.x, 6.x, 4.x** — in that priority order.
- **4A added 2026-10-18** after the visual/spatial consultant (`gpt-6-astra`) ruled: *"Your instinct is
  right: stop local routing attempts and ask the fabricator a targeted feasibility question… Set a clear
  fallback now: if a compliant, assembly-safe small via-in-pad solution is unavailable or unattractive,
  revise U4's local placement/escape. Do not release with U4.13 open."* Its clearance formula
  `c = 0.500 - 0.150 - D/2` was independently verified against measured pad edges and agrees to 4 dp at
  every diameter.
- **What was tried and failed before asking** (all measured, in `docs/fab/D12-VIALESS-GND-FRAGMENTS.md`):
  a plain F.Cu escape (10 um exhaustive sweep, zero viable sites), moving `/SX1280_DCC_SW` to an inner
  layer (no legal via at either end of the vertical within 0.3 mm), and moving `/SX1280_VDD` to an inner
  layer (-0.400 on In1, In2 and B.Cu). The question is not "please waive your rule" but "what can you
  actually build".
- **No order has been placed.** Nothing here authorises one.

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

---

**What we will supply with the order:** the KiCad project, gerbers (4 copper layers, mask, silkscreen,
outline, drill), a **cross-section drawing of the edge-launch connection** showing the pad, the routed
edge, the mating tab and the tolerances, and a note listing the four connector locations as
**intentional edge features**.

**What we are asking for in return:** written confirmation on 2.1 and 2.2 (that the edge-located copper
is buildable as specified, and whether it is plain exposed copper or something else), and the stackup
numbers from 1.1.

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
- **No order has been placed.** Nothing here authorises one.

# System diagram — TERMINAL VERDICT

**Status: CLOSED.** This record concludes the visual review of `docs/boards/system-diagram.png`.

`docs/fab/reviews/system-diagram-r3.md` found four defects and recorded **no terminal verdict**, and its
findings were never acted on. That artefact shipped looking reviewed. This record closes it: the defects
are fixed **in the generator**, the drawing is regenerated, the regenerated render was re-reviewed to
**CLEAN** by the visual consultant, and every claim below is a measurement with a command that
reproduces it.

This is the third instance of the same failure in this repo (the board-gallery framing defect, the
disproven U1.41 claim corrected in one of five documents, and this diagram). The shared cause is the
same: **a finding that cannot fail anything will be ignored.** So each of r3's findings is now an
assertion in `scripts/check_system_diagram_geometry.py`, whose ability to fail is itself tested.

## What r3 found, and what each finding measured

r3's verdict was prose. Re-measured from the artefact r3 actually saw, two of the three were real and one
was a correct observation with a different cause than the one r3 diagnosed:

| # | r3's words | measured on the artefact r3 reviewed | status |
|---|---|---|---|
| 1 | A's link "ends in a downward arrow **to the right of the HUB circle**, leaving a visible gap" | A's arrow **tip was 5.00 px inside r=18** — it did land. The **arrowhead was 33 × 30 user units against a node only 36 across**, because `markerUnits` defaulted to `strokeWidth` on an 11-unit marker over a 3-wide stroke. The head **covered the node**, so the junction could not be read. r3's diagnosis (gap) was wrong; r3's observation (the connection is unreadable) was right. | **FIXED** |
| 2 | "the horizontal red line from the flight-segment box **stops short** of the HUB circle" | that arrow's tip was **3.93 px OUTSIDE r=18**. A real gap. | **FIXED** |
| 3 | "the 'HUB' label is **cramped against and appears to touch/overlap** the circle outline" | label ink **2.00 px** from the ring, on a 27.8-unit-wide label inside a 33.5-unit inner diameter. | **FIXED** |
| 4 | relay "not yet visually unambiguous" as A → balloon → B | no sequential framing: two unlabelled red lines, and the node's label said "HUB" (the name of a *different* box on the drawing) rather than naming the balloon. | **FIXED** |

## The fix (all of it in the generator — no generated output was hand-edited)

`tracker/hardware/make_system_diagram.py`:

- the relay node is **r=34** (was 18), so a fixed arrowhead is a detail on it rather than an object that
  swallows it;
- the arrowhead is **`markerUnits="userSpaceOnUse"`, 12 × 10 units** — its size is a stated number, not a
  product of the stroke width. This was the actual cause of finding 1;
- **`attach()` and `leave()` derive every link endpoint from the node's centre and radius.** The tip of
  each incoming arrow lands **3.00 units inside the ring**; each departure point sits **exactly on** it.
  No endpoint is a literal, so moving the node cannot silently reopen r3's gap;
- the node's label sits **beside** the circle, **14.78 units** clear of the ring, and names what the node
  **is** — `BALLOON / relay node — the flight segment: hub v9 + 4 wings` — instead of "HUB" inside a ring
  barely wider than the word;
- the two hops are **numbered and captioned** (`hop 1 of 2: A → balloon`, `hop 2 of 2: balloon → B`) and
  attach at the node's **top** and **bottom**, so the chain cannot be read as one continuous path;
- A's route is **one elbow**, not two (a reviewer read the intermediate jog as arbitrary), and its **last
  segment points at the node**, because the marker orients on the last segment — a diagonal turn had
  swung the head off-axis;
- balloon → B runs **above** base station B; an earlier revision drove it through B's interior.

## Measured result on the reviewed artefact

```
$ python3 scripts/check_system_diagram_geometry.py
relay node: centre (940.0,330.0) r=34.0 stroke=2.5 -> ring 32.75..35.25
  A -> HUB: endpoint (940.0, 297.5) tip (940.0, 299.0) |tip-centre|=31.0 penetration=+3.00
  HUB -> B: endpoint (1240.0, 558.5) tip (1240.0, 560.0) lands_on_B_edge=True
  node label ink (990.0, 316.0, 1075.0, 328.25) (label outside the ring) clearance=14.78 px
  closest approach of two links outside the node = 71.25 px (min 4.0)
DEFECTS: 0
```

Tolerances, each stated in the script with its reason: tip penetration ≥ 1.5 px; arrowhead ≤ 60 % of the
node's diameter; marker must be `userSpaceOnUse`; label clearance ≥ 3.0 px; two links no closer than
4.0 px outside the node; text-to-text overlap ≤ 0.5 px²; text-to-line ≥ 3.0 px; text-to-foreign-border
≥ 4.0 px. Text bounding boxes are measured from the **real DejaVu metrics** at each element's own
font-size, with the baseline handled correctly.

The raster is cross-checked independently of the SVG's marker arithmetic (`closest_red_ink_above_to_
centre_svg = 33.0`, i.e. the arrow's ink reaches the ring), so a renderer that ignored the marker
definition could not pass the gate silently.

## The gate can fail (this is the point)

`tests/test_system_diagram_geometry.py` reproduces each defect synthetically and requires the gate to
catch it — a check that cannot fail proves nothing:

```
[1] committed svg: exit 0
[2] a_link_short_of_the_node: exit 1 caught=True
[2] node_too_small_for_label_and_head: exit 1 caught=True
[2] label_on_the_ring: exit 1 caught=True
[2] arrowhead_scales_with_stroke: exit 1 caught=True
[3] generator --check: exit 0
SELFTEST: PASS
```

Run against the **pre-fix** artefact from git, the same gate reports 3 defects — it fails on the drawing
r3 was looking at:

```
- FLIGHT SEGMENT -> HUB: arrow tip is -3.93 px from the ring (|tip-centre|=21.93, r=18.0) -- it does NOT land
- node label 'HUB' ink is 2.00 px from the node's ring (needs >= 3.0); placement: label inside the ring
- arrowhead #ar is 33.0 units across against a node 36 units across (92% of the diameter) -- the head covers the node
```

## Re-review of the REGENERATED image

Command, run **after** regeneration (reviewing a stale PNG would make the review a lie):

```
python3 tracker/hardware/ask_astra.py --review docs/boards/system-diagram.png \
    --out docs/fab/reviews/system-diagram-r4.md
```

- **SERVED MODEL: `gpt-6-astra`** (printed by the tool; matches the intended model)
- **Exit code: 0 — `VERDICT: CLEAN`**
- Full transcript: `docs/fab/reviews/system-diagram-r4.md`
- **Reviewed PNG sha256: `313cc7384a396b0de2569d3f887ec0653741a8a760f0eaccb998eac8e68b65d7`**
  (`docs/boards/system-diagram.png`, 1800 × 1067)
- Companion SVG sha256: `886177199210411ab5e8e6b172006671d8703c3a5ae358e5827bfd2829a2277e`

The consultant passed all eight rubric points and reported **no actionable drawing defects**. Its own
words on the point r3 failed: the red arrows "terminate at the balloon's top and station B's top as
described", and on the relay: "the illustrated path matches the stated relay topology".

## The unearned claims the earlier cycles revealed

Three review cycles were run (the bound was 4). Cycles 1 and 2 returned `DEFECTS_PRESENT`, and **none of
their findings were geometric** — the geometry was clean from cycle 1. What they found was the drawing
**asserting things its own content did not support**:

1. **"SIM7600E-H 4G/5G backhaul" was false.** The fitted module is LTE Cat 4, and
   `docs/TELCO-BACKHAUL-DECISIONS.md` **R3** reads *"LTE Cat-4 now. Do NOT buy 5G."* The claim was in
   **four** places (`README.md` ×2, `docs/boards/GALLERY.md`, `make_board_gallery.py`, the generator).
   **All four were fixed**, not only the one that was reviewed.
2. **"0 real electrical errors" was a false reassurance.** The same box lists `U1.41` with no net two
   rows down, and the DRC run reports **4 unconnected** errors besides the 16 edge clearances
   (`GATE-RESULTS.md` line 59). `GATE-RESULTS.md`'s "zero real electrical DRC errors" is about the
   error-class *clearance* items only; as a diagram caption it read as "there are no electrical errors".
3. **"both fully enumerated below"** was a completeness claim the box does not honour. It was mine,
   introduced while fixing (2), and the cycle-3 review caught it.

A fourth was structural: the flight-box-to-node connector was drawn as a **red directional arrow**,
which read as a third radio hop between two devices — but the node **is** the flight segment. It is now a
grey dotted arrowless leader with a terminator dot, the standard "this is that" convention.

## What this diagram CAN and CANNOT establish

**CAN establish** (and the consultant's CLEAN verdict is a verdict about these): that the drawing shows
A → balloon → B as **two separate hops with no ground-to-ground path**; that both hops **visibly terminate
on the relay node** and the node's label does not collide with its outline; that no text overlaps other
text, is clipped, or crosses a border; that the four wings and two stations are present and legible; and
that the stated state is **"fit to show JLCPCB for review; NOT fit to order"**.

**CANNOT establish** — a picture cannot be evidence for any of these, and this verdict must not be read
as if it were:

- **that the relay works**, that the FLRC link closes at any range, or that the link budget is met (that
  is `docs/fab/` link-budget work, not a drawing);
- **that the board is correct or fabricable** — routing completeness, shorts/opens, net connectivity,
  clearances, return paths, 2.4 GHz impedance and antenna keepout. Those are measured by the gates in
  `docs/fab/GATE-RESULTS.md`, which currently read **NOT ORDERABLE**;
- **that the counts are right** — the drawing *quotes* 59 footprints / 57 of 59 nets / 834 tracks / 286
  vias / 20 ERC / 16 + 4 DRC from the gate output. The consultant can only check that the drawing is
  *internally* consistent; the numbers are true only if `GATE-RESULTS.md` is current;
- **that the LTE Cat 4 module is band-compatible with any carrier** — `docs/fab/ASTRA-GAP-ANALYSIS.md`
  B1 still requires the operator to confirm country, carrier and module acceptance;
- **that the wing-socket geometry is decided** — it is OPEN (ADR-046 §4.2.1) and the drawing says so;
- **that the balloons fly**, carry the payload, or reach the stations. Nothing about flight is in scope.

## Provenance / invalidation

The hashes above are of the exact bytes sent to the consultant and committed. **Any change to
`make_system_diagram.py` — a count, a coordinate, a label — invalidates this verdict**: it requires
`python3 tracker/hardware/make_system_diagram.py` and a fresh `--review`, because the geometry gate
cannot judge wording and the consultant cannot judge arithmetic.

## Closing note

An artefact that is reviewed but not concluded is worse than an unreviewed one, because it looks
reviewed. r3's findings sat unacted-on in this tree for exactly that reason: they existed as prose, so
nothing failed. They are now assertions that fail a build, the gate that runs them has been shown to
fail, and the consultant's terminal verdict on the regenerated image is **CLEAN** (served
`gpt-6-astra`, exit 0). This record closes the review.

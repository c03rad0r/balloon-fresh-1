# System diagram — review journey

Three visual reviews of `docs/boards/system-diagram.png`, each after a regeneration (never before — a
review of a stale render is a review of a file that no longer exists).

## Review 1 — 7 defects, ONE SUBSTANTIVE

> "**The 'bent pipe between base stations' topology is incomplete. Only one base station is shown.** A
> second ground station and another radio connection would be needed to illustrate the title's full
> relay concept."

**This is the finding that mattered.** The goal is balloons as a bent pipe connecting base stations
(**plural**). A diagram with one ground node **cannot show a relay at all** — it would have shipped
misrepresenting the architecture, in a document whose whole purpose is to make the system legible.

The other six were layout: heading ran into its border; all four wing boxes too short so "4/6 nets"
straddled the bottom edge; the wing-interface annotation was crossed by the dashed connectors; the red
radio link crossed its own label; the status panel overlapped the ground box; space was unbalanced.

## Review 2 — 4 defects, ONE SUBSTANTIVE AGAIN

> "The red wiring **directly connects A to B**, contradicting the relay-only labels... the drawing depicts
> a direct A-B connection plus a disconnected flight-segment stub."

I had drawn V2's links as an elbow that **shared a vertical segment between A and B** — which *is* a
direct ground-to-ground path. **The picture contradicted the text, in the same document where one box
literally reads "no direct A-B path is assumed."** Fixed by routing the two links so both terminate on
the hub and never touch: A → hub, and hub → B, as two separate hops with arrowheads.

## Review 3 — 1 defect, a CONNECTION GAP — **AND NO VERDICT WAS EVER RECORDED**

> "A's link appears disconnected from the relay... Connect A's arrowhead precisely to the HUB boundary
> and connect the flight-segment line to that node."

No direct A-B path (the substantive point held). The remaining fault was arithmetic: the arrowhead
stopped **40 units to the right of the circle**. It was repositioned by computation rather than by eye —
circle `(960,270) r=18` gives boundary top `y=252`, bottom `y=288`, left `x=942`; the three path
endpoints land at 251, 285 and 945.

**THIS SECTION WAS WRONG TO STOP THERE, and it is the reason the defect shipped.** r3 recorded **four**
findings, not one, and **no terminal verdict**. Re-measured later against the artefact r3 saw: A's tip
was actually 5.00 px *inside* the ring — but the arrowhead was 33 × 30 units against a 36-unit node,
because `markerUnits` defaulted to `strokeWidth`, so the head **covered** the node; the flight-segment
line's tip was **3.93 px outside** the ring; and the label's ink sat **2.00 px** from the ring.

r3's own summary line is the correct one, and it was never acted on:

> "The intended two-hop relay is understandable, but not yet visually unambiguous."

**CLOSED** in `docs/fab/reviews/system-diagram-final.md` — findings measured, fixed in the generator,
gate added that provably fails on the old artefact, and the regenerated render re-reviewed to CLEAN
(served `gpt-6-astra`). The lesson this file already states, made concrete: prose findings do not fail
anything, so nothing was done about them.

## Why this is recorded rather than just fixed

Two of the three reviews found that **the drawing said one thing and showed another**. Both were real
architecture errors, not cosmetics, and both survived my own reading of the code that generated them.
The recurring lesson of this project: **a plausible-looking artefact is not a verified one, and the only
way to catch a picture that contradicts its caption is to have the picture looked at.**

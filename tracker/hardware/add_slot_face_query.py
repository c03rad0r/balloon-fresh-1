"""Add the internal-slot-face construction question to the JLCPCB query, if it is not already there.

WHY. The edge-drawing review (r2/r3) identified a genuine engineering gap that the query does not cover:

  ADR-048 commits a ROUTED SLOT (0.9 x 6.0 mm) in the hub edge, with the four wing-tab lands sitting on
  the slot's OPPOSING INTERNAL FACES. The drawing can depict that, but the review's TECHNICAL CORRECTNESS
  item says plainly: "Ordinary F.Cu/B.Cu on a board does not become broad copper coverage on an internal
  routed wall merely through routing."

The query's section 2 covers the BOARD-EDGE case (rout through pads; is it plating/castellation). It does
NOT ask about the INTERNAL FACES of a routed slot -- a different geometry, and the one ADR-048 commits.

This script appends the question only if it is absent, and says which it did. It does not rewrite the
existing questions, and it does not invent an answer, a price, or a capability claim.
"""
from __future__ import annotations

import os
import sys

TARGET = "docs/fab/JLC-QUERY-DRAFT-MESSAGE.md"

ANCHOR = "### 3. Thin-board handling"

NEW_SECTION = """### 2A. Copper on the INTERNAL FACES of a routed slot -- separate from 2.1/2.2

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

"""


def main() -> int:
    if not os.path.exists(TARGET):
        print(f"ABSENT: {TARGET}")
        return 2
    text = open(TARGET, encoding="utf-8").read()

    if "2A.1" in text or "INTERNAL FACES" in text:
        print(f"{TARGET}: the internal-slot-face question is ALREADY present -- no change made.")
        return 0

    if ANCHOR not in text:
        print(f"{TARGET}: anchor {ANCHOR!r} NOT FOUND -- refusing to guess where to insert.")
        return 2

    out = text.replace(ANCHOR, NEW_SECTION + ANCHOR, 1)
    if out == text:
        print("no change made (replace was a no-op)")
        return 2
    with open(TARGET, "w", encoding="utf-8") as fh:
        fh.write(out)

    # stat it: a "wrote <path>" line is not proof
    if not os.path.exists(TARGET) or os.path.getsize(TARGET) == 0:
        print("RENDER FAILED: file absent or empty after write")
        return 1
    grown = len(out) - len(text)
    print(f"{TARGET}: section 2A added ({grown:+d} chars, now {os.path.getsize(TARGET)} bytes)")
    print("  inserted BEFORE:", ANCHOR)
    print("  the existing sections 1, 2, 3 were NOT modified")
    return 0


if __name__ == "__main__":
    sys.exit(main())

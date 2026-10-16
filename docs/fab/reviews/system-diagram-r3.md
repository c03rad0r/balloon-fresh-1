# Astra visual review

Served model: gpt-6-astra
Images: docs/boards/system-diagram.png

1. **No—not both links connect to the hub/balloon node.** The link from A ends in a downward arrow **to the right of the HUB circle**, leaving a visible gap. The link to B connects to the bottom of the HUB circle. The two links do not touch each other outside the hub, and there is **no direct ground-to-ground A–B line**. Also, the horizontal red line from the flight-segment box stops short of the HUB circle.

2. **Yes.** There is a downward arrowhead at the end of A’s link near the hub and another where the hub-to-B link enters B’s top edge. However, A’s arrowhead does not actually land on the hub.

3. **There is a local text/edge collision:** the **“HUB” label is cramped against and appears to touch/overlap the circle outline**. Otherwise, no obvious text-to-text, text-to-box-edge, or text-to-line overlaps are visible.

4. **The intended two-hop relay is understandable, but not yet visually unambiguous.** A reader is unlikely to see a direct A–B connection; the main problem is that **A’s link appears disconnected from the relay**, and the flight-segment-to-HUB line also has a gap. Connect A’s arrowhead precisely to the HUB boundary and connect the flight-segment line to that node to make **A → balloon → B** explicit.

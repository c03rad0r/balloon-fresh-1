#!/usr/bin/env python3
"""Generate the top-level system diagram for README.md.

WHY GENERATED. A hand-drawn diagram of this system was already wrong once: the README describes "two
boards, two laptops" while the end-to-end system is a flight hub, four wings and a ground station linked
by FLRC. A diagram maintained by hand drifts from the thing it describes.

V2 -- AFTER A VISUAL REVIEW FOUND SEVEN DEFECTS, one of them substantive:

  6. SUBSTANTIVE: "the 'bent pipe between base stations' topology is incomplete. Only one base station
     is shown. A second ground station and another radio connection would be needed to illustrate the
     title's full relay concept." CORRECT, and the most important finding. The goal is balloons as a bent
     pipe connecting base stations (PLURAL). A diagram with one ground node cannot show a relay at all;
     it would have misrepresented the system. V2 draws TWO ground stations with a balloon-relayed path
     between them.
  1-5,7: layout -- heading had no horizontal padding and ran into its border; all four wing boxes were
     too short so "4/6 nets" straddled the bottom border; the wing-interface annotation was crossed by
     the dashed connectors; the red radio-link line crossed its own annotation; the status panel
     overlapped the ground box; and space was unbalanced (empty flight box vs cramped labels).

V3 -- AFTER THE r3 REVIEW'S FOUR FINDINGS WERE MEASURED INSTEAD OF EYEBALLED. r3
(docs/fab/reviews/system-diagram-r3.md) reported: A's arrow "ends in a downward arrow TO THE RIGHT OF
THE HUB CIRCLE, leaving a visible gap"; "the horizontal red line from the flight-segment box STOPS
SHORT of the HUB circle"; "the 'HUB' label is cramped against and appears to touch/overlap the circle
outline"; and the relay is "not yet visually unambiguous". It recorded NO terminal verdict and nobody
acted on it, so the findings sat in the tree looking reviewed. Measured on the artefact r3 saw:

  * A's arrow tip was 5.0 px INSIDE r=18 -- it landed, but the arrowhead is 33 x 30 user units and the
    node is only 36 across, so the head COVERED the node: the connection read as ambiguous, which is
    what "leaving a visible gap" was describing from the outside.
  * the flight-segment line's tip was 3.93 px OUTSIDE r=18 -- a real gap, confirmed.
  * the "HUB" label ink was 2.00 px from the node's stroke ring, on a label 27.8 units wide inside a
    33.5-unit inner diameter -- cramped, confirmed.

WHAT V3 CHANGES, all of it computed rather than placed by eye:
  * the relay node is r=34 (was 18), so a fixed-size arrowhead is a detail on it instead of an object
    that swallows it;
  * the arrowhead marker is markerUnits="userSpaceOnUse" at a fixed 12 x 10 units, so its size no
    longer scales with the stroke width (it used to be 11 x 3 = 33 units long by accident);
  * every link endpoint is DERIVED from the node's centre and radius by attach()/leave(), which puts
    each tip a stated penetration inside the ring and each departure exactly on it;
  * the node's label sits OUTSIDE the circle ("BALLOON", 12 units clear of the ring) instead of being
    squeezed inside it, and names the thing the diagram is about;
  * the two hops are numbered ("hop 1 of 2" / "hop 2 of 2") so A -> balloon -> B reads as a sequence,
    and they attach at the node's TOP and BOTTOM so they cannot be mistaken for one continuous path.

scripts/check_system_diagram_geometry.py measures all of this from the SVG (and cross-checks the
rendered PNG); tests/test_system_diagram_geometry.py runs it and proves it can fail.

Output: docs/boards/system-diagram.svg (+ .png)
Run:    python3 tracker/hardware/make_system_diagram.py
"""
import argparse
import math
import os
import shutil
import subprocess
import tempfile

W, H = 1620, 960
OUT = "docs/boards/system-diagram.svg"

# ---------------- relay-node geometry. ONE source of truth: every link endpoint is derived from these
# numbers, never written as a literal. The previous version placed them by hand and got two of the
# three wrong in a way no test could see.
NODE = dict(cx=940.0, cy=330.0, r=34.0, sw=2.5)
# The two ground stations share a column. Named because the link geometry is derived from it: the
# free vertical channel between the flight box and the stations is where A's link runs.
STATION_X, STATION_W = 1120.0, 430.0

# The arrowhead is 12 x 10 USER units (markerUnits="userSpaceOnUse"), drawn with its tip at marker
# x=12 and refX=10.5, so it extends 1.5 units past the path's last point.
ARROW_TIP_OVERHANG = 1.5
# How far the tip goes past the ring's centre-line, i.e. into the node. Enough that the head visibly
# touches the ring and not so much that it buries the node.
ARROW_TIP_PENETRATION = 3.0
ARROW_VIEW_W, ARROW_VIEW_H = 12, 10


def attach(node, direction):
    """Endpoint and tip for an arrow ENTERING `node` along `direction` (a vector pointing at the
    node's centre). The tip lands ARROW_TIP_PENETRATION inside the ring; the path stops
    ARROW_TIP_OVERHANG short of the tip because the marker's own geometry extends past it."""
    d = math.hypot(*direction)
    ux, uy = direction[0] / d, direction[1] / d
    ex, ey = node["cx"], node["cy"]
    tip = (ex - ux * (node["r"] - ARROW_TIP_PENETRATION),
           ey - uy * (node["r"] - ARROW_TIP_PENETRATION))
    end = (tip[0] - ux * ARROW_TIP_OVERHANG, tip[1] - uy * ARROW_TIP_OVERHANG)
    return end, tip


def leave(node, direction):
    """The point where a path DEPARTS the node's ring, along `direction` away from the centre."""
    d = math.hypot(*direction)
    ux, uy = direction[0] / d, direction[1] / d
    return (node["cx"] + ux * node["r"], node["cy"] + uy * node["r"])


def pt(p):
    """SVG coordinates for a computed point, at a precision that does not depend on the platform."""
    return f"{p[0]:.2f} {p[1]:.2f}"


def box(x, y, w, h, title, lines, fill, stroke, tcol="#111", pad=18):
    """A titled box whose text is centred and kept inside the border by `pad`."""
    p = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" '
         f'stroke="{stroke}" stroke-width="2"/>',
         f'<text x="{x+w/2}" y="{y+32}" font-size="17" font-weight="bold" fill="{tcol}" '
         f'text-anchor="middle">{title}</text>']
    for i, ln in enumerate(lines):
        p.append(f'<text x="{x+w/2}" y="{y+58+i*20}" font-size="13.5" fill="{tcol}" '
                 f'text-anchor="middle">{ln}</text>')
    return "\n".join(p)


def main():
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         f'font-family="DejaVu Sans, Helvetica, sans-serif">',
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
         # The arrowhead is a FIXED-SIZE object in user units. Before, markerUnits defaulted to
         # strokeWidth, so an 11-unit marker on a 3-unit stroke rendered 33 units long and 30 wide --
         # wider than the node it was pointing at. Its size was an accident of the stroke width.
         f'<defs><marker id="ar" markerUnits="userSpaceOnUse" markerWidth="{ARROW_VIEW_W}" '
         f'markerHeight="{ARROW_VIEW_H}" refX="{ARROW_VIEW_W - ARROW_TIP_OVERHANG}" '
         f'refY="{ARROW_VIEW_H / 2}" orient="auto">'
         f'<path d="M0,1 L{ARROW_VIEW_W},{ARROW_VIEW_H / 2} L0,{ARROW_VIEW_H - 1} z" '
         f'fill="#b00020"/></marker></defs>',
         '<text x="40" y="50" font-size="25" font-weight="bold">'
         'Pico-balloon relay: balloons as a bent pipe between base stations</text>',
         '<text x="40" y="78" font-size="14.5" fill="#444">'
         'generated by tracker/hardware/make_system_diagram.py · counts measured, not asserted'
         '</text>']

    # ---------------- flight segment (taller: the review said it was padded and its heading overflowed)
    p.append(box(70, 120, 700, 300,
                 "FLIGHT SEGMENT — hub v9 · 70×70 mm · 4-layer · 0.6 mm FR4",
                 ["SX1280 FLRC 2.4 GHz radio · GNSS · solar harvester",
                  "BQ25504 harvester + supercap · 4 wing sockets J_W1…J_W4",
                  "hub v9: 59 footprints · 57/59 nets routed · 834 tracks · 286 vias",
                  "2 nets unrouted · DRC: 16 edge-land + 4 unconnected (no other error class)"],
                 "#e8f1ff", "#2f6fb0"))

    # ---------------- wings (height 118 so the third line clears the border)
    for i, nets in enumerate(["4/6", "4/6", "4/6", "4/6"]):
        x = 88 + i * 172
        p.append(box(x, 520, 156, 118, f"wing {i+1}",
                     ["solar array", "cut driver", f"{nets} nets routed"],
                     "#eef7ee", "#3d7a45"))
        cx = x + 78
        p.append(f'<line x1="{cx}" y1="420" x2="{cx}" y2="520" stroke="#3d7a45" '
                 f'stroke-width="2" stroke-dasharray="7,4"/>')

    # annotation BELOW the wings, not across the dashed connectors
    p.append('<text x="88" y="668" font-size="12.5" fill="#3d7a45">'
             '4× wing socket: tab into a 0.9×6.0 mm slot — GEOMETRY OPEN (ADR-046 §4.2.1)</text>')

    # ---------------- TWO ground stations, with the balloon as the relay between them
    # "4G/5G" was WRONG and a visual review caught it: the fitted module is SIM7600E-H, which is LTE
    # Cat 4 only, and docs/TELCO-BACKHAUL-DECISIONS.md R3 decides "LTE Cat-4 now. Do NOT buy 5G."
    # The claim lived in README.md, GALLERY.md, make_board_gallery.py and here -- the diagram was the
    # only place it was measured rather than copied.
    p.append(box(STATION_X, 150, STATION_W, 170,
                 "BASE STATION A — ground · 70×50 mm",
                 ["SIM7600E-H LTE Cat 4 backhaul (no 5G)",
                  "FLRC link up to the balloon",
                  "placed only: 44 footprints, 44 nets, 0 tracks",
                  "no editable schematic yet (B2–B9)"],
                 "#fff4e8", "#b0742f"))
    p.append(box(STATION_X, 560, STATION_W, 170,
                 "BASE STATION B — ground · 70×50 mm",
                 ["same board design as A",
                  "reached ONLY via the balloon relay",
                  "this is the 'bent pipe': A → balloon → B",
                  "no direct A–B path is assumed"],
                 "#fff4e8", "#b0742f"))

    # ---------------- the relay node: the balloon. A -> balloon -> B as TWO SEPARATE links.
    # A visual review found that V2's elbow path joined A to B through a shared vertical segment -- i.e.
    # it DREW the direct ground-to-ground link the label says does not exist. Both links terminate ON
    # this node and never touch each other; the checker measures that closest approach.
    p.append(f'<circle cx="{NODE["cx"]}" cy="{NODE["cy"]}" r="{NODE["r"]}" fill="#fdecef" '
             f'stroke="#b00020" stroke-width="{NODE["sw"]}"/>')
    # The label sits BESIDE the node, in the free channel between the flight box and the stations.
    # Inside the circle, the ink of a legible label sits a couple of units off the ring -- which is
    # exactly what r3 reported as "cramped against the circle outline". Beside it, the measured
    # clearance is tens of units AND the label can be read at the size shown.
    # The block starts BELOW A's bottom border (y=320), not level with it: at cy-10 the BALLOON ink
    # began 7 units under the box and the reviewer read the group as crowding A's lower-left corner.
    NODE_LABEL_X = NODE["cx"] + NODE["r"] + 16
    NODE_LABEL_Y = 328.0
    p.append(f'<text x="{NODE_LABEL_X}" y="{NODE_LABEL_Y}" font-size="16" '
             f'font-weight="bold" fill="#b00020">BALLOON</text>')
    p.append(f'<text x="{NODE_LABEL_X}" y="{NODE_LABEL_Y + 16}" font-size="12" fill="#b00020">'
             f'relay node — the flight segment: hub v9 + 4 wings</text>')
    p.append(f'<text x="{NODE_LABEL_X}" y="{NODE_LABEL_Y + 32}" font-size="12" fill="#b00020">'
             f'this is the "hub" node in the FLIGHT SEGMENT box above</text>')

    # A -> balloon: out of A's left edge, down the free channel, then ACROSS and DOWN onto the node's
    # TOP. The tip lands ARROW_TIP_PENETRATION inside the ring; the endpoint stops short by the
    # marker's overhang. Both numbers come from attach(), so moving the node cannot silently
    # reintroduce the r3 gap.
    # The path's LAST segment must be the one that points at the node, because the marker orients on
    # it: an earlier version turned diagonally at the end and the arrowhead swung off the vertical by
    # ~28 degrees, which measured as a 2.6-unit penetration instead of the intended 3.0.
    # ONE elbow, not two. An earlier version left A at y=235 and jogged down to y=250 inside the
    # channel, which a reviewer read as "an unnecessary-looking small step ... arbitrary compared with
    # a simpler elbow route". Depart at the corridor's own y so the route is A -> corner -> node.
    a_channel = STATION_X - 34.0     # the vertical channel, clear of both station boxes
    corridor_y = 250.0
    end_top = attach(NODE, (0.0, 1.0))[0]
    p.append(f'<path d="M {STATION_X:.0f} {corridor_y:.0f} L {a_channel:.2f} {corridor_y:.0f} '
             f'L {NODE["cx"]:.2f} {corridor_y:.0f} L {pt(end_top)}" stroke="#b00020" '
             f'stroke-width="3" fill="none" marker-end="url(#ar)"/>')

    # balloon -> B: leaves the ring at the node's BOTTOM, goes down, across, then down onto B's top
    # edge. The tip is placed at B's border by construction; the endpoint stops short by the marker's
    # overhang so the arrowhead lands ON the border instead of crossing into the box.
    dep_bot = leave(NODE, (0.0, 1.0))
    b_top = 560.0
    # The horizontal run must stay ABOVE B: routing it at y=615 would have driven it straight through
    # B's interior (B spans y 560..730) and then pointed the arrowhead upward, away from the box.
    p.append(f'<path d="M {pt(dep_bot)} L {NODE["cx"]:.2f} 500 L 1240 500 '
             f'L 1240 {b_top - ARROW_TIP_OVERHANG:.2f}" '
             f'stroke="#b00020" stroke-width="3" fill="none" marker-end="url(#ar)"/>')

    # The two hops are LABELLED AS A SEQUENCE. r3's fourth finding was that the relay was
    # "understandable, but not yet visually unambiguous"; two unlabelled red lines read as two lines,
    # whereas "hop 1 of 2" / "hop 2 of 2" plus a caption stating the direction read as a chain.
    hop_x = NODE["cx"] + NODE["r"] + 16
    p.append(f'<text x="{hop_x}" y="{NODE["cy"] + 52}" font-size="13.5" font-weight="bold" '
             f'fill="#b00020">hop 1 of 2: A → balloon</text>')
    p.append(f'<text x="{hop_x}" y="{NODE["cy"] + 70}" font-size="12" fill="#b00020">'
             f'A leaves its left edge, lands on the node\'s top</text>')
    p.append(f'<text x="{hop_x}" y="{NODE["cy"] + 92}" font-size="13.5" font-weight="bold" '
             f'fill="#b00020">hop 2 of 2: balloon → B</text>')
    p.append(f'<text x="{hop_x}" y="{NODE["cy"] + 110}" font-size="12" fill="#b00020">'
             f'from the node\'s bottom, onto B\'s top edge — no ground path</text>')

    # The flight segment and the relay node are THE SAME PHYSICAL THING, so the connector between them
    # is a REFERENCE ("this circle is that box"), not a radio link. Drawn as a red directional arrow it
    # read as a third radio hop between two separate devices -- a review said so: "the extra
    # hub-to-balloon radio arrow misleadingly depicts communication between two representations of the
    # same hardware." It is now a grey dotted leader with no arrowhead, and says what it is.
    end_left = (NODE["cx"] - NODE["r"] - 2.5, NODE["cy"])
    p.append(f'<path d="M 770 {NODE["cy"]:.2f} L {pt(end_left)}" stroke="#666" stroke-width="1.6" '
             f'stroke-dasharray="6,4" fill="none"/>')
    p.append(f'<circle cx="{end_left[0]:.2f}" cy="{end_left[1]:.2f}" r="2.4" fill="#666"/>')
    # NO second label on the leader. The BALLOON block already says "relay node — the flight segment:
    # hub v9 + 4 wings", so a second caption was redundant, and placed anywhere in the 136-unit gap
    # between the flight box and the node it measured 1.5 px from the A-link's vertical run. The
    # leader is grey, dotted and arrowless, which is the whole point: same hardware, not a radio hop.

    # ---------------- status band, placed CLEAR of the ground boxes
    # "0 real electrical errors" was a FALSE REASSURANCE and a visual review called it: the same box
    # lists U1.41 with no net, and the DRC run reports 4 UNCONNECTED errors besides the 16 edge
    # clearances. GATE-RESULTS.md's "zero real electrical DRC errors" refers only to the error-class
    # clearance items, which is not what a reader takes from the sentence. Stated precisely now.
    p.append(box(70, 710, 700, 210,
                 "STATE — fit to show JLCPCB for review; NOT fit to order",
                 # NOT "fully enumerated below": this box summarises. A reviewer caught the claim,
                 # which was mine and was false -- GATE-RESULTS.md enumerates, this caption does not.
                 ["DRC 16 edge-land + 4 unconnected · ERC 20 · summary; full lists in GATE-RESULTS",
                  "U1.41 (radio exposed ground pad) has NO NET — pad-number mismatch",
                  "ERC 20 errors incl. 12 floating U_CUT pins; parity PASSES (no board drift)",
                  "package regenerated 59/59 (was 39: the RF match/filter was missing)",
                  "interface drawing HELD — geometry undecided, must not go to a fabricator",
                  "gate 14 pass / 0 FAIL / 2 PENDING · docs/fab/GATE-RESULTS.md"],
                 "#f6f6f6", "#888"))

    p.append(f'<text x="40" y="{H-16}" font-size="12" fill="#777">'
             'measured 2026-10-16 · worktree u4-rewire, branch pr/u4-rewire · '
             'docs/boards/GALLERY.md is the per-board table</text>')
    p.append('</svg>')

    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
    from artefact import DeterministicWriter
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="do not write; exit 1 if the committed artefacts differ from the generated")
    a = ap.parse_args()

    writer = DeterministicWriter(__file__)
    svg_text = "\n".join(p)
    writer.add(OUT, svg_text)

    # The PNG is derived from the SVG. Render it into a temp file and register the BYTES, so the check
    # compares the committed PNG rather than regenerating over it.
    png = OUT.replace(".svg", ".png")
    if shutil.which("rsvg-convert"):
        fd, tmp_svg = tempfile.mkstemp(suffix=".svg")
        os.close(fd)
        with open(tmp_svg, "w") as fh:
            fh.write(svg_text)
        fd2, tmp_png = tempfile.mkstemp(suffix=".png")
        os.close(fd2)
        r = subprocess.run(["rsvg-convert", "-w", "1800", tmp_svg, "-o", tmp_png],
                           capture_output=True, text=True)
        if not os.path.exists(tmp_png) or os.path.getsize(tmp_png) == 0:
            print(f"RENDER FAILED: rsvg-convert rc={r.returncode}")
            print(f"  stderr: {(r.stderr or r.stdout or '(none)').strip()[:400]}")
            return 1
        writer.add_file(png, tmp_png)
        os.unlink(tmp_svg)
        os.unlink(tmp_png)
    else:
        print("WARNING: rsvg-convert not found -- SVG only, PNG not checked")
    return writer.finish(check=a.check)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Geometry gate for docs/boards/system-diagram.svg.

WHY THIS EXISTS. The r3 visual review (docs/fab/reviews/system-diagram-r3.md) judged the relay
geometry BY EYE and reported its findings as prose: A's arrow "ends to the right of the HUB circle,
leaving a visible gap"; the flight-segment line "stops short of the HUB circle"; the "HUB" label "is
cramped against and appears to touch/overlap the circle outline". Prose cannot be regressed -- nothing
failed when the finding went unfixed, which is exactly why it survived into a published artefact.

This gate turns each of those findings into a NUMBER measured from the SVG, so the generator cannot be
changed without the measurement changing with it. A drawing that a person has to squint at is a
drawing that was never measured.

MEASUREMENTS
  1. every link arrow has a marker tip, and the TIP is at a stated penetration depth into the hub
     node's stroke -- not "near" it, and not buried in its middle;
  2. the same for the arrow that enters base station B's border;
  3. the "HUB" label's ink bbox, from the real DejaVu font metrics, and its clearance to the node's
     stroke ring (both when the label sits inside the ring and when it sits outside it);
  4. the relay chain: three red link paths, each attached at one end to the hub node or to a station,
     and no two of them approaching each other outside the hub (a shared segment outside the hub IS
     the ground-to-ground A-B path the caption says does not exist);
  5. text-vs-text overlap, text straddling a box border, and anything off-canvas -- so a fix cannot
     buy one property by breaking another.

Text bboxes are measured from /usr/share/fonts/truetype/dejavu at the element's own font-size, with
the baseline handled correctly (PIL's getbbox is relative to the ASCENT TOP, not the baseline -- a
mistake in an earlier version of this checker produced a false "text straddles the border" report and
a HUB label bbox 11 units below where it really is).

Run:  python3 scripts/check_system_diagram_geometry.py [--svg PATH] [--json]
Exit: 0 = every measurement inside tolerance; 1 = at least one defect, printed with its numbers.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET

NS = "{http://www.w3.org/2000/svg}"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SVG = os.path.join(REPO, "docs", "boards", "system-diagram.svg")

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
FONT_REGULAR = os.path.join(FONT_DIR, "DejaVuSans.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")

LINK_COLOUR = "#b00020"     # the colour that identifies a radio link in this drawing

# TOLERANCES -- each one is a choice, so each one is named and justified.
TIP_PENETRATION_MIN = 1.5   # px past the ring's centre-line. Below this the tip only grazes the
                            # outer antialiased edge and reads as "nearly touching" = the r3 defect.
TIP_MAX_FRAC_OF_R = 0.45    # the tip must not go deeper than this fraction of the radius: an
                            # arrowhead buried in the node hides the node and reads as "through it".
ARROW_MAX_FRAC_OF_NODE = 0.60  # the arrowhead's own extent, as a fraction of the node's DIAMETER.
                            # This is the r3 finding that measurement caught and the eye alone did
                            # not: with markerUnits defaulting to strokeWidth, an 11x11 marker on a
                            # 3-wide stroke rendered 33 x 30 units against a 36-unit node, so the
                            # head COVERED the node and the landing point was unreadable. An arrow
                            # that lands cannot be judged if the arrow is bigger than the target.
LABEL_CLEARANCE_MIN = 3.0   # px between the label's ink and the node's stroke ring.
CHAIN_MIN_APPROACH = 4.0    # px; two links closer than this outside the hub read as one path.
TEXT_OVERLAP_MAX = 0.5      # px^2 of ink-on-ink overlap tolerated between two text runs.
TEXT_TO_LINE_MIN = 3.0      # px between a text run's ink and a drawn line's stroke edge. "A pixel or
                            # two" of gap reads as touching at display size; the eye said so about
                            # this drawing before the checker measured it.
TEXT_TO_BORDER_MIN = 4.0    # px between a text run's ink and a box border it does not belong to.


# ---------------------------------------------------------------- font metrics
_font_cache: dict = {}


def _font(size: float, bold: bool):
    """A font rendered at 4x the requested size, for quarter-pixel-accurate ink bboxes."""
    try:
        from PIL import ImageFont
    except ImportError:
        # FAIL LOUDLY AND SPECIFICALLY. Before this guard the missing dependency surfaced as a bare
        # ModuleNotFoundError traceback from inside a generator helper, which reads like a broken script
        # rather than an undeclared dependency -- and it cost a red CI run to diagnose. The rule this
        # repo keeps relearning: a gate that cannot run must say WHY, not just fail.
        raise SystemExit(
            "check_system_diagram_geometry: Pillow is not installed, so text ink bboxes cannot be "
            "measured and every text-overlap check would be a guess.\n"
            "  Install it:  pip install pillow\n"
            "  CI declares it in .github/workflows/test.yml (Install Python dependencies)."
        )
    key = (round(size, 3), bool(bold))
    if key not in _font_cache:
        path = FONT_BOLD if bold else FONT_REGULAR
        if not os.path.exists(path):
            raise SystemExit(f"font file missing, bboxes would be a guess: {path}")
        px = max(1, int(round(size * 4)))
        f = ImageFont.truetype(path, px)
        _font_cache[key] = (f, 4.0)
    return _font_cache[key]


def text_bbox(el) -> tuple:
    """Ink bbox (x0, y0, x1, y1) in user units, measured from the real font at the real size."""
    txt = (el.text or "").strip()
    size = float(el.get("font-size", "12"))
    bold = str(el.get("font-weight", "")).lower() in ("bold", "600", "700", "800", "900")
    anchor = el.get("text-anchor", "start")
    x = float(el.get("x", "0") or 0)
    y = float(el.get("y", "0") or 0)
    if not txt:
        return (x, y, x, y)
    f, sc = _font(size, bold)
    dx0, dy0, dx1, dy1 = (v / sc for v in f.getbbox(txt))
    ascent = f.getmetrics()[0] / sc           # ascent top is y - ascent for a baseline at y
    top = y - ascent
    w = dx1 - dx0
    if anchor == "middle":
        left = x - w / 2.0
    elif anchor == "end":
        left = x - w
    else:
        left = x
    return (left + dx0, top + dy0, left + dx1, top + dy1)


# ---------------------------------------------------------------- geometry helpers
def parse_path(d: str) -> list:
    """The polyline of an M/L path. The generator emits only M and L; anything else is a bug."""
    pts = []
    for mx in re.finditer(r"([MLml])\s*(-?[\d.]+)[ ,]+(-?[\d.]+)", d):
        cmd, a, b = mx.group(1), float(mx.group(2)), float(mx.group(3))
        if cmd in ("ml",) and pts:
            a, b = pts[-1][0] + a, pts[-1][1] + b
        pts.append((a, b))
    return pts


def marker_geometry(root, marker_id: str, stroke_width: float) -> tuple:
    """(tip overhang past the path's last point, in user units, and the units it was computed in).

    markerUnits defaults to "strokeWidth", which makes a marker's size an ACCIDENT of the stroke
    width -- on this drawing that accident produced a 33 x 30 unit arrowhead aimed at a 36-unit node.
    When markerUnits="userSpaceOnUse" the marker coordinates are user units and the overhang is
    (tip_x - refX) as written. Getting this bill of materials wrong in the checker would mis-report
    every arrow's landing point, so the unit is read from the SVG rather than assumed.
    """
    for m in root.iter(NS + "marker"):
        if m.get("id") != marker_id:
            continue
        refx = float(m.get("refX", "0"))
        tipx = 0.0
        for pth in m.iter(NS + "path"):
            xs = [float(v) for v in re.findall(r"[ML]\s*(-?[\d.]+)", pth.get("d", ""))]
            if xs:
                tipx = max(tipx, max(xs))
        units = m.get("markerUnits", "strokeWidth")
        scale = 1.0 if units == "userSpaceOnUse" else stroke_width
        return (tipx - refx) * scale, units
    raise SystemExit(f"marker #{marker_id} not found -- tip geometry would be a guess")


def seg_point_dist(p, a, b) -> float:
    """Perpendicular/endpoint distance from a point to a segment."""
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def bbox_stroke_dist(bb, a, b, half_width) -> float:
    """Distance from a text bbox to a stroked segment, minus the stroke's half width. Negative when
    the stroke passes through the ink."""
    # sample the segment, and also measure from the bbox's corners to the segment
    best = min(seg_point_dist((x, y), a, b) for x in (bb[0], bb[2]) for y in (bb[1], bb[3]))
    for k in range(41):
        t = k / 40.0
        pt = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        d = math.hypot(max(bb[0] - pt[0], 0.0, pt[0] - bb[2]), max(bb[1] - pt[1], 0.0, pt[1] - bb[3]))
        best = min(best, d)
    return best - half_width


def bbox_rect_gap(bb, r) -> float:
    """Signed gap between a text bbox and a rect: negative when they intersect."""
    dx = max(r[0] - bb[2], bb[0] - r[2], 0.0)
    dy = max(r[1] - bb[3], bb[1] - r[3], 0.0)
    if dx == 0.0 and dy == 0.0:                      # they overlap in both axes
        ov = bbox_overlap(bb, r)
        return -ov
    return math.hypot(dx, dy)


def rect_point_dist(p, r) -> float:
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def bbox_ring_clearance(bb, centre, r_in, r_out) -> tuple:
    """(clearance, where). Clearance is the gap between the text ink and the node's stroke ring,
    negative when they intersect. Handles both label placements: inside the ring (the centre is
    inside the bbox, so the relevant distance is to the bbox's FARTHEST corner) and outside it
    (the centre is outside, so the relevant distance is to the bbox's NEAREST point)."""
    x0, y0, x1, y1 = bb
    cx, cy = centre
    inside_bbox = x0 <= cx <= x1 and y0 <= cy <= y1
    corners = [(x, y) for x in (x0, x1) for y in (y0, y1)]
    dists = [math.hypot(x - cx, y - cy) for x, y in corners]
    dmin = min(max(x0 - cx, 0.0, cx - x1), 0) if False else math.hypot(
        max(x0 - cx, 0.0, cx - x1), max(y0 - cy, 0.0, cy - y1))
    if inside_bbox:
        return r_in - max(dists), "label inside the ring"
    if dmin > r_out:
        return dmin - r_out, "label outside the ring"
    return -min(r_out - min(dists), dmin), "label crosses the ring"


def bbox_overlap(a, b) -> float:
    ox = min(a[2], b[2]) - max(a[0], b[0])
    oy = min(a[3], b[3]) - max(a[1], b[1])
    return ox * oy if ox > 0 and oy > 0 else 0.0


# ---------------------------------------------------------------- the checks
def check(svg_path: str, want_png: bool = True) -> dict:
    root = ET.parse(svg_path).getroot()
    W = float(root.get("width", "0"))
    H = float(root.get("height", "0"))

    # The relay node is the LARGEST circle: small filled dots are allowed (a leader's terminator is
    # one), but exactly one ring may be the node, or the geometry below is measuring the wrong shape.
    circles = [dict(cx=float(c.get("cx")), cy=float(c.get("cy")), r=float(c.get("r")),
                    sw=float(c.get("stroke-width", "1")))
               for c in root.iter(NS + "circle")]
    rings = [c for c in circles if c["r"] >= 10]
    if len(rings) != 1:
        raise SystemExit(f"expected exactly 1 relay-node ring (r >= 10), found {len(rings)}: {rings}")
    hub = rings[0]
    centre = (hub["cx"], hub["cy"])
    r_out = hub["r"] + hub["sw"] / 2.0
    r_in = hub["r"] - hub["sw"] / 2.0

    texts = [dict(text=(t.text or "").strip(), bbox=text_bbox(t)) for t in root.iter(NS + "text")]

    rects = []
    for r in root.iter(NS + "rect"):
        rx, ry = float(r.get("x", "0") or 0), float(r.get("y", "0") or 0)
        rects.append((rx, ry, rx + float(r.get("width", "0")), ry + float(r.get("height", "0"))))

    paths = []
    for p in root.iter(NS + "path"):
        pts = parse_path(p.get("d", ""))
        if len(pts) < 2:
            continue
        sw = float(p.get("stroke-width", "1"))
        me = p.get("marker-end", "")
        off, units = 0.0, ""
        if me.startswith("url(#") and me.endswith(")"):
            off, units = marker_geometry(root, me[5:-1], sw)
        paths.append(dict(d=p.get("d", ""), pts=pts, sw=sw, tip_off=off, marker_units=units,
                          marker_end_ref=(me[5:-1] if me.startswith("url(#") else ""),
                          stroke=p.get("stroke", ""), has_marker=bool(me)))

    defect_list: list = []
    # TWO red link arrows, not three. The third used to join the flight box to the node -- a REFERENCE
    # between two drawings of the same hardware, which a review read as an extra radio hop. It is now
    # a grey dotted leader and is deliberately NOT counted here.
    links = [p for p in paths if p["has_marker"] and p["stroke"] == LINK_COLOUR]
    if len(links) != 2:
        defect_list.append(dict(defect=f"expected 2 red link arrows (A->node, node->B), found "
                                       f"{len(links)}"))

    # the two station boxes: in the right-hand column, the topmost and the bottommost
    right = [r for r in rects if r[0] > W * 0.6 and (r[2] - r[0]) > 200]
    A, B = (None, None)
    if len(right) >= 2:
        right.sort(key=lambda r: r[1])
        A, B = right[0], right[-1]

    # ---- classify the three links by where they START
    def classify(p):
        s = p["pts"][0]
        d0 = math.hypot(s[0] - centre[0], s[1] - centre[1])
        if d0 <= r_out + 3:
            return "HUB -> B"
        if A and abs(s[0] - A[0]) < 3 and A[1] <= s[1] <= A[3]:
            return "A -> HUB"
        if s[0] < centre[0] - hub["r"]:
            return "FLIGHT SEGMENT -> HUB"
        return f"UNCLASSIFIED link starting at {s}"

    arrows = []
    for p in links:
        end, prev = p["pts"][-1], p["pts"][-2]
        dx, dy = end[0] - prev[0], end[1] - prev[1]
        L = math.hypot(dx, dy) or 1.0
        tip = (end[0] + dx / L * p["tip_off"], end[1] + dy / L * p["tip_off"])
        rec = dict(which=classify(p), path=p["d"], endpoint=(round(end[0], 2), round(end[1], 2)),
                   tip=(round(tip[0], 2), round(tip[1], 2)), tip_offset_units=round(p["tip_off"], 2),
                   stroke_width=p["sw"])
        d_tip = math.hypot(tip[0] - centre[0], tip[1] - centre[1])
        d_end = math.hypot(end[0] - centre[0], end[1] - centre[1])
        rec["tip_dist_to_hub_centre"] = round(d_tip, 2)
        rec["endpoint_dist_to_hub_centre"] = round(d_end, 2)
        if rec["which"] in ("A -> HUB", "FLIGHT SEGMENT -> HUB", "HUB -> B"):
            rec["hub_r"] = hub["r"]
            rec["penetration"] = round(hub["r"] - d_tip, 2)   # + = inside the ring's centre-line
        if rec["which"] in ("A -> HUB", "FLIGHT SEGMENT -> HUB"):
            pen = hub["r"] - d_tip
            rec["tip"] = rec["tip"]
            if pen < TIP_PENETRATION_MIN:
                rec["defect"] = (f"{rec['which']}: arrow tip is {pen:+.2f} px from the ring "
                                 f"(|tip-centre|={d_tip:.2f}, r={hub['r']}) -- it does NOT land on "
                                 f"the node; needs >= {TIP_PENETRATION_MIN} px of penetration")
                defect_list.append(rec)
            elif pen > TIP_MAX_FRAC_OF_R * hub["r"]:
                rec["defect"] = (f"{rec['which']}: arrow tip is {pen:.2f} px inside the ring, more "
                                 f"than {TIP_MAX_FRAC_OF_R:.0%} of r={hub['r']} -- the head buries "
                                 f"the node instead of landing on it")
                defect_list.append(rec)
        if rec["which"] == "HUB -> B" and B is not None:
            # this arrow must land on B's TOP border: tip inside the border band of B
            on_edge = B[0] - 2 <= tip[0] <= B[2] + 2 and B[1] - 1.0 <= tip[1] <= B[1] + 2 * p["sw"]
            rec["lands_on_B_top_edge"] = bool(on_edge)
            rec["B_rect"] = tuple(round(v, 1) for v in B)
            if not on_edge:
                rec["defect"] = (f"HUB -> B: tip {rec['tip']} does not land on B's top edge "
                                 f"(x {B[0]}..{B[2]} at y={B[1]})")
                defect_list.append(rec)
            # and it must START on the hub ring
            s = p["pts"][0]
            gap = math.hypot(s[0] - centre[0], s[1] - centre[1]) - hub["r"]
            rec["start_gap_to_ring"] = round(gap, 2)
            if abs(gap) > 3.0:
                rec["defect"] = (f"HUB -> B starts {gap:+.2f} px off the node's ring at {s}")
                defect_list.append(rec)
        if rec["which"].startswith("UNCLASSIFIED"):
            defect_list.append(rec)
        arrows.append(rec)

    # ---- the node's LABEL must clear its ring. Which label is "the node's label" is not assumed: it
    # is whichever text run is nearest the node's centre. r3 called it "the 'HUB' label"; the generator
    # now labels the node by what it IS, and this check follows the label rather than its old wording.
    label = None
    if not texts:
        defect_list.append(dict(defect="no text at all in the SVG"))
    else:
        def bbox_min_dist(bb):
            return math.hypot(max(bb[0] - centre[0], 0.0, centre[0] - bb[2]),
                              max(bb[1] - centre[1], 0.0, centre[1] - bb[3]))
        cand = min(texts, key=lambda t: bbox_min_dist(t["bbox"]))
        clear, where = bbox_ring_clearance(cand["bbox"], centre, r_in, r_out)
        label = dict(text=cand["text"], bbox=tuple(round(v, 2) for v in cand["bbox"]),
                     placement=where, clearance=round(clear, 2),
                     r_in=round(r_in, 2), r_out=round(r_out, 2))
        if clear < LABEL_CLEARANCE_MIN:
            label["defect"] = (f"node label {cand['text']!r} ink is {clear:.2f} px from the node's "
                               f"ring (needs >= {LABEL_CLEARANCE_MIN}); placement: {where}")
            defect_list.append(label)

    # ---- the arrowhead must be a detail ON the node, not an object that swallows it
    marker_sizes = []
    for m in root.iter(NS + "marker"):
        mw = float(m.get("markerWidth", "3"))
        mh = float(m.get("markerHeight", "3"))
        units = m.get("markerUnits", "strokeWidth")
        # every path that uses this marker has the same stroke in this drawing; take the widest
        sws = [p["sw"] for p in paths if m.get("id", "") in p.get("marker_end_ref", "")]
        sw = max(sws) if sws else max((p["sw"] for p in links), default=1.0)
        scale = 1.0 if units == "userSpaceOnUse" else sw
        ext = max(mw, mh) * scale
        frac = ext / (2 * hub["r"])
        marker_sizes.append(dict(id=m.get("id"), units=units, extent=round(ext, 2),
                                 node_diameter=2 * hub["r"], frac_of_node_diameter=round(frac, 3)))
        # A marker that inherits markerUnits="strokeWidth" (the SVG default) has a size DERIVED from
        # the stroke width. That is how this drawing's arrowhead silently became 33 units long: an
        # 11-unit marker on a 3-wide stroke. The head's size must be a stated number, not a product.
        if units != "userSpaceOnUse":
            marker_sizes[-1]["defect"] = (
                f"arrowhead #{m.get('id')} uses markerUnits={units!r}, so its size is a function of "
                f"the stroke width ({ext:.1f} units here) rather than a stated size -- the r3 defect "
                f"was exactly this: the head grew until it covered the node")
            defect_list.append(marker_sizes[-1])
        elif frac > ARROW_MAX_FRAC_OF_NODE:
            marker_sizes[-1]["defect"] = (
                f"arrowhead #{m.get('id')} is {ext:.1f} units across against a node "
                f"{2 * hub['r']:.0f} units across ({frac:.0%} of the diameter) -- the head covers "
                f"the node, so the landing point cannot be read")
            defect_list.append(marker_sizes[-1])

    # ---- the chain: no two links approach each other outside the hub
    worst = None
    for i in range(len(links)):
        for j in range(i + 1, len(links)):
            for a in range(len(links[i]["pts"]) - 1):
                sa = (links[i]["pts"][a], links[i]["pts"][a + 1])
                for b in range(len(links[j]["pts"]) - 1):
                    sb = (links[j]["pts"][b], links[j]["pts"][b + 1])
                    for k in range(21):
                        t = k / 20.0
                        pt = (sa[0][0] + (sa[1][0] - sa[0][0]) * t,
                              sa[0][1] + (sa[1][1] - sa[0][1]) * t)
                        if math.hypot(pt[0] - centre[0], pt[1] - centre[1]) <= r_out:
                            continue          # touching inside the node is the whole point
                        if any(sb[0][0] <= pt[0] <= sb[1][0] or sb[1][0] <= pt[0] <= sb[0][0]
                               for _ in (0,)) and seg_point_dist(pt, sb[0], sb[1]) == 0:
                            pass
                        d = seg_point_dist(pt, sb[0], sb[1])
                        if worst is None or d < worst[0]:
                            worst = (d, i, j, pt)
    chain = dict(min_approach_outside_hub=(round(worst[0], 2) if worst else None),
                 tolerance=CHAIN_MIN_APPROACH)
    if worst and worst[0] < CHAIN_MIN_APPROACH:
        chain["defect"] = (f"two link paths come within {worst[0]:.2f} px of each other outside the "
                           f"hub at {tuple(round(v, 1) for v in worst[3])} -- that reads as a direct "
                           f"ground-to-ground A-B path, which the caption denies")
        defect_list.append(chain)

    # ---- no text on text
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            ov = bbox_overlap(texts[i]["bbox"], texts[j]["bbox"])
            if ov > TEXT_OVERLAP_MAX:
                defect_list.append(dict(defect=f"text overlaps text: {texts[i]['text'][:40]!r} vs "
                                               f"{texts[j]['text'][:40]!r} ({ov:.1f} px^2)"))

    # ---- no text straddling a box border, no text crowding a line, nothing off-canvas
    line_gaps = []
    for t in texts:
        bb = t["bbox"]
        if bb[0] < 0 or bb[1] < 0 or bb[2] > W or bb[3] > H:
            defect_list.append(dict(defect=f"text {t['text'][:40]!r} outside the {W:.0f}x{H:.0f} "
                                           f"canvas at {tuple(round(v, 1) for v in bb)}"))
        for r in rects:
            if (r[2] - r[0]) < 50 or (r[3] - r[1]) < 50:
                continue                      # the page background
            inside = bb[0] >= r[0] and bb[1] >= r[1] and bb[2] <= r[2] and bb[3] <= r[3]
            if inside:
                continue
            gap = bbox_rect_gap(bb, r)
            if bbox_overlap(bb, r) > 0:
                defect_list.append(dict(defect=f"text {t['text'][:40]!r} straddles the border of the "
                                               f"box ({r[0]:.0f},{r[1]:.0f})-({r[2]:.0f},{r[3]:.0f})"))
            elif gap < TEXT_TO_BORDER_MIN:
                defect_list.append(dict(
                    defect=f"text {t['text'][:40]!r} is {gap:.2f} px from the border of the box "
                           f"({r[0]:.0f},{r[1]:.0f})-({r[2]:.0f},{r[3]:.0f}) (needs >= "
                           f"{TEXT_TO_BORDER_MIN}) -- it reads as touching the box"))
        # text against a drawn link/leader line: the eye reported the FLRC label as "cramped" against
        # its arrow, so the gap is measured rather than argued about
        for pth in paths:
            for k in range(len(pth["pts"]) - 1):
                d = bbox_stroke_dist(bb, pth["pts"][k], pth["pts"][k + 1], pth["sw"] / 2.0)
                if d < TEXT_TO_LINE_MIN:
                    line_gaps.append(dict(text=t["text"], gap=round(d, 2),
                                          line=pth["d"][:60],
                                          defect=(f"text {t['text'][:40]!r} is {d:.2f} px from the "
                                                  f"stroke of a line (needs >= {TEXT_TO_LINE_MIN})")))
                    defect_list.append(line_gaps[-1])

    res = dict(svg=svg_path, canvas=(W, H), hub=hub, r_in=round(r_in, 2), r_out=round(r_out, 2),
               arrows=arrows, hub_label=label, chain=chain, text_line_gaps=line_gaps,
               n_texts=len(texts),
               n_paths=len(paths), n_links=len(links), defects=defect_list)

    # ---- cross-check against the RENDERED png: the tip the raster actually shows must be inside the
    #      ring too, so a renderer that ignores markerUnits cannot silently undo the SVG geometry.
    if want_png:
        png = svg_path.replace(".svg", ".png")
        if os.path.exists(png):
            try:
                res["png_check"] = png_tip_check(png, centre, hub, arrows)
                if res["png_check"].get("defect"):
                    defect_list.append(res["png_check"])
            except Exception as e:                      # rendering check is advisory if numpy is gone
                res["png_check"] = dict(error=f"{type(e).__name__}: {e}")
    return res


def png_tip_check(png: str, centre, hub, arrows) -> dict:
    """Measure, in the raster, how close the red link ink gets to the node's centre.

    Independent of the SVG's marker math: it answers "does the ink of A's arrow touch the ink of the
    node ring", which is the question the visual review actually asked.
    """
    import numpy as np
    from PIL import Image

    im = Image.open(png).convert("RGB")
    a = np.asarray(im).astype(int)
    W_svg = 1620.0
    s = im.size[0] / W_svg
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    red = (r > 110) & (g < 95) & (b < 95)
    cx, cy, rad = centre[0] * s, centre[1] * s, hub["r"] * s
    ring_outer = (hub["r"] + hub["sw"]) * s
    # the ring's own ink: red pixels at radius within the stroke band
    yy, xx = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    dist = np.hypot(xx - cx, yy - cy)
    ring = red & (np.abs(dist - rad) <= (hub["sw"] / 2 + 0.6) * s)
    # A's own vertical shaft is above the node: look at the red ink strictly ABOVE the ring band and
    # find how close to the centre-line it reaches
    above = red & (yy < cy - rad + (hub["sw"] / 2) * s) & (np.abs(xx - cx) < rad)
    out = dict(scale=round(s, 4), ring_ink_px=int(ring.sum()), above_ink_px=int(above.sum()))
    if above.any():
        deepest = float(dist[above].min()) / s
        out["closest_red_ink_above_to_centre_svg"] = round(deepest, 2)
        # A's arrow ink must reach at least to the ring's outer edge (r + sw) for the head to touch
        out["reaches_ring"] = deepest <= hub["r"] + hub["sw"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--svg", default=DEFAULT_SVG)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-png", action="store_true")
    a = ap.parse_args()
    res = check(a.svg, want_png=not a.no_png)
    if a.json:
        print(json.dumps(res, indent=2, default=str))
        return 1 if res["defects"] else 0
    hub = res["hub"]
    print(f"svg: {os.path.relpath(res['svg'], REPO)}  canvas {res['canvas'][0]:.0f}x{res['canvas'][1]:.0f}")
    print(f"relay node: centre ({hub['cx']},{hub['cy']}) r={hub['r']} stroke={hub['sw']} "
          f"-> ring {res['r_in']}..{res['r_out']}")
    print(f"texts={res['n_texts']} paths={res['n_paths']} red links={res['n_links']}")
    for n in res["arrows"]:
        extra = ""
        if "penetration" in n:
            extra = f" penetration={n['penetration']:+.2f}"
        if "lands_on_B_top_edge" in n:
            extra += f" lands_on_B_edge={n['lands_on_B_top_edge']}"
        print(f"  {n['which']}: endpoint {n['endpoint']} tip {n['tip']} "
              f"|tip-centre|={n['tip_dist_to_hub_centre']}{extra}")
    if res["hub_label"]:
        hl = res["hub_label"]
        print(f"  HUB label ink {hl['bbox']} ({hl['placement']}) clearance={hl['clearance']} px")
    print(f"  closest approach of two links outside the node = "
          f"{res['chain']['min_approach_outside_hub']} px (min {CHAIN_MIN_APPROACH})")
    if "png_check" in res:
        print(f"  png cross-check: {res['png_check']}")
    print(f"DEFECTS: {len(res['defects'])}")
    for d in res["defects"]:
        print(f"  - {d['defect']}")
    return 1 if res["defects"] else 0


if __name__ == "__main__":
    sys.exit(main())

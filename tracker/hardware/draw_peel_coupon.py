#!/usr/bin/env python3
"""Draw the two peel-coupon specimens so the work order can actually be built.

WHY A DRAWING. docs/fab/hub-v9/PEEL-COUPON.md currently describes the specimens in prose. A coupon you
build with a soldering iron needs dimensions you can follow: where the land is, which edge the fillet
runs along, and where the load is applied. Prose produces a specimen that tests something else.

WHAT IS DRAWN, both from the SAME inputs as trade_study_wing_joint.py and peel_coupon_design.py so the
three cannot diverge:
  SPECIMEN B (peel)  a 0.6 mm FR4 coupon carrying ONE face land 4.0 x 1.2 mm, with a single fillet along
                     the land's 1.2 mm root edge, pulled perpendicular to the board at 2.0 mm from that
                     root (2.0 mm reproduces the wing's own moment-to-force ratio, L/2 over L). The
                     coupon is the stationary member and the land is the loaded one.
                     Drawn as TWO views, because no single view can show both a plan (where the land sits
                     and where the load lands) and the section that carries the perpendicular pull:
                       B1  plan -- coupon's top face, land 4.0 x 1.2 mm, fillet along the root edge, and
                           the load as an out-of-plane symbol (a circled dot) because in plan the pull
                           is normal to the page
                       B2  section -- substrate edge-on, land on top, corner fillet, load arm
                           dimensioned, the perpendicular pull as a vertical arrow
  SPECIMEN A (shear) a 0.6 mm tab soldered on BOTH faces into a 0.9 mm slot, pulled along the insertion
                     axis so both fillets load in shear. Drawn as a section along the insertion axis at
                     2:1, because that is the only view that shows the 6.0 mm insertion depth, the two
                     1.2 mm-wide solder joints in the 0.15 mm gaps, and the pull at the same time.

Numeric dimensions are drawn from the same constants as the trade study. This script draws; it does not
decide. Anything it cannot source is labelled, not invented -- in particular the earlier draft carried a
"hub wall 3.0 mm thick" dimension that no repo record owns, and the review caught it. The hub material
either side of the slot has no repo dimension, so it is drawn and labelled "not to scale" instead.

Five hard-won rules are encoded here, each measured on THIS drawing:

1. FORCE ARROWHEADS ARE DRAWN AS EXPLICIT POLYGONS, NOT SVG MARKERS. Three review cycles found the force
   graphic contradicting its own caption, twice via `<marker>` semantics: cycle 1 pointed the peel arrow
   INTO the land (an inverted test), and cycle 2's `arU` marker carried refX/refY = 5/8 with an arrow
   path, so `orient="auto"` rotated the head about a point offset from the shaft centre and the head
   rendered SIDEWAYS. (Direct pixel test on a minimal SVG: a vertical shaft's head came out pointing
   left, with its base where a tip should be.) A marker also cannot point a head back along its own
   path, which is what "pull away from the substrate" needs. An explicit polygon makes the direction a
   literal coordinate: the apex is where the load points. Do not reintroduce markers for a force arrow.

2. FEATURES ARE CALLED OUT BY NUMBERED BALLOONS, NOT TEXT LABELS ON LEADERS. Leaders from a stacked
   label column to features that sit behind other labels necessarily cross text -- measured here: the
   earlier version ran a fillet leader through the land label. Balloons put the callout number on (or
   beside) the feature and keep the legend lines in clear space, so no line can cross a word.

3. DIMENSION ARROWHEADS POINT AT THE EXTENSION LINES, apex outward, base inside the span. This was
   built inverted the first time (apex inward, base on the extension line) and a review named it:
   "arrowheads pointing into the dimension span, with their bases rather than their tips at the
   extension lines". Where the span is too narrow for two heads, they move outside and still point
   inward. Check the apex, not the triangle's bulk, when reading this code.

4. EVERY TEXT NODE GOES THROUGH esc(). A literal '<' in a text node once made rsvg-convert fail XML
   parsing and the script printed nothing at all, so a stale PNG was reviewed as if it were the new one.

5. THE RENDERER FAILS LOUDLY. A missing PNG after rendering is a non-zero exit carrying rsvg's own
   stderr, never a silent success.

Output: docs/fab/hub-v9/peel-coupon-specimens.svg (+ .png)
Run:    ~/venvs/kicad/bin/python tracker/hardware/draw_peel_coupon.py
"""
import os
import shutil
import subprocess
import sys

# --- the same constants the trade study and the coupon design use --------------------------------
LAND_LEN_MM = 4.0      # [repo] pad 4.0 mm along the insertion axis
LAND_WID_MM = 1.2      # [repo] pad 1.2 mm
INSERT_DEPTH_MM = 6.0  # [repo] ADR-046 insertion depth
SLOT_W_MM = 0.9        # [repo] ADR-046 slot width, nominal +/-0.10
SLOT_TOL_MM = 0.10     # [repo] ADR-046 slot tolerance
TAB_T_MM = 0.6         # [repo] ADR-046 tab thickness = substrate
LOAD_ARM_MM = LAND_LEN_MM / 2.0   # 2.0 mm, the wing's L/2-over-L lever ratio
SOLDER_GAP_MM = SLOT_W_MM - TAB_T_MM              # 0.30 mm TOTAL, shared by the two faces (ADR 4.1)

# The load case, computed the same way peel_coupon_design.py computes it (13.88 g wing, 10 g shock,
# shared over 4 lands). Shown on the drawing so the spec is complete rather than merely shape-accurate.
WING_MASS_G = 13.88
SHOCK_G = 10.0
G = 9.80665
PER_LAND_N = (WING_MASS_G * 1e-3) * G * SHOCK_G / 4.0     # 0.340 N

SCALE_B = 46.0         # svg units per mm for specimen B (both views)
SCALE_A = 75.0         # svg units per mm for specimen A -- ~1.6:1, enough to show the 0.15 mm gaps
OUT = sys.argv[1] if len(sys.argv) > 1 else "docs/fab/hub-v9/peel-coupon-specimens.svg"

# A portrait sheet. The first version was 1720 x 1560 landscape and drew both specimens stacked in the
# left two-thirds, leaving the right third empty -- a review called that out.
W, H = 1320, 1900

RED = "#b00020"
GOLD, GOLD_DK = "#e0a53a", "#8a4d0c"
GREEN, GREEN_DK = "#2f6b3a", "#1d4425"
COPPER, COPPER_DK = "#c8751a", "#8a4d0c"
INK, GREY = "#111", "#666"
STEEL, STEEL_DK = "#dfe6ee", "#33475b"


def mm(v, scale=SCALE_B):
    return v * scale


def esc(s):
    """Escape XML special characters. A literal '<' in text (e.g. "<1.2x") is parsed as a tag start and
    makes the whole SVG unparseable -- measured: rsvg-convert 'XML parse error ... StartTag: invalid
    element name'. Every text node goes through this."""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def txt(p, x, y, s, size=13, fill=INK, weight=None, anchor=None):
    """One text node. EVERY string that reaches the SVG goes through esc() here."""
    a = f' font-weight="{weight}"' if weight else ""
    an = f' text-anchor="{anchor}"' if anchor else ""
    p.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}"{a}{an}>{esc(s)}</text>')


def hdr(p, x, y, t):
    txt(p, x, y, t, size=20, weight="bold")


def sub(p, x, y, t):
    txt(p, x, y, t, size=13.5, fill="#444")


def note(p, x, y, t, fill=GREY, size=12.5):
    txt(p, x, y, t, size=size, fill=fill)


def balloon(p, x, y, n, r=10.5):
    """A numbered balloon sitting on (or just beside) the feature it names.

    The callout convention used instead of leader lines + stacked labels (rule 2): the number carries no
    long text and the legend line lives in clear space, so no drawn line has to cross a word.
    """
    p.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#ffffff" stroke="{INK}" stroke-width="1.2"/>')
    txt(p, x, y + 4.5, str(n), size=13, weight="bold", anchor="middle")


def stub(p, x1, y1, x2, y2, color=INK):
    """Short leader from a balloon to its feature. Kept short so it cannot run into a text box."""
    p.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1"/>')


def held(p, x1, x2, y, color=INK):
    """A fixed-support symbol: hatching under the member that the fixture restrains."""
    for i in range(int(x1), int(x2), 16):
        p.append(f'<line x1="{i}" y1="{y}" x2="{i-11}" y2="{y+11}" stroke="{color}" '
                 f'stroke-width="1"/>')
    p.append(f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{color}" stroke-width="1.6"/>')


def arrow_v(p, x, y_tail, y_tip, head_len=18, head_w=7.5, width=3.5, color=RED):
    """A force arrow whose head is an explicit polygon.

    y_tail is where the load is applied (on the specimen); y_tip is the arrowhead apex, i.e. the
    direction the load acts. The head is coordinates, not marker semantics -- see rule 1 above.
    """
    s = 1 if y_tip > y_tail else -1
    base = y_tip - s * head_len
    p.append(f'<line x1="{x}" y1="{y_tail}" x2="{x}" y2="{base + s}" stroke="{color}" '
             f'stroke-width="{width}"/>')
    p.append(f'<path d="M{x},{y_tip} L{x-head_w},{base} L{x+head_w},{base} z" fill="{color}"/>')


def _ext_v(p, x, y, y_feat):
    """Vertical extension line: starts just off the feature and runs just past the dimension line."""
    ya, yb = (y_feat + 4, y + 9) if y_feat < y else (y - 9, y_feat - 4)
    p.append(f'<line x1="{x}" y1="{ya}" x2="{x}" y2="{yb}" stroke="{INK}" stroke-width="1"/>')


def _ext_h(p, y, x, x_feat):
    xa, xb = (x_feat + 4, x + 9) if x_feat < x else (x - 9, x_feat - 4)
    p.append(f'<line x1="{xa}" y1="{y}" x2="{xb}" y2="{y}" stroke="{INK}" stroke-width="1"/>')


def dim_h(p, x1, x2, y, label, y_feat=None, label_side="auto"):
    """Horizontal dimension: extension lines, opposed arrowheads with their APEX ON the extension
    lines, and the text clear of both. Below 34 units there is no room for two heads between the
    extension lines, so the heads move outside and still point inward (rule 3)."""
    lo, hi = (x1, x2) if x1 <= x2 else (x2, x1)
    span = hi - lo
    if y_feat is not None:
        _ext_v(p, lo, y, y_feat)
        _ext_v(p, hi, y, y_feat)
    narrow = span < 34
    x_lo, x_hi = (lo - 16, hi + 16) if narrow else (lo, hi)
    p.append(f'<line x1="{x_lo}" y1="{y}" x2="{x_hi}" y2="{y}" stroke="{INK}" stroke-width="1.2"/>')
    if narrow:      # heads outside, apex pointing inward at the extension lines
        p.append(f'<path d="M{lo},{y} L{lo-14},{y-5} L{lo-14},{y+5} z" fill="{INK}"/>')
        p.append(f'<path d="M{hi},{y} L{hi+14},{y-5} L{hi+14},{y+5} z" fill="{INK}"/>')
    else:           # heads inside, apex on the extension lines, base inside the span
        p.append(f'<path d="M{lo},{y} L{lo+13},{y-5} L{lo+13},{y+5} z" fill="{INK}"/>')
        p.append(f'<path d="M{hi},{y} L{hi-13},{y-5} L{hi-13},{y+5} z" fill="{INK}"/>')
    if label_side == "left":
        txt(p, lo - 20, y + 5, label, anchor="end")
    elif label_side == "right":
        txt(p, hi + (20 if narrow else 14), y + 5, label)
    elif label_side == "inside" or span >= 105:
        txt(p, (lo + hi) / 2, y - 8, label, anchor="middle")
    else:
        # too narrow for the text between the extension lines -- put it outside them, never on top
        txt(p, hi + (20 if narrow else 14), y + 5, label)


def dim_v(p, y1, y2, x, label, x_feat=None, label_side="auto"):
    """Vertical dimension. Same convention as dim_h (rule 3); the default label goes to the right."""
    lo, hi = (y1, y2) if y1 <= y2 else (y2, y1)
    span = hi - lo
    if x_feat is not None:
        _ext_h(p, lo, x, x_feat)
        _ext_h(p, hi, x, x_feat)
    narrow = span < 34
    y_lo, y_hi = (lo - 16, hi + 16) if narrow else (lo, hi)
    p.append(f'<line x1="{x}" y1="{y_lo}" x2="{x}" y2="{y_hi}" stroke="{INK}" stroke-width="1.2"/>')
    if narrow:
        p.append(f'<path d="M{x},{lo} L{x-5},{lo-14} L{x+5},{lo-14} z" fill="{INK}"/>')
        p.append(f'<path d="M{x},{hi} L{x-5},{hi+14} L{x+5},{hi+14} z" fill="{INK}"/>')
    else:
        p.append(f'<path d="M{x},{lo} L{x-5},{lo+13} L{x+5},{lo+13} z" fill="{INK}"/>')
        p.append(f'<path d="M{x},{hi} L{x-5},{hi-13} L{x+5},{hi-13} z" fill="{INK}"/>')
    if label_side == "left":
        txt(p, x - 16, (lo + hi) / 2 + 4, label, anchor="end")
    elif label_side == "inside" or span >= 60:
        txt(p, x + 12, (lo + hi) / 2 + 4, label)
    else:
        txt(p, x + 20, (lo + hi) / 2 + 4, label)


def draw_b(p):
    """SPECIMEN B -- peel, as a PLAN (B1) and a SECTION (B2).

    FORCE DIRECTION IS THE POINT of this specimen. Cycle 1 pointed the arrow DOWN into the land (a
    vision review: 'the arrow points down toward the land and substrate, not upward away from them. The
    word "pull" does not resolve that graphical contradiction'); cycle 2 fixed the caption while the
    head still rendered sideways. In B2 here: tail ON the land's top face, apex 150 units straight up,
    i.e. the land pulled OFF the substrate. The fillet root is the pivot, so the land sees a moment
    about one edge -- which is what makes this peel and not pure tension.

    Why two views: cycle 3's review objected that one view mixed projections. A view that shows the
    4.0 x 1.2 mm face and where the load lands is a PLAN; a view that shows a 0.6 mm substrate edge-on
    with a perpendicular pull and a corner fillet is a SECTION. They cannot be the same view, so B1 is
    the plan (load as an out-of-plane circled dot) and B2 is the section (load as an arrow away from
    the board). The load line is the section plane, so B2 is taken from B1 and no dashed cut line is
    needed. Both views show the coupon hatched as the member the fixture holds, because a peel test
    needs a named reaction path: the coupon is stationary and the land is loaded.
    """
    hdr(p, 60, 92, "SPECIMEN B — PEEL  (Option B's failure mode)")
    sub(p, 60, 116, f"{TAB_T_MM:.1f} mm FR4 coupon · ONE fillet along a single {LAND_WID_MM:.1f} mm "
                    f"edge · load applied {LOAD_ARM_MM:.1f} mm from the fillet root · two views "
                    "(B1 plan, B2 section)")

    # ---------- B1: plan ----------
    p.append('<rect x="42" y="150" width="606" height="470" fill="#f6f8f6" stroke="#cfd8cf"/>')
    txt(p, 58, 182, "B1 — PLAN (view down onto the coupon's top face)", size=14, weight="bold")
    txt(p, 58, 214, "1  COPPER LAND — 4.0 × 1.2 mm, the loaded member", size=13, fill=COPPER_DK)
    txt(p, 58, 240, "2  FILLET (solder) — the peel root, along this 1.2 mm edge", size=13, fill=COPPER_DK)
    txt(p, 58, 266, "3  LOAD ⊙ — F is out of the page, 2.0 mm from the fillet root", size=13, fill=RED)
    txt(p, 58, 292, "11  the coupon's own solderable pad — the stationary member (see B2)", size=13,
        fill=COPPER_DK)
    txt(p, 58, 318, "coupon = the stationary member; the fixture holds its left end", size=12.5,
        fill=GREEN)

    bx, by = 190, 420                            # coupon top-left
    bw, bh = mm(8), mm(2.0)                      # 8 mm of coupon shown, 2 mm of its width
    lw, lh = mm(LAND_LEN_MM), mm(LAND_WID_MM)
    lx = bx + bw - lw                            # land flush to the coupon's right-hand end
    ly = by + (bh - lh) / 2                      # centred across the coupon's width
    ax = lx + lw / 2                             # load at the land's centre = 2.0 mm from the root
    sl = ly + lh / 2
    p.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="{GREEN}" '
             f'stroke="{GREEN_DK}" stroke-width="1.5"/>')
    # the coupon's own solderable pad, exposed beside the root fillet -- the SAME member B2 calls
    # out as 11. Leaving it out of the plan made B1 and B2 disagree about the joint; a review said so.
    p.append(f'<rect x="{lx-120}" y="{ly}" width="120" height="{lh}" fill="{COPPER}" '
             f'stroke="{COPPER_DK}" stroke-width="1"/>')
    p.append(f'<rect x="{lx}" y="{ly}" width="{lw}" height="{lh}" fill="{COPPER}" '
             f'stroke="{COPPER_DK}" stroke-width="1.2"/>')
    p.append(f'<rect x="{lx-13}" y="{ly}" width="13" height="{lh}" fill="{GOLD}" '
             f'stroke="{COPPER_DK}" stroke-width="1.2"/>')
    p.append(f'<circle cx="{ax}" cy="{sl}" r="14" fill="#fff" stroke="{RED}" stroke-width="2.5"/>')
    p.append(f'<circle cx="{ax}" cy="{sl}" r="4.2" fill="{RED}"/>')
    held(p, bx, bx + 90, by + bh)                # the fixture holds the coupon's left end
    balloon(p, lx + 34, sl, 1, r=10)             # on the land
    balloon(p, lx - 34, sl, 2, r=10)             # beside the fillet band, short stub to it
    stub(p, lx - 24, sl, lx - 8, sl, color=INK)
    balloon(p, ax + 46, sl, 3, r=10)             # beside the out-of-page load symbol
    stub(p, ax + 36, sl, ax + 16, sl, color=INK)
    balloon(p, lx - 74, sl, 11, r=9)             # on the exposed pad
    stub(p, lx - 74, sl + 9, lx - 74, ly + lh - 2, color=INK)

    dim_h(p, lx, bx + bw, 560, f"land {LAND_LEN_MM:.1f} mm", y_feat=ly + lh, label_side="inside")
    dim_v(p, ly, ly + lh, bx - 46, f"land {LAND_WID_MM:.1f} mm", x_feat=bx, label_side="left")
    note(p, 58, 596, "coupon offcut — FR4, 0.6 mm thick. The land's 4.0 mm runs along the")
    note(p, 58, 614, "insertion axis; the fillet edge and the load line both run across its 1.2 mm")

    # ---------- B2: section ----------
    p.append('<rect x="672" y="150" width="606" height="470" fill="#fdf7f0" stroke="#e6d6c4"/>')
    txt(p, 688, 182, "B2 — SECTION along the insertion axis, through the load line", size=14,
        weight="bold")
    txt(p, 688, 214, "F — pull AWAY from the substrate, perpendicular to the board", size=13,
        weight="bold", fill=RED)
    txt(p, 688, 240, f"applied {LOAD_ARM_MM:.1f} mm from the fillet root, {PER_LAND_N:.3f} N per land "
                     f"at the coupon's 10 g shock", size=13, fill=RED)
    txt(p, 688, 268, "4  COPPER LAND in section (thickness drawn exaggerated)", size=13, fill=COPPER_DK)
    txt(p, 688, 294, "5  FILLET (solder) — the peel root, the pivot", size=13, fill=COPPER_DK)
    txt(p, 688, 320, "6  COUPON SUBSTRATE — FR4, 0.6 mm, held fixed at its left end.", size=13,
        fill=GREEN)
    txt(p, 688, 344, "     The land is held along one 1.2 mm edge only, so it sees a", size=13,
        fill=GREEN)
    txt(p, 688, 366, "     MOMENT about that edge: PEEL, not pure tension.", size=13, fill=GREEN)
    txt(p, 688, 392, "11  the coupon's own solderable pad — the stationary", size=13, fill=COPPER_DK)
    txt(p, 688, 412, "      mating member the root fillet wets. The land is", size=13, fill=COPPER_DK)
    txt(p, 688, 432, "      bonded along THIS edge only.", size=13, fill=COPPER_DK)

    sx, sy = 880, 500                            # substrate top-left, edge-on in this view
    sw, sh = mm(8), mm(TAB_T_MM)
    kt = 20
    kx = sx + sw - mm(LAND_LEN_MM)               # the peel root, at the land's left end
    kax = kx + mm(LAND_LEN_MM) / 2               # the load again 2.0 mm from the root
    p.append(f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" fill="{GREEN}" '
             f'stroke="{GREEN_DK}" stroke-width="1.5"/>')
    p.append(f'<rect x="{kx}" y="{sy-kt}" width="{mm(LAND_LEN_MM)}" height="{kt}" fill="{COPPER}" '
             f'stroke="{COPPER_DK}" stroke-width="1.2"/>')
    # the stationary mating member: the coupon's own solderable pad, drawn as the thin copper strip
    # the root fillet wets. The loaded land touches the FR4 with no bond except along this one edge.
    p.append(f'<rect x="{kx - 120}" y="{sy-6}" width="140" height="6" fill="{COPPER}" '
             f'stroke="{COPPER_DK}" stroke-width="0.8"/>')
    p.append(f'<path d="M{kx},{sy-kt} L{kx-22},{sy} L{kx},{sy} z" fill="{GOLD}" '
             f'stroke="{COPPER_DK}" stroke-width="1.2"/>')
    # THE COUPON IS HELD AT ITS LEFT END -- the same end B1 hatches. Hatching the loaded end would
    # state a different restraint from the legend, which a review caught.
    held(p, sx, sx + 120, sy + sh)
    arrow_v(p, kax, sy - kt - 2, sy - kt - 150)
    balloon(p, kx + 80, sy - kt / 2, 4, r=9)     # on the land, in section
    balloon(p, kx - 150, sy - 46, 11, r=9)       # well clear of callout 6 and the hatch
    stub(p, kx - 141, sy - 44, kx - 60, sy - 4, color=INK)
    balloon(p, kx - 46, sy - 16, 5, r=9)         # beside the fillet triangle
    stub(p, kx - 37, sy - 12, kx - 16, sy - 6, color=INK)
    balloon(p, sx + 140, sy + sh + 4, 6, r=9)    # on the substrate, clear of the load-arm extension
    # the stub must END INSIDE the green body, not on its bottom outline -- a review read the earlier
    # endpoint as landing in the support hatching instead of on the FR4.
    stub(p, sx + 131, sy + sh + 2, sx + 96, sy + sh - 9, color=INK)

    dim_h(p, kx, kax, 560, f"load arm {LOAD_ARM_MM:.1f} mm", y_feat=sy - kt, label_side="left")
    dim_v(p, sy, sy + sh, sx - 72, f"substrate {TAB_T_MM:.1f} mm", x_feat=sx, label_side="left")


def draw_a(p):
    """SPECIMEN A -- shear: a tab soldered on both faces inside a slotted hub edge, as a SECTION along
    the insertion axis at 2:1.

    WHY THIS VIEW. An earlier draft drew the joint as two walls flanking a gap seen across the slot.
    That view cannot show the 6.0 mm insertion depth, cannot show the solder as a 6 mm-long bond on each
    face, and cannot place the fillets on the faces they are on -- the review said so: fillets "drawn
    inside the slot near the same end, rather than on the two opposite wall faces". Cutting ALONG the
    insertion axis instead puts everything in one view, to scale, at 2:1 so the 0.15 mm solder gap is
    visible:

      * the hub edge, with the 0.9 mm-wide slot cut 6.0 mm deep into it (vertical axis = insertion axis)
      * the 0.6 mm tab centred in the slot, emerging 0.6 mm above the hub's edge face so the pull is
        visible, and inserted 6.0 mm
      * the solder as the two 0.15 mm strips the tab is bonded to -- one per face, 6 mm long, which is
        the "soldered on BOTH faces" the specimen exists to test
      * the pull along the insertion axis, so both bonds load in shear

    The lateral extent of the hub material either side of the slot is NOT a repo dimension, so it is
    drawn schematically and labelled "not to scale"; the 0.9, 0.6, 0.15 and 6.0 mm numbers all are.
    """
    # THE PANEL BACKGROUND MUST BE PAINTED BEFORE ANYTHING IT SITS BEHIND. It was appended after the
    # heading on the first attempt, so the tinted rect covered the heading and the subtitle -- and
    # neither a text-position check nor a vision pass can see a text node that has been overdrawn.
    p.append('<rect x="42" y="676" width="1236" height="944" fill="#f6f8f6" stroke="#cfd8cf"/>')
    hdr(p, 60, 706, "SPECIMEN A — SHEAR  (Option A's failure mode)")
    sub(p, 60, 730, f"{TAB_T_MM:.1f} mm tab soldered on BOTH faces into a {SLOT_W_MM:.1f} mm slot · "
                    "pull along the insertion axis · SECTION, ~1.6:1")
    txt(p, 58, 772, "7  FILLET — face 1: solder in the 0.15 mm gap, 6.0 mm long", size=13, fill=COPPER_DK)
    txt(p, 58, 798, "8  FILLET — face 2: the same on the tab's other face", size=13, fill=COPPER_DK)
    txt(p, 58, 824, "9  TAB — 0.6 mm thick, seated 6.0 mm into the slot", size=13, fill=STEEL_DK)
    txt(p, 58, 850, "10  HUB MATERIAL — the slot's walls (lateral extent not to scale)", size=13,
        fill=GREEN)
    txt(p, 58, 880, "the slot's walls resist rotation about an edge, so both fillets load", size=12.5,
        fill=GREY)
    txt(p, 58, 898, "mainly in SHEAR — the loading this coupon is meant to confirm, and the", size=12.5,
        fill=GREY)
    txt(p, 58, 916, "reason Option A is expected to out-perform a face joint. The hub is the fixed", size=12.5,
        fill=GREY)
    txt(p, 58, 934, "member (hatched); only the tab is pulled.", size=12.5, fill=GREY)
    txt(p, 700, 758, "F — pull ALONG the insertion axis", size=15, weight="bold", fill=RED)
    txt(p, 700, 782, "out of the slot; shear — BOTH fillets loaded in-plane", size=13, fill=RED)

    s = SCALE_A
    ym = 1100                                    # the hub's edge face = the slot mouth
    cx = 640                                     # slot centre line
    slot_w = mm(SLOT_W_MM, s)
    tab_w = mm(TAB_T_MM, s)
    gap = (slot_w - tab_w) / 2                   # 0.15 mm per side
    depth = mm(INSERT_DEPTH_MM, s)
    hub_w = mm(3.0, s)                           # schematic lateral extent (not a repo dimension)
    x_slot_l, x_slot_r = cx - slot_w / 2, cx + slot_w / 2
    x_tab_l, x_tab_r = cx - tab_w / 2, cx + tab_w / 2
    y_tab_top = ym - mm(0.6, s)
    y_tip = ym + depth

    hub_drop = depth + 60                        # the hub only needs to extend past the tab tip
    p.append(f'<rect x="{x_slot_l - hub_w}" y="{ym}" width="{hub_w}" height="{hub_drop}" '
             f'fill="{GREEN}" stroke="{GREEN_DK}" stroke-width="1.5"/>')
    p.append(f'<rect x="{x_slot_r}" y="{ym}" width="{hub_w}" height="{hub_drop}" '
             f'fill="{GREEN}" stroke="{GREEN_DK}" stroke-width="1.5"/>')
    # the solder: one 0.15 mm strip per face, running the full 6.0 mm bond length
    p.append(f'<rect x="{x_slot_l}" y="{ym}" width="{gap}" height="{depth}" fill="{GOLD}" '
             f'stroke="{COPPER_DK}" stroke-width="0.6"/>')
    p.append(f'<rect x="{x_tab_r}" y="{ym}" width="{gap}" height="{depth}" fill="{GOLD}" '
             f'stroke="{COPPER_DK}" stroke-width="0.6"/>')
    p.append(f'<rect x="{x_tab_l}" y="{y_tab_top}" width="{tab_w}" height="{depth + mm(0.6, s)}" '
             f'fill="{STEEL}" stroke="{STEEL_DK}" stroke-width="1.6"/>')
    held(p, x_slot_l - hub_w, x_slot_l, ym + hub_drop)        # the hub is held fixed during the pull
    held(p, x_slot_r, x_slot_r + hub_w, ym + hub_drop)
    arrow_v(p, cx, y_tab_top, y_tab_top - 110)
    # slot-mouth datum
    p.append(f'<line x1="{x_slot_l - hub_w - 20}" y1="{ym}" x2="{x_slot_r + hub_w + 150}" y2="{ym}" '
             f'stroke="{INK}" stroke-width="0.9" stroke-dasharray="12 5 3 5"/>')

    # the solder strips are the 0.15 mm lanes just inside each slot wall
    strip_l, strip_r = x_slot_l + gap / 2, x_slot_r - gap / 2
    balloon(p, strip_l - 40, ym + 300, 7, r=9)                     # beside the face-1 solder strip
    stub(p, strip_l - 31, ym + 300, strip_l + 1, ym + 300, color=INK)
    balloon(p, strip_r + 40, ym + 300, 8, r=9)                     # beside the face-2 solder strip
    stub(p, strip_r + 31, ym + 300, strip_r - 1, ym + 300, color=INK)
    balloon(p, cx, ym + depth * 0.72, 9, r=10)                     # on the tab, below the joints
    balloon(p, x_slot_l - hub_w + 40, ym + 120, 10, r=10)          # on the hub material

    dim_h(p, x_slot_l, x_slot_r, y_tab_top - 150, f"slot {SLOT_W_MM:.1f} mm (±{SLOT_TOL_MM:.2f}) — "
          f"tab {TAB_T_MM:.1f} mm centred, {gap/s:.2f} mm per side", y_feat=ym,
          label_side="right")
    dim_v(p, ym, y_tip, x_slot_r + hub_w + 60, f"insertion depth {INSERT_DEPTH_MM:.1f} mm",
          x_feat=x_slot_r + hub_w, label_side="inside")


def notes(p):
    y = 1660
    txt(p, 60, y, "What the two specimens decide", size=17, weight="bold")
    rows = [
        ("measured", "peak force at failure, in N, per specimen"),
        ("samples", "n >= 5 per condition"),
        ("derived", "knockdown_B = (strength of the same fillet in pure tension) / (measured peel "
                    "strength)"),
        ("reference", "knockdown_B's numerator is a THIRD coupon, defined in PEEL-COUPON.md and not "
                      "drawn on this sheet"),
        ("then", "feed knockdown_B into trade_study_wing_joint.py's peel_knockdown input and re-run"),
        ("rule", "~4x -> Option B margin 7.8x (comfortable);  below 1.2x -> Option B approaches Option A"),
        ("variants", "as-soldered · cold-soak (the wing sees −40 °C) · deliberately weak fillet · the "
                     "build's alloy"),
        ("fillet size", "NOT specified here: fillet leg length is the technique variable the coupon "
                        "measures — record each specimen's fillet profile"),
    ]
    for i, (k, v) in enumerate(rows):
        yy = y + 28 + i * 26
        txt(p, 60, yy, k, size=14, weight="bold")
        txt(p, 200, yy, v, size=14, fill="#333")
    txt(p, 60, H - 14, "dimensions from tracker/hardware/trade_study_wing_joint.py and "
                       "peel_coupon_design.py (same constants) · drawn by draw_peel_coupon.py",
        size=12, fill=GREY)


def main():
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         f'font-family="DejaVu Sans, Helvetica, sans-serif">',
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
         '<text x="60" y="36" font-size="22" font-weight="bold">'
         'ADF-046 wing joint — peel coupon specimens</text>',
         '<text x="60" y="62" font-size="12.5" fill="#666">'
         'Sheet scope: PEEL specimen B (B1/B2) and SHEAR specimen A; the pure-tension reference '
         'coupon is a separate work-order item (see PEEL-COUPON.md).</text>']
    draw_b(p)
    draw_a(p)
    notes(p)
    p.append('</svg>')
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w") as fh:
        fh.write("\n".join(p))
    print(f"wrote {OUT}")

    # LAYOUT GATE. tracker/hardware/svg_layout_guard.py measures each label with the same font metrics
    # rsvg/Pango uses and refuses a canvas whose text collides, sits on a filled shape, or runs past the
    # frame. Every defect class this drawing produced across four review cycles was one of those, and
    # all of them are visible in the SVG -- so they should be caught here, not by a vision consultant.
    # Imported lazily so the script still runs (with a warning) if the guard is not present.
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from svg_layout_guard import audit_svg
    except ImportError as e:
        print(f"LAYOUT GUARD SKIPPED: cannot import svg_layout_guard ({e})")
    else:
        probs = audit_svg(OUT)
        print(f"LAYOUT GUARD: {'ok' if not probs else str(len(probs)) + ' collision(s)'}")
        if probs:
            print(f"LAYOUT GUARD FAILED: {len(probs)} collision(s) -- not rendering a bad drawing")
            for q in probs:
                print(f"  - {q}")
            return 1
    png = OUT.replace(".svg", ".png")
    if not shutil.which("rsvg-convert"):
        print("RENDER FAILED: rsvg-convert not found -- SVG written, PNG NOT produced")
        return 1
    r = subprocess.run(["rsvg-convert", "-w", "1680", OUT, "-o", png],
                       capture_output=True, text=True)
    if not os.path.exists(png):
        # A renderer that fails and says nothing is how this file went missing unnoticed once already.
        # Report the tool's own error and exit non-zero.
        print(f"RENDER FAILED: rsvg-convert rc={r.returncode}")
        print(f"  stderr: {(r.stderr or r.stdout or '(no output)').strip()[:400]}")
        return 1
    if r.returncode != 0:
        print(f"RENDER FAILED: rc={r.returncode} but a file exists; "
              f"{(r.stderr or '').strip()[:300]}")
        return 1
    print(f"wrote {png} ({os.path.getsize(png)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

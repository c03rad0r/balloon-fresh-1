#!/usr/bin/env python3
"""Draw the two peel-coupon specimens so the work order can actually be built.

WHY A DRAWING. docs/fab/hub-v9/PEEL-COUPON.md currently describes the specimens in prose. A coupon you
build with a soldering iron needs dimensions you can follow: where the land is, which edge the fillet
runs along, and where the load is applied. Prose produces a specimen that tests something else.

WHAT IS DRAWN, both from the SAME inputs as trade_study_wing_joint.py and peel_coupon_design.py so the
three cannot diverge:
  SPECIMEN B (peel)  a 0.6 mm FR4 coupon carrying ONE face land 4.0 x 1.2 mm, with a single fillet along
                     the 1.2 mm edge, pulled perpendicular to the board at 2.0 mm from the fillet root
                     (2.0 mm reproduces the wing's own moment-to-force ratio, L/2 over L).
  SPECIMEN A (shear) a 0.6 mm tab 6.0 x 1.2 mm soldered on BOTH faces into a 0.9 mm slot, pulled along
                     the insertion axis so both fillets load in shear.

Numeric dimensions are drawn from the same constants as the trade study. This script draws; it does not
decide. Anything it cannot source is labelled, not invented.

Output: docs/fab/hub-v9/peel-coupon-specimens.svg (+ .png)
Run:    python3 tracker/hardware/draw_peel_coupon.py
"""
import os
import shutil
import subprocess
import sys

# --- the same constants the trade study and the coupon design use --------------------------------
LAND_LEN_MM = 4.0      # [repo] pad 4.0 mm along the insertion axis
LAND_WID_MM = 1.2      # [repo] pad 1.2 mm
INSERT_DEPTH_MM = 6.0  # [repo] ADR-046 insertion depth
SLOT_W_MM = 0.9        # [repo] ADR-046 slot width
TAB_T_MM = 0.6         # [repo] ADR-046 tab thickness = substrate
LOAD_ARM_MM = LAND_LEN_MM / 2.0   # 2.0 mm, the wing's L/2-over-L lever ratio

SCALE = 46.0           # svg units per mm, chosen so 6 mm is legible
OUT = sys.argv[1] if len(sys.argv) > 1 else "docs/fab/hub-v9/peel-coupon-specimens.svg"

W, H = 1720, 1560      # grown after a vision review found top/left/bottom clipping


def mm(v):
    return v * SCALE


def esc(s):
    """Escape XML special characters. A literal '<' in text (e.g. "<1.2x") is parsed as a tag start and
    makes the whole SVG unparseable -- measured: rsvg-convert 'XML parse error ... StartTag: invalid
    element name'. Every text node goes through this."""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def hdr(p, x, y, t):
    p.append(f'<text x="{x}" y="{y}" font-size="20" font-weight="bold">{t}</text>')


def sub(p, x, y, t):
    p.append(f'<text x="{x}" y="{y}" font-size="14" fill="#444">{t}</text>')


def dim_h(p, x1, x2, y, label, color="#111"):
    p.append(f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{color}" stroke-width="1.3"/>')
    p.append(f'<line x1="{x1}" y1="{y-7}" x2="{x1}" y2="{y+7}" stroke="{color}" stroke-width="1.3"/>')
    p.append(f'<line x1="{x2}" y1="{y-7}" x2="{x2}" y2="{y+7}" stroke="{color}" stroke-width="1.3"/>')
    p.append(f'<path d="M{x1+11},{y} L{x1},{y-4.5} L{x1},{y+4.5} z" fill="{color}"/>')
    p.append(f'<path d="M{x2-11},{y} L{x2},{y-4.5} L{x2},{y+4.5} z" fill="{color}"/>')
    p.append(f'<text x="{(x1+x2)/2}" y="{y-11}" font-size="14" fill="{color}" '
             f'text-anchor="middle">{label}</text>')


def arrow_down(p, x, y0, y1, label, color="#b00020"):
    p.append(f'<line x1="{x}" y1="{y0}" x2="{x}" y2="{y1}" stroke="{color}" stroke-width="3" '
             f'marker-end="url(#ar)"/>')
    p.append(f'<text x="{x+10}" y="{(y0+y1)/2}" font-size="14" fill="{color}">{label}</text>')


def draw_b(p):
    """SPECIMEN B -- peel: one fillet along a single edge of a face land.

    FORCE DIRECTION IS THE POINT of this specimen, and the first version had it WRONG: the arrow pointed
    DOWN into the land. A peel test pulls the land AWAY from the substrate. A vision review caught it:
    'the arrow points down toward the land and substrate, not upward away from them. The word "pull"
    does not resolve that graphical contradiction.' The arrow now points UP, away, and is labelled as
    the load direction rather than as a verb.
    """
    hdr(p, 90, 90, "SPECIMEN B — PEEL  (Option B's failure mode)")
    sub(p, 90, 116, "0.6 mm FR4 coupon · ONE fillet along a single 1.2 mm edge · load at 2.0 mm from the root")

    bx, by = 140, 330                     # board top-left, well inside the frame
    bw, bh = mm(12), mm(TAB_T_MM)         # a coupon 12 mm wide, one substrate thick
    p.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="#2f6b3a" '
             f'stroke="#1d4425" stroke-width="1.5"/>')
    p.append(f'<text x="{bx}" y="{by+bh+22}" font-size="13" fill="#2f6b3a">'
             f'coupon substrate 0.6 mm FR4</text>')

    # the face land, sitting ON TOP of the coupon, flush to its right edge
    lw, lh = mm(LAND_LEN_MM), mm(LAND_WID_MM)
    lx, ly = bx + bw - lw, by - lh
    p.append(f'<rect x="{lx}" y="{ly}" width="{lw}" height="{lh}" fill="#c8751a" '
             f'stroke="#8a4d0c" stroke-width="1.2"/>')
    p.append(f'<text x="{lx-6}" y="{ly-8}" font-size="13.5" fill="#8a4d0c" text-anchor="end">'
             'copper land</text>')

    # the fillet along the land's LEFT edge (the peel root)
    fx = lx
    p.append(f'<path d="M {fx} {by-lh} q -20 {lh} 0 {lh}" fill="#e0a53a" stroke="#c8751a" '
             f'stroke-width="2"/>')
    p.append(f'<text x="{fx-30}" y="{by+40}" font-size="13" fill="#8a4d0c" text-anchor="end">'
             'fillet (1.2 mm long)</text>')

    dim_h(p, lx, bx + bw, by + bh + 44, f"land {LAND_LEN_MM:.1f} mm")
    dim_h(p, fx, lx, by + bh + 96, f"load arm {LOAD_ARM_MM:.1f} mm")

    # THE LOAD POINTS AWAY FROM THE SUBSTRATE. The first version pointed it down into the land, which
    # inverts the test's meaning -- a vision review caught the contradiction with the word "pull".
    ax = lx + lw / 2
    ay0, ay1 = by - lh - 130, by - lh - 16
    p.append(f'<line x1="{ax}" y1="{ay0}" x2="{ax}" y2="{ay1}" stroke="#b00020" stroke-width="3.5" '
             f'marker-end="url(#arU)"/>')
    p.append(f'<text x="{ax+14}" y="{ay0+6}" font-size="15" font-weight="bold" fill="#b00020">'
             'F — pull AWAY from the substrate</text>')
    p.append(f'<text x="{ax+14}" y="{ay0+28}" font-size="13" fill="#b00020">'
             'perpendicular to the board plane</text>')
    p.append(f'<text x="{bx}" y="{ay0-26}" font-size="13" fill="#777">'
             'the fillet root is the pivot: the land sees a moment about one edge, so this tests PEEL, '
             'not pure tension.</text>')


def draw_a(p):
    """SPECIMEN A -- shear: a tab soldered on both faces inside a slot.

    REBUILT after a vision review: 'The gap between the green shapes could suggest a slot, yet no clearly
    identifiable tab is shown entering it. Two distinct fillets are not visibly established.' The tab is
    now drawn INSIDE the slot with a contrasting fill, both fillets labelled by leader, and the pull is
    along the insertion axis. The whole view sits well inside the frame (the first version was clipped at
    the bottom boundary).
    """
    hdr(p, 90, 700, "SPECIMEN A — SHEAR  (Option A's failure mode)")
    sub(p, 90, 726, "0.6 mm tab soldered on BOTH faces into a 0.9 mm slot · pull along the insertion axis")

    # the slotted hub wall, seen in section: two walls with a gap
    wx = 200
    wy = 800
    wall_t, gap = mm(3.0), mm(SLOT_W_MM)
    wall_h = mm(10.0)
    p.append(f'<rect x="{wx}" y="{wy}" width="{wall_t}" height="{wall_h}" fill="#2f6b3a" '
             f'stroke="#1d4425" stroke-width="1.5"/>')
    p.append(f'<rect x="{wx+wall_t+gap}" y="{wy}" width="{wall_t}" height="{wall_h}" '
             f'fill="#2f6b3a" stroke="#1d4425" stroke-width="1.5"/>')
    p.append(f'<text x="{wx}" y="{wy+wall_h+22}" font-size="13" fill="#2f6b3a">'
             f'hub wall · slot {SLOT_W_MM:.1f} mm</text>')

    # the tab, drawn clearly INSIDE the slot, in a contrasting colour so it cannot be missed
    tx = wx + wall_t + (gap - mm(TAB_T_MM)) / 2      # centred in the gap
    tw, th = mm(TAB_T_MM), mm(INSERT_DEPTH_MM)
    p.append(f'<rect x="{tx}" y="{wy}" width="{tw}" height="{th}" fill="#dfe6ee" '
             f'stroke="#33475b" stroke-width="2"/>')
    p.append(f'<text x="{tx+tw/2}" y="{wy+th+30}" font-size="13.5" fill="#33475b" '
             f'text-anchor="middle">tab {TAB_T_MM:.1f} mm thick, seated in the slot</text>')

    # fillets on BOTH faces, each with a leader so the pairing is explicit
    p.append(f'<path d="M {tx} {wy+14} q -16 20 0 44" fill="#e0a53a" stroke="#c8751a" stroke-width="2"/>')
    p.append(f'<path d="M {tx+tw} {wy+14} q 16 20 0 44" fill="#e0a53a" stroke="#c8751a" stroke-width="2"/>')
    p.append(f'<line x1="{tx-30}" y1="{wy+30}" x2="{tx-8}" y2="{wy+34}" stroke="#8a4d0c" stroke-width="1"/>')
    p.append(f'<text x="{tx-34}" y="{wy+28}" font-size="13" fill="#8a4d0c" text-anchor="end">'
             'fillet — face 1</text>')
    p.append(f'<line x1="{tx+tw+30}" y1="{wy+30}" x2="{tx+tw+8}" y2="{wy+34}" stroke="#8a4d0c" '
             f'stroke-width="1"/>')
    p.append(f'<text x="{tx+tw+34}" y="{wy+28}" font-size="13" fill="#8a4d0c">'
             'fillet — face 2</text>')

    dim_h(p, wx, tx, wy - 26, f"slot {SLOT_W_MM:.1f} mm")

    # the load: pull along the insertion axis, i.e. straight out of the slot. Labelled with the
    # direction and the mechanism, not just a verb.
    ax = tx + tw / 2
    ay0, ay1 = wy + th + 96, wy + th + 16
    p.append(f'<line x1="{ax}" y1="{ay0}" x2="{ax}" y2="{ay1}" stroke="#b00020" stroke-width="3.5" '
             f'marker-end="url(#arU)"/>')
    p.append(f'<text x="{ax+14}" y="{ay0+6}" font-size="15" font-weight="bold" fill="#b00020">'
             'F — pull ALONG the insertion axis</text>')
    p.append(f'<text x="{ax+14}" y="{ay0+28}" font-size="13" fill="#b00020">'
             'shear — BOTH fillets loaded in-plane</text>')
    p.append(f'<text x="{wx}" y="{wy-96}" font-size="13" fill="#777">'
             'the slot prevents rotation about an edge: the fillet area carries the load in SHEAR, which '
             'is the whole reason Option A out-performs a face joint.</text>')


def notes(p):
    y = 1290      # below view A, with clearance -- the first version overlapped it
    p.append(f'<text x="60" y="{y}" font-size="17" font-weight="bold">What the two specimens decide</text>')
    rows = [
        ("measured", "peak force at failure, in N, per specimen"),
        ("samples", "n >= 5 per condition"),
        ("derived", "knockdown_B = (pure tensile strength of the same fillet) / (measured peel strength)"),
        ("then", "feed knockdown_B into trade_study_wing_joint.py's peel_knockdown input and re-run"),
        ("rule", "~4x -> Option B margin 7.8x (comfortable);  below 1.2x -> Option B approaches Option A"),
        ("variants", "as-soldered · cold-soak (wing sees -40 C) · a deliberately weak fillet · the build's own alloy"),
    ]
    for i, (k, v) in enumerate(rows):
        yy = y + 26 + i * 26
        p.append(f'<text x="60" y="{yy}" font-size="14" font-weight="bold">{k}</text>')
        p.append(f'<text x="200" y="{yy}" font-size="14" fill="#333">{v}</text>')
    p.append(f'<text x="60" y="{H-14}" font-size="12" fill="#777">'
             'dimensions from tracker/hardware/trade_study_wing_joint.py and peel_coupon_design.py '
             '(same constants) · generated by draw_peel_coupon.py</text>')


def main():
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         f'font-family="DejaVu Sans, Helvetica, sans-serif">',
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
         '<defs><marker id="ar" markerWidth="10" markerHeight="10" refX="8" refY="5" '
         'orient="auto"><path d="M0,1 L10,5 L0,9 z" fill="#b00020"/></marker>'
         '<marker id="arU" markerWidth="10" markerHeight="10" refX="5" refY="8" '
         'orient="auto"><path d="M1,10 L5,0 L9,10 z" fill="#b00020"/></marker></defs>',
         '<text x="60" y="28" font-size="22" font-weight="bold">'
         'ADF-046 wing joint — peel coupon specimens</text>']
    draw_b(p)
    draw_a(p)
    notes(p)
    p.append('</svg>')
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w") as fh:
        fh.write("\n".join(p))
    print(f"wrote {OUT}")
    png = OUT.replace(".svg", ".png")
    if not shutil.which("rsvg-convert"):
        print("WARNING: rsvg-convert not found -- SVG written, PNG NOT produced")
        return 0
    r = subprocess.run(["rsvg-convert", "-w", "1900", OUT, "-o", png],
                       capture_output=True, text=True)
    if not os.path.exists(png):
        # A renderer that fails and says nothing is how this file went missing unnoticed once already.
        # Report the tool's own error and exit non-zero.
        print(f"RENDER FAILED: rsvg-convert rc={r.returncode}")
        print(f"  stderr: {(r.stderr or r.stdout or '(no output)').strip()[:400]}")
        return 1
    if r.returncode != 0:
        print(f"RENDER WARNING: rc={r.returncode} but a file exists; "
              f"{(r.stderr or '').strip()[:200]}")
    print(f"wrote {png} ({os.path.getsize(png)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

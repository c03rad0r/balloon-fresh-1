#!/usr/bin/env python3
"""Generate the edge-launch drawing for the JLCPCB query -- v2, after a vision review found 9 defects.

WHAT v1 GOT WRONG (found by reviewing the rendered PNG, not by reading the code):
  1. severe text collisions in the lower half -- pad-row labels ran into the requirements column, and
     the red edge annotation crossed the requirements block
  2. the solder fillet was LABELLED but never DRAWN
  3. the mating/contact arrangement was placement-only: no tab copper, no contact, no engagement shown
  4. dimension arrows pointed the same way at both ends, so they read like motion arrows
  5. the 6.0 mm line was ambiguous -- tab length, travel, or engagement depth?
  6. no extension lines tying dimensions to surfaces; the board-to-tab gap was never dimensioned
  7. the lower pad-row view had no orientation cue linking it to the cross-section
  8. an orphaned curved stroke near pad 3
  9. large blank area up top versus crowded annotations below

FIX: a proper TWO-VIEW sheet with hard-separated regions.
  VIEW A  cross-section through the contact row (the joint, drawn)
  VIEW B  plan view of one connector, showing the 4 pads, pitch and the routed edge
  A notes band underneath, in its own ruled column, so nothing can overlap the drawing.

Usage: make_edge_section.py [out.svg]
"""
import os
import shutil
import subprocess
import sys

W, H = 1560, 1180
OUT_SVG = sys.argv[1] if len(sys.argv) > 1 else "docs/fab/jlc-query/edge-launch-cross-section.svg"

# ------------------------------------------------------------------ VIEW A geometry
A_X0, A_X1 = 90, 470          # board body
A_EDGE = A_X1                 # routed edge
A_TAB0, A_TAB1 = A_EDGE + 26, 700
A_TOP, A_BOT = 250, 340       # 0.6 mm drawn as 90 units
CU = 11                       # copper thickness


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def dim_h(x1, x2, y, label, color="#111", above=True, external=False):
    """A horizontal dimension, drawn the conventional way.

    extension = a line at each end, OUTWARD arrowheads pointing at the extension lines.
    `external` = arrows drawn OUTSIDE the span, for spans too small to hold them internally
    (the 0.30 mm gap). The previous version drew inward-pointing heads that met in the middle
    and read as a bow-tie; that was defect 2 of the vision review.
    """
    o = []
    o.append(f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{color}" stroke-width="1.3"/>')
    o.append(f'<line x1="{x1}" y1="{y-8}" x2="{x1}" y2="{y+8}" stroke="{color}" stroke-width="1.3"/>')
    o.append(f'<line x1="{x2}" y1="{y-8}" x2="{x2}" y2="{y+8}" stroke="{color}" stroke-width="1.3"/>')
    if external:
        o.append(f'<path d="M{x1-12},{y} L{x1},{y-4.5} L{x1},{y+4.5} z" fill="{color}"/>')
        o.append(f'<path d="M{x2+12},{y} L{x2},{y-4.5} L{x2},{y+4.5} z" fill="{color}"/>')
    else:
        o.append(f'<path d="M{x1+12},{y} L{x1},{y-4.5} L{x1},{y+4.5} z" fill="{color}"/>')
        o.append(f'<path d="M{x2-12},{y} L{x2},{y-4.5} L{x2},{y+4.5} z" fill="{color}"/>')
    ly = y - 10 if above else y + 20
    o.append(f'<text x="{(x1+x2)/2}" y="{ly}" font-size="13.5" fill="{color}" '
             f'text-anchor="middle">{esc(label)}</text>')
    return "\n".join(o)


def view_a():
    p = []
    p.append(f'<text x="60" y="132" font-size="19" font-weight="bold">'
             'VIEW A — cross-section through the contact row</text>')

    # board substrate, with the four layers hinted
    p.append(f'<rect x="{A_X0}" y="{A_TOP}" width="{A_X1-A_X0}" height="{A_BOT-A_TOP}" '
             f'fill="#2f6b3a" stroke="#1d4425" stroke-width="1.5"/>')
    for i in (1, 2, 3):
        ly = A_TOP + (A_BOT - A_TOP) * i / 4
        p.append(f'<line x1="{A_X0}" y1="{ly}" x2="{A_EDGE}" y2="{ly}" stroke="#1d4425" '
                 f'stroke-width="0.8" opacity="0.55"/>')
    p.append(f'<text x="{A_X0+12}" y="{A_TOP+52}" font-size="14" fill="#ffffff">'
             '0.6 mm FR4, 4 layer</text>')

    # the pad: ON TOP of the substrate, terminating exactly at the edge
    p.append(f'<rect x="{A_X0+150}" y="{A_TOP-CU}" width="{A_EDGE-(A_X0+150)}" height="{CU}" '
             f'fill="#c8751a" stroke="#8a4d0c" stroke-width="1.2"/>')

    # FIX: the cut line must COINCIDE with the copper end (defect 6). The copper pad ends at A_EDGE, so
    # the cut line is drawn exactly at A_EDGE -- no offset that could read as a setback.
    p.append(f'<line x1="{A_EDGE}" y1="{A_TOP-40}" x2="{A_EDGE}" y2="{A_BOT+40}" '
             f'stroke="#b00020" stroke-width="3" stroke-dasharray="10,5"/>')

    # mating tab, SEATED: its facing copper meets the board edge across the 0.30 mm gap
    p.append(f'<rect x="{A_TAB0}" y="{A_TOP}" width="{A_TAB1-A_TAB0}" height="{A_BOT-A_TOP}" '
             f'fill="#dfe6ee" stroke="#5a6b7d" stroke-width="1.5"/>')
    p.append(f'<rect x="{A_TAB0}" y="{A_TOP}" width="{A_TAB1-A_TAB0}" height="6" '
             f'fill="#c8751a" stroke="#8a4d0c" stroke-width="0.9"/>')

    # LABELS in dedicated bands. Top band y<A_TOP-100 holds the copper + tab labels; nothing else goes
    # there, which is what stops the collisions the vision review found.
    p.append(f'<text x="{A_X0+150}" y="{A_TOP-104}" font-size="14" fill="#8a4d0c">'
             'exposed copper pad (F.Cu) — solderable</text>')
    p.append(f'<text x="{A_TAB0+4}" y="{A_TOP-104}" font-size="14" fill="#33475b">'
             'mating wing tab — 0.6 mm FR4, copper facing the board</text>')

    # THE JOINT, drawn as a fillet that visibly wets BOTH surfaces: it starts on the board's copper
    # (left, at A_EDGE) and rises onto the tab's copper (right, at A_TAB0). The previous version drew
    # a floating curve that did not touch the pad -- vision-review defect 4.
    p.append(f'<path d="M {A_EDGE} {A_TOP-CU} '
             f'L {A_TAB0} {A_TOP-CU} '
             f'L {A_TAB0} {A_TOP+22} '
             f'Q {A_EDGE+6} {A_TOP+16} {A_EDGE} {A_TOP-CU+2} Z" '
             f'fill="#e0a53a" stroke="#c8751a" stroke-width="1.6"/>')
    p.append(f'<text x="{A_TAB0+10}" y="{A_TOP+16}" font-size="13" fill="#8a4d0c">'
             'solder fillet — wets pad and tab</text>')

    # the 0.30 mm gap, dimensioned with EXTERNAL arrows (too small for internal ones) and a leader
    p.append(dim_h(A_EDGE, A_TAB0, A_TOP - 150, "0.30 mm", "#33475b", external=True))
    p.append(f'<line x1="{(A_EDGE+A_TAB0)/2}" y1="{A_TOP-142}" x2="{(A_EDGE+A_TAB0)/2}" '
             f'y2="{A_TOP-60}" stroke="#33475b" stroke-width="0.9" stroke-dasharray="3,3"/>')
    p.append(f'<text x="{A_EDGE+40}" y="{A_TOP-168}" font-size="12.5" fill="#33475b">'
             'slot 0.9 mm minus tab 0.6 mm = 0.30 mm</text>')

    # pad length, below the board
    p.append(dim_h(A_X0 + 150, A_EDGE, A_BOT + 30, "pad 4.0 mm", "#111", above=False))

    # INSERTION DEPTH: measured on the SEATED joint -- from the board edge inwards 6.0 mm, drawn inside
    # the board region so it cannot be confused with tab length (vision-review defect 5).
    p.append(dim_h(A_X0 + 40, A_EDGE, A_BOT + 86, "insertion depth 6.0 mm (tab seated into the slot)",
                   "#33475b", above=False))

    # engagement direction, in its own band clear of everything
    p.append(f'<path d="M {A_TAB1} {A_TOP-40} L {A_TAB0+30} {A_TOP-40}" '
             f'stroke="#33475b" stroke-width="2" marker-end="url(#ah)"/>')
    p.append(f'<text x="{A_TAB0+36}" y="{A_TOP-46}" font-size="13" fill="#33475b">'
             'tab travels toward the board</text>')
    return "\n".join(p)


def view_b():
    """Plan view of one connector: 4 pads, pitch, and the routed edge."""
    p = []
    x0, y0 = 790, 150
    p.append(f'<text x="{x0}" y="{y0-18}" font-size="19" font-weight="bold">'
             'VIEW B — connector row, viewed from the component side</text>')
    # the routed edge runs vertically on the RIGHT of the pads
    p.append(f'<rect x="{x0}" y="{y0}" width="250" height="150" fill="#2f6b3a" '
             f'stroke="#1d4425" stroke-width="1.5"/>')
    p.append(f'<line x1="{x0+250}" y1="{y0}" x2="{x0+250}" y2="{y0+150}" '
             f'stroke="#b00020" stroke-width="2.6" stroke-dasharray="10,5"/>')
    p.append(f'<text x="{x0+256}" y="{y0+80}" font-size="13.5" fill="#b00020" '
             f'font-weight="bold">routed edge</text>')
    # 4 pads: 4.0 mm along the insertion axis (horizontal), 1.2 mm wide, pitch 1.8 mm
    # drawn: 4.0 mm -> 100 units, so 1.2 mm -> 30 units, 1.8 mm pitch -> 45 units
    for i in range(4):
        py = y0 + 14 + i * 33
        p.append(f'<rect x="{x0+250-100}" y="{py}" width="100" height="26" '
                 f'fill="#c8751a" stroke="#8a4d0c" stroke-width="1.1"/>')
        p.append(f'<text x="{x0+250-100-8}" y="{py+18}" font-size="12.5" '
                 f'text-anchor="end">{i+1}</text>')
    # pitch dimension
    yy = y0 + 14 + 4 * 33 + 4
    p.append(f'<line x1="{x0+250-100}" y1="{y0+150+40}" x2="{x0+250}" y2="{y0+150+40}" '
             f'stroke="#111" stroke-width="1.3"/>')
    p.append(f'<text x="{x0+250-50}" y="{y0+150+34}" font-size="13" text-anchor="middle">'
             '4.0 mm (insertion axis)</text>')
    p.append(f'<text x="{x0}" y="{y0+150+64}" font-size="13">pad 1.2 mm wide · pitch 1.8 mm '
             f'· 0.6 mm between pad edges</text>')
    p.append(f'<text x="{x0}" y="{y0+150+92}" font-size="13" fill="#b00020">'
             'the edge cut runs along the pad ends — copper is cut flush, this is the contact</text>')
    p.append(f'<text x="{x0}" y="{y0+150+112}" font-size="13" fill="#b00020">'
             'surface. each pad is exposed copper, NOT a castellated hole.</text>')
    return "\n".join(p)


def notes():
    """A ruled notes band in its OWN region, so it cannot overlap the drawing."""
    x, y, w = 60, 620, 1440
    rows = [
        ("Solder mask", "opening ends BEFORE the routed edge; the pad itself is unmasked"),
        ("Surface finish", "ENIG preferred (flat, solderable after assembly); HASL acceptable"),
        ("Copper to edge", "0.00 mm — INTENTIONAL. This is the electrical contact surface."),
        ("NOT wanted", "no castellation, no edge plating. Plain exposed copper at a plain cut."),
        ("Edge positional tolerance", "routed edge vs copper — PLEASE ADVISE your capability"),
        ("Panel tabs", "keep clear of these edges; they are mating surfaces"),
        ("Burrs / peeling", "please advise mitigation if the process produces them at the cut"),
    ]
    p = [f'<text x="{x}" y="{y}" font-size="18" font-weight="bold">Requirements</text>']
    p.append(f'<line x1="{x}" y1="{y+10}" x2="{x+w}" y2="{y+10}" stroke="#ccc" stroke-width="1.2"/>')
    for i, (k, v) in enumerate(rows):
        ry = y + 42 + i * 34
        p.append(f'<line x1="{x}" y1="{ry+10}" x2="{x+w}" y2="{ry+10}" stroke="#eee" stroke-width="1"/>')
        p.append(f'<text x="{x+4}" y="{ry+2}" font-size="14" font-weight="bold">{esc(k)}</text>')
        p.append(f'<text x="{x+300}" y="{ry+2}" font-size="14" fill="#333">{esc(v)}</text>')
    return "\n".join(p)


def main():
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family="DejaVu Sans, Helvetica, sans-serif">',
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
         '<text x="60" y="62" font-size="27" font-weight="bold">'
         'Edge-launch wing socket — hub_board_v9, J_W1…J_W4</text>',
         '<text x="60" y="92" font-size="15" fill="#444">'
         'Interface for JLCPCB fabrication review · dimensions in mm · '
         'copper deliberately terminates at the routed edge</text>']
    p.append(view_a())
    p.append(view_b())
    p.append(notes())
    p.append('<defs><marker id="ah" markerWidth="10" markerHeight="10" refX="8" refY="5" '
             'orient="auto"><path d="M0,1 L10,5 L0,9 z" fill="#33475b"/></marker></defs>')
    p.append(f'<text x="60" y="{H-16}" font-size="12" fill="#777">'
             'geometry measured from tracker/hardware/hub_board_v9.kicad_pcb; '
             'interface per docs/adr/046-wing-board-interface.md</text>')
    p.append('</svg>')

    os.makedirs(os.path.dirname(OUT_SVG) or ".", exist_ok=True)
    with open(OUT_SVG, "w") as fh:
        fh.write("\n".join(p))
    print(f"wrote {OUT_SVG}")
    png = OUT_SVG.replace(".svg", ".png")
    if shutil.which("rsvg-convert"):
        subprocess.run(["rsvg-convert", "-w", "2000", OUT_SVG, "-o", png],
                       capture_output=True, text=True)
        if os.path.exists(png):
            print(f"wrote {png} ({os.path.getsize(png)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

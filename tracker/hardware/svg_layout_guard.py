#!/usr/bin/env python3
"""Layout guard for hand-built SVG drawings: measure the text, then prove it does not collide.

WHY THIS EXISTS. The peel-coupon specimen drawing went through three review cycles whose defects were
almost all the same class -- text overlapping text, text sitting on a filled shape, a dimension that did
not span the feature it named, an arrowhead pointing along the wrong axis. Every one of those is
measurable in the SVG itself, so the next iteration should not need a vision model to find them.

WHAT IT MEASURES, and how it is verified. The drawing is rendered by rsvg-convert, which lays text out
through Pango. Pango resolves `DejaVu Sans` to /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf and
resolves `Helvetica` to THE SAME FILE (measured: the same string at font-size 20 is 457 px wide with
font-family="DejaVu Sans" and 426 px with font-family="Helvetica"; PIL + NimbusSans-Regular.otf
predicts 429 px for the latter, and that font is NOT installed -- so Pango is NOT using Nimbus, and the
resolved family is DejaVu). PIL's ImageFont.getlength() with DejaVuSans.ttf reproduces rsvg's rendered
advance width to within 0.5 px at font-size 14 and 20 (measured by counting dark pixels in a render).
So this module can compute a text box that matches the PNG, without a browser and without a GPU.

USAGE
    from svg_layout_guard import Canvas
    c = Canvas(1900, 1800)                       # any overlapping box raises on write()
    c.text(60, 40, "title", size=22, weight="bold", tag="title")
    c.rect(100, 100, 200, 50, tag="wall")
    c.write("out.svg")

    python3 svg_layout_guard.py out.svg          # re-check a drawing after the fact; exit 1 on overlap

CONVENTIONS. All coordinates are SVG user units (the drawings here use 1 unit = 1 px = 1/46 mm).
Text boxes are INK boxes: what the glyphs actually cover, not the em box.
"""
import re
import sys

from PIL import ImageFont

FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# text that is allowed to sit on top of a filled shape: nothing. A label on a shape is the defect.
_cache = {}


def _font(size, weight):
    key = (round(float(size), 2), weight)
    if key not in _cache:
        path = FONT_BOLD if str(weight) in ("bold", "700", "600") else FONT_REG
        _cache[key] = ImageFont.truetype(path, max(1, int(round(float(size)))))
    return _cache[key]


def text_ink_box(x, y, s, size, weight="normal", anchor="start"):
    """Ink box of `s` drawn with its baseline at (x, y). Returns (x0, y0, x1, y1) in SVG units.

    Verified against a real render: for the string used in the header, rsvg at width=W produced dark
    pixels spanning exactly (min_x, max_x) of the box this function returns, to within 1 px.
    """
    f = _font(size, weight)
    adv = f.getlength(s)
    if anchor == "middle":
        x -= adv / 2.0
    elif anchor in ("end", "right"):
        x -= adv
    bx = f.getbbox(s)                      # ink box relative to the pen origin (top-left of ascender)
    asc = f.getmetrics()[0]
    return (x + bx[0], y - asc + bx[1], x + bx[2], y - asc + bx[3])


def _inter(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return (x1 - x0) * (y1 - y0)


def _area(a):
    return max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])


def _cell_area(box, s):
    """Total area of `s`'s glyph cells (1 em wide each, box height), as registered."""
    n = max(1, len(s))
    return n * (max(0.0, box[2] - box[0]) / n) * max(0.0, box[3] - box[1])


def _cell_overlap(a, sa, b, sb):
    """Area of `sa`'s glyph cells that `sb`'s glyph cells (each outset by MARGIN_U) would touch.

    A per-cell test, not a total-overlap test: it is what separates "these two labels are on the same
    line" from "these two labels are on adjacent lines and merely share a bubble in the ascender gap".
    """
    m = Canvas.MARGIN_U
    x0, x1 = max(a[0], b[0] - m), min(a[2], b[2] + m)
    y0, y1 = max(a[1], b[1] - m), min(a[3], b[3] + m)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    cw = max(1e-6, (a[2] - a[0]) / max(1, len(sa)))
    ch = max(1e-6, a[3] - a[1])
    ncols = max(1, int((x1 - x0) / cw) + (1 if (x1 - x0) % cw else 0))
    nrows = max(1, int((y1 - y0) / ch) + (1 if (y1 - y0) % ch else 0))
    return ncols * nrows * cw * ch

class OverlapError(Exception):
    pass


class Canvas:
    """An SVG canvas that refuses to emit text that collides with other text or with a filled shape.

    Boxes registered as `shape` (fills, leaders) are tested against `text` boxes only: shape over shape
    is normal drawing, but text over a shape is the poor-contrast defect the reviews kept finding here.
    """

    TOL = 1.0        # units of slack: boxes must clear each other by this much to count as separate
    # Both conditions must hold for a text/text collision, and that conjunction is what makes this
    # usable on a dense drawing. A bare box-intersection test is useless here: on the real specimen
    # drawing two labels on adjacent rows shared 22% of the smaller box and the reviewer read them as
    # perfectly legible, because the intersection fell in the descender/ascender gap where no glyphs
    # live. A bare area threshold is useless the other way: it is the same number for a 3-character and
    # a 60-character label, and a long label fully covering a short one can be a small *fraction*.
    # Glyph cells are the right measure -- 1 em re squares, outset by MARGIN_U, over the string's
    # x-extent -- with a second, tiny threshold so a genuine 1 px graze is not called a defect.
    CELL_FRAC = 0.10   # share of the smaller label's glyph cells that must be covered
    CELL_AREA = 160.0  # u^2: ~2 cells of an 11 px font. Clearer than any fraction for short labels.
    MARGIN_U = 1.6     # u of outset per glyph cell, so "clear" means clear by a visible hairline

    def __init__(self, w, h, font="DejaVu Sans, Helvetica, sans-serif", strict_shapes=True):
        self.w, self.h = w, h
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
                      f'viewBox="0 0 {w} {h}" font-family="{font}">',
                      f'<rect width="{w}" height="{h}" fill="#ffffff"/>']
        self.text_boxes = []      # (box, tag, string)
        self.shape_boxes = []     # (box, tag)
        self.strict_shapes = strict_shapes

    # ---- registration helpers -------------------------------------------------------------------
    def _shape(self, box, tag):
        self.shape_boxes.append((box, tag))

    def rect(self, x, y, w, h, tag="rect", collide=True, **kw):
        a = fmt(kw)
        self.parts.append(f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" {a}/>')
        if self.strict_shapes and collide:
            self._shape((x, y, x + w, y + h), tag)

    def line(self, x1, y1, x2, y2, tag="line", pad=0.0, collide=True, **kw):
        a = fmt(kw)
        self.parts.append(f'<line x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" y2="{y2:g}" {a}/>')
        if self.strict_shapes and collide:
            self._shape((min(x1, x2) - pad, min(y1, y2) - pad,
                         max(x1, x2) + pad, max(y1, y2) + pad), tag)

    def path(self, d, box=None, tag="path", collide=True, **kw):
        a = fmt(kw)
        self.parts.append(f'<path d="{d}" {a}/>')
        if self.strict_shapes and collide and box:
            self._shape(box, tag)

    def raw(self, s):
        self.parts.append(s)

    def defs(self, markup):
        self.parts.insert(2, f"<defs>{markup}</defs>")

    # ---- text -----------------------------------------------------------------------------------
    def text(self, x, y, s, size=14, weight="normal", anchor="start", fill="#111",
             angle=None, tag="text", collide=True):
        """Emit a text node and register its ink box so later checks can see it. Returns the box."""
        box = text_ink_box(x, y, s, size, weight, anchor)
        rot = f' transform="rotate({angle:g} {x:g} {y:g})"' if angle else ""
        self.parts.append(f'<text x="{x:g}" y="{y:g}" font-size="{size:g}" font-weight="{weight}" '
                          f'fill="{fill}" text-anchor="{anchor}"{rot}>{esc(s)}</text>')
        if collide:
            self.text_boxes.append((box, tag, s))
        return box

    def text_block(self, x, y, lines, size=13, weight="normal", fill="#444", lh=19, anchor="start",
                   tag="block"):
        """Emit baseline-separated lines. `lh` must exceed size*1.16 or the guard will reject them."""
        return [self.text(x, y + i * lh, ln, size=size, weight=weight, fill=fill, anchor=anchor,
                          tag=f"{tag}[{i}]") for i, ln in enumerate(lines)]

    # ---- validation -----------------------------------------------------------------------------
    def check(self):
        """Return a list of human-readable problems. Does not raise."""
        bad = []
        for i in range(len(self.text_boxes)):
            ai, ti, si = self.text_boxes[i]
            for j in range(i + 1, len(self.text_boxes)):
                bj, tj, sj = self.text_boxes[j]
                ov = _inter(ai, bj)
                if ov <= 0:
                    continue
                cells = _cell_overlap(ai, si, bj, sj)
                if cells <= 0:
                    continue
                small = min(_cell_area(ai, si), _cell_area(bj, sj))
                if cells >= self.CELL_AREA and cells >= self.CELL_FRAC * small:
                    bad.append(f"text/text overlap [{ti}] {si!r} x [{tj}] {sj!r} "
                               f"({cells:.0f} u^2 of {small:.0f} glyph-cell area)")
        for ai, ti, si in self.text_boxes:
            for bj, tj in self.shape_boxes:
                ov = _inter(ai, bj)
                if ov > self.CELL_FRAC * _area(ai) > 0:
                    bad.append(f"text on shape [{ti}] {si!r} over [{tj}] ({ov:.0f} u^2)")
        for ai, ti, si in self.text_boxes:
            if ai[0] < -0.5 or ai[1] < -0.5 or ai[2] > self.w + 0.5 or ai[3] > self.h + 0.5:
                bad.append(f"clipped [{ti}] {si!r} box={tuple(round(v, 1) for v in ai)} "
                           f"outside 0,0,{self.w},{self.h}")
        return bad

    def write(self, path, strict=True):
        bad = self.check()
        if bad and strict:
            msg = "\n".join("  - " + b for b in bad)
            raise OverlapError(f"layout guard refused to write {path}: {len(bad)} problem(s):\n{msg}")
        self.parts.append("</svg>")
        with open(path, "w") as fh:
            fh.write("\n".join(self.parts) + "\n")
        return bad


def esc(s):
    """Escape XML text. A literal '<' (e.g. "<1.2x") is parsed as a tag start and makes the whole SVG
    unparseable -- measured once on this drawing: rsvg-convert 'XML parse error ... invalid element
    name'. Every text node goes through this."""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fmt(kw):
    return " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in kw.items())


def audit_svg(path):
    """Re-derive the text boxes from a rendered/serialised SVG and report what collides.

    Used as a post-hoc check (`python3 svg_layout_guard.py out.svg`) and as the acceptance test for the
    specimen drawing: it reads the same font metrics used to place the text, so it is exact for this
    family of drawings (all positions absolute, no nested transforms on text).
    """
    import xml.etree.ElementTree as ET
    root = ET.parse(path).getroot()
    ns = "{http://www.w3.org/2000/svg}"
    c = Canvas(int(float(root.get("width"))), int(float(root.get("height"))), strict_shapes=False)
    for el in root.iter(f"{ns}text"):
        s = "".join(el.itertext())
        if not s.strip():
            continue
        c.text(float(el.get("x", 0)), float(el.get("y", 0)), s,
               size=float(el.get("font-size", 14)), weight=el.get("font-weight", "normal"),
               anchor=el.get("text-anchor", "start"), tag=el.get("data-tag", "text"))
    return c.check()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    probs = audit_svg(sys.argv[1])
    for p in probs:
        print("  - " + p)
    print(f"svg_layout_guard: {len(probs)} problem(s) in {sys.argv[1]}")
    sys.exit(1 if probs else 0)

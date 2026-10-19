"""Exact copper-to-copper gap kernel for KiCad 9 pcbnew. Validated, reusable.

WHY THIS EXISTS
---------------
`SHAPE_COMPOUND.Distance()` is WRONG for roundrect pads (reported 0.275 mm where the
true gap is 0.025 mm — the error equals the corner radius), and
`SHAPE_COMPOUND.Collide(SHAPE_COMPOUND)` silently returns False even for overlapping
shapes. Neither failure raises, so a probe built on them produces plausible garbage.

This kernel instead models every copper item as a CONVEX CORE (list of segments)
inflated by a radius:
    trace -> one segment,            radius = width/2
    via   -> degenerate point,       radius = diameter/2
    pad   -> GetEffectivePolygon(),  radius = 0   (exact, incl. roundrect/rotated)
Edge-to-edge gap = core distance - rA - rB;  negative means overlap.

VALIDATION (measured 2026-10-18 on hub_board_v9)
------------------------------------------------
  trace/via point-probes vs SHAPE.Distance()  -> max error 3 nm
  pad-vs-pad vs SHAPE_POLY_SET.Collide        -> exact
  pad point-probes vs GetEffectivePolygon     -> exact
Re-run `validate(board)` after any pcbnew upgrade before trusting the numbers.

Run under ~/venvs/kicad/bin/python — pcbnew lives only there.
"""
import math

import pcbnew

U = 1_000_000.0  # internal units (nm) per millimetre


# ---------------------------------------------------------------- primitives
def _sd_point_seg(px, py, a, b):
    ax, ay = a
    bx, by = b
    vx, vy = bx - ax, by - ay
    L = vx * vx + vy * vy
    if L == 0.0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * vx + (py - ay) * vy) / L
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return math.hypot(px - (ax + t * vx), py - (ay + t * vy))


def _sd_seg_seg(a, b, c, d):
    def ccw(p, q, r):
        return (r[1] - p[1]) * (q[0] - p[0]) > (q[1] - p[1]) * (r[0] - p[0])

    if ccw(a, c, d) != ccw(b, c, d) and ccw(a, b, c) != ccw(a, b, d):
        return 0.0
    return min(
        _sd_point_seg(a[0], a[1], c, d),
        _sd_point_seg(b[0], b[1], c, d),
        _sd_point_seg(c[0], c[1], a, b),
        _sd_point_seg(d[0], d[1], a, b),
    )


def point_in_poly(px, py, pts):
    if len(pts) < 3:
        return False
    inside = False
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 > py) != (y2 > py):
            if px < x1 + (py - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
    return inside


# -------------------------------------------------------------------- items
class Item:
    """One piece of copper of one net on one layer."""

    __slots__ = ("segs", "r", "net", "kind", "label", "pts", "bbox")

    def __init__(self, segs, r, net, kind="", label=""):
        self.segs = segs
        self.r = float(r)
        self.net = net
        self.kind = kind
        self.label = label
        self.pts = [p for s in segs for p in s]
        xs = [p[0] for p in self.pts]
        ys = [p[1] for p in self.pts]
        self.bbox = (min(xs) - self.r, min(ys) - self.r, max(xs) + self.r, max(ys) + self.r)

    def d_point(self, px, py):
        """Edge-to-edge distance from a point (0 if inside)."""
        if self.r == 0.0 and len(self.pts) >= 3 and point_in_poly(px, py, self.pts):
            return 0.0
        d = min(_sd_point_seg(px, py, a, b) for a, b in self.segs)
        return max(0.0, d - self.r)

    def d_seg(self, a, b):
        """Edge-to-edge distance from a segment, e.g. a proposed trace."""
        if self.r == 0.0 and len(self.pts) >= 3:
            if point_in_poly(a[0], a[1], self.pts) or point_in_poly(b[0], b[1], self.pts):
                return 0.0
        return min(_sd_seg_seg(a, b, c, e) for c, e in self.segs) - self.r

    def gap_to(self, other):
        """Edge-to-edge gap between two Items (both already inflated)."""
        if self.r == 0.0 and len(self.pts) >= 3 and point_in_poly(
            self.pts[0][0], self.pts[0][1], other.pts
        ):
            return -other.r
        d = min(_sd_seg_seg(a, b, c, e) for a, b in self.segs for c, e in other.segs)
        return d - self.r - other.r


# ---------------------------------------------------------------- factories
def poly_edges(poly):
    """Edges of a SHAPE_POLY_SET in mm (handles holes / multiple outlines)."""
    out = []
    for i in range(poly.OutlineCount()):
        o = poly.Outline(i)
        n = o.PointCount()
        seq = [(o.CPoint(j).x / U, o.CPoint(j).y / U) for j in range(n)]
        for j in range(n):
            out.append((seq[j], seq[(j + 1) % n]))
    return out


def poly_pts(poly):
    pts = []
    for i in range(poly.OutlineCount()):
        o = poly.Outline(i)
        pts += [(o.CPoint(j).x / U, o.CPoint(j).y / U) for j in range(o.PointCount())]
    return pts


def pad_item(pad, layer):
    """Exact pad copper. Use THIS, not GetEffectiveShape(), for pad geometry."""
    return Item(poly_edges(pad.GetEffectivePolygon(layer)), 0.0, pad.GetNetCode(), "pad")


def trace_item(t):
    s, e = t.GetStart(), t.GetEnd()
    return Item([((s.x / U, s.y / U), (e.x / U, e.y / U))],
                t.GetWidth() / U / 2.0, t.GetNetCode(), "trace", t.GetNetname())


def via_item(t, layer):
    # PCB_VIA::GetWidth() asserts without a layer argument.
    p = t.GetPosition()
    return Item([((p.x / U, p.y / U), (p.x / U, p.y / U))],
                t.GetWidth(layer) / U / 2.0, t.GetNetCode(), "via", t.GetNetname())


def collect(board, layer, skip_net, win):
    """Other-net FIXED copper on `layer` intersecting win=(x0,y0,x1,y1).

    Zones are deliberately EXCLUDED: a GND pour re-pours around new copper, so it
    is not a hard obstacle. Measure it separately (uniform zone-clearance gap =
    re-pourable). Including it marks every pad on a poured board as blocked.
    """
    x0, y0, x1, y1 = win
    out = []
    for t in board.GetTracks():
        if t.GetNetCode() == skip_net:
            continue
        if t.Type() == pcbnew.PCB_TRACE_T:
            if not t.IsOnLayer(layer):
                continue
            it = trace_item(t)
        elif t.Type() == pcbnew.PCB_VIA_T:
            it = via_item(t, layer)
        else:
            continue
        b = it.bbox
        if b[2] < x0 or b[0] > x1 or b[3] < y0 or b[1] > y1:
            continue
        out.append(it)
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetCode() == skip_net or not p.IsOnLayer(layer):
                continue
            pos = p.GetPosition()
            px, py = pos.x / U, pos.y / U
            if not (x0 - 2 < px < x1 + 2 and y0 - 2 < py < y1 + 2):
                continue
            it = pad_item(p, layer)
            it.label = "%s.%s" % (fp.GetReference(), p.GetNumber())
            out.append(it)
    return out


# ------------------------------------------------------------------ validate
def validate(board, sample=300, verbose=True):
    """Prove the kernel still matches pcbnew. Run after any pcbnew upgrade."""
    import random

    rnd = random.Random(7)
    worst_t = 0.0
    n = 0
    for t in board.GetTracks():
        if n >= sample:
            break
        if t.Type() == pcbnew.PCB_TRACE_T:
            it, sh = trace_item(t), t.GetEffectiveShape()
        elif t.Type() == pcbnew.PCB_VIA_T:
            lay = pcbnew.F_Cu
            it, sh = via_item(t, lay), t.GetEffectiveShape(lay)
        else:
            continue
        n += 1
        a = it.pts[0]
        for _ in range(3):
            ang = rnd.uniform(0, 6.283)
            d = rnd.uniform(0, 3)
            px, py = a[0] + d * math.cos(ang), a[1] + d * math.sin(ang)
            kicad = sh.Distance(pcbnew.VECTOR2I(int(px * U), int(py * U))) / U
            worst_t = max(worst_t, abs(kicad - it.d_point(px, py)))

    # pad-vs-pad: compare against polygon Collide, the trustworthy overload
    worst_p = 0.0
    pads = [p for f in board.GetFootprints() for p in f.Pads()
            if p.GetShape() in (pcbnew.PAD_SHAPE_CIRCLE, pcbnew.PAD_SHAPE_RECT,
                                pcbnew.PAD_SHAPE_OVAL, pcbnew.PAD_SHAPE_ROUNDRECT)]
    for _ in range(min(sample, 120)):
        if len(pads) < 2:
            break
        p1, p2 = rnd.sample(pads, 2)
        A = pad_item(p1, pcbnew.F_Cu)
        B = pad_item(p2, pcbnew.F_Cu)
        if abs(A.pts[0][0] - B.pts[0][0]) > 0.5 or abs(A.pts[0][1] - B.pts[0][1]) > 0.5:
            continue
        mine = A.gap_to(B)
        sh1 = p1.GetEffectiveShape(pcbnew.F_Cu)
        ps2 = p2.GetEffectivePolygon(pcbnew.F_Cu)
        lo, hi = 0, int(2 * U)
        if not sh1.Collide(ps2, 0):
            kicad = 0.0
        elif not sh1.Collide(ps2, hi):
            continue
        else:
            for _ in range(40):
                m = (lo + hi) // 2
                if sh1.Collide(ps2, int(m)):
                    lo = m
                else:
                    hi = m
            kicad = lo / U
        worst_p = max(worst_p, abs(mine - kicad))

    ok = worst_t < 1e-5 and worst_p < 1e-5
    if verbose:
        print("kernel validation: traces/vias %.6f mm, pads %.6f mm -> %s"
              % (worst_t, worst_p, "OK" if ok else "MISMATCH — do not trust results"))
    return ok


if __name__ == "__main__":
    import sys

    board = pcbnew.LoadBoard(sys.argv[1] if len(sys.argv) > 1
                             else "tracker/hardware/hub_board_v9.kicad_pcb")
    if board is None:
        raise SystemExit("LoadBoard returned None — path must end in .kicad_pcb")
    sys.exit(0 if validate(board) else 1)

#!/usr/bin/env python3
"""F.Cu ESCAPE FEASIBILITY MAP for the four unrouted SX1280 pads on hub_board_v9.

This is a MEASUREMENT, not a router. It answers one question per pad:

    can the pad's own copper reach open board area, DRC-legally, at the
    board's own rules -- and if not, which rule binds and by how much?

It does NOT choose a route, does NOT write the board, and does NOT claim that
"reachable" means "routable to the destination". See the CANNOT-CONCLUDE
section of docs/fab/FCU-ESCAPE-FEASIBILITY.md.

Why this file exists
--------------------
tracker/hardware/pad_reachability.py (worktree wing-fix) printed

    => PAD ESCAPE CLEAR (nearest 0.970 mm >= 0.300 mm)

while labelling four obstacles [BLOCKING] at 0.970/1.260/1.312/1.810 mm. Three
independent defects caused that contradiction:

  D1  UNIT MISMATCH. It compared `d` (millimetres) against `need * UM`
      (nanometres), so `d < need*UM` was true for *every* obstacle and every
      one printed [BLOCKING]. Line:
          blocked = "BLOCKING" if d < need * UM else "clear"
  D2  WRONG THRESHOLD. `need = track_w/2 + clearance` (0.300 mm) is the
      clearance a *trace centreline* needs. A *pad* escapes from its own edge,
      so the threshold is the pad half-diagonal + clearance (1.0746 mm for a
      1.50x0.90 pad), not 0.300 mm.
  D3  WRONG LAYER. It only collected B.Cu obstacles, but all four pads are
      F.Cu-only SMD. B.Cu obstacles are not reachable from the pad without a
      via, so that measurement describes a layer the pad cannot touch.

Every threshold in this file is computed from the object whose escape is being
judged, and `self_check()` refuses to print a verdict that disagrees with the
obstacle data that produced it.

Reproduce
---------
    ~/venvs/kicad/bin/python tracker/hardware/fcu_escape_feasibility.py

`pcbnew` exists only in that interpreter. BOARD_DESIGN_SETTINGS has no
GetDefault() in KiCad 9, so rules are read from m_MinClearance /
GetSmallestClearanceValue() / the current tool sizes.
"""

from __future__ import annotations

import math
import sys

import pcbnew

BOARD = "tracker/hardware/hub_board_v9.kicad_pcb"
U = 1_000_000.0  # internal units (nm) per millimetre

# The four unrouted endpoints: both nets have BOTH endpoints unrouted.
PADS = [("U1", "8"), ("U1", "22"), ("U4", "17"), ("U4", "18")]

COPPER_LAYERS = [
    (pcbnew.F_Cu, "F.Cu"),
    (pcbnew.In1_Cu, "In1.Cu"),
    (pcbnew.In2_Cu, "In2.Cu"),
    (pcbnew.B_Cu, "B.Cu"),
]

EPS = 1e-9


# --------------------------------------------------------------------------
# geometry kernel
#
# Each copper item is a CONVEX CORE (a list of segments) inflated by a radius:
#   trace  -> one segment, radius = width/2
#   via    -> degenerate point, radius = diameter/2
#   pad    -> its exact KiCad polygon (convex for the shapes on this board),
#             radius = 0.  GetEffectivePolygon() is used rather than
#             GetEffectiveShape().Distance(), because Distance() on the
#             SH_COMPOUND that a roundrect pad returns is NOT the true gap
#             (measured: reported 0.275 mm where the true gap is 0.025 mm).
# Edge-to-edge gap = core distance - rA - rB.  Negative means overlap.
# --------------------------------------------------------------------------
def _rot(x, y, deg):
    if deg == 0.0:
        return x, y
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return x * c - y * s, x * s + y * c


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


def _point_in_poly(px, py, pts):
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


class Item:
    """One piece of copper of one net on one layer."""

    __slots__ = ("segs", "r", "net", "kind", "label", "pts", "bbox")

    def __init__(self, segs, r, net, kind, label):
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
        """Edge-to-edge distance from a point to this copper (0 if inside)."""
        if self.r == 0.0 and len(self.pts) >= 3 and _point_in_poly(px, py, self.pts):
            return 0.0
        d = min(_sd_point_seg(px, py, a, b) for a, b in self.segs)
        return max(0.0, d - self.r)

    def d_seg(self, a, b):
        """Edge-to-edge distance from a segment (a trace) to this copper."""
        if self.r == 0.0 and len(self.pts) >= 3:
            if _point_in_poly(a[0], a[1], self.pts) or _point_in_poly(b[0], b[1], self.pts):
                return 0.0
        d = min(_sd_seg_seg(a, b, c, e) for c, e in self.segs)
        return d - self.r

    def gap_to(self, other):
        """Edge-to-edge gap between two Items (both already inflated)."""
        if self.r == 0.0 and len(self.pts) >= 3 and _point_in_poly(self.pts[0][0], self.pts[0][1], other.pts):
            return -other.r
        d = min(_sd_seg_seg(a, b, c, e) for a, b in self.segs for c, e in other.segs)
        return d - self.r - other.r


def poly_to_pts(poly):
    pts = []
    for i in range(poly.OutlineCount()):
        o = poly.Outline(i)
        n = o.PointCount()
        seq = [(o.CPoint(j).x / U, o.CPoint(j).y / U) for j in range(n)]
        for j in range(n):
            pts.append((seq[j], seq[(j + 1) % n]))
    return pts


def pad_item(pad, layer):
    return Item(poly_to_pts(pad.GetEffectivePolygon(layer)), 0.0, pad.GetNetCode(), "pad", "")


# --------------------------------------------------------------------------
# board
# --------------------------------------------------------------------------
class Rules:
    def __init__(self, board):
        ds = board.GetDesignSettings()
        # KiCad 9: no GetDefault(). m_MinClearance is 0 here (floor unset), so the
        # rule actually in force is the tightest netclass/local clearance.
        self.clearance = max(ds.m_MinClearance, ds.GetSmallestClearanceValue()) / U
        self.track_w = ds.GetCurrentTrackWidth() / U
        self.via_dia = ds.GetCurrentViaSize() / U
        self.via_drill = ds.GetCurrentViaDrill() / U
        self.via_min_dia = ds.m_ViasMinSize / U
        self.via_min_drill = ds.m_ViasMinDrill / U if hasattr(ds, "m_ViasMinDrill") else 0.30
        self.hole_clear = ds.m_HoleClearance / U
        self.hole_to_hole = ds.m_HoleToHoleMin / U
        self.edge_clear = ds.m_CopperEdgeClearance / U

    @property
    def trace_edge_to_copper(self):
        """Centreline offset a trace needs from other-net COPPER."""
        return self.track_w / 2.0 + self.clearance


def collect(board, layer, skip_net, win):
    """Other-net fixed copper on `layer` intersecting `win` = (x0,y0,x1,y1).

    Zones are deliberately EXCLUDED: the F.Cu GND pour is re-poured around new
    copper, so it is not a hard obstacle. It is measured separately (pour_gap)
    and reported as "re-pourable", never as a blocker.
    """
    x0, y0, x1, y1 = win
    out = []
    for t in board.GetTracks():
        if t.GetNetCode() == skip_net:
            continue
        if t.Type() == pcbnew.PCB_TRACE_T:
            if not t.IsOnLayer(layer):
                continue
            s, e = t.GetStart(), t.GetEnd()
            it = Item(
                [((s.x / U, s.y / U), (e.x / U, e.y / U))],
                t.GetWidth() / U / 2.0,
                t.GetNetCode(),
                "trace",
                t.GetNetname(),
            )
        elif t.Type() == pcbnew.PCB_VIA_T:
            p = t.GetPosition()
            it = Item(
                [((p.x / U, p.y / U), (p.x / U, p.y / U))],
                t.GetWidth(layer) / U / 2.0,
                t.GetNetCode(),
                "via",
                t.GetNetname(),
            )
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


def collect_holes(board, skip_net):
    """Every drilled hole that is not on the escaping net: (x, y, radius, label)."""
    out = []
    for t in board.GetTracks():
        if t.Type() != pcbnew.PCB_VIA_T or t.GetNetCode() == skip_net:
            continue
        p = t.GetPosition()
        out.append((p.x / U, p.y / U, t.GetDrill() / U / 2.0, t.GetNetname()))
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetCode() == skip_net:
                continue
            ds = p.GetDrillSize()
            if ds.x <= 0:
                continue
            pos = p.GetPosition()
            out.append((pos.x / U, pos.y / U, ds.x / U / 2.0, "%s.%s" % (fp.GetReference(), p.GetNumber())))
    return out


# --------------------------------------------------------------------------
# measurement stages
# --------------------------------------------------------------------------
def pad_geometry(pad):
    sz = pad.GetSize()
    w, h = sz.x / U, sz.y / U
    half_diag = math.hypot(w / 2.0, h / 2.0)  # corner radius of the escape ring
    pos = pad.GetPosition()
    return {
        "w": w,
        "h": h,
        "half_diag": half_diag,
        "centre": (pos.x / U, pos.y / U),
        "size_mm": (sz.x / U, sz.y / U),
        "angle": pad.GetOrientationDegrees(),
        "shape": pad.GetShape(),
    }


def ring_obstacles(board, pad, layer, radius):
    """Other-net copper whose nearest approach to the pad is inside `radius`.

    `radius` is measured FROM THE PAD CENTRE, and equals half-diagonal +
    clearance: the corner of the pad is at half_diag, and the clearance band
    around that corner ends at half_diag + clearance. Distances are reported
    from the pad EDGE (the honest number for judging a gap).
    """
    g = pad_geometry(pad)
    cx, cy = g["centre"]
    win = (cx - radius - 1, cy - radius - 1, cx + radius + 1, cy + radius + 1)
    me = pad_item(pad, layer)
    rows = []
    for it in collect(board, layer, pad.GetNetCode(), win):
        d = me.gap_to(it)
        if d <= radius:
            rows.append((d, it.kind, it.label))
    rows.sort(key=lambda r: r[0])
    return rows


def pour_gap(board, pad, layer):
    for z in board.Zones():
        if not z.IsOnLayer(layer) or z.GetNetCode() == pad.GetNetCode():
            continue
        if not z.IsFilled():
            continue
        it = Item(poly_to_pts(z.GetFilledPolysList(layer)), 0.0, z.GetNetCode(), "zone", z.GetNetname())
        return pad_item(pad, layer).gap_to(it), it.label, z.GetLocalClearance() / U
    return None, None, None


def existing_net_copper(board, pad):
    """Copper the pad's OWN net already has on the board.

    Load-bearing: if a via already exists inside the pad, the pad is ALREADY
    layer-transitioned, and "can F.Cu leave?" is no longer the deciding
    question. Reporting a verdict without this would be the same class of
    error as measuring B.Cu for an F.Cu pad.
    """
    net = pad.GetNetCode()
    g = pad_geometry(pad)
    cx, cy = g["centre"]
    out = []
    for t in board.GetTracks():
        if t.GetNetCode() != net:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            p = t.GetPosition()
            d = math.hypot(p.x / U - cx, p.y / U - cy)
            out.append({
                "kind": "via",
                "pos": (p.x / U, p.y / U),
                "dia": t.GetWidth(pcbnew.F_Cu) / U,
                "drill": t.GetDrill() / U,
                "spans": (board.GetLayerName(t.TopLayer()), board.GetLayerName(t.BottomLayer())),
                "dist": d,
                "in_pad": pad_item(pad, pcbnew.F_Cu).d_point(p.x / U, p.y / U) < t.GetWidth(pcbnew.F_Cu) / U / 2.0,
            })
        elif t.Type() == pcbnew.PCB_TRACE_T:
            s, e = t.GetStart(), t.GetEnd()
            out.append({
                "kind": "trace",
                "pos": (s.x / U, s.y / U),
                "end": (e.x / U, e.y / U),
                "layer": board.GetLayerName(t.GetLayer()),
                "dist": math.hypot(s.x / U - cx, s.y / U - cy),
            })
    return out


def via_continues(board, rules, pad, vpos, reach=1.0):
    """True if the via at `vpos` has own-net copper continuing beyond itself on
    any inner/back layer, i.e. the via is an escape rather than a stub."""
    net = pad.GetNetCode()
    for t in board.GetTracks():
        if t.GetNetCode() != net:
            continue
        if t.Type() not in (pcbnew.PCB_TRACE_T, pcbnew.PCB_ARC_T):
            continue
        L = t.GetLayer()
        if L not in (pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
            continue
        s, e = t.GetStart(), t.GetEnd()
        it = Item([((s.x / U, s.y / U), (e.x / U, e.y / U))], t.GetWidth() / U / 2.0, net, "trace", "")
        if it.d_point(vpos[0], vpos[1]) <= reach:
            return True, board.GetLayerName(L)
    return False, None


def via_is_legal(board, rules, pad, vpos, vdia, drill):
    """Re-check one specific existing via against every rule (no search)."""
    net = pad.GetNetCode()
    win = (vpos[0] - 2, vpos[1] - 2, vpos[0] + 2, vpos[1] + 2)
    worst_cu, who = float("inf"), None
    for L, lname in COPPER_LAYERS:
        for it in collect(board, L, net, win):
            v = it.d_point(vpos[0], vpos[1]) - vdia / 2.0
            if v < worst_cu:
                worst_cu, who = v, (lname, it.kind, it.label)
    worst_h, hn = float("inf"), None
    for hx, hy, hr, hlab in collect_holes(board, net):
        v = math.hypot(hx - vpos[0], hy - vpos[1]) - drill / 2.0 - hr
        if v < worst_h:
            worst_h, hn = v, hlab
    ok = worst_cu >= rules.clearance - EPS and worst_h >= rules.hole_to_hole - EPS
    return ok, worst_cu, who, worst_h, hn


def fcu_reachability(board, pad, rules, half=2.5, step=0.05):
    """DRC-legal flood fill on F.Cu from the pad's own copper.

    A cell is legal when a trace centreline placed there keeps
    `track_w/2 + clearance` from every other-net F.Cu item. 8-connected, but a
    diagonal step also requires both orthogonal neighbours to be legal (no
    corner-cutting). Returns how far the pad's copper can legally travel.
    """
    g = pad_geometry(pad)
    cx, cy = g["centre"]
    win = (cx - half - 1, cy - half - 1, cx + half + 1, cy + half + 1)
    obst = collect(board, pcbnew.F_Cu, pad.GetNetCode(), win)
    need = rules.trace_edge_to_copper

    n = int(round(2 * half / step)) + 1
    xs = [cx - half + i * step for i in range(n)]
    ys = [cy - half + j * step for j in range(n)]

    # 1. legal grid (own-net copper is not in `obst`, so the pad body is legal)
    legal = [[False] * n for _ in range(n)]
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            d = float("inf")
            for it in obst:
                b = it.bbox
                bd = math.hypot(max(b[0] - x, 0.0, x - b[2]), max(b[1] - y, 0.0, y - b[3]))
                if bd - 1.0 > d:
                    continue
                v = it.d_point(x, y)
                if v < d:
                    d = v
                    if d < need:
                        break
            legal[i][j] = d >= need - EPS

    # 2. seeds = grid cells inside the pad polygon
    me = pad_item(pad, pcbnew.F_Cu)
    seeds = [(i, j) for j, y in enumerate(ys) for i, x in enumerate(xs)
             if legal[i][j] and _point_in_poly(x, y, me.pts)]
    if not seeds:
        return {"escaped": False, "note": "no legal cell inside the pad", "reach": 0.0, "cells": 0}

    # 3. BFS
    seen = [[False] * n for _ in range(n)]
    stack = list(seeds)
    for i, j in seeds:
        seen[i][j] = True
    cells = 0
    far = 0.0
    reached_edge = False
    while stack:
        i, j = stack.pop()
        cells += 1
        d = math.hypot(xs[i] - cx, ys[j] - cy)
        if d > far:
            far = d
        if i in (0, n - 1) or j in (0, n - 1):
            reached_edge = True
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            a, b = i + di, j + dj
            if not (0 <= a < n and 0 <= b < n) or seen[a][b] or not legal[a][b]:
                continue
            if di and dj and not (legal[i + di][j] and legal[i][j + dj]):
                continue  # no corner cutting
            seen[a][b] = True
            stack.append((a, b))

    return {
        "escaped": reached_edge,
        "reach": far,
        "cells": cells,
        "half": half,
        "step": step,
        "note": "reached sampling-window edge" if reached_edge else "cannot leave the local pad field",
    }


def via_search(board, pad, rules, r_max=2.0, step_deg=3.0, step_r=0.05):
    """DRC-legal via placements for this pad, on every copper layer.

    A candidate must satisfy, at once:
      * copper clearance to every other-net item on EVERY copper layer it spans
      * hole-to-hole clearance to every other drilled hole
      * a legal F.Cu approach: a `track_w`-wide trace from pad centre to via
    Returns the legal set plus the best near-miss (which names the binding rule).
    """
    g = pad_geometry(pad)
    cx, cy = g["centre"]
    net = pad.GetNetCode()
    win = (cx - r_max - 3, cy - r_max - 3, cx + r_max + 3, cy + r_max + 3)
    obst = {L: collect(board, L, net, win) for L, _ in COPPER_LAYERS}
    fcu = obst[pcbnew.F_Cu]
    holes = collect_holes(board, net)
    centre = (cx, cy)

    sizes = []
    for d in (rules.via_dia, rules.via_min_dia):
        if d > 0 and all(abs(d - s) > 1e-6 for s in sizes):
            sizes.append(d)

    me = pad_item(pad, pcbnew.F_Cu)
    results = {}
    for vd in sizes:
        legal, near, inpad = [], None, []
        for ri in range(1, int(round(r_max / step_r)) + 1):
            R = ri * step_r
            for ki in range(int(round(360 / step_deg))):
                ang = math.radians(ki * step_deg)
                vx, vy = cx + R * math.cos(ang), cy + R * math.sin(ang)

                # copper clearance, worst case over all layers
                wc, who = float("inf"), None
                for L, lname in COPPER_LAYERS:
                    for it in obst[L]:
                        b = it.bbox
                        bd = math.hypot(max(b[0] - vx, 0.0, vx - b[2]), max(b[1] - vy, 0.0, vy - b[3]))
                        if bd - vd / 2.0 > wc:
                            continue
                        v = it.d_point(vx, vy) - vd / 2.0
                        if v < wc:
                            wc, who = v, (lname, it.kind, it.label)

                # hole-to-hole
                wh, whn = float("inf"), None
                for hx, hy, hr, hn in holes:
                    v = math.hypot(hx - vx, hy - vy) - rules.via_drill / 2.0 - hr
                    if v < wh:
                        wh, whn = v, hn

                # pad -> via approach on F.Cu
                wa, wao = float("inf"), None
                for it in fcu:
                    v = it.d_seg(centre, (vx, vy)) - rules.track_w / 2.0
                    if v < wa:
                        wa, wao = v, (it.kind, it.label)

                ok = (
                    wc >= rules.clearance - EPS
                    and wh >= rules.hole_to_hole - EPS
                    and wa >= rules.clearance - EPS
                )
                # via-in-pad = the via body still overlaps the pad's OWN copper.
                # Electrically legal (same net) but it is a different technique
                # (needs filled/plugged vias), so it is counted separately from a
                # dogbone escape that sits fully outside the land.
                in_pad = me.d_point(vx, vy) < vd / 2.0
                rec = {"R": R, "deg": ki * step_deg, "cu": wc, "cu_by": who,
                       "h2h": wh, "h2h_by": whn, "appr": wa, "appr_by": wao,
                       "in_pad": in_pad}
                if ok and not in_pad:
                    legal.append(rec)
                elif ok and in_pad:
                    inpad.append(rec)
                # near-miss = the candidate whose *minimum* margin is largest
                margin = min(wc, wh, wa)
                if near is None or margin > near["margin"]:
                    rec["margin"] = margin
                    near = rec
        results[vd] = {"legal": legal, "near": near, "inpad": len(inpad)}
    return results


# --------------------------------------------------------------------------
# verdict + self-consistency
# --------------------------------------------------------------------------
def self_check(name, verdict, ring_rows, via_res, rules, _existing_seen=()):
    """Refuse to emit a verdict that contradicts the measured obstacle data.

    This is the gate that pad_reachability.py lacked: the verdict and the
    obstacle list must be derived from the same threshold, in the same units.
    """
    problems = []
    inside = [r for r in ring_rows if r[0] < 0.0]
    if inside:
        problems.append("%d obstacle(s) overlap the pad copper itself" % len(inside))
    if verdict["kind"] == "F.CU" and not verdict.get("fcu_escaped"):
        problems.append("verdict says F.Cu-escapable but the flood fill never left the pad field")
    if verdict["kind"] == "VIA":
        if not any(v["legal"] for v in via_res.values()):
            problems.append("verdict says via-escapable but no legal via candidate was found")
    if verdict["kind"] == "STUB_VIA":
        stubs = [e for e in _existing_seen if e["kind"] == "via" and e.get("legal", (False,))[0]
                 and e["in_pad"] and not e.get("continues", (False,))[0]]
        if not stubs:
            problems.append("verdict says stub via but no legal in-pad via without continuation was found")
    if verdict["kind"] == "ALREADY_VIA" and not any(
            e["kind"] == "via" and e.get("legal", (False,))[0] for e in _existing_seen):
        problems.append("verdict says an existing legal via exists but none was found legal")
    if verdict["kind"] == "BLOCKED":
        if verdict.get("fcu_escaped"):
            problems.append("verdict says blocked but the F.Cu flood fill escaped")
        if any(v["legal"] for v in via_res.values()):
            problems.append("verdict says blocked but a legal via exists")
    return problems


def measure(board, rules, ref, num):
    fp = board.FindFootprintByReference(ref)
    pad = None
    for p in fp.Pads():
        if str(p.GetNumber()) == num:
            pad = p
            break
    if pad is None:
        raise SystemExit("%s.%s: pad not found" % (ref, num))

    g = pad_geometry(pad)
    ring_r = g["half_diag"] + rules.clearance
    layers = [board.GetLayerName(l) for l in pad.GetLayerSet().Seq()]
    fcu_ring = ring_obstacles(board, pad, pcbnew.F_Cu, ring_r)
    all_rings = {}
    for L, ln in COPPER_LAYERS:
        all_rings[ln] = ring_obstacles(board, pad, L, ring_r)
    pg, pz, pclr = pour_gap(board, pad, pcbnew.F_Cu)
    reach = fcu_reachability(board, pad, rules)
    vias = via_search(board, pad, rules)
    existing = existing_net_copper(board, pad)
    for e in existing:
        if e["kind"] == "via":
            e["legal"] = via_is_legal(board, rules, pad, e["pos"], e["dia"], e["drill"])
            # does the via actually GO anywhere? a via with no continuing copper
            # is a stub, not an escape.
            e["continues"] = via_continues(board, rules, pad, e["pos"])

    # verdict.
    # An existing LEGAL via-in-pad already transitions this pad to every inner
    # layer + B.Cu. In that case "can F.Cu leave?" is not the question that
    # decides the escape: the layer transition already exists on the board.
    live_vias = [e for e in existing if e["kind"] == "via" and e.get("legal", (False,))[0]]
    in_pad_via = [e for e in live_vias if e["in_pad"]]

    if in_pad_via:
        e = min(in_pad_via, key=lambda x: x["dist"])
        ok, cu, cu_by, hh, hn = e["legal"]
        cont, clay = e.get("continues", (False, None))
        fcu_note = ("F.Cu also escapes" if reach["escaped"] else
                    "F.Cu itself does not escape (flood fill stalls at %.2f mm)" % reach["reach"])
        via_txt = ("an existing %.2f/%.2f mm through via at (%.3f, %.3f) sits inside this pad "
                   "(%.4f mm from centre) and re-checks LEGAL (worst copper %.4f mm, "
                   "hole-to-hole %.4f mm)"
                   % (e["dia"], e["drill"], e["pos"][0], e["pos"][1], e["dist"], cu, hh))
        if cont:
            verdict = {
                "kind": "ALREADY_VIA",
                "fcu_escaped": reach["escaped"],
                "text": "ESCAPABLE only via layer transition (F.Cu -> %s) -- transition already on the board" % clay,
                "layer": clay,
                "detail": via_txt + (". Copper continues on %s, so this via IS an escape. %s."
                                    % (clay, fcu_note)),
            }
        else:
            verdict = {
                "kind": "STUB_VIA",
                "fcu_escaped": reach["escaped"],
                "text": "ESCAPABLE via layer transition (F.Cu -> In1/In2/B.Cu) -- existing in-pad via is a STUB, not an escape",
                "layer": "B.Cu",
                "detail": via_txt + (". But NO own-net copper continues on In1/In2/B.Cu beyond "
                                    "the via: it is a stub (a via with nothing on the far side), "
                                    "so it does not constitute an escape. %s." % fcu_note),
            }
    elif reach["escaped"]:
        best = min(
            (r for r in fcu_ring if r[1] != "zone"),
            default=(float("inf"), "", ""),
            key=lambda r: r[0],
        )
        verdict = {
            "kind": "F.CU",
            "fcu_escaped": True,
            "text": "ESCAPABLE on F.Cu",
            "detail": "legal F.Cu corridor leaves the pad field (reached %.1f mm from pad centre)"
                      % reach["reach"],
        }
        _ = best
    else:
        legal_sizes = sorted(vd for vd, v in vias.items() if v["legal"])
        if legal_sizes:
            vd = legal_sizes[0]
            v = min(vias[vd]["legal"], key=lambda r: r["R"])
            verdict = {
                "kind": "VIA",
                "fcu_escaped": False,
                "text": "ESCAPABLE only via layer transition (F.Cu -> In1/In2/B.Cu)",
                "layer": "B.Cu",
                "detail": ("no F.Cu exit; legal via at R=%.2f mm @%.0f deg, dia %.2f mm, "
                           "worst-case copper clearance %.4f mm, hole-to-hole %.4f mm"
                           % (v["R"], v["deg"], vd, v["cu"], v["h2h"])),
            }
        else:
            smallest = min(vias)
            near = vias[smallest]["near"]
            # which of the three constraints actually fails, and by how much?
            parts = [
                ("copper clearance", near["cu"], rules.clearance, near["cu_by"]),
                ("hole-to-hole", near["h2h"], rules.hole_to_hole, ("hole", near["h2h_by"])),
                ("F.Cu pad-to-via approach", near["appr"], rules.clearance, near["appr_by"]),
            ]
            bind_name, bind_achieved, bind_need, binding = min(parts, key=lambda t: t[1] - t[2])
            short = bind_need - bind_achieved
            if binding and len(binding) >= 3:
                bind_what = "%s %s" % (binding[1], binding[2])
            elif binding:
                bind_what = "%s %s" % (binding[0], binding[1])
            else:
                bind_what = "n/a"
            verdict = {
                "kind": "BLOCKED",
                "fcu_escaped": False,
                "text": "NOT ESCAPABLE at current rules",
                "detail": ("best dogbone via candidate (dia %.2f mm, R=%.2f mm @%.0f deg) "
                           "misses by %.4f mm on the %s rule (%.3f mm required, %.4f mm "
                           "achieved); tightest neighbour: %s"
                           % (smallest, near["R"], near["deg"], short, bind_name,
                              bind_need, bind_achieved, bind_what)),
                "binds": binding,
                "short_by": short,
            }

    problems = self_check("%s.%s" % (ref, num), verdict, fcu_ring, vias, rules, existing)
    return {
        "ref": "%s.%s" % (ref, num),
        "net": pad.GetNetname(),
        "geom": g,
        "layers": layers,
        "ring_r": ring_r,
        "ring": fcu_ring,
        "rings_all": all_rings,
        "pour": (pg, pz, pclr),
        "reach": reach,
        "vias": vias,
        "existing": existing,
        "verdict": verdict,
        "problems": problems,
    }


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------
def main():
    board = pcbnew.LoadBoard(BOARD)
    if board is None:
        raise SystemExit("LoadBoard returned None -- path needs a .kicad_pcb suffix")
    rules = Rules(board)
    bb = board.GetBoardEdgesBoundingBox()

    print("=" * 100)
    print("F.Cu ESCAPE FEASIBILITY MAP -- tracker/hardware/hub_board_v9.kicad_pcb")
    print("=" * 100)
    print("board %.2f x %.2f mm | %d footprints | %d tracks/vias | %d copper layers"
          % (bb.GetWidth() / U, bb.GetHeight() / U, len(board.GetFootprints()),
             len(board.GetTracks()), board.GetCopperLayerCount()))
    print("\nRULES READ FROM THE BOARD (not assumed):")
    print("  clearance            %.3f mm   (max(m_MinClearance, GetSmallestClearanceValue()))" % rules.clearance)
    print("  track width          %.3f mm" % rules.track_w)
    print("  via                  %.3f mm / drill %.3f mm" % (rules.via_dia, rules.via_drill))
    print("  via floors           %.3f mm / drill %.3f mm" % (rules.via_min_dia, rules.via_min_drill))
    print("  hole clearance       %.3f mm" % rules.hole_clear)
    print("  hole-to-hole         %.3f mm" % rules.hole_to_hole)
    print("  => a trace CENTRELINE needs %.3f mm from other-net copper" % rules.trace_edge_to_copper)
    print("  NOTE a PAD does not escape from its centreline: its ring radius is")
    print("       half-diagonal + clearance, which is %.3f mm for a 1.50x0.90 pad" % (math.hypot(0.75, 0.45) + rules.clearance))

    results = []
    for ref, num in PADS:
        results.append(measure(board, rules, ref, num))

    for r in results:
        g, v = r["geom"], r["verdict"]
        print("\n" + "-" * 100)
        print("%s   net %s" % (r["ref"], r["net"]))
        print("-" * 100)
        print("  PAD GEOMETRY   %.2f x %.2f mm  (shape %d, %.0f deg)  centre (%.3f, %.3f)"
              % (g["w"], g["h"], g["shape"], g["angle"], g["centre"][0], g["centre"][1]))
        print("                 half-diagonal %.4f mm   layers %s" % (g["half_diag"], r["layers"]))
        print("                 SMD-only: %s" % ("yes" if "B.Cu" not in r["layers"] else "no"))
        print("  ESCAPE RING    radius %.4f mm  (= half-diagonal %.4f + clearance %.3f)"
              % (r["ring_r"], g["half_diag"], rules.clearance))
        pg, pz, pclr = r["pour"]
        if pg is not None:
            print("  F.Cu POUR      %s at %.4f mm from pad edge (zone local clearance %.3f mm)"
                  % (pz, pg, pclr))
            print("                 -> RE-POURABLE: the pour flows around new copper; NOT counted as a blocker")
        print("  F.Cu OBSTACLES INSIDE THE RING (other net), distance from pad EDGE:")
        ring = [x for x in r["ring"] if x[1] != "zone"]
        if not ring:
            print("                 none")
        for d, kind, label in ring:
            verdict_tag = "INSIDE RING" if d < r["ring_r"] else "outside"
            print("                 %+8.4f mm  %-6s %-14s [%s]" % (d, kind, label, verdict_tag))
        print("  OBSTACLE COUNT INSIDE THE RING, PER LAYER:")
        for ln in ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"):
            n = len([x for x in r["rings_all"][ln] if x[1] != "zone"])
            print("                 %-7s %2d" % (ln, n))
        rc = r["reach"]
        print("  F.Cu REACHABILITY (%.2f mm grid, %s window): %s"
              % (rc["step"], rc.get("half", 0), rc["note"]))
        print("                 legal cells reached %d, furthest %.2f mm from pad centre"
              % (rc["cells"], rc["reach"]))
        print("  EXISTING COPPER ON THIS NET (from the board, not from a router):")
        if not any(e["kind"] == "via" for e in r["existing"]) and \
           not any(e["kind"] == "trace" for e in r["existing"]):
            print("                 none -- the net has no copper at all")
        for e in r["existing"]:
            if e["kind"] == "via":
                ok, cu, cu_by, hh, hn = e["legal"]
                print("                 via %.2f/%.2f mm at (%.3f, %.3f), spans %s->%s"
                      % (e["dia"], e["drill"], e["pos"][0], e["pos"][1], e["spans"][0], e["spans"][1]))
                print("                   %.4f mm from pad centre -> %s"
                      % (e["dist"], "VIA-IN-PAD (pad is already layer-transitioned)"
                         if e["in_pad"] else "outside the pad"))
                print("                   re-checked: %s (worst copper %.4f mm vs %.3f required%s; "
                      "hole-to-hole %.4f mm)"
                      % ("LEGAL" if ok else "NOT LEGAL", cu, rules.clearance,
                         (", " + " ".join(str(x) for x in cu_by if x)) if cu_by else "",
                         hh))
                if not ok:
                    print("                   violation neighbour: %s / %s" % (cu_by, hn))
                cont, clay = e.get("continues", (False, None))
                print("                   own-net copper continuing beyond it: %s"
                      % (("yes, on " + clay) if cont else "NO -- stub, this via is not an escape"))
            else:
                print("                 trace on %s from (%.2f, %.2f) to (%.2f, %.2f)"
                      % (e["layer"], e["pos"][0], e["pos"][1], e["end"][0], e["end"][1]))
        print("  LEGAL VIA CANDIDATES (all 4 copper layers + hole-to-hole + F.Cu approach):")
        for vd in sorted(r["vias"]):
            legal = r["vias"][vd]["legal"]
            if legal:
                v0 = min(legal, key=lambda x: x["R"])
                print("                 dia %.2f mm: %d legal DOGBONE spots; nearest R=%.2f mm @%.0f deg  "
                      "worstCu=%.4f  h2h=%.4f  approach=%.4f   (+%d via-in-pad)"
                      % (vd, len(legal), v0["R"], v0["deg"], v0["cu"], v0["h2h"], v0["appr"],
                         r["vias"][vd]["inpad"]))
            else:
                nm = r["vias"][vd]["near"]
                print("                 dia %.2f mm: NONE legal dogbone. best near-miss min-margin=%.4f mm "
                      "(cu=%.4f h2h=%.4f appr=%.4f) at R=%.2f @%.0f deg"
                      % (vd, nm["margin"], nm["cu"], nm["h2h"], nm["appr"], nm["R"], nm["deg"]))
        print("  VERDICT        %s" % v["text"])
        print("                 %s" % v["detail"])
        print("  SELF-CHECK     %s" % ("OK -- verdict agrees with the obstacle data" if not r["problems"]
                                       else "FAIL: " + "; ".join(r["problems"])))

    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print("%-8s %-12s %-9s %-9s %-10s %s" % ("pad", "net", "ring mm", "F.Cu", "via0.60", "verdict"))
    for r in results:
        v60 = r["vias"].get(rules.via_dia)
        print("%-8s %-12s %9.4f %-9s %-10s %s"
              % (r["ref"], r["net"].replace("/SX1280_", ""), r["ring_r"],
                 "escape" if r["reach"]["escaped"] else "no exit",
                 ("%d spots" % len(v60["legal"])) if v60 and v60["legal"] else "none",
                 r["verdict"]["text"]))
    bad = [r for r in results if r["problems"]]
    print("\nconsistency: %s" % ("ALL PADS PASS" if not bad else "FAILURES: " + ", ".join(r["ref"] for r in bad)))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())

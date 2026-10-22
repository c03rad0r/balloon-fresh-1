#!/usr/bin/env python3
"""v10 grid A* router with via support -- THE ONLY PERMITTED ROUTING METHOD (ADR-126).

Why this replaced the straight/L router (operator directive 2026-10-21):
the L-path router produced a lane at 0.000 mm over U_C.9, two dead-end stubs, and 21.7 mm
of copper through the F33's body. The operator chose "a real grid/A* router with via
support -- and make sure this approach is taken in all future attempts".

DESIGN
  * grid: 0.1 mm pitch over the board outline
  * two layers: F.Cu (0) and B.Cu (1); a via (0.50 / 0.25 mm, the measured legal minimum)
    costs VIA_COST, so vias are used only when they save real distance
  * obstacles come from the CONNECTIVITY REGISTRY, not from hand-typed tables:
      - every pad of another net -> blocked + CLEAR margin (unnamed pads INCLUDED: they
        are metal -- this is bug B5, which is how U_C.9 was hit)
      - every NPTH hole (tether/wing) -> blocked + 0.5 mm (ADR-125)
      - component bodies -> blocked on their own side (ADR: no copper under modules)
      - board edge -> blocked within EDGE_KEEP
  * cost = distance + VIA_COST per via + small bend penalty; A* with a Manhattan heuristic
  * the path is validated by the SAME predicates the gates use before a single track is
    written: a route that would fail check_lane_clearance / check_lane_integrity /
    check_copper_under_body / check_hole_clearance is rejected, never saved.

USAGE
    route_v10_astar.py [--nets N1,N2] [--dry-run] [--board B] [--pitch 0.1]
"""
import argparse
import heapq
import math
import os
import sys
from collections import defaultdict

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")
UM = 1_000_000.0
TRACK_W = 0.200          # mm
CLEAR = 0.200            # mm copper-to-copper
HOLE_CLEAR = 0.500       # mm (ADR-125, applied to lanes)
EDGE_KEEP = 0.300        # mm
VIA_D = 0.500            # mm measured legal minimum (m_ViasMinSize)
VIA_DRILL = 0.250
VIA_COST = 25            # in grid steps -- a via is worth ~2.5 mm of detour
                         # overridable with --via-cost: LOWER makes the router drop to the
                         # back layer EARLIER (lever (b) for the congested U1 corridor)
BEND_COST = 2
HOLE_PREFIXES = ("H", "HW")
# B17 (2026-10-21): ONLY the E28 has a datasheet rule against routing beneath the module
# (E28 manual 4.1; ADR-118 line 22). U1/U2/U3/U_C/U5 have NO such rule -- copper under a
# castellated/shielded module is normal practice and KiCad's DRC does not flag it.
# Blocking every footprint's courtyard box blocked the whole board: measured, every F33 net
# failed and U1's start row had 404/722 cells blocked, because U1's own courtyard is 19.5 x
# 19.2 mm of solid terrain.
KEEPOUT_REFS = ("U_E28",)
F, B = 0, 1              # layer indices -> pcbnew F_Cu / B_Cu


def pad_rect(pad):
    """Rotation-aware pad rectangle.

    B10 (2026-10-21): the first version used GetPosition() + GetSize(), which ignore the
    pad's rotation. For the rotated U1 footprint that produced rectangles overlapping the
    neighbouring pins, so the router believed it had room where there was none.
    GetBoundingBox() accounts for rotation.
    """
    bb = pad.GetBoundingBox()
    return (bb.GetX() / UM, bb.GetY() / UM,
            (bb.GetX() + bb.GetWidth()) / UM, (bb.GetY() + bb.GetHeight()) / UM)


def load_world(board_path):
    """Everything the router needs, read once. Returns a dict."""
    b = pcbnew.LoadBoard(board_path)
    if b is None:
        raise SystemExit(f"REFUSED: cannot load {board_path}")
    bb = b.GetBoardEdgesBoundingBox()
    ox, oy = bb.GetX() / UM, bb.GetY() / UM
    w, h = bb.GetWidth() / UM, bb.GetHeight() / UM

    pads = []      # (ref, num, net, code, sides, rect)
    bodies = []    # (ref, side, rect)
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        front = fp.GetLayer() == pcbnew.F_Cu
        if not ref.startswith(HOLE_PREFIXES) and ref in KEEPOUT_REFS:
            # B17 (2026-10-21): GetBoundingBox(False, True) returns the COURTYARD box --
            # for U1/U2 that is a 40x22mm slab covering most of the board, so the router
            # could not route anywhere near the two biggest parts (measured: every F33 net
            # failed, U1's start row 404/722 cells blocked). What must stay clear on the
            # part's own side is the PAD FIELD, not the outline: the module is soldered to
            # its pads and copper beneath the rest of the body is normal practice (KiCad's
            # own DRC has no "copper under footprint" rule for this reason).
            # We therefore block the footprint's PAD-FIELD bounding box, grown slightly,
            # and let check_copper_under_body.py remain the gate for genuine traversals.
            # B40 (2026-10-22): for a KEEP-OUT module the body must be its COURTYARD, not its
            # pad field. Measured: the E28 pad field is (48.06,60.40)-(57.95,77.60) but its
            # courtyard is (41.92,64.08)-(60.38,77.62) -- the pad-field rect left an uncovered
            # strip x 41.92..48.06, and /E28_BUSY's 8.00mm run at y=76.5 sat exactly in that
            # strip. validate_plan never saw it (body_rect too small) while the GATE did
            # (courtyard) -- so the router emitted a keep-out violation and the gate caught it
            # afterwards. A keep-out means the whole MODULE, so use the courtyard there.
            if ref in KEEPOUT_REFS:
                fbb = fp.GetBoundingBox(False, True)
                body_rect = (fbb.GetX() / UM, fbb.GetY() / UM,
                             (fbb.GetX() + fbb.GetWidth()) / UM,
                             (fbb.GetY() + fbb.GetHeight()) / UM)
            else:
                pbbs = [p.GetBoundingBox() for p in fp.Pads()]
                if pbbs:
                    x0 = min(b.GetX() for b in pbbs) / UM
                    y0 = min(b.GetY() for b in pbbs) / UM
                    x1 = max(b.GetX() + b.GetWidth() for b in pbbs) / UM
                    y1 = max(b.GetY() + b.GetHeight() for b in pbbs) / UM
                    fbb = None
                    body_rect = (x0, y0, x1, y1)
                else:
                    fbb = fp.GetBoundingBox(False, True)
                    body_rect = None
            if body_rect is None:
                body_rect = (fbb.GetX() / UM, fbb.GetY() / UM,
                             (fbb.GetX() + fbb.GetWidth()) / UM,
                             (fbb.GetY() + fbb.GetHeight()) / UM)
            b_layers = (F, B) if ref in KEEPOUT_REFS else ((F if front else B),)
            for bl in b_layers:
                bodies.append((ref, bl, body_rect))
        for p in fp.Pads():
            n = p.GetNet()
            ls = p.GetLayerSet()
            sides = set()
            if ls.Contains(pcbnew.F_Cu):
                sides.add(F)
            if ls.Contains(pcbnew.B_Cu):
                sides.add(B)
            pads.append((ref, p.GetNumber() or '""',
                         n.GetNetname() if n else "", n.GetNetCode() if n else 0,
                         sides, pad_rect(p)))

    # nets that need routing: >= 2 distinct pads
    net_pads = defaultdict(list)
    for ref, num, name, code, sides, rect in pads:
        if code:
            net_pads[(code, name)].append((ref, num, sides, rect))
    return {"board": b, "origin": (ox, oy), "size": (w, h),
            "pads": pads, "bodies": bodies, "net_pads": net_pads}


def build_via_ok(blocked, nx, ny, pitch):
    """B28 (2026-10-21): precompute where a via may legally sit, ONCE.

    The A* was re-checking a (2r+1)^2 ~ 225-cell free disc at EVERY expansion -- measured
    330,050 disc calls = 2.0s of the 5.07s per net. A via's legality depends only on the
    static obstacles, so it is computed once per grid here and read as O(1) in the search.
    """
    r = int(math.ceil((VIA_D / 2 + CLEAR + TRACK_W / 2) / pitch)) + 1
    ok = [bytearray(nx * ny) for _ in (0, 1)]
    for lay in (0, 1):
        for j in range(ny):
            row = ok[lay]
            for i in range(nx):
                good = True
                for dj in range(-r, r + 1):
                    nj = j + dj
                    if nj < 0 or nj >= ny:
                        good = False
                        break
                    brow = blocked[lay][nj]
                    brow2 = blocked[1 - lay][nj]
                    for di in range(-r, r + 1):
                        ni = i + di
                        if ni < 0 or ni >= nx or brow[ni] or brow2[ni]:
                            good = False
                            break
                    if not good:
                        break
                if good:
                    # B32 (2026-10-21): MUST be the flat index j*nx+i. Writing row[i] made
                    # every row overwrite the same nx slots, so the table only held the LAST
                    # row's values while A* read j*nx+i -- measured: via_ok reported 0.0%
                    # across the ENTIRE board and the router placed ZERO vias (down from 16).
                    row[j * nx + i] = 1
    return ok


def build_grid(world, pitch):
    """Occupancy grid per layer. A cell is blocked if any obstacle covers it."""
    ox, oy = world["origin"]
    w, h = world["size"]
    nx = int(math.ceil(w / pitch)) + 1
    ny = int(math.ceil(h / pitch)) + 1
    blocked = [[bytearray(nx) for _ in range(ny)] for _ in range(2)]
    # own-pad exceptions are applied per-route, not globally, so the grid stays shared

    def mark(layer, rect, grow):
        x0, y0, x1, y1 = rect
        i0 = max(0, int((x0 - grow - ox) / pitch) - 1)
        i1 = min(nx - 1, int((x1 + grow - ox) / pitch) + 1)
        j0 = max(0, int((y0 - grow - oy) / pitch) - 1)
        j1 = min(ny - 1, int((y1 + grow - oy) / pitch) + 1)
        for j in range(j0, j1 + 1):
            row = blocked[layer][j]
            for i in range(i0, i1 + 1):
                row[i] = 1

    half = TRACK_W / 2
    for ref, num, name, code, sides, rect in world["pads"]:
        if name == "HOLE" or ref.startswith(HOLE_PREFIXES):
            grow = HOLE_CLEAR + half
        else:
            # unnamed pads are METAL (bug B5) -- same margin as named ones
            grow = CLEAR + half
        for layer in sides:
            mark(layer, rect, grow)
    for ref, layer, rect in world["bodies"]:
        mark(layer, rect, 0.0)
    # edge keep-out
    mark(F, (ox - EDGE_KEEP, oy - EDGE_KEEP, ox, oy + h + EDGE_KEEP), 0)
    mark(B, (ox - EDGE_KEEP, oy - EDGE_KEEP, ox, oy + h + EDGE_KEEP), 0)
    mark(F, (ox + w, oy - EDGE_KEEP, ox + w + EDGE_KEEP, oy + h + EDGE_KEEP), 0)
    mark(B, (ox + w, oy - EDGE_KEEP, ox + w + EDGE_KEEP, oy + h + EDGE_KEEP), 0)
    mark(F, (ox, oy - EDGE_KEEP, ox + w, oy), 0)
    mark(B, (ox, oy - EDGE_KEEP, ox + w, oy), 0)
    mark(F, (ox, oy + h, ox + w, oy + h + EDGE_KEEP), 0)
    mark(B, (ox, oy + h, ox + w, oy + h + EDGE_KEEP), 0)
    return blocked, nx, ny


def to_cell(world, pitch, x, y):
    ox, oy = world["origin"]
    return (int(round((x - ox) / pitch)), int(round((y - oy) / pitch)))


def to_mm(world, pitch, i, j):
    ox, oy = world["origin"]
    return (ox + i * pitch, oy + j * pitch)


def unblock_own(blocked, world, pitch, own_pads, sides_union, all_pads, reach=0.35):
    """Clear a small disc/rect around each own pad so a route can ENTER the pad.

    The first version cleared the endpoint footprints' whole bodies. That let a route
    travel under U1 and cut across its entire pin row: measured 38 under-clearance
    violations and 5 hard SHORTs (a track through U1.2..U1.7). The exception must be
    just big enough to reach the pad -- `reach` mm around the pad rect -- never the body.

    Returns a restore list for `restore()`.
    """
    ox, oy = world["origin"]
    nx = len(blocked[0][0])
    ny = len(blocked[0])
    saved = []
    for rect in own_pads:
        x0, y0, x1, y1 = (rect[0] - reach, rect[1] - reach, rect[2] + reach, rect[3] + reach)
        i0 = max(0, int((x0 - ox) / pitch))
        i1 = min(nx - 1, int((x1 - ox) / pitch))
        j0 = max(0, int((y0 - oy) / pitch))
        j1 = min(ny - 1, int((y1 - oy) / pitch))
        for layer in sides_union:
            for j in range(j0, j1 + 1):
                for i in range(i0, i1 + 1):
                    mx, my = ox + i * pitch, oy + j * pitch
                    # B18 (2026-10-21): the pad's OWN INTERIOR is always reachable.
                    # Without this the goal cell stayed blocked -- measured: /F33_CS_N's
                    # goal cell blocked=1 and every F33 net was unroutable, because at
                    # U2's 1.27mm pad pitch each neighbour's clearance ring overlaps this
                    # pad's centre, so the guard below vetoed clearing the pad's middle.
                    inside_own = (rect[0] <= mx <= rect[2] and rect[1] <= my <= rect[3])
                    if not inside_own:
                        # In the HALO only: never clear another pad's clearance ring
                        # (rect grown by CLEAR + half). Guarding only the bare rect let a
                        # route run 0.03mm from U1.38 (measured SHORT through /I2C_SCL).
                        g = CLEAR + TRACK_W / 2
                        if any(p2[0] - g <= mx <= p2[2] + g and p2[1] - g <= my <= p2[3] + g
                               for p2 in all_pads if p2 != rect):
                            continue
                    if blocked[layer][j][i]:
                        saved.append((layer, j, i))
                        blocked[layer][j][i] = 0
    return saved


def restore(blocked, saved):
    for layer, j, i in saved:
        blocked[layer][j][i] = 1


def astar(blocked, nx, ny, start, goal, pitch, allow_layers, via_ok=None, hweight=2.0,
          max_exp=2000000, via_cost=None):
    """A* over (i, j, layer). start/goal are (i, j, layer) tuples."""
    if start[2] not in allow_layers or goal[2] not in allow_layers:
        return None
    si, sj, sl = start
    gi, gj, gl = goal
    if blocked[sl][sj][si] and (si, sj) != (gi, gj):
        return None
    if blocked[gl][gj][gi] and (si, sj) != (gi, gj):
        return None
    if via_ok is None:
        via_ok = [[1] * (nx * ny) for _ in (0, 1)]

    def h(i, j, l):
        # B26 (2026-10-21): the heuristic was UNWEIGHTED, so with BEND_COST and via costs in
        # the path cost the search expanded nearly every reachable cell -- measured 5.07s
        # for ONE 2-pad net. Multiplier 2.0 trades optimality for speed; we do not need the
        # shortest path, only a LEGAL one, because validate_plan gates every candidate
        # afterwards. Higher is faster; 2.0 keeps the search well behaved.
        return 2.0 * (abs(i - gi) + abs(j - gj))

    # B27 (2026-10-21): flat arrays instead of dicts keyed by (i,j,l) tuples. The dict
    # versions allocated a tuple per node and dominated runtime (2.22s per net even after
    # the heuristic fix). Array indexing is ~10x faster and the grid is fixed-size.
    INF = float("inf")
    ncell = nx * ny * 2
    def idx(i, j, l):
        return (i * ny + j) * 2 + l
    best_g = [INF] * ncell
    prev_of = [-1] * ncell
    openq = [(h(si, sj, sl), 0, (si, sj, sl))]
    DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))
    closed = bytearray(ncell)
    expansions = 0
    MAX_EXP = max_exp
    while openq:
        expansions += 1
        if expansions > MAX_EXP:
            return None
        f, g, cur = heapq.heappop(openq)
        i, j, l = cur
        ci = idx(i, j, l)
        if closed[ci]:
            continue
        closed[ci] = 1
        if (i, j, l) == (gi, gj, gl):
            path = []
            node_i = ci
            while node_i != -1:
                k = node_i // 2          # k = i*ny + j  (see idx())
                li = node_i % 2
                ii, jj = divmod(k, ny)   # stride is ny, NOT nx -- measured bug
                path.append((ii, jj, li))
                node_i = prev_of[node_i]
            return list(reversed(path))
        # planar moves
        for di, dj in DIRS:
            ni, nj = i + di, j + dj
            if 0 <= ni < nx and 0 <= nj < ny and not blocked[l][nj][ni]:
                bend = 0
                if prev_of[ci] != -1:
                    pk = prev_of[ci] // 2
                    pj_, pi_ = divmod(pk, nx)
                    if pi_ != i or pj_ != j:
                        bend = BEND_COST
                ng = g + 1 + bend
                nidx = idx(ni, nj, l)
                if not closed[nidx] and ng < best_g[nidx]:
                    best_g[nidx] = ng
                    prev_of[nidx] = ci
                    heapq.heappush(openq, (ng + h(ni, nj, l), ng, (ni, nj, l)))
        # via moves
        for nl in (0, 1):
            if nl == l or nl not in allow_layers:
                continue
            # B28: O(1) lookup of the precomputed via-feasibility bitmap. The precise
            # rules (clearance to every pad, hole, routed track and via) are enforced by
            # validate_plan on the finished route -- this is a fast necessary condition.
            ok = bool(via_ok[l][j * nx + i])
            if ok:
                ng = g + (via_cost if via_cost is not None else VIA_COST)
                nidx = idx(i, j, nl)
                if not closed[nidx] and ng < best_g[nidx]:
                    best_g[nidx] = ng
                    prev_of[nidx] = ci
                    heapq.heappush(openq, (ng + h(i, j, nl), ng, (i, j, nl)))
    return None


def path_to_copper(world, pitch, path):
    """Convert an (i,j,layer) cell path into per-layer segments plus via positions.

    BUG FIXED 2026-10-21: the first version collapsed each same-layer RUN into a single
    straight segment from the run's start to its end. A* zig-zags, so that straight line
    cut straight across the obstacles the path had carefully steered around -- measured as
    48 under-clearance violations and 47 dead ends. Every consecutive cell pair must
    become its own segment.
    """
    segs = []       # (layer, (x0,y0), (x1,y1))
    vias = []       # (x, y)
    for k in range(1, len(path)):
        i, j, l = path[k]
        pi, pj, pl = path[k - 1]
        if l != pl:
            vias.append(to_mm(world, pitch, i, j))
            continue
        p0 = to_mm(world, pitch, pi, pj)
        p1 = to_mm(world, pitch, i, j)
        if p0 != p1:
            segs.append((l, p0, p1))
    return segs, vias


def merge_collinear(segs):
    """Merge consecutive segments that share a layer and are collinear -- keeps the board
    readable and the DRC happy without changing the geometry."""
    out = []
    for layer, p0, p1 in segs:
        if out and out[-1][0] == layer:
            l0, a, b = out[-1]
            if (abs(b[0] - p0[0]) < 1e-9 and abs(b[1] - p0[1]) < 1e-9):
                cross = (b[0] - a[0]) * (p1[1] - b[1]) - (b[1] - a[1]) * (p1[0] - b[0])
                dot = (b[0] - a[0]) * (p1[0] - b[0]) + (b[1] - a[1]) * (p1[1] - b[1])
                if abs(cross) < 1e-9 and dot > 0:
                    out[-1] = (layer, a, p1)
                    continue
        out.append((layer, p0, p1))
    return out


def _seg_rect_dist(x0, y0, x1, y1, bb):
    """Exact-ish segment-to-rectangle distance (25 um sampling + edge distances)."""
    rx0, ry0, rx1, ry1 = bb
    L = math.hypot(x1 - x0, y1 - y0)
    steps = max(2, int(L / 0.025) + 2)
    for i in range(steps + 1):
        t = i / steps
        px, py = x0 + t * (x1 - x0), y0 + t * (y1 - y0)
        if rx0 <= px <= rx1 and ry0 <= py <= ry1:
            return 0.0
    best = 1e9
    for (ex0, ey0, ex1, ey1) in ((rx0, ry0, rx1, ry0), (rx1, ry0, rx1, ry1),
                                 (rx1, ry1, rx0, ry1), (rx0, ry1, rx0, ry0)):
        for (px, py) in ((x0, y0), (x1, y1)):
            best = min(best, _pt_seg(px, py, ex0, ey0, ex1, ey1))
        for (qx, qy) in ((ex0, ey0), (ex1, ey1)):
            best = min(best, _pt_seg(qx, qy, x0, y0, x1, y1))
    return best


def _pt_seg(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def _pt_seg_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def _seg_seg_dist(ax0, ay0, ax1, ay1, bx0, by0, bx1, by1, res=0.05):
    """Approximate segment-to-segment distance (sample the shorter one)."""
    La = math.hypot(ax1 - ax0, ay1 - ay0)
    Lb = math.hypot(bx1 - bx0, by1 - by0)
    if Lb < La:
        ax0, ay0, ax1, ay1, bx0, by0, bx1, by1 = bx0, by0, bx1, by1, ax0, ay0, ax1, ay1
        La = Lb
    n = max(2, int(La / res) + 2)
    best = 1e9
    for i in range(n + 1):
        t = i / n
        best = min(best, _pt_seg_dist(ax0 + t * (ax1 - ax0), ay0 + t * (ay1 - ay0),
                                      bx0, by0, bx1, by1))
    return best


def validate_plan(world, pitch, plan, own_keys, own_rects, code):
    """In-memory gate check on a planned route BEFORE any copper is written.

    This is what makes the router gate-bound: a plan that would fail
    check_lane_clearance / check_hole_clearance / check_copper_under_body is discarded
    here, so the router cannot emit copper the gates would reject. Returns (ok, reason).
    """
    half = TRACK_W / 2
    segs, vias = [], []
    for path in plan:
        s2, v2 = path_to_copper(world, pitch, path)
        segs += s2
        vias += v2
    if not segs:
        return False, "no segments"
    # 1. endpoints must land inside their own pads, on a layer the pad owns
    own = {}
    for key, sides, rect in own_rects:
        own[key] = (sides, rect)
    first = segs[0]
    last = segs[-1]
    def in_pad(pt, key):
        sides, rect = own[key]
        return (rect[0] - 0.05 <= pt[0] <= rect[2] + 0.05
                and rect[1] - 0.05 <= pt[1] <= rect[3] + 0.05)
    ka, kc = own_keys[0], own_keys[1]
    if not in_pad(first[1], ka):
        return False, f"start not on pad {ka[0]}.{ka[1]}"
    if not in_pad(last[2], kc):
        return False, f"end not on pad {kc[0]}.{kc[1]}"
    if first[0] not in own[ka][0]:
        return False, f"start on layer without pad {ka[0]}.{ka[1]}"
    if last[0] not in own[kc][0]:
        return False, f"end on layer without pad {kc[0]}.{kc[1]}"
    # 2. clearance against every foreign pad and every hole
    for layer, p0, p1 in segs:
        for ref, num, name, pcode, sides, rect in world["pads"]:
            if pcode == code and (ref, num) in own:
                continue
            if name == "HOLE" or ref.startswith(HOLE_PREFIXES):
                if _seg_rect_dist(p0[0], p0[1], p1[0], p1[1], rect) - half < HOLE_CLEAR - 0.001:
                    return False, f"hole {ref} clearance"
                continue
            if layer not in sides:
                continue
            if (ref, num) in own and pcode == code:
                continue
            if _seg_rect_dist(p0[0], p0[1], p1[0], p1[1], rect) - half < CLEAR - 0.001:
                return False, f"clearance to {ref}.{num}"
    # 3. no traversal of a foreign body (own-pad entry exempt)
    # B38 (2026-10-22): this check was PER SEGMENT -- `L * inside / steps > 0.5` -- so at a
    # fine grid pitch each zigzag segment is ~0.05mm long and EVERY segment passed while the
    # route tunnelled through the keep-out. Measured: /E28_BUSY ran 5.71mm beneath U_E28 and
    # validate_plan accepted it; the gate caught it afterwards. Now the inside-length is
    # ACCUMULATED over the whole plan and compared once.
    total_inside = 0.0
    for layer, p0, p1 in segs:
        for ref, blayer, rect in world["bodies"]:
            if blayer != layer:
                continue
            L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
            if L == 0:
                continue
            steps = max(2, int(L / 0.02) + 2)
            inside = 0
            for i in range(steps):
                t = (i + 0.5) / steps
                px, py = p0[0] + t * (p1[0] - p0[0]), p0[1] + t * (p1[1] - p0[1])
                if not (rect[0] <= px <= rect[2] and rect[1] <= py <= rect[3]):
                    continue
                # B39 (2026-10-22): the own-pad exemption was a 2.0mm halo around EVERY own
                # pad. For a pad on the keep-out module's BOUNDARY (E28 pads sit on the
                # module edge, opening outward) that halo reaches INSIDE the module, so a
                # route could cross the keep-out along the pad row and be exempted the whole
                # way: measured /E28_BUSY crossing 5.71mm. The exemption is now a tight
                # 0.6mm reach -- enough to touch the pad and its immediate escape, not enough
                # to tunnel along the boundary.
                if any(r2[0] - 0.6 <= px <= r2[2] + 0.6 and r2[1] - 0.6 <= py <= r2[3] + 0.6
                       for _k, _sd, r2 in own_rects):
                    continue
                inside += 1
            total_inside += L * inside / steps
    if total_inside > 0.5:
        return False, f"traverses a keep-out module ({total_inside:.2f}mm under body)"

    # 4. B24 (2026-10-21): ISOLATION against copper already routed by earlier nets.
    # Measured: 5 violations appeared once more nets were placed -- /F33_BUSY running
    # straight through /F33_RESET_N's via (-0.350mm) and through /F33_RESET_N track
    # (-0.200mm), /SPI2_MISO x via. The router marked routed copper as a grid OBSTACLE but
    # never validated its own output against it, so a path that grazed a via was accepted.
    # Same rules as check_lane_isolation.py: track-vs-track (same layer), track-vs-via,
    # via-vs-via, all >= CLEAR between copper edges.
    for layer, p0, p1 in segs:
        for rnet, rlayer, q0, q1, rw in world.get("routed_segs", []):
            if rnet == code or rlayer != layer:
                continue
            if _seg_seg_dist(p0[0], p0[1], p1[0], p1[1], q0[0], q0[1], q1[0], q1[1]) - half - rw / 2 < CLEAR - 0.001:
                return False, f"isolation vs routed {rnet}"
    for layer, p0, p1 in segs:
        for rnet, rp, rw in world.get("routed_vias", []):
            if rnet == code:
                continue
            if _pt_seg_dist(rp[0], rp[1], p0[0], p0[1], p1[0], p1[1]) - half - rw / 2 < CLEAR - 0.001:
                return False, f"isolation vs routed via {rnet}"
    for (vx, vy) in vias:
        for rnet, rlayer, q0, q1, rw in world.get("routed_segs", []):
            if rnet == code:
                continue
            if _pt_seg_dist(vx, vy, q0[0], q0[1], q1[0], q1[1]) - VIA_D / 2 - rw / 2 < CLEAR - 0.001:
                return False, f"isolation vs routed {rnet} (via)"
        for rnet, rp, rw in world.get("routed_vias", []):
            if rnet == code:
                continue
            if math.hypot(vx - rp[0], vy - rp[1]) - VIA_D / 2 - rw / 2 < CLEAR - 0.001:
                return False, f"isolation vs routed via {rnet} (via)"
    return True, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default=BOARD)
    ap.add_argument("--pitch", type=float, default=0.1)
    ap.add_argument("--nets", default="")
    ap.add_argument("--order", default="constrained",
                    choices=["alpha", "constrained", "reverse", "longest"],
                    help="net ordering: 'constrained' (fewest pads first -- standard PCB "
                         "practice) or 'alpha'. See --promote for rip-up-and-reroute.")
    ap.add_argument("--via-cost", type=int, default=None,
                    help="A* cost of one via in grid steps (default 25 = ~2.5mm of detour). "
                         "Lower values bias the router to escape to the back layer EARLY, "
                         "which is the lever for a congested single-layer corridor.")
    ap.add_argument("--promote", default="",
                    help="comma-separated nets forced to the FRONT of the route order. This is "
                         "the rip-up-and-reroute lever: a net that failed because an earlier "
                         "net's via blocked it can be routed first, then the rest follow.")
    ap.add_argument("--append", action="store_true",
                    help="route onto a board that already has copper (incremental routing). "
                         "Existing tracks become obstacles AND are loaded as routed copper so "
                         "the isolation checks apply. Without this the router refuses (exit 4).")
    ap.add_argument("--max-expansions", type=int, default=2000000,
                    help="per-net A* expansion cap; exceeded -> net reported UNROUTED, not hung")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    world = load_world(args.board)
    world["routed_segs"] = []   # copper placed by already-accepted nets (B24)
    world["routed_vias"] = []
    b = world["board"]
    existing = [t for t in b.GetTracks() if "TRACK" in str(type(t)) and "VIA" not in str(type(t))]
    if existing and not args.dry_run and not args.append:
        print(f"REFUSED: board already has {len(existing)} track(s) -- "
              "run build_hub_board_v10.py for a clean board first, or pass --append")
        return 4
    if existing and args.append:
        # B33 (2026-10-22): incremental routing. Load the existing copper as routed copper so
        # the isolation self-check applies to it, and mark it as grid obstacles so new nets
        # route around it. This is what makes cumulative routing possible.
        for t in b.GetTracks():
            if "VIA" in str(type(t)):
                p = t.GetPosition()
                world["routed_vias"].append((t.GetNetname() or "?", (p.x / UM, p.y / UM),
                                             t.GetWidth() / UM))
            elif "TRACK" in str(type(t)):
                world["routed_segs"].append((
                    t.GetNetname() or "?", t.GetLayer(),
                    (t.GetStart().x / UM, t.GetStart().y / UM),
                    (t.GetEnd().x / UM, t.GetEnd().y / UM), t.GetWidth() / UM))


    blocked, nx, ny = build_grid(world, args.pitch)
    if existing and args.append:
        # B37 (2026-10-22): loading existing copper for VALIDATION is not enough -- it must
        # also be marked into the A* GRID as an obstacle, or the search routes straight
        # through it and validate_plan rejects every candidate. Measured: pass 2 of the
        # escalating route retried 12 nets and routed 0, every one failing with
        # "self-check: isolation vs routed <net>". Same failure class as B34, different site.
        ox0, oy0 = world["origin"]
        g_mark = CLEAR + TRACK_W
        for t in b.GetTracks():
            if "TRACK" not in str(type(t)) or "VIA" in str(type(t)):
                continue
            lay = F if t.GetLayer() == pcbnew.F_Cu else B
            x0, y0 = t.GetStart().x / UM, t.GetStart().y / UM
            x1, y1 = t.GetEnd().x / UM, t.GetEnd().y / UM
            rx0, rx1 = min(x0, x1), max(x0, x1)
            ry0, ry1 = min(y0, y1), max(y0, y1)
            i0 = max(0, int((rx0 - g_mark - ox0) / args.pitch) - 1)
            i1 = min(nx - 1, int((rx1 + g_mark - ox0) / args.pitch) + 1)
            j0 = max(0, int((ry0 - g_mark - oy0) / args.pitch) - 1)
            j1 = min(ny - 1, int((ry1 + g_mark - oy0) / args.pitch) + 1)
            for j in range(j0, j1 + 1):
                for i in range(i0, i1 + 1):
                    mx, my = ox0 + i * args.pitch, oy0 + j * args.pitch
                    if _seg_rect_dist(mx, my, mx, my, (rx0, ry0, rx1, ry1)) <= g_mark + args.pitch:
                        blocked[lay][j][i] = 1
        
    via_ok = build_via_ok(blocked, nx, ny, args.pitch)
    want = set(n for n in args.nets.split(",") if n)

    routed, failed, railed = [], [], []
    # Rails (GND / +3V3) are POUR territory (ADR-118 two-sided planes; v9 practice):
    # thin 0.2mm tracks are the wrong tool for a 580mA TX peak supply. They are skipped
    # here and poured in the next phase -- reported, never hidden.
    RAILS = ("GND", "+3V3")
    # B25 (2026-10-21): ordering matters. Measured with the old alphabetical order: a
    # flexible net routed early and its via blocked three later nets (F33_BUSY blocked
    # SPI2_MISO, SPI2_MOSI, F33_RESET_N -- each reported "self-check: isolation vs routed
    # /F33_BUSY (via)"). Standard PCB practice is to route the MOST CONSTRAINED nets first:
    # fewest pads, then smallest pad bounding box. A net with 2 pads and 8mm between them
    # has far less freedom than a 5-pad net spanning the board.
    items = sorted(world["net_pads"].items())
    def _n_pads(plist):
        return len({(r, n) for r, n, _sd, _rc in plist})
    def _extent(plist):
        xs = [rc[0] for *_x, rc in plist] + [rc[2] for *_x, rc in plist]
        ys = [rc[1] for *_x, rc in plist] + [rc[3] for *_x, rc in plist]
        return math.hypot(max(xs) - min(xs), max(ys) - min(ys)) if xs else 0.0
    if args.order == "constrained":
        items.sort(key=lambda kv: (_n_pads(kv[1]), _extent(kv[1]), kv[1][0][1]))
    elif args.order == "reverse":
        items = list(reversed(items))
    promote = [n for n in args.promote.split(",") if n]
    if promote:
        # B31 (2026-10-21): rip-up-and-reroute, done as a deterministic re-order. The
        # router is greedy: whichever net runs first keeps its copper. Promoting a
        # previously-blocked net to the front IS the rip-up -- the promoted net places
        # first, and the nets that used to block it re-route around it (or report failed).
        # Measured: different orderings route DIFFERENT net sets (constrained gets
        # SPI2_MISO/I2C/VTCXO; alpha gets F33_BUSY/F33_IRQ), so the order is a real lever.
        rank = {n: i for i, n in enumerate(promote)}
        items.sort(key=lambda kv: (rank.get(kv[1][0][1], len(promote)),
                                   _n_pads(kv[1]), _extent(kv[1]), kv[1][0][1]))
    elif args.order == "longest":
        items.sort(key=lambda kv: (-_extent(kv[1]), _n_pads(kv[1]), kv[1][0][1]))
    for (code, name), plist in items:
        if want and name not in want:
            continue
        if name in RAILS and not want:
            railed.append(name)
            continue
        uniq = {}
        for ref, num, sides, rect in plist:
            uniq.setdefault((ref, num), (sides, rect))
        if len(uniq) < 2:
            continue
        keys = list(uniq.keys())
        # route pads in sequence: first -> each subsequent (chain), which is what a
        # multi-pad net needs on a single layer pair
        ok_all = True
        plan = []
        for a_key, c_key in zip(keys[:-1], keys[1:]):
            (a_sides, a_rect) = uniq[a_key]
            (c_sides, c_rect) = uniq[c_key]
            # start on the START pad's own layer, finish on the GOAL pad's own layer.
            # The first version forced both ends onto the same layer, so a cross-side net
            # (U1 front-only -> U3 back-only) ended on a layer where the goal pad has no
            # copper: measured as dead ends at U1.24 / U1.25 / U1.26. The via the path
            # needs is inserted by astar() itself.
            #
            # B14 (2026-10-21): allow was the UNION OF THE TWO PADS' sides -- for a
            # same-side net that locked the whole route onto one layer, so a front->front
            # net (e.g. U2.14 -> U1.12) could not via down to the EMPTY BACK to detour
            # around front bodies. Measured: every cross-side net routed, every same-side
            # F33/SPI2/antenna net failed. The route may use BOTH layers; only the
            # endpoints must sit on their own pads' layers (enforced by the start/goal
            # layer loop and validate_plan).
            allow = [F, B]
            all_rects = [pr[5] for pr in world["pads"]]
            saved = unblock_own(blocked, world, args.pitch, [a_rect, c_rect], set(allow),
                                all_rects)
            try:
                start = to_cell(world, args.pitch, (a_rect[0] + a_rect[2]) / 2,
                                (a_rect[1] + a_rect[3]) / 2)
                goal = to_cell(world, args.pitch, (c_rect[0] + c_rect[2]) / 2,
                               (c_rect[1] + c_rect[3]) / 2)
                best = None
                for ls in sorted(a_sides):
                    for lg in sorted(c_sides):
                        p = astar(blocked, nx, ny, (start[0], start[1], ls),
                                  (goal[0], goal[1], lg), args.pitch, set(allow),
                                  via_ok=via_ok)
                        if p and (best is None or len(p) < len(best)):
                            best = p
            finally:
                restore(blocked, saved)
            if best is None:
                ok_all = False
                failed.append((name, f"{a_key[0]}.{a_key[1]} -> {c_key[0]}.{c_key[1]}"))
                break
            plan.append(best)
        if not ok_all:
            continue
        own_triples = [(k, uniq[k][0], uniq[k][1]) for k in keys]
        good, why = validate_plan(world, args.pitch, plan, keys, own_triples, code)
        if not good:
            failed.append((name, f"self-check: {why}"))
            continue
        routed.append((name, plan))
        # record this net's copper so LATER nets are validated against it (B24)
        for path in plan:
            s2, v2 = path_to_copper(world, args.pitch, path)
            for layer, p0, p1 in s2:
                world["routed_segs"].append((name, layer, p0, p1, TRACK_W))
            for (vx, vy) in v2:
                world["routed_vias"].append((name, (vx, vy), VIA_D))
        # B14 fix (2026-10-21): a routed net must become an OBSTACLE for the next net.
        # Without this the router placed 152 different-net under-clearances on B.Cu --
        # /F33_IRQ crossed /F33_RESET_N, /U3_CS_N, USB, GNSS lines (measured -0.19mm).
        # Mark every segment + via of this net into the shared grid, grown by CLEAR+half.
        for path in plan:
            s2, v2 = path_to_copper(world, args.pitch, path)
            for layer, p0, p1 in s2:
                if abs(p1[0]-p0[0]) < 1e-9 and abs(p1[1]-p0[1]) < 1e-9:
                    continue
                r = (min(p0[0],p1[0]), min(p0[1],p1[1]), max(p0[0],p1[0]), max(p0[1],p1[1]))
                ox, oy = world["origin"]
                nx = len(blocked[0][0]); ny = len(blocked[0])
                # B34 (2026-10-22): MUST be CLEAR + TRACK_W, not CLEAR + TRACK_W/2.
                # A grid cell is a candidate CENTRELINE for the new track, so keeping CLEAR
                # between copper EDGES needs
                #     centre-to-centre >= CLEAR + (other half) + (own half) = CLEAR + TRACK_W
                # Marking only CLEAR + TRACK_W/2 under-marked by 0.10mm, so A* happily routed
                # paths that validate_plan then rejected: measured
                # "self-check: isolation vs routed /SPI2_MISO" on both /SPI2_MOSI and
                # /SPI2_SCK -- the router found a path and threw it away, which is why those
                # nets could never route together no matter the ordering or via cost.
                g = CLEAR + TRACK_W
                i0 = max(0, int((r[0]-g-ox)/args.pitch)-1); i1 = min(nx-1, int((r[2]+g-ox)/args.pitch)+1)
                j0 = max(0, int((r[1]-g-oy)/args.pitch)-1); j1 = min(ny-1, int((r[3]+g-oy)/args.pitch)+1)
                for j in range(j0, j1+1):
                    for i in range(i0, i1+1):
                        mx, my = ox+i*args.pitch, oy+j*args.pitch
                        d = _seg_rect_dist(mx, my, mx, my, (r[0], r[1], r[2], r[3]))
                        if d <= g + args.pitch:
                            blocked[layer][j][i] = 1
            for (vx, vy) in v2:
                ox, oy = world["origin"]
                nx = len(blocked[0][0]); ny = len(blocked[0])
                g = CLEAR + VIA_D/2 + TRACK_W/2
                i0 = max(0, int((vx-g-ox)/args.pitch)); i1 = min(nx-1, int((vx+g-ox)/args.pitch))
                j0 = max(0, int((vy-g-oy)/args.pitch)); j1 = min(ny-1, int((vy+g-oy)/args.pitch))
                for lay in (F, B):
                    for j in range(j0, j1+1):
                        for i in range(i0, i1+1):
                            mx, my = ox+i*args.pitch, oy+j*args.pitch
                            if math.hypot(mx-vx, my-vy) <= g:
                                blocked[lay][j][i] = 1
        if args.limit and len(routed) >= args.limit:
            break

    print(f"routed {len(routed)} net(s): {[n for n, _ in routed]}")
    print(f"rails deferred to pours: {railed}")
    print(f"failed {len(failed)}: {failed[:12]}")
    if args.dry_run:
        return 0

    for name, plan in routed:
        net = b.FindNet(name)
        if net is None:
            b.Add(pcbnew.NETINFO_ITEM(b, name))
            net = b.FindNet(name)
        for path in plan:
            segs, vias = path_to_copper(world, args.pitch, path)
            segs = merge_collinear(segs)
            for layer_idx, (x0, y0), (x1, y1) in segs:
                if abs(x1 - x0) < 1e-9 and abs(y1 - y0) < 1e-9:
                    continue
                t = pcbnew.PCB_TRACK(b)
                t.SetNet(net)
                t.SetLayer(pcbnew.F_Cu if layer_idx == F else pcbnew.B_Cu)
                t.SetWidth(int(TRACK_W * UM))
                t.SetStart(pcbnew.VECTOR2I(int(x0 * UM), int(y0 * UM)))
                t.SetEnd(pcbnew.VECTOR2I(int(x1 * UM), int(y1 * UM)))
                b.Add(t)
            for (x, y) in vias:
                v = pcbnew.PCB_VIA(b)
                v.SetNet(net)
                v.SetPosition(pcbnew.VECTOR2I(int(x * UM), int(y * UM)))
                v.SetWidth(int(VIA_D * UM))
                v.SetDrill(int(VIA_DRILL * UM))
                b.Add(v)
    nfps = len(b.GetFootprints())
    if nfps < 20:
        raise SystemExit(f"REFUSED: refusing to save a board with only {nfps} footprints "
                         "(clobber guard -- expected 28)")
    pcbnew.SaveBoard(args.board, b)
    print(f"saved {args.board}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
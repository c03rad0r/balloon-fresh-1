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
BEND_COST = 2
HOLE_PREFIXES = ("H", "HW")
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
        if not ref.startswith(HOLE_PREFIXES):
            fbb = fp.GetBoundingBox(False, True)
            bodies.append((ref, F if front else B,
                           (fbb.GetX() / UM, fbb.GetY() / UM,
                            (fbb.GetX() + fbb.GetWidth()) / UM,
                            (fbb.GetY() + fbb.GetHeight()) / UM)))
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
                    # never clear a cell that belongs to ANOTHER pad: the first version
                    # cleared a 1.2mm halo, which at U1's 1.27mm pin pitch reached the
                    # neighbouring pins (measured: 5 hard SHORTs through U1.2..U1.7)
                    # the neighbouring pad's CLEARANCE RING (rect grown by CLEAR + half)
                    # is what must stay blocked -- guarding only its bare rect let the
                    # route run 0.03mm from U1.38 (measured SHORT through /I2C_SCL)
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


def astar(blocked, nx, ny, start, goal, pitch, allow_layers):
    """A* over (i, j, layer). start/goal are (i, j, layer) tuples."""
    if start[2] not in allow_layers or goal[2] not in allow_layers:
        return None
    si, sj, sl = start
    gi, gj, gl = goal
    if blocked[sl][sj][si] and (si, sj) != (gi, gj):
        return None
    if blocked[gl][gj][gi] and (si, sj) != (gi, gj):
        return None

    def h(i, j, l):
        return abs(i - gi) + abs(j - gj)

    openq = [(h(si, sj, sl), 0, (si, sj, sl), None)]
    seen = {}
    came = {}
    DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))
    while openq:
        f, g, cur, prev = heapq.heappop(openq)
        if cur in seen and seen[cur] <= g:
            continue
        seen[cur] = g
        came[cur] = prev
        i, j, l = cur
        if (i, j, l) == (gi, gj, gl):
            path = []
            node = cur
            while node is not None:
                path.append(node)
                node = came.get(node)
            return list(reversed(path))
        # planar moves
        for di, dj in DIRS:
            ni, nj = i + di, j + dj
            if 0 <= ni < nx and 0 <= nj < ny and not blocked[l][nj][ni]:
                ng = g + 1 + (BEND_COST if prev is not None and (prev[0] != i or prev[1] != j) else 0)
                node = (ni, nj, l)
                if node not in seen or seen[node] > ng:
                    heapq.heappush(openq, (ng + h(ni, nj, l), ng, node, cur))
        # via moves
        for nl in (0, 1):
            if nl == l or nl not in allow_layers:
                continue
            # a via occupies both layers; require a small free disc
            ok = True
            r = int(math.ceil((VIA_D / 2) / pitch)) + 1
            for dj in range(-r, r + 1):
                for di in range(-r, r + 1):
                    ni, nj = i + di, j + dj
                    if not (0 <= ni < nx and 0 <= nj < ny):
                        ok = False
                        break
                    if blocked[l][nj][ni] or blocked[nl][nj][ni]:
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                ng = g + VIA_COST
                node = (i, j, nl)
                if node not in seen or seen[node] > ng:
                    heapq.heappush(openq, (ng + h(i, j, nl), ng, node, cur))
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
    for layer, p0, p1 in segs:
        for ref, blayer, rect in world["bodies"]:
            if blayer != layer:
                continue
            L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
            if L == 0:
                continue
            steps = max(2, int(L / 0.05) + 2)
            inside = 0
            for i in range(steps):
                t = (i + 0.5) / steps
                px, py = p0[0] + t * (p1[0] - p0[0]), p0[1] + t * (p1[1] - p0[1])
                if not (rect[0] <= px <= rect[2] and rect[1] <= py <= rect[3]):
                    continue
                if any(r2[0] - 2.0 <= px <= r2[2] + 2.0 and r2[1] - 2.0 <= py <= r2[3] + 2.0
                       for _k, _sd, r2 in own_rects):
                    continue
                inside += 1
            if L * inside / steps > 0.5:
                return False, f"traverses {ref}"
    return True, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default=BOARD)
    ap.add_argument("--pitch", type=float, default=0.1)
    ap.add_argument("--nets", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    world = load_world(args.board)
    b = world["board"]
    existing = [t for t in b.GetTracks() if "TRACK" in str(type(t)) and "VIA" not in str(type(t))]
    if existing and not args.dry_run:
        print(f"REFUSED: board already has {len(existing)} track(s) -- "
              "run build_hub_board_v10.py for a clean board first")
        return 4

    blocked, nx, ny = build_grid(world, args.pitch)
    want = set(n for n in args.nets.split(",") if n)

    routed, failed = [], []
    items = sorted(world["net_pads"].items())
    for (code, name), plist in items:
        if want and name not in want:
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
            allow = sorted(a_sides | c_sides)
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
                                  (goal[0], goal[1], lg), args.pitch, set(allow))
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
        if args.limit and len(routed) >= args.limit:
            break

    print(f"routed {len(routed)} net(s): {[n for n, _ in routed]}")
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
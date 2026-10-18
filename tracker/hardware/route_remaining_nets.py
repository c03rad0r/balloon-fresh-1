"""Route the last four nets on hub v9 deterministically, then let kicad-cli DRC judge.

WHY A SCRIPT AND NOT A GUI SESSION. Six routing attempts failed because the failure was never in the
router's strategy -- it was that U4.17/U4.18 have NO legal escape at 0.60mm via size under 0.20/0.20
rules, and the blocking copper belongs to U4's OWN neighbours. Once measured (see
docs/fab/DECISIONS-UNROUTED-NETS.md) the remaining work is arithmetic. A grid A* with the CORRECT
clearance model does this exactly and reproducibly. No LLM, no GUI, no judgement.

WHY FOUR NETS AND NOT TWO. Astra's prescribed order: "establish those exits first, then reroute MISO and
DIO1 around them." You cannot route MOSI/SCK unless MISO/DIO1 move, and you cannot leave MISO/DIO1
unrouted. So: rip up MISO+DIO1 F.Cu, route SCK, MOSI, then restore MISO and DIO1 around them.
Dropping the rip-up and forgetting the restore would BREAK two nets that currently work -- that was a
real bug in the first version of this script and it is recorded here.

CLEARANCE MODEL -- the thing that made earlier attempts wrong.
Earlier scripts compared obstacle distance against the TRACK clearance (0.300mm) instead of what a PAD
escape needs, and printed "PAD ESCAPE CLEAR" while listing obstacles as BLOCKING. Here every obstacle is
inflated by (new_track_half + rule_clearance) and a grid cell is either blocked or not -- there is no
verdict line that can disagree with the data.

  track width      0.200 mm   clearance 0.200 mm
  via              0.500 mm dia / 0.250 mm drill  (== m_ViasMinSize, so NO waiver)
  grid             0.100 mm

TWO-PHASE, because pcbnew segfaults / raises on mutation-while-iterating:
  phase 1  read all geometry into plain Python data (no mutation)
  phase 2  reload the board, remove, add, refill, save

Usage:
    ~/venvs/kicad/bin/python tracker/hardware/route_remaining_nets.py \
        --in tracker/hardware/hub_board_v9.kicad_pcb --out /tmp/hub_routed.kicad_pcb --apply
"""
from __future__ import annotations

import argparse
import heapq
import math
import sys
from collections import defaultdict, namedtuple

import pcbnew

UM = 1_000_000.0

TRACK_W = 0.200
RULE_CLR = 0.200
VIA_DIA = 0.500
VIA_DRILL = 0.250
GRID = 0.100

NETS = ("/SX1280_MOSI", "/SX1280_SCK", "/SX1280_MISO", "/SX1280_DIO1")
RIP_F = ("/SX1280_MISO", "/SX1280_DIO1")     # ripped on F.Cu only, restored afterwards
LAYERS = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")

Seg = namedtuple("Seg", "x1 y1 x2 y2 infl net code layer")
Pad = namedtuple("Pad", "cx cy w h infl code")


def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def rect_dist(px, py, cx, cy, w, h):
    dx = max(cx - w / 2 - px, 0.0, px - (cx + w / 2))
    dy = max(cy - h / 2 - py, 0.0, py - (cy + h / 2))
    return math.hypot(dx, dy)


def read_geometry(path):
    """Phase 1: everything into plain data. No board mutation, so no SWIG invalidation."""
    b = pcbnew.LoadBoard(path)
    codes = {n: b.FindNet(n).GetNetCode() for n in NETS}
    rip_codes = {codes[n] for n in RIP_F}
    r_track = TRACK_W / 2 + RULE_CLR

    tracks = []          # (net, code, layer, x1,y1,x2,y2, width)
    vias = []            # (net, code, x, y, dia)
    for t in list(b.GetTracks()):
        if t.Type() == pcbnew.PCB_TRACE_T:
            s, e = t.GetStart(), t.GetEnd()
            tracks.append((t.GetNetname(), t.GetNetCode(), b.GetLayerName(t.GetLayer()),
                           s.x / UM, s.y / UM, e.x / UM, e.y / UM, t.GetWidth() / UM))
        elif t.Type() == pcbnew.PCB_VIA_T:
            p = t.GetPosition()
            vias.append((t.GetNetname(), t.GetNetCode(), p.x / UM, p.y / UM,
                         t.GetWidth(pcbnew.F_Cu) / UM))

    pads = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            pos = p.GetPosition()
            pads.append((fp.GetReference(), str(p.GetNumber()), p.GetNetCode(),
                         pos.x / UM, pos.y / UM, p.GetSize().x / UM, p.GetSize().y / UM,
                         tuple(LAYERS[i] for i in range(4)
                               if p.IsOnLayer((pcbnew.F_Cu, pcbnew.In1_Cu,
                                               pcbnew.In2_Cu, pcbnew.B_Cu)[i]))))
    return codes, rip_codes, tracks, vias, pads, r_track


class Model:
    """Obstacle model built from plain data, with named nets optionally ignored."""

    def __init__(self, tracks, vias, pads, r_track, ignore_nets=(), ignore_f_of=()):
        self.segs = defaultdict(list)
        self.pads = defaultdict(list)
        for net, code, layer, x1, y1, x2, y2, w in tracks:
            if net in ignore_nets:
                continue
            if net in ignore_f_of and layer == "F.Cu":
                continue
            self.segs[layer].append(Seg(x1, y1, x2, y2, w / 2 + r_track, net, code, layer))
        for net, code, x, y, dia in vias:
            if net in ignore_nets:
                continue
            for layer in LAYERS:
                self.segs[layer].append(Seg(x, y, x, y, dia / 2 + r_track, net, code, layer))
        for ref, num, code, cx, cy, w, h, side in pads:
            for layer in side:
                self.pads[layer].append(Pad(cx, cy, w, h, r_track, code))

    def blocked(self, layer, x, y, own_code):
        for s in self.segs[layer]:
            if own_code is not None and s.code == own_code:
                continue          # own-net copper may be approached; it is the route itself
            if seg_dist(x, y, s.x1, s.y1, s.x2, s.y2) < s.infl:
                return True
        for p in self.pads[layer]:
            if p.code == own_code:
                continue
            if rect_dist(x, y, p.cx, p.cy, p.w, p.h) < p.infl:
                return True
        return False


def astar(model, layer, own_code, start, goal, margin=None, grid=GRID):
    """Grid A*.

    GRID PHASE IS NOT COSMETIC. The first version derived x0 from the endpoints minus a margin,
    which put cells at 50.275 + i*0.100 -- none of which is 54.450. The MISO corridor between U4's
    thermal pad (right edge x=54.100) and the right pad column (left edge x=54.750) is only
    0.650 - 0.200 - 2*0.200 = 0.050 mm wide, and its usable range is 54.400..54.450. A 0.100 grid
    whose origin is arbitrary misses that entirely and reports "no path" on a corridor the shipped
    board actually routes at x=54.450 (0.250 mm to the thermal pad, exactly 0.200 to the column).
    So: align the origin to ABSOLUTE multiples of the step, via math.floor.
    """
    if margin is None:
        # A route must be allowed to go around things, not just between endpoints.
        margin = max(4.0, 0.35 * math.hypot(goal[0] - start[0], goal[1] - start[1]))
    x0 = math.floor((min(start[0], goal[0]) - margin) / grid) * grid
    y0 = math.floor((min(start[1], goal[1]) - margin) / grid) * grid
    nx = int(math.ceil((max(start[0], goal[0]) + margin - x0) / grid)) + 1
    ny = int(math.ceil((max(start[1], goal[1]) + margin - y0) / grid)) + 1

    def cell(p):
        return (int(round((p[0] - x0) / grid)), int(round((p[1] - y0) / grid)))

    si, sj = cell(start)
    gi, gj = cell(goal)
    if not (0 <= si < nx and 0 <= sj < ny and 0 <= gi < nx and 0 <= gj < ny):
        return None, f"start/goal outside grid {nx}x{ny}"

    free = bytearray(nx * ny)
    for j in range(ny):
        y = y0 + j * grid
        row = j * nx
        for i in range(nx):
            free[row + i] = 0 if model.blocked(layer, x0 + i * grid, y, own_code) else 1

    if not free[sj * nx + si]:
        # start cell may be the pad itself; clear a small disc around start and goal
        for j in range(max(0, sj - 2), min(ny, sj + 3)):
            for i in range(max(0, si - 2), min(nx, si + 3)):
                free[j * nx + i] = 1
    if not free[gj * nx + gi]:
        for j in range(max(0, gj - 2), min(ny, gj + 3)):
            for i in range(max(0, gi - 2), min(nx, gi + 3)):
                free[j * nx + i] = 1

    NB = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
          (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142))
    openq = [(0.0, si, sj)]
    best = {(si, sj): 0.0}
    came = {}
    while openq:
        _, i, j = heapq.heappop(openq)
        if (i, j) == (gi, gj):
            path = [(i, j)]
            while (i, j) in came:
                i, j = came[(i, j)]
                path.append((i, j))
            return [(x0 + a * grid, y0 + b * grid) for a, b in path[::-1]], None
        cur = best[(i, j)]
        for di, dj, cost in NB:
            ni, nj = i + di, j + dj
            if not (0 <= ni < nx and 0 <= nj < ny) or not free[nj * nx + ni]:
                continue
            nc = cur + cost
            if nc < best.get((ni, nj), 1e18):
                best[(ni, nj)] = nc
                came[(ni, nj)] = (i, j)
                heapq.heappush(openq, (nc + math.hypot(ni - gi, nj - gj), ni, nj))
    return None, "no path"


def simplify(pts):
    if len(pts) <= 2:
        return pts
    out = [pts[0]]
    for k in range(1, len(pts) - 1):
        ax, ay = out[-1]
        bx, by = pts[k]
        cx, cy = pts[k + 1]
        if abs((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) > 1e-9:
            out.append(pts[k])
    out.append(pts[-1])
    return out



def plan_dogbone(m, layer, netcode, start_pad, goal_pad, commit, vias_dia=VIA_DIA):
    """Route between two pads by dogboning onto an inner layer at both ends.

    A track from a 0.5mm-pitch QFN pad cannot reach an inner layer directly; it must first escape on
    F.Cu to a legal via site, then transition. This helper finds the FIRST legal via site outward from
    each pad (exhaustive small search, all four layers), routes the F.Cu stubs, routes the inner-layer
    leg, and commits every piece into the model so later nets see it.
    """
    R = vias_dia / 2

    def legal_via(x, y):
        worst = 1e9
        for lyr in LAYERS:
            for s in m.segs[lyr]:
                if s.code == netcode:
                    continue
                if seg_dist(x, y, s.x1, s.y1, s.x2, s.y2) - R < RULE_CLR - 1e-9:
                    return False
        for lyr in LAYERS:
            for pd in m.pads[lyr]:
                if pd.code == netcode:
                    continue
                if rect_dist(x, y, pd.cx, pd.cy, pd.w, pd.h) - R < RULE_CLR - 1e-9:
                    return False
        return True

    def find_via(pad):
        px, py = pad
        cands = []
        for r in (0.30, 0.40, 0.50, 0.60, 0.70, 0.85, 1.00, 1.20, 1.40, 1.70, 2.00, 2.40):
            for ang in range(0, 360, 15):
                a = math.radians(ang)
                x, y = px + r * math.cos(a), py + r * math.sin(a)
                if legal_via(x, y):
                    cands.append((r, x, y))
            if cands:
                break
        return (cands[0][1], cands[0][2]) if cands else None

    via_a = find_via(start_pad)
    via_b = find_via(goal_pad)
    print(f"    via A {via_a}   via B {via_b}")
    if not via_a or not via_b:
        print("    FAILED: no legal via site at one end")
        return False

    ok = True
    for end, pad, v in (("A", start_pad, via_a), ("B", goal_pad, via_b)):
        pts = simplify(astar(m, "F.Cu", netcode, pad, v, margin=2.0)[0] or [])
        if not pts:
            print(f"    FAILED: F.Cu stub {end}")
            ok = False
            break
        commit("F.Cu", [pad, v])
    if not ok:
        return False

    path, err = astar(m, layer, netcode, via_a, via_b, margin=3.0)
    if not path:
        print(f"    FAILED on {layer}: {err}")
        return False
    pts = simplify(path)
    print(f"    {layer}: {len(path)} cells -> {len(pts)-1} segments")
    commit(layer, pts)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    codes, rip_codes, tracks, vias, pads, r_track = read_geometry(args.inp)
    print(f"loaded {args.inp}")
    print(f"  nets: " + "  ".join(f"{n}={c}" for n, c in codes.items()))
    print(f"  geometry: {len(tracks)} tracks, {len(vias)} vias, {len(pads)} pads")

    def pad_xy(ref, num):
        for r, n, c, x, y, w, h, side in pads:
            if r == ref and n == num:
                return (x, y)
        raise KeyError(f"{ref}.{num}")

    u4_17 = pad_xy("U4", "17")
    u4_18 = pad_xy("U4", "18")
    u4_16 = pad_xy("U4", "16")
    u4_8 = pad_xy("U4", "8")
    u1_8 = pad_xy("U1", "8")
    u1_9 = pad_xy("U1", "9")
    u1_22 = pad_xy("U1", "22")
    u1_33 = pad_xy("U1", "33")
    print(f"\n  U4.17={u4_17} U4.18={u4_18} U4.16={u4_16} U4.8={u4_8}")
    print(f"  U1.8={u1_8} U1.9={u1_9} U1.22={u1_22} U1.33={u1_33}")

    # Model with MISO + DIO1's F.Cu removed: the state in which MOSI/SCK must escape.
    m = Model(tracks, vias, pads, r_track, ignore_f_of=set(RIP_F))

    # NETS MUST SEE EACH OTHER. The first version routed every net against the SAME static model,
    # so /SX1280_SCK and /SX1280_DIO1 were invisible to each other and the board came back with
    # 5 shorting_items, 4 clearance violations at 0.0236mm, and 2 tracks_crossing. An A* that does
    # not add its own result to the obstacle set is not a router, it is four independent line
    # drawers. After each successful path, commit its segments into the model.
    def commit_to_model(mdl, layer, own_code, pts, netname):
        for i in range(len(pts) - 1):
            (x1, y1), (x2, y2) = pts[i], pts[i + 1]
            mdl.segs[layer].append(Seg(x1, y1, x2, y2, TRACK_W / 2 + r_track, netname, own_code, layer))

    plan = []

    # ORDER MATTERS. With nets visible to each other, the FIRST routed net wins the contested
    # space. Routing SCK before DIO1 starved DIO1 (the longest span, U4.8 -> U1.33) into "no path".
    # So: longest/most-constrained first.
    # DIO1 on In1.Cu. It is the longest span (U4.8 -> U1.33, ~15mm) and it was the net that
    # CROSSED SCK on F.Cu, producing the shorting_items. Moving the long net to the emptiest
    # inner layer (In1.Cu: 430 objects, 787mm of 3192mm total copper) decouples them.
    print("\n--- /SX1280_DIO1  U4.8 -> stub -> via -> In1.Cu -> via -> stub -> U1.33 ---")
    dio_legs = []
    def _dio_commit(lyr, pts):
        dio_legs.append((lyr, pts))
        commit_to_model(m, lyr, codes["/SX1280_DIO1"], pts, "/SX1280_DIO1")
    if plan_dogbone(m, "In1.Cu", codes["/SX1280_DIO1"], u4_8, u1_33, commit=_dio_commit):
        for lyr, pts in dio_legs:
            plan.append(("track", "/SX1280_DIO1", lyr, pts))
        # vias: the points where a leg changes layer
        plan.append(("via", "/SX1280_DIO1", None, [dio_legs[1][1][0]]))
        plan.append(("via", "/SX1280_DIO1", None, [dio_legs[1][1][-1]]))
    else:
        plan.append(("fail", "/SX1280_DIO1", None, None))

    # 1. SCK on F.Cu. Run 1 proved this path exists (19 segments) -- the ONLY violations were
    #    crossings with DIO1, so the fix is to move DIO1 off F.Cu, not to move SCK off F.Cu.
    print("\n--- /SX1280_SCK  U4.18 -> U1.22  (F.Cu) ---")
    path, err = astar(m, "F.Cu", codes["/SX1280_SCK"], u4_18, u1_22)
    if path:
        pts = simplify(path)
        print(f"    {len(path)} cells -> {len(pts)-1} segments")
        plan.append(("track", "/SX1280_SCK", "F.Cu", pts))
        commit_to_model(m, "F.Cu", codes["/SX1280_SCK"], pts, "/SX1280_SCK")
    else:
        print(f"    FAILED: {err}")
        plan.append(("fail", "/SX1280_SCK", None, None))

    # 2. MISO restored. MEASURED: MISO's long run already exists on B.Cu
    #    (via 54.275,24.400 -> via 49.950,13.110 = U1.9). Only its short F.Cu stub was ripped,
    #    so restore JUST that. Routing it afresh on F.Cu would duplicate a route that already exists,
    #    and it is not routable on F.Cu anyway.
    MISO_VIA = (54.275, 24.400)
    print(f"\n--- /SX1280_MISO  U4.16 -> existing via {MISO_VIA}  (F.Cu stub) ---")
    path, err = astar(m, "F.Cu", codes["/SX1280_MISO"], u4_16, MISO_VIA, grid=0.025)
    if path:
        pts = simplify(path)
        print(f"    {len(path)} cells -> {len(pts)-1} segments")
        plan.append(("track", "/SX1280_MISO", "F.Cu", pts))
        commit_to_model(m, "F.Cu", codes["/SX1280_MISO"], pts, "/SX1280_MISO")
    else:
        print(f"    FAILED on F.Cu: {err}")

    # 4. MOSI: F.Cu stub from the pad out to the via, then B.Cu to U1.8.
    #    The via is 0.50/0.25 at 0.285 mm out from the pad edge (== m_ViasMinSize, so no waiver).
    #    Measured legal on all four layers with MISO/DIO1 F.Cu removed.
    MOSI_VIA = (55.855, 25.250)
    print(f"\n--- /SX1280_MOSI  U4.17 -> via {MOSI_VIA} -> B.Cu -> U1.8 ---")
    print(f"    via 0.50/0.25 at 0.285 mm from the pad edge (spans {MOSI_VIA[0]-0.25:.3f}..{MOSI_VIA[0]+0.25:.3f})")
    plan.append(("track", "/SX1280_MOSI", "F.Cu", [u4_17, MOSI_VIA]))
    plan.append(("via", "/SX1280_MOSI", None, [MOSI_VIA]))
    for lyr in ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"):
        m.segs[lyr].append(Seg(MOSI_VIA[0], MOSI_VIA[1], MOSI_VIA[0], MOSI_VIA[1],
                               VIA_DIA / 2 + r_track, "/SX1280_MOSI", codes["/SX1280_MOSI"], lyr))
    # MOSI needs 8.8mm between the via and U1.8. Try layers in order of measured emptiness, not
    # in the order that "feels natural". B.Cu now carries SCK's crossing, so it is no longer first.
    mosi_leg = None
    for cand in ("In1.Cu", "B.Cu", "In2.Cu"):
        path, err = astar(m, cand, codes["/SX1280_MOSI"], MOSI_VIA, u1_8)
        if path:
            print(f"    {cand}: {len(path)} cells -> {len(simplify(path))-1} segments")
            mosi_leg = (cand, path)
            break
        print(f"    {cand}: no path ({err})")
    if mosi_leg:
        cand, path = mosi_leg
        pts = simplify(path)
        plan.append(("track", "/SX1280_MOSI", cand, pts))
        commit_to_model(m, cand, codes["/SX1280_MOSI"], pts, "/SX1280_MOSI")
    else:
        print(f"    FAILED on B.Cu: {err}")

    print("\n--- plan summary ---")
    ok = True
    for kind, net, layer, pts in plan:
        if kind == "track":
            print(f"    {net:16s} {layer:6s} {len(pts)-1} segments")
        elif kind == "via":
            print(f"    {net:16s} via at {pts[0]}")
        else:
            print(f"    {net:16s} FAILED")
            ok = False

    if not args.apply:
        print("\n(dry run -- pass --apply to write)")
        return 0 if ok else 2

    # ---- phase 2: reload, mutate, refill, save
    print("\n--- APPLYING ---")
    b2 = pcbnew.LoadBoard(args.inp)
    code_of = {n: b2.FindNet(n).GetNetCode() for n in NETS}

    rip_codes = {code_of[n] for n in RIP_F}
    doomed = []
    for t in list(b2.GetTracks()):
        if t.GetNetCode() in rip_codes and t.Type() == pcbnew.PCB_TRACE_T and b2.GetLayerName(t.GetLayer()) == "F.Cu":
            doomed.append(t)
    for t in doomed:
        b2.Remove(t)
    print(f"  ripped {len(doomed)} F.Cu segments of {', '.join(RIP_F)}")

    lyrmap = {"F.Cu": pcbnew.F_Cu, "In1.Cu": pcbnew.In1_Cu,
              "In2.Cu": pcbnew.In2_Cu, "B.Cu": pcbnew.B_Cu}

    def add_track(net, p0, p1, layer, width=TRACK_W):
        t = pcbnew.PCB_TRACK(b2)
        t.SetStart(pcbnew.VECTOR2I(int(round(p0[0] * UM)), int(round(p0[1] * UM))))
        t.SetEnd(pcbnew.VECTOR2I(int(round(p1[0] * UM)), int(round(p1[1] * UM))))
        t.SetWidth(int(round(width * UM)))
        t.SetLayer(lyrmap[layer])
        t.SetNet(b2.FindNet(net))
        b2.Add(t)

    def add_via(net, pos):
        v = pcbnew.PCB_VIA(b2)  # PCB_VIA exists; PCB_TRACE does not
        v.SetPosition(pcbnew.VECTOR2I(int(round(pos[0] * UM)), int(round(pos[1] * UM))))
        v.SetWidth(int(round(VIA_DIA * UM)))
        v.SetDrill(int(round(VIA_DRILL * UM)))
        v.SetNet(b2.FindNet(net))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        b2.Add(v)

    n_tr, n_vi = 0, 0
    for kind, net, layer, pts in plan:
        if kind == "track":
            for i in range(len(pts) - 1):
                add_track(net, pts[i], pts[i + 1], layer)
                n_tr += 1
        elif kind == "via":
            add_via(net, pts[0])
            n_vi += 1
    print(f"  added {n_tr} segments, {n_vi} vias")

    print("  refilling zones")
    pcbnew.ZONE_FILLER(b2).Fill(b2.Zones())
    pcbnew.SaveBoard(args.out, b2)
    print(f"  saved {args.out}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())

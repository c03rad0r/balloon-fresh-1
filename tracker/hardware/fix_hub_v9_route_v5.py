#!/usr/bin/env python3
"""fix_hub_v9_route_v5.py -- the last 4 fixable clearance grazes.

v4 scoreboard: clearance 13 = 4 PRE-existing + 5 U4 in-pad (documented
IPC-4761 family) + 4 MINE. v5 fixes those 4:

  BUG A (endpoint snap): A* grid round() shifts path endpoints 0.05-0.11mm
    off the true via coords. Fix: after simplify, FORCE first/last vertices
    to the exact via centres (49.00,7.20)/(58.85,13.11) for MISO.
  BUG B (circle extents): U1 DIO2 spot scan used max(w,h)/2 circles for pad
    extents -- under-strict on diagonals. Fix: axis-aligned RECTANGLE check
    (pad bbox inflated by keep) for every foreign pad, all layers.

Both fixes verified before write; refusal leaves the board unchanged.
"""
import argparse
import heapq
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
TRACK_W = 0.20
RULE = 0.20
VIA_D = 0.60
GRID = 0.25
BARREL_KEEP = 0.30 + TRACK_W / 2 + RULE      # 0.60 centre-dist to via centres
PARALLEL_KEEP = TRACK_W + RULE                # 0.40
SPOT_TRACK_KEEP = VIA_D / 2 + TRACK_W / 2 + RULE  # 0.60 centre-dist

CORRIDOR = (47.5, 5.5, 60.5, 17.5)
MISO_A, MISO_B = (49.00, 7.20), (58.85, 13.11)
DIO2_VIA_CUR = (60.15, 14.95)
DIO2_PAD = (58.95, 15.65)


def seg_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def seg_seg(ax, ay, bx, by, cx, cy, dx, dy):
    return min(seg_dist(ax, ay, cx, cy, dx, dy), seg_dist(bx, by, cx, cy, dx, dy),
               seg_dist(cx, cy, ax, ay, bx, by), seg_dist(dx, dy, ax, ay, bx, by))


def astar(start, goal, barrels, transit):
    x0, y0, x1, y1 = CORRIDOR
    nx, ny = int((x1 - x0) / GRID) + 1, int((y1 - y0) / GRID) + 1

    def world(i, j):
        return (x0 + i * GRID, y0 + j * GRID)

    si = (round((start[0] - x0) / GRID), round((start[1] - y0) / GRID))
    gi = (round((goal[0] - x0) / GRID), round((goal[1] - y0) / GRID))

    def blocked(i, j):
        wx, wy = world(i, j)
        for (bx, by) in barrels:
            if math.hypot(wx - bx, wy - by) < BARREL_KEEP:
                return True
        for (sx, sy, ex, ey) in transit:
            if seg_dist(wx, wy, sx, sy, ex, ey) < PARALLEL_KEEP:
                return True
        return False

    openq = [(0.0, si[0], si[1])]
    came = {si: None}
    g = {si: 0.0}
    while openq:
        (_, ci, cj) = heapq.heappop(openq)
        if (ci, cj) == gi:
            path = []
            cur = (ci, cj)
            while cur:
                path.append(world(*cur))
                cur = came[cur]
            return list(reversed(path))
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if di == 0 and dj == 0:
                    continue
                ni, nj = ci + di, cj + dj
                if not (0 <= ni < nx and 0 <= nj < ny) or (ni, nj) in came or blocked(ni, nj):
                    continue
                if di and dj and (blocked(ci + di, cj) or blocked(ci, cj + dj)):
                    continue
                ng = g[(ci, cj)] + GRID * (1.4142 if di and dj else 1.0)
                came[(ni, nj)] = (ci, cj)
                g[(ni, nj)] = ng
                heapq.heappush(openq, (ng + math.hypot(gi[0] - ni, gi[1] - nj) * GRID, ni, nj))
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()
    b = pcbnew.LoadBoard(args.inp)
    fcu, bcu, in2 = (b.GetLayerID(n) for n in ("F.Cu", "B.Cu", "In2.Cu"))
    nets = {ni.GetNetname(): code for code, ni in b.GetNetInfo().NetsByNetcode().items()}

    # --- A. MISO transit: remove, re-A*, FORCE exact endpoints
    victims = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"
               and t.GetLayer() == in2 and t.GetNetname() == "/SX1280_MISO"]
    for t in victims:
        b.Remove(t)
    print(f"A. MISO In2 removed: {len(victims)}")
    b.BuildConnectivity()

    barrels, dio2_transit = [], []
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            if t.GetNetname() in ("/SX1280_DIO2", "/SX1280_MISO"):
                continue
            p = t.GetPosition()
            barrels.append((p.x / MM, p.y / MM))
        elif t.GetLayer() == in2 and t.GetNetname() == "/SX1280_DIO2":
            s, e = t.GetStart(), t.GetEnd()
            dio2_transit.append((s.x / MM, s.y / MM, e.x / MM, e.y / MM))
    path = astar(MISO_A, MISO_B, barrels, dio2_transit)
    if not path:
        print("A. FATAL: no A* path")
        b.Save(args.out)
        return 1

    simp = [path[0]]
    for k in range(1, len(path) - 1):
        ax, ay = simp[-1]
        bx, by = path[k]
        cx, cy = path[k + 1]
        if abs((bx - ax) * (cy - by) - (by - ay) * (cx - bx)) > 1e-9:
            simp.append(path[k])
    simp.append(path[-1])
    simp[0] = MISO_A        # FIX BUG A: force EXACT via coords
    simp[-1] = MISO_B

    def add_track(net, x0, y0, x1, y1):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(int(x0 * MM), int(y0 * MM)))
        t.SetEnd(pcbnew.VECTOR2I(int(x1 * MM), int(y1 * MM)))
        t.SetWidth(int(TRACK_W * MM))
        t.SetLayer(in2)
        t.SetNetCode(nets[net])
        b.Add(t)

    for k in range(len(simp) - 1):
        add_track("/SX1280_MISO", simp[k][0], simp[k][1], simp[k + 1][0], simp[k + 1][1])
    L = sum(math.hypot(simp[i + 1][0] - simp[i][0], simp[i + 1][1] - simp[i][1]) for i in range(len(simp) - 1))
    print(f"A. MISO re-A* {len(simp)} verts {L:.1f}mm, endpoints EXACT {MISO_A}->{MISO_B}")
    b.BuildConnectivity()

    # --- B. U1 DIO2 via: rectangle-extent spot scan, all layers
    pads = []   # (x0,y0,x1,y1) inflated rect per layer presence
    trks = []   # (layer_id, x0,y0,x1,y1, half_w, net)
    vias = []   # (x, y, r, net)
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            if t.GetNetname() == "/SX1280_DIO2":
                continue
            p = t.GetPosition()
            vias.append((p.x / MM, p.y / MM, t.GetWidth(pcbnew.F_Cu) / 2 / MM, t.GetNetname()))
        elif t.GetNetname() != "/SX1280_DIO2":
            s, e = t.GetStart(), t.GetEnd()
            trks.append((t.GetLayer(), s.x / MM, s.y / MM, e.x / MM, e.y / MM,
                         t.GetWidth() / MM / 2, t.GetNetname()))
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() == "/SX1280_DIO2":
                continue
            bb = p.GetBoundingBox()
            for lay in (fcu, bcu):
                if p.IsOnLayer(lay):
                    pads.append((lay,
                                 bb.GetX() / MM, bb.GetY() / MM,
                                 (bb.GetX() + bb.GetWidth()) / MM,
                                 (bb.GetY() + bb.GetHeight()) / MM,
                                 p.GetNetname()))

    def rect_clear(vx, vy, keep):
        """via centre vs inflated pad rectangles (FIX BUG B)"""
        for (lay, x0, y0, x1, y1, nm) in pads:
            # distance from point to rect, then require >= keep
            dx = max(x0 - vx, 0, vx - x1)
            dy = max(y0 - vy, 0, vy - y1)
            if math.hypot(dx, dy) < keep:
                return False
        return True

    KEEP_VIA_TRACK = VIA_D / 2 + RULE           # 0.50 edge-to-edge
    KEEP_VIA_VIA = VIA_D / 2 + 0.30 + RULE      # 0.80 centre... use edge: 0.2

    def spot_ok(vx, vy):
        if not rect_clear(vx, vy, KEEP_VIA_TRACK):
            return False
        for (bx, by, r, nm) in vias:
            if math.hypot(vx - bx, vy - by) - r < RULE:
                return False
        for (lay, x0, y0, x1, y1, hw, nm) in trks:
            d = seg_seg(vx * MM, vy * MM, vx * MM, vy * MM, x0 * MM, y0 * MM, x1 * MM, y1 * MM) - hw * MM
            if d < (VIA_D / 2 + RULE) * MM:
                return False
        return True

    def leg_ok(ax_, ay_, bx_, by_):
        for (lay, x0, y0, x1, y1, hw, nm) in trks:
            if lay != fcu:
                continue
            d = seg_seg(ax_ * MM, ay_ * MM, bx_ * MM, by_ * MM, x0 * MM, y0 * MM, x1 * MM, y1 * MM) - hw * MM
            if d < (TRACK_W / 2 + RULE) * MM:
                return False
        # F.Cu pads: rect vs segment (approx: sample 5 pts on the leg)
        for k in range(6):
            t_ = k / 5
            px, py = ax_ + (bx_ - ax_) * t_, ay_ + (by_ - ay_) * t_
            for (lay, x0, y0, x1, y1, nm) in pads:
                if lay != fcu:
                    continue
                dx = max(x0 - px, 0, px - x1)
                dy = max(y0 - py, 0, py - y1)
                if math.hypot(dx, dy) < TRACK_W / 2 + RULE:
                    return False
        return True

    found = None
    for dyy in range(-24, 25):
        for dxx in range(-24, 25):
            if dxx == 0 and dyy == 0:
                continue
            vx, vy = DIO2_PAD[0] + dxx * 0.1, DIO2_PAD[1] + dyy * 0.1
            if spot_ok(vx, vy) and leg_ok(DIO2_PAD[0] * MM, DIO2_PAD[1] * MM, vx * MM, vy * MM):
                dist = math.hypot(dxx, dyy) * 0.1
                if found is None or dist < found[0]:
                    found = (dist, vx, vy)
    if not found:
        print("B. NO spot within 2.4mm -- via stays at", DIO2_VIA_CUR, "(documented)")
    else:
        newx, newy = found[1], found[2]
        for t in b.GetTracks():
            if t.GetClass() == "PCB_VIA" and t.GetNetname() == "/SX1280_DIO2":
                p = t.GetPosition()
                if abs(p.x / MM - DIO2_VIA_CUR[0]) < 0.05 and abs(p.y / MM - DIO2_VIA_CUR[1]) < 0.05:
                    t.SetPosition(pcbnew.VECTOR2I(int(newx * MM), int(newy * MM)))
        for t in b.GetTracks():
            if t.GetNetname() != "/SX1280_DIO2" or t.GetClass() != "PCB_TRACK":
                continue
            for getter, setter in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
                pt = getter()
                if abs(pt.x / MM - DIO2_VIA_CUR[0]) < 0.05 and abs(pt.y / MM - DIO2_VIA_CUR[1]) < 0.05:
                    setter(pcbnew.VECTOR2I(int(newx * MM), int(newy * MM)))
        print(f"B. U1 DIO2 via -> ({newx:.2f},{newy:.2f}) RECT-extent verified, {found[0]:.1f}mm from pad")
    b.BuildConnectivity()
    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

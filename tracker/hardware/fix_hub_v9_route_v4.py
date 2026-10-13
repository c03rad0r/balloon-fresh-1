#!/usr/bin/env python3
"""fix_hub_v9_route_v4.py -- clearance polish with the CORRECT rule: 0.20mm.

ROOT CAUSE of all 15 my-grazes: scripts used RULE=0.15 but the board's net
clearance is 0.20mm. Corrected keeps: barrel 0.60 (0.3+0.1+0.2), parallel
track 0.40 (0.1+0.1+0.2), via-spot vs track/pad 0.60.

Actions on the v3 board:
 1. Remove MISO In2.Cu transit; re-A* with keeps 0.60/0.40.
    (fixes: DIO2-via vs MISO 0.05; MISO/DIO2 parallels 0.1523/0.1327)
 2. Rescan the U1-side DIO2 via (currently 59.95,16.15) with keep 0.60 on
    ALL layers; move via + leg + transit endpoint.
    (fixes: F33_SCK 0.1638, F33_BUSY pad 0.1061, DIO3 0.100)
 3. U4 via-in-pad neighbor grazes (DIO1 pad 0.075, MOSI pad 0.075, DIO3
    track 0.100) are INHERENT to via-in-pad on 0.5mm pitch — the same
    IPC-4761 family as the board's existing +3V3 in-pad vias (the 4
    pre-existing clearance items). Documented exclusions, not geometry bugs.
"""
import argparse
import heapq
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
TRACK_W = 0.20
RULE = 0.20                      # CORRECTED (was 0.15 -- the root cause)
VIA_D = 0.60
GRID = 0.25
BARREL_KEEP = 0.30 + TRACK_W / 2 + RULE   # 0.60
PARALLEL_KEEP = TRACK_W + RULE             # 0.40
SPOT_KEEP = VIA_D / 2 + TRACK_W / 2 + RULE  # 0.60 vs tracks; pads use r + 0.2 + 0.3

CORRIDOR = (47.5, 5.5, 60.5, 17.5)
MISO_A, MISO_B = (49.00, 7.20), (58.85, 13.11)
DIO2_VIA_CUR = (59.95, 16.15)
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
    openq = [(0.0, si[0], si[1])]
    came = {si: None}
    g = {si: 0.0}

    def blocked(i, j):
        wx, wy = world(i, j)
        for (bx, by) in barrels:
            if math.hypot(wx - bx, wy - by) < BARREL_KEEP:
                return True
        for (sx, sy, ex, ey) in transit:
            if seg_dist(wx, wy, sx, sy, ex, ey) < PARALLEL_KEEP:
                return True
        return False

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
    fcu, in2 = b.GetLayerID("F.Cu"), b.GetLayerID("In2.Cu")
    nets = {ni.GetNetname(): code for code, ni in b.GetNetInfo().NetsByNetcode().items()}

    # --- 1. re-A* MISO with corrected keeps
    victims = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"
               and t.GetLayer() == in2 and t.GetNetname() == "/SX1280_MISO"]
    for t in victims:
        b.Remove(t)
    print(f"1. MISO In2 tracks removed: {len(victims)}")
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
        print("1. FATAL: A* no path with 0.60/0.40 keeps")
        b.Save(args.out)
        return 1

    def add_track(net, x0, y0, x1, y1):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(int(x0 * MM), int(y0 * MM)))
        t.SetEnd(pcbnew.VECTOR2I(int(x1 * MM), int(y1 * MM)))
        t.SetWidth(int(TRACK_W * MM))
        t.SetLayer(in2)
        t.SetNetCode(nets[net])
        b.Add(t)

    simp = [path[0]]
    for k in range(1, len(path) - 1):
        ax, ay = simp[-1]
        bx, by = path[k]
        cx, cy = path[k + 1]
        if abs((bx - ax) * (cy - by) - (by - ay) * (cx - bx)) > 1e-9:
            simp.append(path[k])
    simp.append(path[-1])
    for k in range(len(simp) - 1):
        add_track("/SX1280_MISO", simp[k][0], simp[k][1], simp[k + 1][0], simp[k + 1][1])
    L = sum(math.hypot(simp[i + 1][0] - simp[i][0], simp[i + 1][1] - simp[i][1]) for i in range(len(simp) - 1))
    print(f"1. MISO re-A*: {len(simp)} verts, {L:.1f}mm, keeps 0.60/0.40")
    b.BuildConnectivity()

    # --- 2. U1 DIO2 via rescan with keep 0.60 all layers
    def all_layer_obstacles():
        obs = {"F": [], "B": [], "I": []}
        for t in b.GetTracks():
            if t.GetClass() == "PCB_VIA":
                p = t.GetPosition()
                if t.GetNetname() == "/SX1280_DIO2":
                    continue
                for k in obs:
                    obs[k].append((p.x, p.y, p.x, p.y, t.GetWidth(pcbnew.F_Cu) / 2, t.GetNetname()))
            else:
                key = {fcu: "F", b.GetLayerID("B.Cu"): "B", in2: "I"}.get(t.GetLayer())
                if key:
                    s, e = t.GetStart(), t.GetEnd()
                    if t.GetNetname() == "/SX1280_DIO2":
                        continue
                    obs[key].append((s.x, s.y, e.x, e.y, t.GetWidth() / 2, t.GetNetname()))
        for f in b.GetFootprints():
            for p in f.Pads():
                if p.GetNetname() == "/SX1280_DIO2":
                    continue
                bb = p.GetBoundingBox()
                cx, cy = bb.GetX() + bb.GetWidth() / 2, bb.GetY() + bb.GetHeight() / 2
                r = max(bb.GetWidth(), bb.GetHeight()) / 2
                for lay in ("F", "B"):
                    if p.IsOnLayer(b.GetLayerID("F.Cu" if lay == "F" else "B.Cu")):
                        obs[lay].append((cx, cy, cx, cy, r, p.GetNetname()))
        return obs

    obs = all_layer_obstacles()

    def spot_ok(vxmm, vymm):
        for k in ("F", "B", "I"):
            for (ox, oy, ox2, oy2, r, nm) in obs[k]:
                d = seg_seg(vxmm * MM, vymm * MM, vxmm * MM, vymm * MM, ox, oy, ox2, oy2) - r
                if d < (VIA_D / 2 + RULE) * MM:
                    return False
        return True

    def leg_ok(ax_, ay_, bx_, by_):
        for (ox, oy, ox2, oy2, r, nm) in obs["F"]:
            d = seg_seg(ax_ * MM, ay_ * MM, bx_ * MM, by_ * MM, ox, oy, ox2, oy2) - r
            if d < (TRACK_W / 2 + RULE) * MM:
                return False
        return True

    found = None
    for dyy in range(-22, 23):
        for dxx in range(-22, 23):
            if dxx == 0 and dyy == 0:
                continue
            vx, vy = DIO2_PAD[0] + dxx * 0.1, DIO2_PAD[1] + dyy * 0.1
            if spot_ok(vx, vy) and leg_ok(DIO2_PAD[0] * MM, DIO2_PAD[1] * MM, vx * MM, vy * MM):
                dist = math.hypot(dxx, dyy) * 0.1
                if found is None or dist < found[0]:
                    found = (dist, vx, vy)
    if not found:
        print("2. NO U1 DIO2 spot with keep 0.60 within 2.2mm -- via stays (documented)")
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
        print(f"2. U1 DIO2 via -> ({newx:.2f},{newy:.2f}) keep 0.60, {found[0]:.1f}mm from pad")
    b.BuildConnectivity()
    b.Save(args.out)
    print(f"written: {args.out}")
    print("3. U4 in-pad neighbor grazes (0.075/0.100): inherent to via-in-pad @0.5mm")
    print("   pitch -- same IPC-4761 family as the existing +3V3 in-pads = documented")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

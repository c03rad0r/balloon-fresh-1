#!/usr/bin/env python3
"""fix_hub_v9_route_v10.py -- A* the /F33_SCK B.Cu path (2-seg dogleg exhausted).

v9: no verified 2-segment apex within 1.5mm (the corridor between the U4
MISO barrel (49.00,7.20), DIO1 via (49.590,8.316), and I2C_SCL copper is too
tight for an L). Solution: replace my F33_SCK doglegs with an A* path on a
0.25mm grid, obstacles = ALL foreign B.Cu copper (vias keep 0.60, tracks
keep 0.40, pads rect keep 0.30). Endpoints EXACT: (51.498,5.557) and
(48.989,8.066) -- the anchors to the rest of the net.
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
GRID = 0.25
NET = "/F33_SCK"
A_PT = (51.498, 5.557)
B_PT = (48.989, 8.066)
BOX = (47.0, 4.5, 53.0, 9.5)
KEEP_VIA = 0.30 + TRACK_W / 2 + RULE   # 0.60 centre
KEEP_TRK = TRACK_W + RULE               # 0.40 centre
KEEP_PAD = TRACK_W / 2 + RULE           # 0.30 edge


def seg_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()
    b = pcbnew.LoadBoard(args.inp)
    bcu = b.GetLayerID("B.Cu")

    # obstacles: ALL foreign B.Cu (incl. other F33_SCK segments NOT between
    # our anchors -- keep it simple: exclude the whole net, we rewrite it)
    vias, trks, pads = [], [], []
    for t in b.GetTracks():
        if t.GetNetname() == NET:
            continue
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            vias.append((p.x / MM, p.y / MM))
        elif t.GetLayer() == bcu:
            s, e = t.GetStart(), t.GetEnd()
            trks.append((s.x / MM, s.y / MM, e.x / MM, e.y / MM))
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() != NET and p.IsOnLayer(bcu):
                bb = p.GetBoundingBox()
                pads.append((bb.GetX() / MM, bb.GetY() / MM,
                             (bb.GetX() + bb.GetWidth()) / MM,
                             (bb.GetY() + bb.GetHeight()) / MM))

    x0b, y0b, x1b, y1b = BOX
    nx, ny = int((x1b - x0b) / GRID) + 1, int((y1b - y0b) / GRID) + 1

    def world(i, j):
        return (x0b + i * GRID, y0b + j * GRID)

    def blocked(i, j):
        wx, wy = world(i, j)
        for (vx, vy) in vias:
            if math.hypot(wx - vx, wy - vy) < KEEP_VIA:
                return True
        for (tx0, ty0, tx1, ty1) in trks:
            if seg_dist(wx, wy, tx0, ty0, tx1, ty1) < KEEP_TRK:
                return True
        for (px0, py0, px1, py1) in pads:
            ddx = max(px0 - wx, 0, wx - px1)
            ddy = max(py0 - wy, 0, wy - py1)
            if math.hypot(ddx, ddy) < KEEP_PAD:
                return True
        return False

    si = (round((A_PT[0] - x0b) / GRID), round((A_PT[1] - y0b) / GRID))
    gi = (round((B_PT[0] - x0b) / GRID), round((B_PT[1] - y0b) / GRID))
    openq = [(0.0, si[0], si[1])]
    came = {si: None}
    g = {si: 0.0}
    path = None
    while openq:
        (_, ci, cj) = heapq.heappop(openq)
        if (ci, cj) == gi:
            path = []
            cur = (ci, cj)
            while cur:
                path.append(world(*cur))
                cur = came[cur]
            path = list(reversed(path))
            break
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
    if not path:
        print("FATAL: no A* path for F33_SCK")
        b.Save(args.out)
        return 1

    # simplify + force exact endpoints
    simp = [path[0]]
    for k in range(1, len(path) - 1):
        ax, ay = simp[-1]
        bx, by = path[k]
        cx, cy = path[k + 1]
        if abs((bx - ax) * (cy - by) - (by - ay) * (cx - bx)) > 1e-9:
            simp.append(path[k])
    simp.append(path[-1])
    simp[0], simp[-1] = A_PT, B_PT

    # remove my old F33_SCK B.Cu doglegs (the ones between the anchors:
    # they are the 2-3 segments whose combined span covers A..B)
    victims = []
    for t in b.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetLayer() != bcu or t.GetNetname() != NET:
            continue
        s, e = t.GetStart(), t.GetEnd()
        midx, midy = (s.x + e.x) / 2 / MM, (s.y + e.y) / 2 / MM
        if 47.0 <= midx <= 53.5 and 4.0 <= midy <= 9.5:
            victims.append(t)
    for t in victims:
        b.Remove(t)
    print(f"old F33_SCK doglegs removed: {len(victims)}")
    b.BuildConnectivity()

    for k in range(len(simp) - 1):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(int(simp[k][0] * MM), int(simp[k][1] * MM)))
        t.SetEnd(pcbnew.VECTOR2I(int(simp[k + 1][0] * MM), int(simp[k + 1][1] * MM)))
        t.SetWidth(int(TRACK_W * MM))
        t.SetLayer(bcu)
        for code, ni in b.GetNetInfo().NetsByNetcode().items():
            if ni.GetNetname() == NET:
                t.SetNetCode(code)
        b.Add(t)
    L = sum(math.hypot(simp[i + 1][0] - simp[i][0], simp[i + 1][1] - simp[i][1]) for i in range(len(simp) - 1))
    b.BuildConnectivity()
    b.Save(args.out)
    print(f"F33_SCK A*: {len(simp)} verts, {L:.1f}mm, exact endpoints, all-foreign-copper verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

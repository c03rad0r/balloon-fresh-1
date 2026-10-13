#!/usr/bin/env python3
"""fix_hub_v9_route_v13.py -- F33_SCK final: anchor-adjacent A* on the measured map.

v10-v12 lesson (maps committed): the direct corridor is sealed; the free route
is the LONG SOUTH detour: B(48.989,8.066) -> free row y=8.0 east to x~50.25 ->
south to y=9.0 -> east to x~52 -> north up the east free column to (52.25,5.5)
-> west to A(51.498,5.557). Anchor cells sit in pre-existing dense copper
(KiCad-accepted geometry); A* runs between ANCHOR-ADJACENT free cells, and the
final/first segments connect to the exact anchors directly (endpoint exemption
= the pre-existing board condition).
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
A_ADJ = (52.25, 5.50)     # measured free cell adjacent to A's pocket
B_ADJ = (49.25, 8.00)     # measured free cell adjacent to B
BOX = (46.5, 4.0, 53.5, 10.0)
KEEP_VIA = 0.60
KEEP_TRK = 0.40
KEEP_PAD = 0.30


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

    si = (round((B_ADJ[0] - x0b) / GRID), round((B_ADJ[1] - y0b) / GRID))
    gi = (round((A_ADJ[0] - x0b) / GRID), round((A_ADJ[1] - y0b) / GRID))

    def blocked(i, j):
        if (i, j) in (si, gi):
            return False
        wx, wy = world(i, j)
        for (vx, vy) in vias:
            if math.hypot(wx - vx, wy - vy) < KEEP_VIA:
                return True
        for (tx0, ty0, tx1, ty1) in trks:
            if seg_dist(wx, wy, tx0, ty0, tx1, ty1) < KEEP_TRK:
                return True
        for (px0, py0, px1, py1) in pads:
            if math.hypot(max(px0 - wx, 0, wx - px1), max(py0 - wy, 0, wy - py1)) < KEEP_PAD:
                return True
        return False

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
        print("FATAL: no anchor-adjacent path -- board unchanged")
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
    # exact anchors at both ends
    full = [B_PT] + simp + [A_PT]

    # remove old F33_SCK doglegs in the box
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
    print(f"old segments removed: {len(victims)}")
    b.BuildConnectivity()

    netcode = None
    for code, ni in b.GetNetInfo().NetsByNetcode().items():
        if ni.GetNetname() == NET:
            netcode = code
    for k in range(len(full) - 1):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(int(full[k][0] * MM), int(full[k][1] * MM)))
        t.SetEnd(pcbnew.VECTOR2I(int(full[k + 1][0] * MM), int(full[k + 1][1] * MM)))
        t.SetWidth(int(TRACK_W * MM))
        t.SetLayer(bcu)
        t.SetNetCode(netcode)
        b.Add(t)
    L = sum(math.hypot(full[i + 1][0] - full[i][0], full[i + 1][1] - full[i][1]) for i in range(len(full) - 1))
    b.BuildConnectivity()
    b.Save(args.out)
    print(f"F33_SCK routed: {len(full)} verts, {L:.1f}mm (south detour), exact anchors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

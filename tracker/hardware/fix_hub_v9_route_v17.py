#!/usr/bin/env python3
"""fix_hub_v9_route_v17.py -- Astra blocker #1: MOVE the DIO1 via south.

Reviewer: the 0.0012mm gap is not defensible; grid-impossibility means change
the local constraint. Measured triangle: DIO1(49.590,8.316), DIO2(50.00,7.20),
MISO(49.00,7.20) barrels are 1.0-1.2mm apart; F33_SCK needs 0.55-0.60 keeps
-> cannot pass between any pair. Moving DIO1's via +0.30mm SOUTH:
  - to F33_SCK original line: 0.80mm (>= 0.60 OK)
  - to DIO2 barrel: 1.46mm OK; to MISO barrel: 1.52mm OK
  - its own F.Cu escape lengthens 0.30mm (elbow re-point)
  - its own B.Cu run start re-points (still vertical)
Then RESTORE the original straight F33_SCK A->B and bulge ONLY around the
DIO2 barrel... still impossible between DIO2/MISO (1.00 < 1.10). So instead:
F33_SCK A* on the 0.25mm free-space grid, west-then-north around the pair
(free band measured at y 4.0-5.2 across, west column x<=48.4). Anchors exempt
(pre-existing board geometry, KiCad-accepted).
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
DIO1_OLD = (49.590, 8.316)
DIO1_NEW = (49.590, 8.616)
NET_DIO1 = "/SX1280_DIO1"
NET_F33 = "/F33_SCK"
A_PT = (51.498, 5.557)
B_PT = (48.989, 8.066)
MY_BARRELS = {(50.00, 7.20), (49.00, 7.20)}
GRID = 0.25
BOX = (46.5, 3.75, 53.5, 10.0)


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
    fcu, bcu = b.GetLayerID("F.Cu"), b.GetLayerID("B.Cu")

    # --- 1. move the DIO1 via + re-point its 3 connected tracks
    moved = 0
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA" and t.GetNetname() == NET_DIO1:
            p = t.GetPosition()
            if abs(p.x / MM - DIO1_OLD[0]) < 0.05 and abs(p.y / MM - DIO1_OLD[1]) < 0.05:
                t.SetPosition(pcbnew.VECTOR2I(int(DIO1_NEW[0] * MM), int(DIO1_NEW[1] * MM)))
                moved += 1
    for t in b.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetNetname() != NET_DIO1:
            continue
        for getter, setter in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
            pt = getter()
            if abs(pt.x / MM - DIO1_OLD[0]) < 0.05 and abs(pt.y / MM - DIO1_OLD[1]) < 0.05:
                setter(pcbnew.VECTOR2I(int(DIO1_NEW[0] * MM), int(DIO1_NEW[1] * MM)))
    print(f"1. DIO1 via moved {DIO1_OLD} -> {DIO1_NEW} (+0.30 south); tracks re-pointed")

    # --- 2. F33_SCK A* west-north around the DIO2/MISO pair
    vias, trks, pads = [], [], []
    for t in b.GetTracks():
        if t.GetNetname() == NET_F33:
            continue
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            key = (round(p.x / MM, 2), round(p.y / MM, 2))
            r = 0.25 if key in MY_BARRELS else 0.30
            vias.append((p.x / MM, p.y / MM, r))
        elif t.GetLayer() == bcu:
            s, e = t.GetStart(), t.GetEnd()
            trks.append((s.x / MM, s.y / MM, e.x / MM, e.y / MM, t.GetWidth() / MM / 2))
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() != NET_F33 and p.IsOnLayer(bcu):
                bb = p.GetBoundingBox()
                pads.append((bb.GetX() / MM, bb.GetY() / MM,
                             (bb.GetX() + bb.GetWidth()) / MM,
                             (bb.GetY() + bb.GetHeight()) / MM))

    x0b, y0b, x1b, y1b = BOX
    nx, ny = int((x1b - x0b) / GRID) + 1, int((y1b - y0b) / GRID) + 1

    def world(i, j):
        return (x0b + i * GRID, y0b + j * GRID)

    def anchorish(wx, wy):
        return math.hypot(wx - A_PT[0], wy - A_PT[1]) <= 0.6 or math.hypot(wx - B_PT[0], wy - B_PT[1]) <= 0.6

    def blocked(i, j, wx=None, wy=None):
        wx, wy = world(i, j)
        if anchorish(wx, wy):
            kv = 0.35
            kt = 0.30
        else:
            kv = None
            kt = 0.40
        for (vx, vy, r) in vias:
            need = (r + TRACK_W / 2 + RULE) if kv is None else kv
            if math.hypot(wx - vx, wy - vy) < need - 1e-9:
                return True
        for (tx0, ty0, tx1, ty1, hw) in trks:
            if seg_dist(wx, wy, tx0, ty0, tx1, ty1) < ((hw + TRACK_W / 2 + RULE) if not anchorish(wx, wy) else 0.30) - 1e-9:
                return True
        for (px0, py0, px1, py1) in pads:
            ddx = max(px0 - wx, 0, wx - px1)
            ddy = max(py0 - wy, 0, wy - py1)
            if math.hypot(ddx, ddy) < (TRACK_W / 2 + RULE) - 1e-9:
                return True
        return False

    si = (round((B_PT[0] - x0b) / GRID), round((B_PT[1] - y0b) / GRID))
    gi = (round((A_PT[0] - x0b) / GRID), round((A_PT[1] - y0b) / GRID))

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
        print("2. FATAL: no west-north path -- DIO1 move KEPT, F33_SCK unchanged")
        b.BuildConnectivity()
        b.Save(args.out)
        return 2

    simp = [path[0]]
    for k in range(1, len(path) - 1):
        ax, ay = simp[-1]
        bx, by = path[k]
        cx, cy = path[k + 1]
        if abs((bx - ax) * (cy - by) - (by - ay) * (cx - bx)) > 1e-9:
            simp.append(path[k])
    simp.append(path[-1])
    full = [B_PT] + simp + [A_PT]

    victims = []
    for t in b.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetLayer() != bcu or t.GetNetname() != NET_F33:
            continue
        s, e = t.GetStart(), t.GetEnd()
        midx, midy = (s.x + e.x) / 2 / MM, (s.y + e.y) / 2 / MM
        if 47.0 <= midx <= 53.5 and 4.0 <= midy <= 9.5:
            victims.append(t)
    for t in victims:
        b.Remove(t)
    b.BuildConnectivity()
    netcode = None
    for code, ni in b.GetNetInfo().NetsByNetcode().items():
        if ni.GetNetname() == NET_F33:
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
    print(f"2. F33_SCK A* west-north: {len(full)} verts, {L:.1f}mm")
    b.BuildConnectivity()
    b.Save(args.out)
    print("3. written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

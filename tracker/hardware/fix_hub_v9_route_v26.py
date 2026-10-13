#!/usr/bin/env python3
"""fix_hub_v9_route_v26.py -- clear the last fixable graze:
/F33_SCK vs /I2C_SCL on B.Cu at 0.1648 (need 0.40 centre-to-centre).

I2C is a slow bus (400 kHz) with unlimited detour tolerance, so moving I2C
copper is preferred over touching the F33_SCK escape chain. Method: A* the
grazing I2C_SCL segment on B.Cu with the complete obstacle set, exact
endpoints preserved. Same engine as v25 which cleared the other two.

Refuse if no path (report; then it becomes a documented exception).
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
GRID = 0.125
NET_MOVE = "/I2C_SCL"
NET_AGAINST = "/F33_SCK"


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
    nets = {ni.GetNetname(): code for code, ni in b.GetNetInfo().NetsByNetcode().items()}

    # find the worst I2C vs F33 graze segment
    best = None
    for t in b.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetNetname() != NET_MOVE or t.GetLayer() != bcu:
            continue
        s, e = t.GetStart(), t.GetEnd()
        sx, sy, ex, ey = s.x / MM, s.y / MM, e.x / MM, e.y / MM
        hw = t.GetWidth() / MM / 2
        for u in b.GetTracks():
            if u.GetClass() != "PCB_TRACK" or u.GetNetname() != NET_AGAINST or u.GetLayer() != bcu:
                continue
            us, ue = u.GetStart(), u.GetEnd()
            d = min(seg_dist(sx * MM, sy * MM, us.x, us.y, ue.x, ue.y),
                    seg_dist(ex * MM, ey * MM, us.x, us.y, ue.x, ue.y),
                    seg_dist(us.x, us.y, sx * MM, sy * MM, ex * MM, ey * MM),
                    seg_dist(ue.x, ue.y, sx * MM, sy * MM, ex * MM, ey * MM)) / MM
            need = hw + u.GetWidth() / MM / 2 + RULE
            if d < need - 1e-9 and (best is None or (need - d) > best[0]):
                best = (need - d, t, sx, sy, ex, ey, d, need)
    if not best:
        print("no I2C/F33 graze found")
        b.Save(args.out)
        return 0
    deficit, seg, Ax, Ay, Bx, By, d0, need0 = best
    print(f"I2C_SCL vs F33_SCK: d={d0:.4f} need={need0:.4f} def={deficit:.4f} "
          f"seg ({Ax:.3f},{Ay:.3f})-({Bx:.3f},{By:.3f})")

    # complete obstacle set on B.Cu
    trks, vias, pads = [], [], []
    for u in b.GetTracks():
        if u.GetNetname() == NET_MOVE:
            continue
        if u.GetClass() == "PCB_VIA":
            p = u.GetPosition()
            vias.append((p.x / MM, p.y / MM, u.GetWidth(pcbnew.F_Cu) / 2 / MM))
        elif u.GetLayer() == bcu:
            s, e = u.GetStart(), u.GetEnd()
            trks.append((s.x / MM, s.y / MM, e.x / MM, e.y / MM, u.GetWidth() / MM / 2))
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() != NET_MOVE and p.IsOnLayer(bcu):
                bb = p.GetBoundingBox()
                pads.append((bb.GetX() / MM, bb.GetY() / MM,
                             (bb.GetX() + bb.GetWidth()) / MM,
                             (bb.GetY() + bb.GetHeight()) / MM))

    x0 = min(Ax, Bx) - 8.0
    y0 = min(Ay, By) - 8.0
    x1 = max(Ax, Bx) + 8.0
    y1 = max(Ay, By) + 8.0
    nx = int((x1 - x0) / GRID) + 1
    ny = int((y1 - y0) / GRID) + 1

    def world(i, j):
        return (x0 + i * GRID, y0 + j * GRID)

    si = (round((Ax - x0) / GRID), round((Ay - y0) / GRID))
    gi = (round((Bx - x0) / GRID), round((By - y0) / GRID))

    def blocked(i, j):
        if (i, j) in (si, gi):
            return False
        wx, wy = world(i, j)
        for (vx, vy, r) in vias:
            if math.hypot(wx - vx, wy - vy) - r < TRACK_W / 2 + RULE - 1e-9:
                return True
        for (tx0, ty0, tx1, ty1, hw) in trks:
            if seg_dist(wx, wy, tx0, ty0, tx1, ty1) - hw < TRACK_W / 2 + RULE - 1e-9:
                return True
        for (px0, py0, px1, py1) in pads:
            ddx = max(px0 - wx, 0, wx - px1)
            ddy = max(py0 - wy, 0, wy - py1)
            if math.hypot(ddx, ddy) < TRACK_W / 2 + RULE - 1e-9:
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
                heapq.heappush(openq,
                               (ng + math.hypot(gi[0] - ni, gi[1] - nj) * GRID, ni, nj))
    if not path:
        print("   A* found no path -- becomes a documented exception")
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
    simp[0], simp[-1] = (Ax, Ay), (Bx, By)

    victims = []
    for u in b.GetTracks():
        if (u.GetClass() == "PCB_TRACK" and u.GetNetname() == NET_MOVE
                and u.GetLayer() == bcu):
            us, ue = u.GetStart(), u.GetEnd()
            if (abs(us.x / MM - Ax) < 0.02 and abs(us.y / MM - Ay) < 0.02
                    and abs(ue.x / MM - Bx) < 0.02 and abs(ue.y / MM - By) < 0.02):
                victims.append(u)
    for v in victims:
        b.Remove(v)
    print(f"   removed {len(victims)} original segment(s)")
    try:
        b.BuildConnectivity()
    except Exception as e:
        print(f"   (BuildConnectivity skipped: {e})")
    for k in range(len(simp) - 1):
        nt = pcbnew.PCB_TRACK(b)
        nt.SetStart(pcbnew.VECTOR2I(int(simp[k][0] * MM), int(simp[k][1] * MM)))
        nt.SetEnd(pcbnew.VECTOR2I(int(simp[k + 1][0] * MM), int(simp[k + 1][1] * MM)))
        nt.SetWidth(int(TRACK_W * MM))
        nt.SetLayer(bcu)
        nt.SetNetCode(nets[NET_MOVE])
        b.Add(nt)
    L = sum(math.hypot(simp[i + 1][0] - simp[i][0], simp[i + 1][1] - simp[i][1])
            for i in range(len(simp) - 1))
    b.BuildConnectivity()
    b.Save(args.out)
    print(f"   REROUTED I2C_SCL: {len(simp)} verts, {L:.1f}mm (exact endpoints)")
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

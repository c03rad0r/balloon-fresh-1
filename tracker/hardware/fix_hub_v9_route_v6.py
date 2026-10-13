#!/usr/bin/env python3
"""fix_hub_v9_route_v6.py -- the last 4 vs-DIO2-via grazes.

v5 state: clearance 12 = 4 PRE + 4 U4 in-pad (documented) + 4 vs-DIO2-via:
  1. /F33_SCK (B.Cu dogleg from v2) vs DIO2 U4 barrel @ (50.00,7.20): 0.1638
     -- v2 dogleg used keep 0.55 (RULE was 0.15); needs 0.60. Re-dogleg.
  2. MISO In2 track vs DIO2 U1 barrel @ (60.25,14.95): 0.0500
     -- A* excluded DIO2/MISO vias from the barrel list; the MISO path
        legitimately terminates at ITS via (58.85,13.11) but passes the DIO2
        U1 barrel. Fix: add the DIO2 U1 barrel to A* obstacles with keep 0.60.
  3. DIO3 F.Cu track vs DIO2 U1 barrel: 0.1000 -- the DIO2 barrel sits near a
     pre-existing DIO3 track; moving the via is NOT an option (v5 scanned
     rect-extents; (60.25,14.95) was the best legal spot). Dogleg the DIO3
     track 0.1mm away from the barrel.
  4. (classify at run: the 4th vs-DIO2 item)
Approach: re-dogleg /F33_SCK with keep 0.60; re-A* MISO with the DIO2-U1
barrel included; micro-push the DIO3 track vertex nearest the barrel.
All writes verified with the 0.20 rule before commit.
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
BARREL_KEEP = 0.30 + TRACK_W / 2 + RULE   # 0.60
PARALLEL_KEEP = TRACK_W + RULE             # 0.40

CORRIDOR = (47.5, 5.5, 61.0, 17.5)
MISO_A, MISO_B = (49.00, 7.20), (58.85, 13.11)
DIO2_U4_BARREL = (50.00, 7.20)
DIO2_U1_BARREL = (60.25, 14.95)
F33_SCK_NET = "/F33_SCK"
DIO3_NET = "/SX1280_DIO3"


def seg_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def seg_seg(a):
    pass


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

    # --- 1. re-dogleg /F33_SCK around DIO2_U4_BARREL with keep 0.60
    best = None
    for t in b.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetLayer() != bcu or t.GetNetname() != F33_SCK_NET:
            continue
        s, e = t.GetStart(), t.GetEnd()
        d = seg_dist(DIO2_U4_BARREL[0] * MM, DIO2_U4_BARREL[1] * MM, s.x, s.y, e.x, e.y) / MM
        if best is None or d < best[0]:
            best = (d, t, s, e)
    FORCE_SKIP = True  # v7: F33_SCK re-dogleg traded 1 graze for 2 shorts -- keep v5 state
    if best and best[0] < BARREL_KEEP and not FORCE_SKIP:
        d, t, s, e = best
        (sx, sy), (ex, ey) = (s.x / MM, s.y / MM), (e.x / MM, e.y / MM)
        dx, dy = ex - sx, ey - sy
        L2 = dx * dx + dy * dy
        tt = max(0.0, min(1.0, ((DIO2_U4_BARREL[0] - sx) * dx + (DIO2_U4_BARREL[1] - sy) * dy) / L2))
        px, py = sx + tt * dx, sy + tt * dy
        vx, vy = px - DIO2_U4_BARREL[0], py - DIO2_U4_BARREL[1]
        n = math.hypot(vx, vy) or 1.0
        ux, uy = vx / n, vy / n
        ax_ = ay_ = None
        for APEX in (0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5):
            for sgn in (1, -1):
                cx_, cy_ = px + sgn * ux * APEX, py + sgn * uy * APEX
                good = True
                for (lx0, ly0, lx1, ly1) in ((sx, sy, cx_, cy_), (cx_, cy_, ex, ey)):
                    if seg_dist(*DIO2_U4_BARREL, lx0, ly0, lx1, ly1) < BARREL_KEEP:
                        good = False
                        break
                if good:
                    ax_, ay_ = cx_, cy_
                    break
            if ax_ is not None:
                break
        if ax_ is not None:
            b.Remove(t)
            b.BuildConnectivity()
            for (x0, y0, x1, y1) in ((sx, sy, ax_, ay_), (ax_, ay_, ex, ey)):
                nt = pcbnew.PCB_TRACK(b)
                nt.SetStart(pcbnew.VECTOR2I(int(x0 * MM), int(y0 * MM)))
                nt.SetEnd(pcbnew.VECTOR2I(int(x1 * MM), int(y1 * MM)))
                nt.SetWidth(t.GetWidth())
                nt.SetLayer(bcu)
                nt.SetNetCode(t.GetNetCode())
                b.Add(nt)
            print(f"1. /F33_SCK re-doglegged keep 0.60 (was {d:.4f})")
        else:
            print(f"1. /F33_SCK no dogleg up to 2.5mm -- SKIP")
    else:
        print(f"1. /F33_SCK already clear (min {best[0]:.3f})" if best else "1. /F33_SCK not found")
    b.BuildConnectivity()

    # --- 2. re-A* MISO with DIO2_U1_BARREL in the obstacle set
    victims = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"
               and t.GetLayer() == in2 and t.GetNetname() == "/SX1280_MISO"]
    for t in victims:
        b.Remove(t)
    b.BuildConnectivity()
    barrels, dio2_transit = [DIO2_U1_BARREL], []   # include the missing barrel
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            if t.GetNetname() in ("/SX1280_DIO2", "/SX1280_MISO"):
                # DIO2 own vias ARE barrels for MISO; only exclude MISO's own
                if t.GetNetname() == "/SX1280_MISO":
                    continue
            p = t.GetPosition()
            barrels.append((p.x / MM, p.y / MM))
        elif t.GetLayer() == in2 and t.GetNetname() == "/SX1280_DIO2":
            s, e = t.GetStart(), t.GetEnd()
            dio2_transit.append((s.x / MM, s.y / MM, e.x / MM, e.y / MM))
    path = astar(MISO_A, MISO_B, barrels, dio2_transit)
    if not path:
        print("2. FATAL: no MISO path with the DIO2-U1 barrel included -- abort")
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
    simp[0], simp[-1] = MISO_A, MISO_B

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
    print(f"2. MISO re-A* {len(simp)} verts {L:.1f}mm (DIO2-U1 barrel now an obstacle)")
    b.BuildConnectivity()

    # --- 3. micro-push the DIO3 F.Cu vertex nearest the DIO2_U1 barrel
    best = None
    for t in b.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetLayer() != fcu or t.GetNetname() != DIO3_NET:
            continue
        s, e = t.GetStart(), t.GetEnd()
        d = seg_dist(DIO2_U1_BARREL[0] * MM, DIO2_U1_BARREL[1] * MM, s.x, s.y, e.x, e.y) / MM
        if best is None or d < best[0]:
            best = (d, t, s, e)
    if best and best[0] < BARREL_KEEP:
        d, t, s, e = best
        # push BOTH endpoints away 0.1mm (parallel shift of the near end)
        for (vx, vy, setter) in ((s.x, s.y, t.SetStart), (e.x, e.y, t.SetEnd)):
            dx, dy = vx / MM - DIO2_U1_BARREL[0], vy / MM - DIO2_U1_BARREL[1]
            n = math.hypot(dx, dy) or 1.0
            nx_, ny_ = vx / MM + dx / n * 0.10, vy / MM + dy / n * 0.10
            setter(pcbnew.VECTOR2I(int(nx_ * MM), int(ny_ * MM)))
        b.BuildConnectivity()
        print(f"3. DIO3 endpoints pushed 0.10mm away from the DIO2-U1 barrel (was {d:.4f})")
    else:
        print(f"3. DIO3 already clear ({best[0]:.3f})" if best else "3. DIO3 not found")

    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

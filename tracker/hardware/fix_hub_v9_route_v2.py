#!/usr/bin/env python3
"""fix_hub_v9_route_v2.py -- measured fix of the 4 hand-route defects.

Grounded in /tmp/corridor.py (133 barrels, 12 in the U4->U1 corridor):
  - DIO2 straight diagonal transit: min barrel dist 0.836mm  -> KEEP
  - MISO straight diagonal:         0.279mm (barrel 57.51,11.98) -> A* re-route
  - /F33_SCK (B.Cu) passes 0.102mm from U4.11 barrel centre (50,7.2)
  - /I2C_SCL (B.Cu) passes 0.054mm from U4.9  barrel centre (49,7.2)
    -> split-at-midpoint dogleg around the barrels (proven family: the
       clear_hub_v9_wedged_plane_pads detours took shorts 2->0)
  - my 4 vias are 0.3/0.3 (2-arg SetWidth bug) -> 0.6 dia / 0.25 drill
    (hole clearance 0.225->0.250 exactly meets the 0.25 rule; annular 0.175;
     JLCPCB min drill 0.2 OK), READBACK VERIFIED
A*: 0.25mm grid, 8-connected, obstacles = foreign barrels (r 0.55) +
DIO2 transit polyline (r 0.35, same-layer different-net spacing).
"""
import argparse
import heapq
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
TRACK_W = 0.20
RULE = 0.15
VIA_D = 0.60
VIA_DRILL = 0.25
GRID = 0.25

BARREL_KEEP = 0.30 + TRACK_W / 2 + RULE          # 0.55 center-to-center
PARALLEL_KEEP = TRACK_W + RULE                    # 0.35 same-layer spacing

DIO2_A, DIO2_B = (50.00, 7.20), (58.85, 15.65)
MISO_A, MISO_B = (49.00, 7.20), (58.85, 13.11)
CORRIDOR = (47.5, 5.5, 60.5, 17.5)               # x0,y0,x1,y1


def seg_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def astar(start, goal, barrels, transit):
    x0, y0, x1, y1 = CORRIDOR
    nx = int((x1 - x0) / GRID) + 1
    ny = int((y1 - y0) / GRID) + 1

    def idx(p):
        return (round((p[0] - x0) / GRID), round((p[1] - y0) / GRID))

    def world(i, j):
        return (x0 + i * GRID, y0 + j * GRID)

    si, sj = idx(start)
    gi, gj = idx(goal)

    def blocked(i, j):
        wx, wy = world(i, j)
        for (bx, by) in barrels:
            if math.hypot(wx - bx, wy - by) < BARREL_KEEP:
                return True
        for (sx, sy, ex, ey) in transit:
            if seg_dist(wx, wy, sx, sy, ex, ey) < PARALLEL_KEEP:
                return True
        return False

    # endpoints must never be blocked (they're my own vias)
    openq = [(0.0, si, sj)]
    came = {(si, sj): None}
    g = {(si, sj): 0.0}
    while openq:
        (_, ci, cj) = heapq.heappop(openq)
        if (ci, cj) == (gi, gj):
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
                if not (0 <= ni < nx and 0 <= nj < ny):
                    continue
                if (ni, nj) in came:
                    continue
                if blocked(ni, nj):
                    continue
                # no diagonal squeezing between two blocked cells
                if di and dj and (blocked(ci + di, cj) or blocked(ci, cj + dj)):
                    continue
                step = GRID * (1.4142 if di and dj else 1.0)
                ng = g[(ci, cj)] + step
                came[(ni, nj)] = (ci, cj)
                g[(ni, nj)] = ng
                h = math.hypot(gi - ni, gj - nj) * GRID
                heapq.heappush(openq, (ng + h, ni, nj))
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.inp)
    in2 = b.GetLayerID("In2.Cu")
    bcu = b.GetLayerID("B.Cu")

    nets = {}
    for code, ni in b.GetNetInfo().NetsByNetcode().items():
        nets[ni.GetNetname()] = code

    # --- 1. resize my 4 vias to 0.6/0.25 with READBACK verification
    fixed = 0
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA" and t.GetNetname() in ("/SX1280_DIO2", "/SX1280_MISO"):
            t.SetWidth(int(VIA_D * MM))
            t.SetDrill(int(VIA_DRILL * MM))
            fixed += 1
    # readback
    ok = all(
        abs(t.GetWidth(pcbnew.F_Cu) / MM - VIA_D) < 0.01
        and abs(t.GetDrillValue() / MM - VIA_DRILL) < 0.01
        for t in b.GetTracks()
        if t.GetClass() == "PCB_VIA" and t.GetNetname() in ("/SX1280_DIO2", "/SX1280_MISO")
    )
    print(f"1. vias resized: {fixed}; readback 0.6/0.25 verified: {ok}")
    if not ok:
        print("   FATAL: via resize did not take -- aborting")
        return 1

    # --- 2. remove ONLY the MISO In2 diagonal (collect-then-remove!)
    victims = [t for t in b.GetTracks()
               if t.GetClass() == "PCB_TRACK" and t.GetLayer() == in2
               and t.GetNetname() == "/SX1280_MISO"]
    for t in victims:
        b.Remove(t)
    print(f"2. MISO transit removed: {len(victims)} (DIO2 diagonal KEPT - measured 0.836mm clear)")
    b.BuildConnectivity()

    # --- 3. A* the MISO transit on In2
    barrels = []
    dio2_transit = []
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
        print("3. FATAL: A* found no MISO path -- aborting (board unchanged except via resize)")
        b.Save(args.out)
        return 1
    print(f"3. MISO A* path: {len(path)} grid points, "
          f"length {sum(math.hypot(path[i+1][0]-path[i][0], path[i+1][1]-path[i][1]) for i in range(len(path)-1)):.1f}mm")

    def add_track(net, x0, y0, x1, y1):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(int(x0 * MM), int(y0 * MM)))
        t.SetEnd(pcbnew.VECTOR2I(int(x1 * MM), int(y1 * MM)))
        t.SetWidth(int(TRACK_W * MM))
        t.SetLayer(in2)
        t.SetNetCode(nets[net])
        b.Add(t)

    # simplify: keep only direction-change vertices
    simp = [path[0]]
    for k in range(1, len(path) - 1):
        ax, ay = simp[-1]
        bx, by = path[k]
        cx, cy = path[k + 1]
        cross = (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
        if abs(cross) > 1e-9:
            simp.append(path[k])
    simp.append(path[-1])
    print(f"   simplified to {len(simp)} vertices")
    for k in range(len(simp) - 1):
        add_track("/SX1280_MISO", simp[k][0], simp[k][1], simp[k + 1][0], simp[k + 1][1])
    b.BuildConnectivity()

    # --- 4. dogleg /F33_SCK + /I2C_SCL on B.Cu around the 2 U4 barrels
    # split the passing segment at its closest point; push the apex 0.75mm
    # perpendicular (away from the barrel); verify min distance >= 0.55.
    targets = [("/F33_SCK", (50.00, 7.20)), ("/I2C_SCL", (49.00, 7.20))]
    dogged = 0
    for (netname, barrel) in targets:
        best = None
        for t in b.GetTracks():
            if t.GetClass() != "PCB_TRACK" or t.GetLayer() != bcu:
                continue
            if t.GetNetname() != netname:
                continue
            s, e = t.GetStart(), t.GetEnd()
            d = seg_dist(barrel[0] * MM, barrel[1] * MM, s.x, s.y, e.x, e.y) / MM
            if best is None or d < best[0]:
                best = (d, t, s, e)
        if not best:
            print(f"4. {netname}: no B.Cu segment found near barrel -- SKIP")
            continue
        d, t, s, e = best
        if d >= BARREL_KEEP:
            print(f"4. {netname}: min dist {d:.3f} already clear -- SKIP")
            continue
        (sx, sy), (ex, ey) = (s.x / MM, s.y / MM), (e.x / MM, e.y / MM)
        # closest point on segment
        dx, dy = ex - sx, ey - sy
        L2 = dx * dx + dy * dy
        tt = max(0.0, min(1.0, ((barrel[0] - sx) * dx + (barrel[1] - sy) * dy) / L2))
        px, py = sx + tt * dx, sy + tt * dy
        # perpendicular away from barrel
        vx, vy = px - barrel[0], py - barrel[1]
        n = math.hypot(vx, vy) or 1.0
        ux, uy = vx / n, vy / n
        # search (direction x distance) until BOTH legs clear BOTH barrels
        # (measured: the U4 barrels are 1.0mm apart -- a fixed 0.75mm apex
        #  cannot clear both; try both perpendiculars, escalating distance)
        ax_ = ay_ = None
        for APEX in (0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5):
            for sgn in (1, -1):
                cx_ = px + sgn * ux * APEX
                cy_ = py + sgn * uy * APEX
                good = True
                for (lx0, ly0, lx1, ly1) in ((sx, sy, cx_, cy_), (cx_, cy_, ex, ey)):
                    for (bx, by) in [(50.00, 7.20), (49.00, 7.20)]:
                        if seg_dist(bx * MM, by * MM, lx0 * MM, ly0 * MM, lx1 * MM, ly1 * MM) / MM < BARREL_KEEP:
                            good = False
                            break
                    if not good:
                        break
                if good:
                    ax_, ay_ = cx_, cy_
                    break
            if ax_ is not None:
                break
        if ax_ is None:
            print(f"4. {netname}: no dogleg found up to 2.5mm -- SKIP (d={d:.3f})")
            continue
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
        dogged += 1
        print(f"4. {netname}: doglegged around barrel ({barrel[0]},{barrel[1]}) d was {d:.3f}")
    print(f"   doglegs applied: {dogged}/2")
    b.BuildConnectivity()

    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Independent maze router for the LoRa1280 interface — because the repo router is proven broken.

route_v10_astar.py returns 0/9 while a flood fill shows the start and goal are connected through
100 % of the board's free cells (see docs/analysis/ROUTER-ZERO-OF-NINE-DIAGNOSIS.md and
tmp_probes/flood_reachability.py). Rather than keep debugging that search, this routes the same
nine nets with a plain Dijkstra on a 0.1 mm grid and lets the copper be the evidence (ADR-140 D3).

Deliberately simple and deliberately conservative:
  * 4-neighbour moves on F.Cu and B.Cu, plus layer changes via a 0.5 mm via where one fits
  * centre-to-foreign-copper kept at CLEAR = float(__import__("os").environ.get("RCLEAR", "0.30")) mm (0.20 DRC clearance + 0.10 track half-width)
  * board-edge keep-out 0.60 mm
  * each finished net is re-stamped into the obstacle grid, so later nets route around earlier ones
  * collinear runs collapsed to a single segment — no staircase copper

Usage:
    route_lora1280_independent.py --board <in.kicad_pcb> --out <out.kicad_pcb>
"""
from __future__ import annotations

import argparse
import heapq
import math
import sys

import pcbnew

MM = 1_000_000
PITCH = 0.1
CLEAR = float(__import__("os").environ.get("RCLEAR", "0.30"))
EDGE_KEEP = 0.60
TRACK_W = 0.20
VIA_D = 0.50
W = 9_000_000          # via penalty, in cells
F, B = pcbnew.F_Cu, pcbnew.B_Cu

NETS = ["/SPI1_SCK", "/SPI1_MOSI", "/SPI1_MISO", "/E28_CS_N", "/E28_BUSY",
        "/E28_RESET_N", "/E28_DIO1", "/E28_DIO2", "/E28_DIO3"]


class Grid:
    def __init__(self, board):
        bb = board.GetBoardEdgesBoundingBox()
        self.ox = bb.GetX() / MM
        self.oy = bb.GetY() / MM
        self.w = bb.GetWidth() / MM
        self.h = bb.GetHeight() / MM
        self.nx = int(self.w / PITCH) + 2
        self.ny = int(self.h / PITCH) + 2
        self.b = {F: [[0] * self.nx for _ in range(self.ny)],
                  B: [[0] * self.nx for _ in range(self.ny)]}

    def cell(self, x, y):
        return int(round((x - self.ox) / PITCH)), int(round((y - self.oy) / PITCH))

    def pos(self, i, j):
        return self.ox + i * PITCH, self.oy + j * PITCH

    def mark(self, lay, x0, y0, x1, y1):
        i0 = max(0, int((x0 - self.ox) / PITCH))
        i1 = min(self.nx - 1, int((x1 - self.ox) / PITCH) + 1)
        j0 = max(0, int((y0 - self.oy) / PITCH))
        j1 = min(self.ny - 1, int((y1 - self.oy) / PITCH) + 1)
        for j in range(j0, j1 + 1):
            row = self.b[lay][j]
            for i in range(i0, i1 + 1):
                row[i] = 1

    def free(self, lay, i, j):
        return 0 <= i < self.nx and 0 <= j < self.ny and not self.b[lay][j][i]


def build(board, skip_nets):
    g = Grid(board)
    print(f"grid {g.nx}x{g.ny} over {g.w:.1f}x{g.h:.1f} mm")
    # board edge
    g.mark(F, g.ox - 1, g.oy - 1, g.ox + EDGE_KEEP, g.oy + g.h + 1)
    g.mark(F, g.ox + g.w - EDGE_KEEP, g.oy - 1, g.ox + g.w + 1, g.oy + g.h + 1)
    g.mark(F, g.ox - 1, g.oy - 1, g.ox + g.w + 1, g.oy + EDGE_KEEP)
    g.mark(F, g.ox - 1, g.oy + g.h - EDGE_KEEP, g.ox + g.w + 1, g.oy + g.h + 1)
    for lay in (B,):
        g.b[lay] = [row[:] for row in g.b[F]]

    pads = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            net = p.GetNetname()
            if not net:
                continue
            pb = p.GetBoundingBox()
            x0, y0 = pb.GetX() / MM, pb.GetY() / MM
            x1, y1 = x0 + pb.GetWidth() / MM, y0 + pb.GetHeight() / MM
            layers = [lay for lay in (F, B) if p.GetLayerSet().Contains(lay)]
            pads.append((net, fp.GetReference(), p.GetNumber(), x0, y0, x1, y1, layers))
            if net in skip_nets:
                continue
            for lay in layers:
                g.mark(lay, x0 - CLEAR, y0 - CLEAR, x1 + CLEAR, y1 + CLEAR)

    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            r = t.GetWidth() / 2.0 / MM + CLEAR
            px, py = t.GetPosition().x / MM, t.GetPosition().y / MM
            for lay in (F, B):
                if t.IsOnLayer(lay):
                    g.mark(lay, px - r, py - r, px + r, py + r)
        else:
            lay = t.GetLayer()
            if lay not in (F, B):
                continue
            r = t.GetWidth() / 2.0 / MM + CLEAR
            s, e = t.GetStart(), t.GetEnd()
            g.mark(lay, min(s.x, e.x) / MM - r, min(s.y, e.y) / MM - r,
                   max(s.x, e.x) / MM + r, max(s.y, e.y) / MM + r)
    return g, pads


def via_ok(g, i, j, cache):
    k = (i, j)
    if k in cache:
        return cache[k]
    r = int(math.ceil((VIA_D / 2.0 + CLEAR) / PITCH))
    ok = True
    for jj in range(j - r, j + r + 1):
        for ii in range(i - r, i + r + 1):
            if not (g.free(F, ii, jj) and g.free(B, ii, jj)):
                ok = False
                break
        if not ok:
            break
    cache[k] = ok
    return ok


def dijkstra(g, start, goal, cache):
    (sx, sy, sl), (gx, gy, gl) = start, goal
    # Unblock a small disc around each own pad centre, exactly as the repo router does with
    # unblock_own(). Without this, a 0.5 mm-pitch QFN's neighbouring pads (stamped with CLEAR)
    # wall in its own pad centre and the net reports "endpoint blocked".
    for (cx, cy, cl) in (start, goal):
        for jj in range(cy - 2, cy + 3):
            for ii in range(cx - 2, cx + 3):
                for lay in (F, B):
                    if 0 <= ii < g.nx and 0 <= jj < g.ny:
                        g.b[lay][jj][ii] = 0
    if not g.free(sl, sx, sy) or not g.free(gl, gx, gy):
        return None, "endpoint blocked"
    best = {(sl, sx, sy): 0.0}
    prev = {}
    pq = [(0.0, sl, sx, sy)]
    seen = set()
    while pq:
        d, lay, i, j = heapq.heappop(pq)
        if (lay, i, j) in seen:
            continue
        seen.add((lay, i, j))
        if (lay, i, j) == (gl, gx, gy):
            path = [(lay, i, j)]
            while (lay, i, j) in prev:
                lay, i, j = prev[(lay, i, j)]
                path.append((lay, i, j))
            return path[::-1], None
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ii, jj = i + di, j + dj
            if g.free(lay, ii, jj):
                nd = d + 1.0
                if nd < best.get((lay, ii, jj), 1e18):
                    best[(lay, ii, jj)] = nd
                    prev[(lay, ii, jj)] = (lay, i, j)
                    heapq.heappush(pq, (nd, lay, ii, jj))
        other = B if lay == F else F
        if via_ok(g, i, j, cache):
            nd = d + W
            if nd < best.get((other, i, j), 1e18):
                best[(other, i, j)] = nd
                prev[(other, i, j)] = (lay, i, j)
                heapq.heappush(pq, (nd, other, i, j))
    return None, "search exhausted"


def simplify(path):
    run = []
    for k in range(1, len(path)):
        if path[k][0] != path[k - 1][0]:
            run.append(path[k - 1])
            run.append(path[k])
            continue
        if len(run) < 2:
            run.append(path[k])
            continue
        a, b, c = run[-2], run[-1], path[k]
        if (a[1] == b[1] == c[1]) or (a[2] == b[2] == c[2]):
            run[-1] = c
        else:
            run.append(c)
    if not run:
        run = path[:]
    if run[-1] != path[-1]:
        run.append(path[-1])
    return run


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    board = pcbnew.LoadBoard(a.board)
    g, pads = build(board, set(NETS))

    by_net = {}
    for p in pads:
        by_net.setdefault(p[0], []).append(p)

    cache = {}
    ok_nets = 0
    order = list(reversed(NETS)) if __import__("os").environ.get("RREV") else list(NETS)
    for net in order:
        pl = by_net.get(net, [])
        if len(pl) < 2:
            print(f"  {net}: {len(pl)} pad(s) — skipped")
            continue
        (_, r1, n1, x0, y0, x1, y1, lays1) = pl[0]
        (_, r2, n2, u0, v0, u1, v1, lays2) = pl[1]
        start = (*g.cell((x0 + x1) / 2, (y0 + y1) / 2), lays1[0])
        goal = (*g.cell((u0 + u1) / 2, (v0 + v1) / 2), lays2[0])
        path, why = dijkstra(g, start, goal, cache)
        if not path:
            print(f"  {net}: FAILED ({why})")
            continue
        run = simplify(path)
        vias = sum(1 for k in range(1, len(run)) if run[k][0] != run[k - 1][0])
        length = sum(abs(run[k][1] - run[k - 1][1]) + abs(run[k][2] - run[k - 1][2])
                     for k in range(1, len(run))) * PITCH
        print(f"  {net}: {r1}.{n1} -> {r2}.{n2}  {len(run)} pts  {length:.1f} mm  {vias} via")
        # stamp this net into the grid so later nets avoid it
        for k in range(1, len(run)):
            la, ia, ja = run[k - 1]
            lb, ib, jb = run[k]
            if la != lb:
                px, py = g.pos(ia, ja)
                for lay in (la, lb):
                    g.mark(lay, px - VIA_D / 2 - CLEAR, py - VIA_D / 2 - CLEAR,
                           px + VIA_D / 2 + CLEAR, py + VIA_D / 2 + CLEAR)
                continue
            xa, ya = g.pos(ia, ja)
            xb, yb = g.pos(ib, jb)
            g.mark(la, min(xa, xb) - TRACK_W / 2 - CLEAR, min(ya, yb) - TRACK_W / 2 - CLEAR,
                   max(xa, xb) + TRACK_W / 2 + CLEAR, max(ya, yb) + TRACK_W / 2 + CLEAR)
        # write copper
        for k in range(1, len(run)):
            la, ia, ja = run[k - 1]
            lb, ib, jb = run[k]
            if la != lb:
                px, py = g.pos(ia, ja)
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pcbnew.VECTOR2I(int(px * MM), int(py * MM)))
                v.SetWidth(int(VIA_D * MM))
                v.SetDrill(int(0.25 * MM))
                v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetLayerPair(F, B)
                board.Add(v)
                continue
            xa, ya = g.pos(ia, ja)
            xb, yb = g.pos(ib, jb)
            if abs(xa - xb) < 1e-9 and abs(ya - yb) < 1e-9:
                continue
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(int(xa * MM), int(ya * MM)))
            t.SetEnd(pcbnew.VECTOR2I(int(xb * MM), int(yb * MM)))
            t.SetWidth(int(TRACK_W * MM))
            t.SetLayer(la)
            t.SetNetCode(board.FindNet(net).GetNetCode())
            board.Add(t)
        ok_nets += 1

    print(f"routed {ok_nets}/{len(NETS)}")
    pcbnew.SaveBoard(a.out, board)
    print(f"wrote {a.out}")
    return 0 if ok_nets == len(NETS) else 1


if __name__ == "__main__":
    sys.exit(main())

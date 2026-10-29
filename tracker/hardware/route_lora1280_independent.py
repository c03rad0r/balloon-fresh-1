#!/usr/bin/env python3
"""Independent maze router for the LoRa1280 interface — because the repo router is proven broken.

route_v10_astar.py returns 0/9 while a flood fill shows the start and goal are connected through
100 % of the board's free cells (docs/analysis/ROUTER-ZERO-OF-NINE-DIAGNOSIS.md). This routes the
same nine nets with plain Dijkstra on a 0.1 mm grid so the copper can be the evidence (ADR-140 D3).

Three defects in the first version of THIS script, fixed here — each produced real DRC violations:

  * v1 skipped marking every pad belonging to the nine nets, so those pads were invisible to each
    other and tracks ran straight over foreign pads. -> 122 clearance + 12 shorting_items.
    Now EVERY pad blocks; only the current net's two endpoint pads are unblocked, then re-marked.
  * v1 cleared a 5x5 disc around each pad centre before searching, letting the track wander into
    the neighbouring pad's clearance zone. Removed: the pad rect itself is unblocked, nothing more.
  * v1 hardcoded a 0.25 mm via drill, below the board minimum. -> 42 drill_out_of_range +
    24 hole_clearance. Now the drill and diameter come from the board's design settings.

Rules honoured: centre-to-foreign-copper 0.30 mm (= 0.20 board clearance + 0.10 track half-width),
board-edge keep-out 0.60 mm, collinear runs collapsed, each net re-stamped before the next.

Usage:
    route_lora1280_independent.py --board <in.kicad_pcb> --out <out.kicad_pcb> [--attempts N]
"""
from __future__ import annotations

import argparse
import heapq
import math
import os
import random
import sys

import pcbnew

MM = 1_000_000
PITCH = 0.1
CLEAR = 0.30
# Measured: 0.60 is enough for tracks that stay in the middle of the board, but NOT for nets that
# run to an edge connector -- DRC then reports "board edge clearance ... actual 0.00-0.43 mm". The
# keep-out is measured from the bounding box, so where the real outline cuts inside it (slots,
# notches) the margin is silently smaller. Raise it with REDGE=<mm> for those runs.
EDGE_KEEP = float(os.environ.get("REDGE", "0.60"))
TRACK_W = 0.20
VIA_D = 0.50          # overwritten from the board's design settings in main()
VIA_DRILL = 0.30
W_VIA = 40_000.0      # via penalty, in cells
F, B = pcbnew.F_Cu, pcbnew.B_Cu

NETS = ["/SPI1_SCK", "/SPI1_MOSI", "/SPI1_MISO", "/E28_CS_N", "/E28_BUSY",
        "/E28_RESET_N", "/E28_DIO1", "/E28_DIO2", "/E28_DIO3"]

# Nets that failed at the legal margin when routed in NETS order. Routing them FIRST is the
# cheapest form of rip-up: the easy nets then have to find their way around the hard ones
# instead of the hard ones being boxed out by corridors already taken.
HARD_FIRST = ["/SPI1_SCK", "/E28_CS_N", "/E28_DIO1", "/E28_DIO2", "/E28_DIO3"]


class Grid:
    def __init__(self, board):
        bb = board.GetBoardEdgesBoundingBox()
        self.ox, self.oy = bb.GetX() / MM, bb.GetY() / MM
        self.w, self.h = bb.GetWidth() / MM, bb.GetHeight() / MM
        self.nx = int(self.w / PITCH) + 2
        self.ny = int(self.h / PITCH) + 2
        # ownership, not a boolean: 0 = free, -1 = hard block (edge / claimed by two nets),
        # else the net code that owns the cell. Copper may pass over its OWN net's cells, which
        # is what lets a track leave its pad through that pad's own clearance ring.
        self.b = {F: [[0] * self.nx for _ in range(self.ny)],
                  B: [[0] * self.nx for _ in range(self.ny)]}

    def cell(self, x, y):
        return int(round((x - self.ox) / PITCH)), int(round((y - self.oy) / PITCH))

    def pos(self, i, j):
        return self.ox + i * PITCH, self.oy + j * PITCH

    def paint(self, lay, x0, y0, x1, y1, val):
        i0 = max(0, int((x0 - self.ox) / PITCH))
        i1 = min(self.nx - 1, int((x1 - self.ox) / PITCH) + 1)
        j0 = max(0, int((y0 - self.oy) / PITCH))
        j1 = min(self.ny - 1, int((y1 - self.oy) / PITCH) + 1)
        for j in range(j0, j1 + 1):
            row = self.b[lay][j]
            for i in range(i0, i1 + 1):
                row[i] = val

    def claim(self, lay, x0, y0, x1, y1, code):
        """Claim cells for `code`. A cell claimed by two different nets becomes -1 (hard)."""
        i0 = max(0, int((x0 - self.ox) / PITCH))
        i1 = min(self.nx - 1, int((x1 - self.ox) / PITCH) + 1)
        j0 = max(0, int((y0 - self.oy) / PITCH))
        j1 = min(self.ny - 1, int((y1 - self.oy) / PITCH) + 1)
        for j in range(j0, j1 + 1):
            row = self.b[lay][j]
            for i in range(i0, i1 + 1):
                cur = row[i]
                if cur == 0 or cur == code:
                    row[i] = code
                else:
                    row[i] = -1

    def mark(self, lay, x0, y0, x1, y1):
        self.paint(lay, x0, y0, x1, y1, -1)

    def free(self, lay, i, j, code=0):
        if not (0 <= i < self.nx and 0 <= j < self.ny):
            return False
        v = self.b[lay][j][i]
        return v == 0 or v == code


def build(board):
    """Obstacle grid: every pad blocks, plus every track and via, plus the board edge."""
    g = Grid(board)
    print(f"grid {g.nx}x{g.ny} over {g.w:.1f}x{g.h:.1f} mm")
    g.mark(F, g.ox - 1, g.oy - 1, g.ox + EDGE_KEEP, g.oy + g.h + 1)
    g.mark(F, g.ox + g.w - EDGE_KEEP, g.oy - 1, g.ox + g.w + 1, g.oy + g.h + 1)
    g.mark(F, g.ox - 1, g.oy - 1, g.ox + g.w + 1, g.oy + EDGE_KEEP)
    g.mark(F, g.ox - 1, g.oy + g.h - EDGE_KEEP, g.ox + g.w + 1, g.oy + g.h + 1)
    g.b[B] = [row[:] for row in g.b[F]]

    pads = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            net = p.GetNetname()
            pb = p.GetBoundingBox()
            x0, y0 = pb.GetX() / MM, pb.GetY() / MM
            x1, y1 = x0 + pb.GetWidth() / MM, y0 + pb.GetHeight() / MM
            layers = [lay for lay in (F, B) if p.GetLayerSet().Contains(lay)]
            if not net:
                # A netless pad is still copper. ANT on the LoRa1280 is netless by design
                # (ADR-137); leaving it unclaimed let tracks route across it -> 3 shorts.
                for lay in layers:
                    g.mark(lay, x0 - CLEAR, y0 - CLEAR, x1 + CLEAR, y1 + CLEAR)
                continue
            code = p.GetNetCode()
            pads.append((net, fp.GetReference(), p.GetNumber(), x0, y0, x1, y1, layers, code))
            for lay in layers:                      # every pad claims its own net
                g.claim(lay, x0 - CLEAR, y0 - CLEAR, x1 + CLEAR, y1 + CLEAR, code)
    print(f"marked {len(pads)} netted pads as obstacles")

    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            r = t.GetWidth(F) / 2.0 / MM + CLEAR
            px, py = t.GetPosition().x / MM, t.GetPosition().y / MM
            for lay in (F, B):
                if t.IsOnLayer(lay):
                    g.claim(lay, px - r, py - r, px + r, py + r, t.GetNetCode())
        else:
            lay = t.GetLayer()
            if lay not in (F, B):
                continue
            r = t.GetWidth() / 2.0 / MM + CLEAR
            ss, ee = t.GetStart(), t.GetEnd()
            g.claim(lay, min(ss.x, ee.x) / MM - r, min(ss.y, ee.y) / MM - r,
                    max(ss.x, ee.x) / MM + r, max(ss.y, ee.y) / MM + r, t.GetNetCode())
    return g, pads


def via_ok(g, i, j, cache, code):
    k = (i, j, code)
    if k in cache:
        return cache[k]
    r = int(math.ceil((VIA_D / 2.0 + CLEAR) / PITCH))
    ok = True
    for jj in range(j - r, j + r + 1):
        for ii in range(i - r, i + r + 1):
            if not (g.free(F, ii, jj, code) and g.free(B, ii, jj, code)):
                ok = False
                break
        if not ok:
            break
    cache[k] = ok
    return ok


def route(g, start, goal, cache, code):
    (sx, sy, sl), (gx, gy, gl) = start, goal
    if not g.free(sl, sx, sy, code) or not g.free(gl, gx, gy, code):
        return None, "endpoint blocked"
    def h(ii, jj):                      # admissible: Manhattan, never overestimates
        return abs(ii - gx) + abs(jj - gy)

    best = {(sl, sx, sy): 0.0}
    prev, seen = {}, set()
    pq = [(float(h(sx, sy)), 0.0, sl, sx, sy)]
    while pq:
        _f, d, lay, i, j = heapq.heappop(pq)
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
            if g.free(lay, ii, jj, code):
                nd = d + 1.0
                if nd < best.get((lay, ii, jj), 1e18):
                    best[(lay, ii, jj)] = nd
                    prev[(lay, ii, jj)] = (lay, i, j)
                    heapq.heappush(pq, (nd + h(ii, jj), nd, lay, ii, jj))
        other = B if lay == F else F
        if via_ok(g, i, j, cache, code):
            nd = d + W_VIA
            if nd < best.get((other, i, j), 1e18):
                best[(other, i, j)] = nd
                prev[(other, i, j)] = (lay, i, j)
                heapq.heappush(pq, (nd + h(i, j), nd, other, i, j))
    return None, "search exhausted"


def simplify(path):
    if len(path) < 3:
        return list(path)
    out = [path[0]]
    for k in range(1, len(path) - 1):
        p, c, n = out[-1], path[k], path[k + 1]
        if c[0] == n[0] == p[0] and ((p[1] == c[1] == n[1]) or (p[2] == c[2] == n[2])):
            continue
        out.append(c)
    out.append(path[-1])
    return out


def stamp(g, run, code):
    for k in range(1, len(run)):
        la, ia, ja = run[k - 1]
        lb, ib, jb = run[k]
        if la != lb:
            px, py = g.pos(ia, ja)
            for lay in (la, lb):
                g.claim(lay, px - VIA_D / 2 - CLEAR, py - VIA_D / 2 - CLEAR,
                        px + VIA_D / 2 + CLEAR, py + VIA_D / 2 + CLEAR, code)
            continue
        xa, ya = g.pos(ia, ja)
        xb, yb = g.pos(ib, jb)
        g.claim(la, min(xa, xb) - TRACK_W / 2 - CLEAR, min(ya, yb) - TRACK_W / 2 - CLEAR,
                max(xa, xb) + TRACK_W / 2 + CLEAR, max(ya, yb) + TRACK_W / 2 + CLEAR, code)


def attempt(g0, pads, order, cache):
    """Route `order` on a copy of the base grid. Returns (n_ok, {net: run})."""
    g = Grid.__new__(Grid)
    g.__dict__.update(g0.__dict__)
    g.b = {F: [r[:] for r in g0.b[F]], B: [r[:] for r in g0.b[B]]}
    cache.clear()
    done, ok = {}, 0
    for net in order:
        pl = pads.get(net, [])
        if len(pl) < 2:
            continue
        (_, r1, n1, x0, y0, x1, y1, l1, code) = pl[0]
        (_, r2, n2, u0, v0, u1, v1, l2, _c2) = pl[1]
        path, why = route(g, (*g.cell((x0 + x1) / 2, (y0 + y1) / 2), l1[0]),
                          (*g.cell((u0 + u1) / 2, (v0 + v1) / 2), l2[0]), cache, code)
        if not path:
            continue
        run = simplify(path)
        stamp(g, run, code)
        done[net] = (run, r1, n1, r2, n2)
        ok += 1
    return ok, done


def main():
    global VIA_D, VIA_DRILL
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--attempts", type=int, default=6)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    board = pcbnew.LoadBoard(a.board)
    ds = board.GetDesignSettings()
    VIA_DRILL = max(ds.m_MinThroughDrill / MM, 0.30)
    ring = getattr(ds, "m_ViasMinAnnularWidth", 0) / MM
    VIA_D = max(0.50, VIA_DRILL + 2.0 * ring + 0.04)
    print(f"via: drill {VIA_DRILL:.2f} dia {VIA_D:.2f} "
          f"(board min drill {ds.m_MinThroughDrill / MM:.2f})")

    g0, padlist = build(board)
    pads = {}
    for p in padlist:
        pads.setdefault(p[0], []).append(p)

    cache, rng = {}, random.Random(a.seed)
    best_ok, best_order = -1, None
    for att in range(a.attempts):
        if __import__("os").environ.get("ORDER") == "hard":
            order = HARD_FIRST + [n for n in NETS if n not in HARD_FIRST]
        elif att == 0:
            order = list(NETS)
        elif att == 1:
            order = HARD_FIRST + [n for n in NETS if n not in HARD_FIRST]
        else:
            order = rng.sample(NETS, len(NETS))
        ok, _ = attempt(g0, pads, order, cache)
        print(f"  attempt {att}: routed {ok}/{len(NETS)}")
        if ok > best_ok:
            best_ok, best_order = ok, order
        if ok == len(NETS):
            break
    print(f"best {best_ok}/{len(NETS)}")

    ok, done = attempt(g0, pads, best_order, cache)
    for net in best_order:
        if net not in done:
            print(f"  {net}: FAILED")
            continue
        run, r1, n1, r2, n2 = done[net]
        vias = sum(1 for k in range(1, len(run)) if run[k][0] != run[k - 1][0])
        length = sum(abs(run[k][1] - run[k - 1][1]) + abs(run[k][2] - run[k - 1][2])
                     for k in range(1, len(run))) * PITCH
        print(f"  {net}: {r1}.{n1} -> {r2}.{n2}  {len(run)} pts  {length:.1f} mm  {vias} via")

        ncode = board.FindNet(net).GetNetCode()
        for k in range(1, len(run)):
            la, ia, ja = run[k - 1]
            lb, ib, jb = run[k]
            if la != lb:
                px, py = g0.pos(ia, ja)
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pcbnew.VECTOR2I(int(px * MM), int(py * MM)))
                v.SetWidth(int(VIA_D * MM))
                v.SetDrill(int(VIA_DRILL * MM))
                v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetLayerPair(F, B)
                v.SetNetCode(ncode)
                board.Add(v)
                continue
            xa, ya = g0.pos(ia, ja)
            xb, yb = g0.pos(ib, jb)
            if abs(xa - xb) < 1e-9 and abs(ya - yb) < 1e-9:
                continue
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(int(xa * MM), int(ya * MM)))
            t.SetEnd(pcbnew.VECTOR2I(int(xb * MM), int(yb * MM)))
            t.SetWidth(int(TRACK_W * MM))
            t.SetLayer(la)
            t.SetNetCode(ncode)
            board.Add(t)

    print(f"routed {ok}/{len(NETS)}")
    if board.Zones():
        print(f"refilling {len(board.Zones())} zone(s): the router has no zone model, so the "
              f"pour must be re-knitted around the new copper")
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(a.out, board)
    print(f"wrote {a.out}")
    return 0 if ok == len(NETS) else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Is the module's pad area a closed pocket? Flood-fill reachability around the goal.

DEBUG_NET showed the start and goal cells are both free, with empty 5x5 neighbourhoods, and that
raising the A* expansion cap changes nothing. That can only mean the goal sits in a region the
search cannot reach. This measures that region directly instead of inferring it from another A*
run: flood-fill from the goal over both copper layers, with via moves allowed, and report how much
of the board is reachable and where the pocket's bounding box is.

Usage:
    flood_reachability.py            # uses /tmp/hub_lora.kicad_pcb if present
"""
from __future__ import annotations

import math
import sys
from collections import deque

import pcbnew

MM = 1_000_000
PITCH = 0.1
CLEAR = 0.20
F, B = pcbnew.F_Cu, pcbnew.B_Cu
START = (218, 517)     # from DEBUG_NET
GOAL = (459, 716)      # from DEBUG_NET


def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/hub_lora.kicad_pcb"
    b = pcbnew.LoadBoard(path)
    bb = b.GetBoardEdgesBoundingBox()
    ox, oy = bb.GetX() / MM, bb.GetY() / MM
    nx = int(bb.GetWidth() / MM / PITCH) + 1
    ny = int(bb.GetHeight() / MM / PITCH) + 1
    print(f"board {bb.GetWidth()/MM:.1f}x{bb.GetHeight()/MM:.1f} grid {nx}x{ny}")

    blocked = {F: [[0] * nx for _ in range(ny)], B: [[0] * nx for _ in range(ny)]}

    def mark(lay, x0, y0, x1, y1):
        i0 = max(0, int((x0 - ox) / PITCH))
        i1 = min(nx - 1, int((x1 - ox) / PITCH) + 1)
        j0 = max(0, int((y0 - oy) / PITCH))
        j1 = min(ny - 1, int((y1 - oy) / PITCH) + 1)
        for j in range(j0, j1 + 1):
            row = blocked[lay][j]
            for i in range(i0, i1 + 1):
                row[i] = 1

    for t in b.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            r = t.GetWidth() / 2.0 / MM + CLEAR
            px, py = t.GetPosition().x / MM, t.GetPosition().y / MM
            for lay in (F, B):
                if t.IsOnLayer(lay):
                    mark(lay, px - r, py - r, px + r, py + r)
        else:
            lay = t.GetLayer()
            if lay not in (F, B):
                continue
            r = t.GetWidth() / 2.0 / MM + CLEAR
            s, e = t.GetStart(), t.GetEnd()
            mark(lay, min(s.x, e.x) / MM - r, min(s.y, e.y) / MM - r,
                 max(s.x, e.x) / MM + r, max(s.y, e.y) / MM + r)

    goal_rect = None
    for f in b.GetFootprints():
        for p in f.Pads():
            try:
                if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                    continue
                pb = p.GetBoundingBox()
                x0, y0 = pb.GetX() / MM, pb.GetY() / MM
                x1, y1 = x0 + pb.GetWidth() / MM, y0 + pb.GetHeight() / MM
                ls = p.GetLayerSet()
                # unblock the goal pad, as the router does for its own endpoints
                cx = int(((x0 + x1) / 2 - ox) / PITCH)
                cy = int(((y0 + y1) / 2 - oy) / PITCH)
                if (cx, cy) == GOAL:
                    goal_rect = (x0, y0, x1, y1)
                    continue
                for lay in (F, B):
                    if ls.Contains(lay):
                        mark(lay, x0 - CLEAR, y0 - CLEAR, x1 + CLEAR, y1 + CLEAR)
            except Exception:
                continue

    print(f"goal pad rect {goal_rect}")
    seen = {F: [[False] * nx for _ in range(ny)], B: [[False] * nx for _ in range(ny)]}
    dq = deque([(F, GOAL[0], GOAL[1])])
    seen[F][GOAL[1]][GOAL[0]] = True
    cnt = 0
    minx = miny = 10 ** 9
    maxx = maxy = -10 ** 9
    while dq:
        lay, x, y = dq.popleft()
        cnt += 1
        minx = min(minx, x); maxx = max(maxx, x)
        miny = min(miny, y); maxy = max(maxy, y)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxx, nyy = x + dx, y + dy
            if 0 <= nxx < nx and 0 <= nyy < ny and not seen[lay][nyy][nxx] \
                    and not blocked[lay][nyy][nxx]:
                seen[lay][nyy][nxx] = True
                dq.append((lay, nxx, nyy))
        other = B if lay == F else F
        if not seen[other][y][x] and not blocked[other][y][x]:
            seen[other][y][x] = True
            dq.append((other, x, y))

    reach_start = seen[F][START[1]][START[0]] or seen[B][START[1]][START[0]]
    free = sum(1 for lay in (F, B) for j in range(ny) for i in range(nx) if not blocked[lay][j][i])
    print(f"reachable from goal: {cnt} cells of {free} free ({100.0*cnt/max(free,1):.1f}%)")
    print(f"reachable bbox: x {ox+minx*PITCH:.2f}..{ox+maxx*PITCH:.2f}  "
          f"y {oy+miny*PITCH:.2f}..{oy+maxy*PITCH:.2f}")
    print(f"START reachable from GOAL: {reach_start}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

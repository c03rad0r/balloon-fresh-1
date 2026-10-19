"""Fix the C_CAP2.2 drill conflict: delete the concentric via, add a REAL GND connection.

WHY THIS EXISTS (measured + consultant ruling, gpt-6-astra 2026-10-19):

DRC reports holes_co_located (ERROR class): a 0.60/0.30 GND via drilled at the EXACT centre of
C_CAP2's pad 2 -- a PTH pad, 2.0x2.0 mm, 1.0 mm drill, net GND.

The naive fix -- delete the via -- would float the pad, because:
  GND tracks touching the pad vicinity on F.Cu: 0, on B.Cu: 0
  the pad centre is NOT inside the In1/In2/B.Cu GND pours

But keeping it is worse, because the via is a CAD FICTION, not a real connection:
  the drill file carries TWO holes at one point (1.0 mm pad + 0.30 mm via).
  The fabricator resolves that to ONE 1.0 mm plated hole; the via's 0.60 mm land lies entirely
  inside the 1.0 mm hole and does not survive drilling as an independent copper feature.
  Astra: "the via may supply a connection in the CAD connectivity model without supplying a
  realizable connection on the fabricated board. Treat C_CAP2.2 as NOT RELIABLY CONNECTED in the
  manufactured result already."

So this is a THIRD open ground nobody had counted -- one that DRC's own error was pointing at.

THE FIX (Astra rank 1): delete the concentric via, then route a real GND track from the pad's
SURVIVING annulus (the 2.0 mm pad copper, outside the 1.0 mm hole) to established GND copper.
The area is wide open: a clearance sweep found 72/72 angles clear at r=0.2..1.5 mm around the pad
(a supercap is big, its neighbourhood is not dense).

Run:
    ~/venvs/kicad/bin/python tracker/hardware/fix_cap2_gnd.py \\
        --in <board> --out <out> [--apply]
"""
from __future__ import annotations

import argparse
import math
import sys

import pcbnew

UM = 1_000_000.0
CLR = 0.200
TRK_W = 0.200
TRK_R = 0.100
VIA_POS = (56.7925, 47.2925)      # the phantom via
PAD_POS = (56.7925, 47.2925)      # C_CAP2.2 centre


def segd(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    board = pcbnew.LoadBoard(args.inp)
    gnd = board.FindNet("GND")
    gndcode = gnd.GetNetCode()

    # ---------- 1. find the phantom via ----------
    target = None
    for t in board.GetTracks():
        if t.Type() != pcbnew.PCB_VIA_T:
            continue
        p = t.GetPosition()
        if abs(p.x / UM - VIA_POS[0]) < 0.001 and abs(p.y / UM - VIA_POS[1]) < 0.001:
            target = t
            break
    if target is None:
        print("phantom via not found -- nothing to do")
        return 1
    print(f"found phantom via at {VIA_POS} net={target.GetNetname()}")

    # ---------- 2. target: the GND POUR EDGE around the pad, not a distant via ----------
    # Load the filled F.Cu GND polygons; find the nearest point of main-plane copper to the pad.
    planes = {}
    for z in board.Zones():
        ln = board.GetLayerName(z.GetLayer())
        if ln != "F.Cu":
            continue
        poly = z.GetFilledPolysList(z.GetLayer())
        arr = []
        for i in range(poly.OutlineCount()):
            ol = poly.Outline(i)
            pts = [(ol.CPoint(k).x / UM, ol.CPoint(k).y / UM) for k in range(ol.PointCount())]
            a = 0.0
            for k in range(len(pts)):
                x1, y1 = pts[k]
                x2, y2 = pts[(k + 1) % len(pts)]
                a += x1 * y2 - x2 * y1
            arr.append((abs(a) / 2, pts))
        arr.sort(key=lambda tt: -tt[0])
        planes[ln] = arr

    def inside(pts, x, y):
        ins = False
        n = len(pts)
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            if (y1 > y) != (y2 > y):
                xin = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                if x < xin:
                    ins = not ins
        return ins

    main = planes["F.Cu"][0][1]
    # nearest point ON the main-plane outline to the pad centre
    best = (1e9, None)
    for i in range(len(main)):
        ax, ay = main[i]
        bx, by = main[(i + 1) % len(main)]
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            t = 0.0
        else:
            t = max(0.0, min(1.0, ((PAD_POS[0] - ax) * dx + (PAD_POS[1] - ay) * dy) / (dx * dx + dy * dy)))
        px_, py_ = ax + t * dx, ay + t * dy
        d = math.hypot(px_ - PAD_POS[0], py_ - PAD_POS[1])
        if d < best[0]:
            best = (d, (px_, py_))
    print(f"nearest main-plane GND pour edge: {best[1]} at {best[0]:.3f} mm")
    goal = best[1]

    # ---------- 3. obstacles (foreign copper on F.Cu) ----------
    obstacles = []
    for t in board.GetTracks():
        if t.GetNetCode() == gndcode:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            p = t.GetPosition()
            obstacles.append(("via", p.x / UM, p.y / UM, t.GetWidth(pcbnew.F_Cu) / 2 / UM, str(t.GetNetname())))
        elif t.Type() == pcbnew.PCB_TRACE_T and board.GetLayerName(t.GetLayer()) == "F.Cu":
            s, e = t.GetStart(), t.GetEnd()
            obstacles.append(("trk", s.x / UM, s.y / UM, e.x / UM, e.y / UM, t.GetWidth() / 2 / UM, str(t.GetNetname())))
    padobs = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetCode() == gndcode:
                continue
            if "F.Cu" not in [board.GetLayerName(l) for l in p.GetLayerSet().Seq()]:
                continue
            pos = p.GetPosition()
            padobs.append((pos.x / UM, pos.y / UM, p.GetSize().x / UM, p.GetSize().y / UM,
                           fp.GetReference() + "." + str(p.GetNumber())))

    def clr(x, y):
        w = (1e9, None)
        for ob in obstacles:
            if ob[0] == "via":
                d = math.hypot(x - ob[1], y - ob[2]) - ob[3] - TRK_R
            else:
                d = segd(x, y, ob[1], ob[2], ob[3], ob[4]) - ob[5] - TRK_R
            if d < w[0]:
                w = (d, ob[-1])
        for px, py, ww, hh, nm in padobs:
            dxr = max(px - ww / 2 - x, 0.0, x - (px + ww / 2))
            dyr = max(py - hh / 2 - y, 0.0, y - (py + hh / 2))
            d = math.hypot(dxr, dyr) - TRK_R
            if d < w[0]:
                w = (d, nm)
        return w

    # ---------- 4. A* from the pad's annulus edge to the pour edge ----------
    import heapq
    dxn, dyn = goal[0] - PAD_POS[0], goal[1] - PAD_POS[1]
    nn = math.hypot(dxn, dyn)
    start = (PAD_POS[0] + dxn / nn * 1.06, PAD_POS[1] + dyn / nn * 1.06)
    NODE = 0.05
    gx, gy = goal
    oh = [(math.hypot(gx - start[0], gy - start[1]), 0.0, start[0], start[1])]
    seen = {(round(start[0] / NODE), round(start[1] / NODE)): 0.0}
    par = {}
    gk = (round(gx / NODE), round(gy / NODE))
    path = None
    bx0, by0 = min(start[0], gx) - 2.0, min(start[1], gy) - 2.0
    bx1, by1 = max(start[0], gx) + 2.0, max(start[1], gy) + 2.0
    while oh:
        f, g, x, y = heapq.heappop(oh)
        k = (round(x / NODE), round(y / NODE))
        if k == gk or math.hypot(x - gx, y - gy) < 0.08:
            path = [(x, y)]
            while k in par:
                k = par[k]
                path.append((k[0] * NODE, k[1] * NODE))
            path = path[::-1]
            break
        for ddx, ddy in ((NODE, 0), (-NODE, 0), (0, NODE), (0, -NODE),
                         (NODE, NODE), (-NODE, NODE), (NODE, -NODE), (-NODE, -NODE)):
            nx_, ny_ = x + ddx, y + ddy
            if not (bx0 <= nx_ <= bx1 and by0 <= ny_ <= by1):
                continue
            nk = (round(nx_ / NODE), round(ny_ / NODE))
            ng = g + math.hypot(ddx, ddy)
            if nk in seen and seen[nk] <= ng:
                continue
            if clr(nx_, ny_)[0] < CLR:
                continue
            seen[nk] = ng
            par[nk] = k
            heapq.heappush(oh, (ng + math.hypot(gx - nx_, gy - ny_), ng, nx_, ny_))
    if path is None:
        print("A* FAILED: no path from the pad annulus to the GND pour edge")
        return 1
    # simplify
    simp = [path[0]]
    for i in range(1, len(path) - 1):
        ax, ay = simp[-1]
        bx_, by_ = path[i]
        cx_, cy_ = path[i + 1]
        if abs((bx_ - ax) * (cy_ - ay) - (by_ - ay) * (cx_ - ax)) > 1e-9:
            simp.append(path[i])
    simp.append(path[-1])
    L = sum(math.hypot(simp[i + 1][0] - simp[i][0], simp[i + 1][1] - simp[i][1]) for i in range(len(simp) - 1))
    print(f"A* path: {len(path)} nodes -> {len(simp) - 1} segments, {L:.2f} mm, ends at {simp[-1]}")
    end = simp[-1]

    if not args.apply:
        print("(dry run -- pass --apply to write)")
        return 0

    # ---------- 5. apply: remove via, add track ----------
    board.Remove(target)
    print("removed phantom via")
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I(int(round(start[0] * UM)), int(round(start[1] * UM))))
    t.SetEnd(pcbnew.VECTOR2I(int(round(end[0] * UM)), int(round(end[1] * UM))))
    t.SetWidth(int(round(TRK_W * UM)))
    t.SetLayer(board.GetLayerID("F.Cu"))
    t.SetNet(gnd)
    board.Add(t)
    print(f"added GND track {start} -> {end}")
    print("refilling zones")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(args.out, board)
    print(f"saved {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

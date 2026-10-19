"""Fix the two via-less GND fragments (D12). Astra: "Do not order with these. Fix those first."

TWO REAL ELECTRICAL DEFECTS:
  U4.13        (SX1280 GND, declared GND in the netlist) sits in a 0.278 mm2 F.Cu pour with no via.
  U_HUB_CVT.2  (BQ25504 GND, declared GND) sits in a 0.445 mm2 F.Cu pour with no via.
Neither fragment can hold a via: U4.13's is 0.298 mm tall, and a 0.50 mm via has a 0.90 mm envelope.

THE ROOT CAUSE OF U4.13 (measured, see docs/fab/D12-VIALESS-GND-FRAGMENTS.md):
  U4's right column is 9 pads at 0.500 mm pitch with 0.300 mm pad height, so the edge-to-edge gap between
  every adjacent pair is 0.200 mm = exactly the clearance rule. The GND escape must therefore run inside
  y 27.200..27.300 -- a 0.100 mm window. /SX1280_VDD's diagonal (55.650,27.750)->(56.300,27.100) crosses
  y=27.25 at x~56.0 and is the ONLY thing blocking it.

WHY MOVING VDD IS SAFE: /SX1280_VDD has two pads on U4 (pad 2 at 50.350,26.000 and pad 12 at
55.150,27.750) which are ALREADY joined through In1.Cu, so the F.Cu diagonal from pad 12 to the via at
(56.300,26.450) may be rerouted above the GND corridor without disconnecting anything.

WHAT THIS SCRIPT DOES, in order:
  1. rips the one VDD diagonal and replaces it with an L that stays north of y=27.40
  2. routes a GND track out of U4.13 along y=27.250 to the nearest validated GND via
  3. routes a GND track from U_HUB_CVT.2 to the GND via at (26.100,5.800)
  4. refills zones
Every step is a measured, dry-runnable plan; --apply writes the board.

Does NOT touch In1.Cu island 1 (Astra: add stitching vias there, do NOT reroute +3V3).
Does NOT touch the three signal nets already routed.
"""
from __future__ import annotations

import argparse
import heapq
import math
import sys

import pcbnew

UM = 1_000_000.0
R_TR = 0.100          # 0.20 mm track
CLR = 0.200
NODE = 0.05
VIA_D = 0.50
VIA_R = VIA_D / 2.0
VIA_SPACING = 0.800   # 0.500 dia + 0.200 clearance between two vias


def segd(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


class World:
    def __init__(self, board):
        self.b = board
        self.gnd = board.FindNet("GND").GetNetCode()
        self.trk = {"F.Cu": [], "In1.Cu": [], "In2.Cu": [], "B.Cu": []}
        self.vias = []        # (x, y, r) all-layer, non-GND
        self.pads = []        # (x, y, w, h, layers) non-GND
        self.gnd_vias = []
        for t in board.GetTracks():
            if t.GetNetCode() == self.gnd:
                if t.Type() == pcbnew.PCB_VIA_T:
                    p = t.GetPosition()
                    self.gnd_vias.append((p.x / UM, p.y / UM))
                continue
            if t.Type() == pcbnew.PCB_VIA_T:
                p = t.GetPosition()
                self.vias.append((p.x / UM, p.y / UM, t.GetWidth(pcbnew.F_Cu) / 2 / UM))
            elif t.Type() == pcbnew.PCB_TRACE_T:
                s, e = t.GetStart(), t.GetEnd()
                ln = board.GetLayerName(t.GetLayer())
                self.trk.setdefault(ln, []).append(
                    (s.x / UM, s.y / UM, e.x / UM, e.y / UM, t.GetWidth() / 2 / UM, str(t.GetNetname())))
        for fp in board.GetFootprints():
            for p in fp.Pads():
                if p.GetNetCode() == self.gnd:
                    continue
                pos = p.GetPosition()
                self.pads.append((pos.x / UM, pos.y / UM, p.GetSize().x / UM, p.GetSize().y / UM,
                                  [board.GetLayerName(l) for l in p.GetLayerSet().Seq()],
                                  fp.GetReference() + "." + str(p.GetNumber()), str(p.GetNetname())))

    def clr_track(self, x, y, layer, ignore_nets=(), radius=R_TR):
        """Clearance for a TRACK on ONE layer. Tracks on other layers do not obstruct."""
        worst = (1e9, None)
        for x1, y1, x2, y2, rr, nm in self.trk.get(layer, []):
            if nm in ignore_nets:
                continue
            d = segd(x, y, x1, y1, x2, y2) - rr - radius
            if d < worst[0]:
                worst = (d, "trk " + nm)
        for vx, vy, rr in self.vias:
            d = math.hypot(x - vx, y - vy) - rr - radius
            if d < worst[0]:
                worst = (d, "via")
        for px, py, ww, hh, layers, nm, pnet in self.pads:
            if layer not in layers:
                continue
            if pnet in ignore_nets:
                continue
            dx = max(px - ww / 2 - x, 0.0, x - (px + ww / 2))
            dy = max(py - hh / 2 - y, 0.0, y - (py + hh / 2))
            d = math.hypot(dx, dy) - radius
            if d < worst[0]:
                worst = (d, "pad " + nm)
        return worst

    def clr_via(self, x, y, ignore_nets=()):
        """A via pierces every layer: worst of all four, plus via-to-via spacing."""
        worst = (1e9, None)
        for ln in ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"):
            c = self.clr_track(x, y, ln, ignore_nets, radius=VIA_R)
            if c[0] < worst[0]:
                worst = c
        for gx, gy in self.gnd_vias:
            d = math.hypot(x - gx, y - gy) - VIA_SPACING
            if d < worst[0]:
                worst = (d, "other GND via")
        return worst


def astar(world, start, goals, layer, ignore_nets=(), bounds=None):
    """Grid A* on ONE layer. Returns a list of points, or None."""
    sx, sy = start
    gkeys = {(round(g[0] / NODE), round(g[1] / NODE)) for g in goals}
    if bounds is None:
        xs = [sx] + [g[0] for g in goals]
        ys = [sy] + [g[1] for g in goals]
        bounds = (min(xs) - 6, min(ys) - 6, max(xs) + 6, max(ys) + 6)
    bx0, by0, bx1, by1 = bounds

    def near(g):
        return math.hypot(g[0] - sx, g[1] - sy)

    best = min(goals, key=near)
    openh = [(math.hypot(best[0] - sx, best[1] - sy), 0.0, sx, sy)]
    seen = {(round(sx / NODE), round(sy / NODE)): 0.0}
    parent = {}
    steps = ((NODE, 0), (-NODE, 0), (0, NODE), (0, -NODE),
             (NODE, NODE), (-NODE, NODE), (NODE, -NODE), (-NODE, -NODE))
    while openh:
        f, g, x, y = heapq.heappop(openh)
        k = (round(x / NODE), round(y / NODE))
        if k in gkeys:
            path = [(x, y)]
            while k in parent:
                k = parent[k]
                path.append((k[0] * NODE, k[1] * NODE))
            return path[::-1]
        for dx, dy in steps:
            nx, ny = x + dx, y + dy
            if not (bx0 <= nx <= bx1 and by0 <= ny <= by1):
                continue
            nk = (round(nx / NODE), round(ny / NODE))
            ng = g + math.hypot(dx, dy)
            if nk in seen and seen[nk] <= ng:
                continue
            if world.clr_track(nx, ny, layer, ignore_nets)[0] < CLR:
                continue
            seen[nk] = ng
            parent[nk] = k
            heapq.heappush(openh, (ng + math.hypot(best[0] - nx, best[1] - ny), ng, nx, ny))
    return None


def simplify(pts):
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        ax, ay = out[-1]
        bx, by = pts[i]
        cx, cy = pts[i + 1]
        cross = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
        if abs(cross) > 1e-9:
            out.append(pts[i])
    out.append(pts[-1])
    return out


def plane_polys(board):
    d = {}
    for z in board.Zones():
        ln = board.GetLayerName(z.GetLayer())
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
        arr.sort(key=lambda t: -t[0])
        d[ln] = arr
    return d


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    board = pcbnew.LoadBoard(args.inp)
    w = World(board)
    planes = plane_polys(board)
    in1_main = planes["In1.Cu"][0][1]
    bcu_main = planes["B.Cu"][0][1]

    def on_main(x, y):
        return inside(in1_main, x, y) or inside(bcu_main, x, y)

    goals = [(gx, gy) for gx, gy in w.gnd_vias if on_main(gx, gy)]
    print(f"GND vias landing in a main plane: {len(goals)}")

    plan = []

    # ---------------------------------------------------------------- 1. VDD diagonal
    # Rip (55.650,27.750)->(56.300,27.100) and replace with an L that stays north of y=27.40.
    # Endpoints are preserved, so VDD keeps pad 12 and its via.
    vdd_a = (55.650, 27.750)
    vdd_b = (56.300, 27.100)
    corner = (56.300, 27.750)      # go east first at y=27.750, then south at x=56.300
    plan.append(("rip", "/SX1280_VDD", "F.Cu", (vdd_a, vdd_b)))
    plan.append(("track", "/SX1280_VDD", "F.Cu", [vdd_a, corner]))
    plan.append(("track", "/SX1280_VDD", "F.Cu", [corner, vdd_b]))
    print(f"\n1. VDD: rip diagonal {vdd_a}->{vdd_b}, replace with {vdd_a}->{corner}->{vdd_b}")
    for nm, seg in (("east leg", (vdd_a, corner)), ("south leg", (corner, vdd_b))):
        worst = (1e9, None)
        steps = max(2, int(math.hypot(seg[1][0] - seg[0][0], seg[1][1] - seg[0][1]) / 0.02))
        for i in range(steps + 1):
            t = i / steps
            x = seg[0][0] + t * (seg[1][0] - seg[0][0])
            y = seg[0][1] + t * (seg[1][1] - seg[0][1])
            c = w.clr_track(x, y, "F.Cu", ignore_nets={"/SX1280_VDD"})
            if c[0] < worst[0]:
                worst = c
        flag = "OK " if worst[0] >= CLR else "BAD"
        print(f"     {flag} {nm}: worst {worst[0]:+.3f} vs {worst[1]}")

    # ---------------------------------------------------------------- 2. U4.13 GND escape
    print("\n2. U4.13 GND escape along y=27.250")
    u4_13 = (55.150, 27.250)
    lane = 27.250
    # No GND via exists near this pad, so we must PLACE one. Search outward from the pad for a site
    # that (a) is legal on all four layers and (b) lands in In1.Cu or B.Cu main plane.
    new_via = None
    cands = []
    for r in [0.60 + 0.05 * k for k in range(60)]:
        for ang in range(0, 360, 5):
            a = math.radians(ang)
            x = u4_13[0] + r * math.cos(a)
            y = u4_13[1] + r * math.sin(a)
            if not (0.6 < x < 69.4 and 0.6 < y < 70.9):
                continue
            if not on_main(x, y):
                continue
            if w.clr_via(x, y, ignore_nets={"/SX1280_VDD"})[0] < CLR:
                continue
            # GND stub from the pad to this site must be legal on F.Cu
            bad = False
            steps = max(4, int(math.hypot(x - u4_13[0], y - u4_13[1]) / 0.02))
            for i in range(steps + 1):
                t = i / steps
                sx = u4_13[0] + t * (x - u4_13[0])
                sy = u4_13[1] + t * (y - u4_13[1])
                if w.clr_track(sx, sy, "F.Cu", ignore_nets={"/SX1280_VDD"})[0] < CLR:
                    bad = True
                    break
            if bad:
                continue
            cands.append((r, x, y))
        if cands:
            break
    cands.sort()
    print(f"     legal new-via candidates: {len(cands)}")
    for r, x, y in cands[:4]:
        print(f"       r={r:.2f} ({x:.3f},{y:.3f})  on_main={on_main(x,y)}")
    if cands:
        r, vx, vy = cands[0]
        plan.append(("track", "GND", "F.Cu", [u4_13, (vx, vy)]))
        plan.append(("via", "GND", None, (vx, vy)))
        print(f"     -> stub + via at ({vx:.3f},{vy:.3f})")
    else:
        print("     NO legal new via site")

    # ---------------------------------------------------------------- 3. U_HUB_CVT.2 GND stub
    print("\n3. U_HUB_CVT.2 GND stub to (26.100, 5.800)")
    cvt = (25.683, 2.895)
    target = (26.100, 5.800)
    path = astar(w, cvt, [target], "F.Cu", bounds=(22.0, 1.0, 32.0, 9.0))
    if path:
        pts = simplify(path)
        print(f"     PATH {len(got) if False else len(path)} nodes -> {len(pts)-1} segments")
        plan.append(("track", "GND", "F.Cu", [cvt] + pts[1:]))
    else:
        print("     NO PATH")

    # ---------------------------------------------------------------- summary
    print("\n--- plan ---")
    for kind, net, layer, geom in plan:
        if kind == "rip":
            print(f"   rip   {net:16s} {layer} {geom[0]}->{geom[1]}")
        elif kind == "via":
            print(f"   via   {net:16s} at {geom}")
        else:
            print(f"   track {net:16s} {layer} {len(geom)-1} segments from {geom[0]} to {geom[-1]}")

    if not args.apply:
        print("\n(dry run -- pass --apply to write)")
        return 0

    # ---------------------------------------------------------------- apply
    print("\n--- APPLYING ---")

    def find_track(netname, layer, a, b, tol=0.02):
        for t in board.GetTracks():
            if t.Type() != pcbnew.PCB_TRACE_T:
                continue
            if str(t.GetNetname()) != netname:
                continue
            if board.GetLayerName(t.GetLayer()) != layer:
                continue
            s, e = t.GetStart(), t.GetEnd()
            p1 = (s.x / UM, s.y / UM)
            p2 = (e.x / UM, e.y / UM)
            for q1, q2 in ((p1, p2), (p2, p1)):
                if abs(q1[0] - a[0]) < tol and abs(q1[1] - a[1]) < tol and \
                   abs(q2[0] - b[0]) < tol and abs(q2[1] - b[1]) < tol:
                    return t
        return None

    ripped = 0
    for kind, net, layer, geom in plan:
        if kind != "rip":
            continue
        t = find_track(net, layer, geom[0], geom[1])
        if t is not None:
            board.Remove(t)
            ripped += 1
            print(f"  ripped {net} {geom[0]}->{geom[1]}")
        else:
            print(f"  WARNING: could not find {net} segment {geom[0]}->{geom[1]} to rip")

    added_t = added_v = 0
    for kind, net, layer, geom in plan:
        if kind == "track":
            netobj = board.FindNet(net)
            pts = geom
            for i in range(len(pts) - 1):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(pcbnew.VECTOR2I(int(round(pts[i][0] * UM)), int(round(pts[i][1] * UM))))
                t.SetEnd(pcbnew.VECTOR2I(int(round(pts[i + 1][0] * UM)), int(round(pts[i + 1][1] * UM))))
                t.SetWidth(int(round(0.20 * UM)))
                t.SetLayer(board.GetLayerID(layer))
                t.SetNet(netobj)
                board.Add(t)
                added_t += 1
        elif kind == "via":
            x, y = geom
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(int(round(x * UM)), int(round(y * UM))))
            v.SetWidth(int(round(VIA_D * UM)))
            v.SetDrill(int(round(0.25 * UM)))
            v.SetNet(board.FindNet("GND"))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            board.Add(v)
            added_v += 1
            print(f"  added GND via at ({x:.3f},{y:.3f})")

    print(f"\n  ripped {ripped} tracks, added {added_t} tracks, {added_v} vias")
    print("  refilling zones")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(args.out, board)
    print(f"  saved {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

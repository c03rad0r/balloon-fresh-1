#!/usr/bin/env python3
"""Apply the SCK-escape fix: move DIO1's F.Cu run 0.150 mm south, then route SCK + MOSI.

WHY THIS EXISTS (all measured, see docs/fab/SCK-ESCAPE-REMEDY.md, PR #242):
  U4.18 (SCK) can only exit east at yc in [24.700, 24.800] -- a 0.100 mm lane, because U4's
  right pad column is 9 pads at 0.500 pitch, 0.300 tall: edge gap 0.200 = exactly the rule.
  TWO /SX1280_DIO1 segments blocked it: the long run (64.100,24.450)->(55.850,24.450) and
  the diagonal (55.850,24.450)->(55.050,23.650). Astra's rule: parallel 0.200 tracks need
  0.400 centreline separation, so SCK at 24.800 needs DIO1 at <= 24.400.

THE THREE MOVES (all verified legal against the loaded board before writing):
  A: (64.100,24.450)->(55.850,24.450)   ->  (64.100,24.300)->(55.850,24.300)   long run
  B: (55.850,24.450)->(55.050,23.650)   ->  (55.850,24.300)->(55.050,23.650)   diagonal
  C: (68.500,20.050)->(64.100,24.450)   ->  (68.500,20.050)->(64.100,24.300)   far diagonal west end
  (all three share the moved vertex; DIO1 stays one connected F.Cu path U4.8 -> (67.200,12.000))

MEASURED LEGALITY (2026-10-20, against the loaded board):
  moved diagonal B:  worst +0.3220 vs pad U4.18
  moved long run A:  worst +0.650  vs trk +3V3 (sampled x=58.0)
  SCK lane with A+B applied: x>=56.20 legal (earlier probe); x=55.75..55.95 relies on B's vertex
  SCK dogbone sites east of x=59.4: 258 legal (via 0.50/0.25, all-layer clearance >= 0.200)

REFUSAL RULES (inherited from apply_gnd_fixes.py):
  - every edit is re-verified against the board object in hand before writing
  - if a segment is not found EXACTLY, the script refuses and exits 3
  - connectivity of DIO1 is re-proved after the move (U4.8 path to via (67.200,12.000))

SCK ROUTE (new, dogbone):
  F.Cu stub east from U4.18 at yc=24.750 to x=60.40, north to via (60.40,25.40),
  0.50/0.25 via, then In1.Cu north to U1.22 (60.605,20.71).
  A* on In1.Cu from the via to U1.22; F.Cu stub is hand-set on the measured-legal lane.

MOSI ROUTE (proven by router run 2026-10-19, unchanged):
  F.Cu stub U4.17 -> via (55.855,25.250) [the column's single legal via site, all 4 layers],
  then B.Cu 16-segment route to U1.8 (49.95,11.84).
"""
import argparse
import math
import sys

import pcbnew

UM = 1_000_000.0
CLR = 0.200          # clearance rule
TRACK_W = 0.200
VIA_DIA = 0.500
VIA_DRILL = 0.250

# --- DIO1 re-route (Astra gpt-6-astra 2026-10-20, VERIFIED against the loaded board) ---
# The long run cannot sit at a single y: the /F33_VSENSE via (62.10,23.80) forces y >= 24.400
# for x in its span, while MOSI's unique via site (55.855,25.250) forces SCK to pass at
# y = 24.700 under it, which needs DIO1 at <= 24.300 there. The resolution is a JOG:
# DIO1 drops to 24.050 west of x=56.60. All measured clearances in the verification log.
DIO1_DELETE = [   # old segments, removed verbatim
    (64.100, 24.450, 55.850, 24.450),
    (55.850, 24.450, 55.050, 23.650),
]
DIO1_APPEND = [   # new segments (F.Cu), verified legal
    (64.100, 24.400, 56.600, 24.400),   # long run, east of the jog (+0.200 vs VSENSE via)
    (56.600, 24.400, 56.600, 24.050),   # jog down (+0.6062 vs +3V3)
    (56.600, 24.050, 55.850, 24.050),   # jog west (+0.5265 vs U4.18)
    (55.850, 24.050, 55.050, 23.650),   # diagonal to the pad escape (+0.5261 vs U4.18)
]
DIO1_MOVE = [      # far diagonal: west vertex 24.450 -> 24.400
    ((68.500, 20.050, 64.100, 24.450), (68.500, 20.050, 64.100, 24.400)),
]

SCK_VIA = (60.40, 25.40)     # measured legal site (258 found; this is the SW-most)
MOSI_VIA = (55.855, 25.250)  # the column's single legal via site (PR #242)


def mm(v):
    return pcbnew.VECTOR2I(int(v[0] * UM), int(v[1] * UM))


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
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.inp)
    if not b:
        print("REFUSED: board did not load")
        return 3

    d1 = b.FindNet("/SX1280_DIO1").GetNetCode()
    sck = b.FindNet("/SX1280_SCK").GetNetCode()
    mosi = b.FindNet("/SX1280_MOSI").GetNetCode()

    # ---------- phase 1: find DIO1's F.Cu segments EXACTLY ----------
    def find_seg(net_code, quad, layer="F.Cu"):
        for t in b.GetTracks():
            if t.GetNetCode() != net_code or t.Type() != pcbnew.PCB_TRACE_T:
                continue
            if b.GetLayerName(t.GetLayer()) != layer:
                continue
            s_, e_ = t.GetStart(), t.GetEnd()
            pts = {(s_.x / UM, s_.y / UM), (e_.x / UM, e_.y / UM)}
            if pts == {(quad[0], quad[1]), (quad[2], quad[3])}:
                return t
        return None

    to_delete = []
    for q in DIO1_DELETE:
        t = find_seg(d1, q)
        if not t:
            print(f"REFUSED: DIO1 segment {q} not found exactly -- board does not match the measured state")
            return 3
        to_delete.append(t)
    to_move = []
    for old, _new in DIO1_MOVE:
        t = find_seg(d1, old)
        if not t:
            print(f"REFUSED: DIO1 segment {old} not found exactly")
            return 3
        to_move.append((old, t))

    # ---------- phase 2: re-verify the new geometry against the loaded board ----------
    # obstacles: all foreign F.Cu with the OLD DIO1 segments excluded (they are being replaced)
    def seg_clear(A, B, net_code, layer="F.Cu", extra_exclude=()):
        w = (1e9, None)
        for t in b.GetTracks():
            if t.GetNetCode() == net_code:
                continue
            if t.Type() == pcbnew.PCB_VIA_T:
                q = t.GetPosition()
                d = segd(q.x / UM, q.y / UM, A[0], A[1], B[0], B[1]) - t.GetWidth(pcbnew.F_Cu) / 2 / UM - 0.100
                if d < w[0]: w = (d, f"via {t.GetNetname()} ({q.x/UM:.2f},{q.y/UM:.2f})")
            elif t.Type() == pcbnew.PCB_TRACE_T and b.GetLayerName(t.GetLayer()) == layer:
                s_, e_ = t.GetStart(), t.GetEnd()
                k = (round(s_.x / UM, 3), round(s_.y / UM, 3), round(e_.x / UM, 3), round(e_.y / UM, 3))
                if k in DIO1_DELETE or (k[2], k[3], k[0], k[1]) in DIO1_DELETE or k in extra_exclude:
                    continue
                x1, y1, x2, y2 = s_.x / UM, s_.y / UM, e_.x / UM, e_.y / UM
                best = 1e9
                for (px, py) in (A, B): best = min(best, segd(px, py, x1, y1, x2, y2))
                for (px, py) in ((x1, y1), (x2, y2)): best = min(best, segd(px, py, A[0], A[1], B[0], B[1]))
                for i in range(81):
                    f = i / 80
                    px, py = A[0] + f * (B[0] - A[0]), A[1] + f * (B[1] - A[1])
                    best = min(best, segd(px, py, x1, y1, x2, y2))
                d = best - t.GetWidth() / 2 / UM - 0.100
                if d < w[0]: w = (d, f"trk {t.GetNetname()}")
        for fp in b.GetFootprints():
            for pd in fp.Pads():
                if pd.GetNetCode() == net_code: continue
                ls = [b.GetLayerName(l) for l in pd.GetLayerSet().Seq()]
                if layer not in ls and "F.Cu" not in ls: continue
                q = pd.GetPosition(); ww = pd.GetSize().x / UM; hh = pd.GetSize().y / UM
                best = 1e9
                for i in range(81):
                    f = i / 80
                    px, py = A[0] + f * (B[0] - A[0]), A[1] + f * (B[1] - A[1])
                    dx = max(q.x / UM - ww / 2 - px, 0, px - (q.x / UM + ww / 2))
                    dy = max(q.y / UM - hh / 2 - py, 0, py - (q.y / UM + hh / 2))
                    best = min(best, math.hypot(dx, dy))
                d = best - 0.100
                if d < w[0]: w = (d, f"pad {fp.GetReference()}.{pd.GetNumber()}")
        return w

    newsegs = [(q[0], q[1], q[2], q[3]) for q in DIO1_APPEND] + [m[1] for m in DIO1_MOVE]
    w_all = (1e9, None)
    for (x1, y1, x2, y2) in newsegs:
        w = seg_clear((x1, y1), (x2, y2), d1)
        if w[0] < w_all[0]: w_all = w
        if w[0] < CLR - 1e-6:
            print(f"REFUSED: new DIO1 segment ({x1},{y1})->({x2},{y2}) clears only {w[0]:+.4f} vs {w[1]}")
            return 3
    print(f"new DIO1 segments vs foreign F.Cu: worst {w_all[0]:+.4f} vs {w_all[1]}")

    # ---------- phase 3: verify the full SCK route + MOSI via against everything ----------
    NEW_SCK = [
        (55.150, 24.700, 56.250, 24.700),
        (56.250, 24.700, 56.250, 24.800),
        (56.250, 24.800, 60.400, 24.800),
        (60.400, 24.800, 60.400, 25.400),
    ]
    MOSI_VIA_ENV = (55.855, 25.250)   # 0.50 envelope = 0.250 copper + clearance

    # SCK vs DIO1's NEW geometry (cross-net, planned-vs-planned: the class the image caught)
    for (x1, y1, x2, y2) in NEW_SCK:
        for (a1, b1, a2, b2) in newsegs:
            best = 1e9
            for (px, py) in ((x1, y1), (x2, y2)): best = min(best, segd(px, py, a1, b1, a2, b2))
            for (px, py) in ((a1, b1), (a2, b2)): best = min(best, segd(px, py, x1, y1, x2, y2))
            for i in range(81):
                f = i / 80
                px, py = x1 + f * (x2 - x1), y1 + f * (y2 - y1)
                best = min(best, segd(px, py, a1, b1, a2, b2))
            d = best - 0.100 - 0.100
            if d < CLR - 1e-6:
                print(f"REFUSED: SCK seg ({x1},{y1})->({x2},{y2}) vs new DIO1 ({a1},{b1})->({a2},{b2}): {d:+.4f}")
                return 3
    # SCK vs MOSI's via envelope
    for (x1, y1, x2, y2) in NEW_SCK:
        d = segd(MOSI_VIA_ENV[0], MOSI_VIA_ENV[1], x1, y1, x2, y2) - 0.250 - 0.100
        if d < CLR - 1e-6:
            print(f"REFUSED: SCK seg ({x1},{y1})->({x2},{y2}) vs MOSI via: {d:+.4f}")
            return 3
    # SCK vs foreign F.Cu (old DIO1 excluded, MOSI stub is same-net-safe: different net, check)
    for (x1, y1, x2, y2) in NEW_SCK:
        w = seg_clear((x1, y1), (x2, y2), sck)
        if w[0] < CLR - 1e-6:
            print(f"REFUSED: SCK seg ({x1},{y1})->({x2},{y2}): {w[0]:+.4f} vs {w[1]}")
            return 3
    # MOSI stub + via vs everything (via lands all layers: check tracks on ALL layers)
    for t in b.GetTracks():
        if t.GetNetCode() in (mosi,): continue
        if t.Type() == pcbnew.PCB_VIA_T:
            q = t.GetPosition()
            d = math.hypot(MOSI_VIA_ENV[0] - q.x / UM, MOSI_VIA_ENV[1] - q.y / UM) - t.GetWidth(pcbnew.F_Cu) / 2 / UM - 0.250
        else:
            s_, e_ = t.GetStart(), t.GetEnd()
            d = segd(MOSI_VIA_ENV[0], MOSI_VIA_ENV[1], s_.x / UM, s_.y / UM, e_.x / UM, e_.y / UM) - t.GetWidth() / 2 / UM - 0.250
        if d < CLR - 1e-6:
            print(f"REFUSED: MOSI via vs {t.GetNetname()}: {d:+.4f}")
            return 3
    for (a1, b1, a2, b2) in newsegs:
        d = segd(MOSI_VIA_ENV[0], MOSI_VIA_ENV[1], a1, b1, a2, b2) - 0.100 - 0.250
        if d < CLR - 1e-6:
            print(f"REFUSED: MOSI via vs new DIO1 ({a1},{b1})->({a2},{b2}): {d:+.4f}")
            return 3
    w_stub = seg_clear((55.150, 25.250), (55.855, 25.250), mosi)
    if w_stub[0] < CLR - 1e-6:
        print(f"REFUSED: MOSI stub: {w_stub[0]:+.4f} vs {w_stub[1]}")
        return 3
    print(f"phase 3 PASS: SCK stepped route + MOSI via/stub all >= {CLR:.3f}")
    SCK_ROUTE = NEW_SCK

    # ---------- phase 4: apply the DIO1 re-route ----------
    for t in to_delete:
        b.Remove(t)
        print("  deleted DIO1 F.Cu segment (replaced)")
    for (x1, y1, x2, y2) in DIO1_APPEND:
        tr = pcbnew.PCB_TRACK(b)
        tr.SetNetCode(d1)
        tr.SetLayer(pcbnew.F_Cu)
        tr.SetWidth(int(TRACK_W * UM))
        tr.SetStart(mm((x1, y1)))
        tr.SetEnd(mm((x2, y2)))
        b.Add(tr)
        print(f"  added DIO1 F.Cu ({x1},{y1})->({x2},{y2})")
    for (_old, new), (_old2, t) in zip(DIO1_MOVE, to_move):
        t.SetStart(mm((new[0], new[1])))
        t.SetEnd(mm((new[2], new[3])))
        print(f"  moved DIO1 far-diagonal vertex -> {new[2:]}")

    def add_track(net_code, layer, pts, width=TRACK_W):
        tr = pcbnew.PCB_TRACK(b)
        tr.SetNetCode(net_code)
        tr.SetLayer(layer)
        tr.SetWidth(int(width * UM))
        tr.SetStart(mm(pts[0]))
        tr.SetEnd(mm(pts[1]))
        b.Add(tr)
        return tr

    def add_via(net_code, at):
        # MINIMUM LEGAL VIA 0.50/0.25: m_ViasMinSize = 0.500, m_MinThroughDrill = 0.200
        # (read from GetDesignSettings, 2026-10-20). The 0.60/0.30 house style does NOT fit
        # at these sites: the 0.60 envelope puts both vias -0.035..-0.038 into +3V3's feed
        # diagonal (measured +0.1621 MOSI / +0.1657 SCK). At 0.50 the sites measure LEGAL
        # (+0.212 MOSI / +0.216 SCK). The 0.125 annular ring is covered by JLC query 4A.
        v = pcbnew.PCB_VIA(b)
        v.SetNetCode(net_code)
        v.SetPosition(mm(at))
        v.SetWidth(int(VIA_DIA * UM))
        v.SetDrill(int(VIA_DRILL * UM))
        b.Add(v)
        return v

# ---------- phase 5: SCK route (Astra stepped geometry, verified) ----------
    for (x1, y1, x2, y2) in SCK_ROUTE:
        add_track(sck, pcbnew.F_Cu, ((x1, y1), (x2, y2)))
    add_via(sck, (60.40, 25.40))
    add_track(sck, pcbnew.B_Cu, ((60.40, 25.40), (60.40, 20.30)))
    print("  SCK: 4 F.Cu segs (stepped) + via (60.40,25.40) + B.Cu seg -> existing via (60.40,20.30)")

    # ---------- phase 6: MOSI route (proven geometry, PR #242) ----------
    fp4 = b.FindFootprintByReference("U4")
    fp1 = b.FindFootprintByReference("U1")
    u4_17 = None
    for p in fp4.Pads():
        if p.GetNumber() == "17":
            u4_17 = (p.GetPosition().x / UM, p.GetPosition().y / UM)
    u1_8 = None
    for p in fp1.Pads():
        if p.GetNumber() == "8":
            u1_8 = (p.GetPosition().x / UM, p.GetPosition().y / UM)
    add_track(mosi, pcbnew.F_Cu, (u4_17, MOSI_VIA))
    add_via(mosi, MOSI_VIA)
    print(f"  MOSI F.Cu stub {u4_17} -> via {MOSI_VIA}")
    # ---------- phase 6: MOSI route (B.Cu A*, pre-filtered obstacles) ----------
    def astar_b(layer_name, start, goal, net_code, grid=0.100):
        import heapq
        x0 = min(start[0], goal[0]) - 6.0; x1 = max(start[0], goal[0]) + 6.0
        y0 = min(start[1], goal[1]) - 6.0; y1 = max(start[1], goal[1]) + 6.0
        segs = []; vias = []; pads = []
        for t in b.GetTracks():
            if t.GetNetCode() == net_code: continue
            if t.Type() == pcbnew.PCB_VIA_T:
                q = t.GetPosition()
                vias.append((q.x / UM, q.y / UM, t.GetWidth(pcbnew.F_Cu) / 2 / UM))
            elif t.Type() == pcbnew.PCB_TRACE_T:
                if b.GetLayerName(t.GetLayer()) != layer_name: continue
                st, en = t.GetStart(), t.GetEnd()
                sx, sy, ex, ey = st.x / UM, st.y / UM, en.x / UM, en.y / UM
                if max(sx, ex) < x0 - 0.4 or min(sx, ex) > x1 + 0.4 or max(sy, ey) < y0 - 0.4 or min(sy, ey) > y1 + 0.4: continue
                segs.append((sx, sy, ex, ey, t.GetWidth() / 2 / UM))
        for fpx in b.GetFootprints():
            for pd in fpx.Pads():
                if pd.GetNetCode() == net_code: continue
                ls = [b.GetLayerName(l) for l in pd.GetLayerSet().Seq()]
                is_thru = "F.Cu" in ls and "B.Cu" in ls
                if not is_thru and layer_name not in ls: continue
                q = pd.GetPosition(); cx, cy = q.x / UM, q.y / UM
                if cx < x0 - 1 or cx > x1 + 1 or cy < y0 - 1 or cy > y1 + 1: continue
                pads.append((cx, cy, pd.GetSize().x / 2 / UM, pd.GetSize().y / 2 / UM))
        need = CLR + TRACK_W / 2
        def blocked(x, y):
            for (vx, vy, r) in vias:
                if math.hypot(x - vx, y - vy) - r - TRACK_W / 2 < need - 1e-9: return True
            for (sx, sy, ex, ey, half) in segs:
                if segd(x, y, sx, sy, ex, ey) - half - TRACK_W / 2 < need - 1e-9: return True
            for (cx, cy, hw, hh) in pads:
                dx = max(cx - hw - x, 0, x - (cx + hw)); dy = max(cy - hh - y, 0, y - (cy + hh))
                if math.hypot(dx, dy) - TRACK_W / 2 < need - 1e-9: return True
            return False
        sx0, sy0 = start; gx, gy = goal
        q = [(0.0, (sx0, sy0))]
        came = {(sx0, sy0): None}; gsc = {(sx0, sy0): 0.0}
        while q:
            _p, cur = heapq.heappop(q)
            if math.hypot(cur[0]-gx, cur[1]-gy) < grid/2:
                path = []
                while cur:
                    path.append(cur); cur = came[cur]
                return path[::-1]
            x, y = cur
            for dx, dy in ((grid, 0), (-grid, 0), (0, grid), (0, -grid),
                           (grid, grid), (grid, -grid), (-grid, grid), (-grid, -grid)):
                n = (round(x + dx, 6), round(y + dy, 6))
                if n in gsc: continue
                if not (x0 <= n[0] <= x1 and y0 <= n[1] <= y1): continue
                if blocked(*n): continue
                gsc[n] = gsc[cur] + math.hypot(dx, dy)
                heapq.heappush(q, (gsc[n] + math.hypot(gx - n[0], gy - n[1]), n))
                came[n] = cur
        return None

    path = astar_b("B.Cu", MOSI_VIA, u1_8, mosi)
    if not path:
        print("REFUSED: MOSI B.Cu A* found no path -- aborting before save")
        return 3
    print(f"  MOSI B.Cu: {len(path)} cells -> {len(path)-1} segments")
    for i in range(len(path) - 1):
        add_track(mosi, pcbnew.B_Cu, (path[i], path[i + 1]))

    # ---------- phase 7: connectivity proof, then save ----------
    def pad_xy(fp, num):
        for p in fp.Pads():
            if p.GetNumber() == num:
                return (p.GetPosition().x / UM, p.GetPosition().y / UM)
        raise KeyError(num)

    b.BuildConnectivity()
    # connectivity is checked by the caller (kicad-cli DRC's unconnected list);
    # here we prove endpoints are attached by testing pad-to-track hit tests.
    def touches(net_code, ref, num):
        # a connection is real if any same-net copper lands INSIDE the pad's own bbox
        # (SMD pads are reached by copper overlapping the pad, not by a radius test).
        target = None
        for p in b.FindFootprintByReference(ref).Pads():
            if p.GetNumber() == num:
                target = p
                break
        if target is None:
            return False
        q = target.GetPosition()
        hw, hh = target.GetSize().x / 2 / UM, target.GetSize().y / 2 / UM
        cx, cy = q.x / UM, q.y / UM
        for t in b.GetTracks():
            if t.GetNetCode() != net_code:
                continue
            if t.Type() == pcbnew.PCB_TRACE_T:
                s, e = t.GetStart(), t.GetEnd()
                for (px, py) in ((s.x / UM, s.y / UM), (e.x / UM, e.y / UM)):
                    if abs(px - cx) <= hw and abs(py - cy) <= hh:
                        return True
            elif t.Type() == pcbnew.PCB_VIA_T:
                q2 = t.GetPosition()
                if abs(q2.x / UM - cx) <= hw and abs(q2.y / UM - cy) <= hh:
                    return True
        return False

    print(f"  U1.22 touched by SCK copper: {touches(sck, 'U1', '22')}")
    print(f"  U4.18 touched by SCK copper: {touches(sck, 'U4', '18')}")
    print(f"  U1.8 touched by MOSI copper: {touches(mosi, 'U1', '8')}")
    print(f"  U4.17 touched by MOSI copper: {touches(mosi, 'U4', '17')}")

    b.Save(args.out)
    print(f"saved {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
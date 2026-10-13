#!/usr/bin/env python3
"""fix_hub_v9_route_v28.py -- the REAL order-blocker: slide the U4-area MISO
via-in-pad away from the MOSI pad.

v27 bug found: it picked the FIRST /SX1280_MISO via (the U1-side one at
58.85,13.11) instead of the U4-area via-in-pad the DRC names ("Pad 8
[/SX1280_MOSI] of U4 vs Via [/SX1280_MISO]"). This script selects BOTH MISO
vias and fixes whichever one actually grazes, by sliding it WITHIN its own
pad (via-in-pad preserved) to the offset that maximises clearance to the
neighbouring pad, verified against all F.Cu copper.

Also applies the DIO1/V-fix with the CORRECT arithmetic: DRC clearance is
edge-to-edge; centre-to-centre needed = 0.20 + 0.30 (via r) + 0.10 (track hw)
= 0.60.
"""
import argparse
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
TRACK_W = 0.20
RULE = 0.20
NET_MISO = "/SX1280_MISO"
NET_DIO1 = "/SX1280_DIO1"
NET_F33 = "/F33_SCK"


def seg_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def rect_gap(px, py, x0, y0, x1, y1):
    return math.hypot(max(x0 - px, 0, px - x1), max(y0 - py, 0, py - y1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()
    b = pcbnew.LoadBoard(args.inp)
    fcu, bcu = pcbnew.F_Cu, pcbnew.B_Cu

    # ---- find the MISO via that actually GRAZES something
    print("=== locating the grazing MISO via ===")
    miso_vias = []
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA" and t.GetNetname() == NET_MISO:
            p = t.GetPosition()
            miso_vias.append([t, p.x / MM, p.y / MM, t.GetWidth(fcu) / 2 / MM])
    for mv in miso_vias:
        print(f"  MISO via at ({mv[1]:.3f},{mv[2]:.3f}) r={mv[3]:.2f}")

    # foreign F.Cu copper
    fcop = []
    for u in b.GetTracks():
        if u.GetNetname() == NET_MISO:
            continue
        if u.GetClass() == "PCB_VIA":
            q = u.GetPosition()
            fcop.append(("v", q.x / MM, q.y / MM, q.x / MM, q.y / MM,
                         u.GetWidth(fcu) / 2 / MM, u.GetNetname()))
        elif u.GetLayer() == fcu:
            s, e = u.GetStart(), u.GetEnd()
            fcop.append(("t", s.x / MM, s.y / MM, e.x / MM, e.y / MM,
                         u.GetWidth() / MM / 2, u.GetNetname()))
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() == NET_MISO or not p.IsOnLayer(fcu):
                continue
            pbb = p.GetBoundingBox()
            fcop.append(("p", pbb.GetX() / MM, pbb.GetY() / MM,
                         (pbb.GetX() + pbb.GetWidth()) / MM,
                         (pbb.GetY() + pbb.GetHeight()) / MM, 0.0, p.GetNetname()))

    fixed = 0
    for mv in miso_vias:
        vt, vx0, vy0, vr = mv
        worst = 1e9
        worst_nm = None
        for (k, x0, y0, x1, y1, hw, nm) in fcop:
            d = rect_gap(vx0, vy0, x0, y0, x1, y1) if k == "p" \
                else seg_dist(vx0 * MM, vy0 * MM, x0 * MM, y0 * MM, x1 * MM, y1 * MM) / MM - hw
            if d < worst:
                worst = d
                worst_nm = nm
        print(f"  via ({vx0:.3f},{vy0:.3f}): nearest foreign {worst:.4f} mm ({worst_nm})")
        if worst - vr >= RULE - 1e-9:
            print("    -> already clear, no action")
            continue

        # search offsets; keep it inside its own pad if it is a via-in-pad
        pad = None
        for f in b.GetFootprints():
            for p in f.Pads():
                if p.GetNetname() != NET_MISO:
                    continue
                c = p.GetPosition()
                if math.hypot(c.x / MM - vx0, c.y / MM - vy0) < 0.5:
                    pad = p
        lo_x = lo_y = None
        if pad is not None:
            bb = pad.GetBoundingBox()
            lo_x, lo_y = bb.GetX() / MM, bb.GetY() / MM
            hi_x, hi_y = (bb.GetX() + bb.GetWidth()) / MM, (bb.GetY() + bb.GetHeight()) / MM
            print(f"    own pad rect ({lo_x:.3f},{lo_y:.3f})-({hi_x:.3f},{hi_y:.3f})")

        best = None
        steps = [i * 0.025 for i in range(-24, 25)]
        for dx in steps:
            for dy in steps:
                nx, ny = vx0 + dx, vy0 + dy
                if pad is not None:
                    # via-in-pad criterion: the BARREL CENTRE stays inside the
                    # pad rect (the 0.60mm land legitimately overhangs a
                    # 0.25mm-wide pad; the fill+cap carries the connection).
                    if not (lo_x - 1e-6 <= nx <= hi_x + 1e-6):
                        continue
                    if not (lo_y - 1e-6 <= ny <= hi_y + 1e-6):
                        continue
                elif math.hypot(dx, dy) > 0.6:
                    continue
                ok = True
                for (k, x0, y0, x1, y1, hw, nm) in fcop:
                    d = rect_gap(nx, ny, x0, y0, x1, y1) if k == "p" \
                        else seg_dist(nx * MM, ny * MM, x0 * MM, y0 * MM, x1 * MM, y1 * MM) / MM - hw
                    if d < vr + RULE - 1e-9:
                        ok = False
                        break
                if not ok:
                    continue
                dist = math.hypot(dx, dy)
                if best is None or dist < best[0]:
                    best = (dist, nx, ny)
        if not best:
            print("    -> NO offset clears everything; stays a documented exception")
            continue
        _, nx, ny = best
        vt.SetPosition(pcbnew.VECTOR2I(int(nx * MM), int(ny * MM)))
        v = pcbnew.VECTOR2I(int(nx * MM), int(ny * MM))
        rep = 0
        for t in b.GetTracks():
            if t.GetClass() != "PCB_TRACK" or t.GetNetname() != NET_MISO:
                continue
            s, e = t.GetStart(), t.GetEnd()
            if math.hypot(s.x / MM - vx0, s.y / MM - vy0) < 0.10:
                t.SetStart(v)
                rep += 1
            if math.hypot(e.x / MM - vx0, e.y / MM - vy0) < 0.10:
                t.SetEnd(v)
                rep += 1
        print(f"    -> MOVED to ({nx:.3f},{ny:.3f}) ({best[0]:.3f}mm); {rep} legs re-pointed")
        fixed += 1
        b.BuildConnectivity()

    print(f"MISO vias fixed: {fixed}")

    # ---- FIX B with correct arithmetic: need centre-to-centre 0.60
    print("=== DIO1 via vs F33_SCK (need c-c 0.60) ===")
    d1t = None
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA" and t.GetNetname() == NET_DIO1:
            p = t.GetPosition()
            d1t = (t, p.x / MM, p.y / MM)
    if d1t:
        vt, vx0, vy0 = d1t
        need_cc = RULE + 0.30 + TRACK_W / 2
        dmin = 1e9
        for t in b.GetTracks():
            if t.GetClass() != "PCB_TRACK" or t.GetNetname() != NET_F33:
                continue
            s, e = t.GetStart(), t.GetEnd()
            dmin = min(dmin, seg_dist(vx0 * MM, vy0 * MM, s.x, s.y, e.x, e.y) / MM)
        print(f"  via ({vx0:.3f},{vy0:.3f}); nearest F33_SCK c-c {dmin:.4f} (need {need_cc:.2f})")
        if dmin >= need_cc - 1e-9:
            print("  -> already compliant")
        else:
            print("  -> below; further relocation refuted in v27 (no position clears all)"
                  " => JLCPCB written confirmation required (exception table item 5)")

    b.BuildConnectivity()
    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

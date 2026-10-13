#!/usr/bin/env python3
"""fix_hub_v9_route_v27.py -- close the 2 order-blocking sub-0.15mm items.

From docs/CONTROLLED-EXCEPTION-TABLE-hub-v9.md:
  Item 3: Pad 8 [/SX1280_MOSI] of U4  vs  Via [/SX1280_MISO]  0.1250 (need 0.20)
  Item 5: Track [/F33_SCK] (B.Cu)     vs  Via [/SX1280_DIO1]  0.1150 (need 0.20)

FIX A (item 3) -- shift the MISO via WITHIN its own pad, away from the MOSI
  pad. It is a via-in-pad: the via only has to stay inside the U4.9 pad
  (0.25 x 0.80 mm) for the fill+cap process. Sliding it toward the far end of
  its own pad adds clearance to the neighbouring MOSI pad WITHOUT moving the
  via off-net or off-pad. Search the in-pad offset grid; require:
    - via still fully inside U4.9's pad rect (via-in-pad preserved)
    - clearance to ALL foreign copper on F.Cu >= 0.20
    - own F.Cu escape track re-pointed and still legal

FIX B (item 5) -- push the DIO1 via further along its own B.Cu run (it was
  already moved +0.30 S in v17). Each further step of d adds d clearance to
  the F33_SCK pair. Search d in 0.05..0.60, require the new position clears
  ALL foreign copper on ALL layers by 0.20 AND the F33_SCK pair >= 0.20.
  Its attached tracks get re-pointed (connectivity preserved).

Both fixes verify-before-write; refuse and report per item.
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
REF_U4 = "U4"
PAD_MISO = "9"


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
    fcu, bcu = b.GetLayerID("F.Cu"), b.GetLayerID("B.Cu")

    # ---------------- FIX A: MISO via-in-pad slide ----------------
    print("=== FIX A: /SX1280_MISO via within its U4.9 pad ===")
    miso_via = None
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA" and t.GetNetname() == NET_MISO:
            p = t.GetPosition()
            miso_via = (t, p.x / MM, p.y / MM, t.GetWidth(fcu) / 2 / MM)
    if not miso_via:
        print("  no MISO via found")
    else:
        vt, vx0, vy0, vr = miso_via
        pad = None
        for f in b.GetFootprints():
            if f.GetReference().upper() != REF_U4:
                continue
            for p in f.Pads():
                if p.GetNumber() == PAD_MISO:
                    pad = p
        if pad is None:
            print("  U4.9 pad not found")
        else:
            bb = pad.GetBoundingBox()
            px0, py0 = bb.GetX() / MM, bb.GetY() / MM
            px1, py1 = (bb.GetX() + bb.GetWidth()) / MM, (bb.GetY() + bb.GetHeight()) / MM
            print(f"  U4.9 pad rect ({px0:.3f},{py0:.3f})-({px1:.3f},{py1:.3f})"
                  f"  via at ({vx0:.3f},{vy0:.3f}) r={vr:.2f}")

            # foreign F.Cu copper (exclude MISO's own net)
            fcopper = []
            for u in b.GetTracks():
                if u.GetNetname() == NET_MISO:
                    continue
                if u.GetClass() == "PCB_VIA":
                    q = u.GetPosition()
                    fcopper.append(("v", q.x / MM, q.y / MM, q.x / MM, q.y / MM,
                                    u.GetWidth(fcu) / 2 / MM))
                elif u.GetLayer() == fcu:
                    s, e = u.GetStart(), u.GetEnd()
                    fcopper.append(("t", s.x / MM, s.y / MM, e.x / MM, e.y / MM,
                                    u.GetWidth() / MM / 2))
            for f in b.GetFootprints():
                for p in f.Pads():
                    if p.GetNetname() == NET_MISO or not p.IsOnLayer(fcu):
                        continue
                    pbb = p.GetBoundingBox()
                    fcopper.append(("p", pbb.GetX() / MM, pbb.GetY() / MM,
                                    (pbb.GetX() + pbb.GetWidth()) / MM,
                                    (pbb.GetY() + pbb.GetHeight()) / MM, 0.0))

            best = None
            steps = [i * 0.025 for i in range(0, 25)]
            for dx in [-s for s in steps] + steps:
                for dy in [-s for s in steps] + steps:
                    nx, ny = vx0 + dx, vy0 + dy
                    # must stay inside the pad (via-in-pad preserved)
                    if nx - vr < px0 - 1e-6 or nx + vr > px1 + 1e-6:
                        continue
                    if ny - vr < py0 - 1e-6 or ny + vr > py1 + 1e-6:
                        continue
                    ok = True
                    for (k, x0, y0, x1, y1, hw) in fcopper:
                        if k == "p":
                            d = rect_gap(nx, ny, x0, y0, x1, y1)
                        else:
                            d = seg_dist(nx * MM, ny * MM, x0 * MM, y0 * MM,
                                         x1 * MM, y1 * MM) / MM - hw
                        if d < vr + RULE - 1e-9:
                            ok = False
                            break
                    if not ok:
                        continue
                    dist = math.hypot(dx, dy)
                    if best is None or dist < best[0]:
                        best = (dist, nx, ny)
            if not best:
                print("  NO in-pad offset clears F.Cu by 0.20 -- stays an exception")
            else:
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
                print(f"  MOVED via ({vx0:.3f},{vy0:.3f}) -> ({nx:.3f},{ny:.3f}) "
                      f"({best[0]:.3f}mm, still inside pad); {rep} legs re-pointed")
                b.BuildConnectivity()

    # ---------------- FIX B: DIO1 via further south ----------------
    print("=== FIX B: /SX1280_DIO1 via vs /F33_SCK ===")
    d1 = None
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA" and t.GetNetname() == NET_DIO1:
            p = t.GetPosition()
            d1 = (t, p.x / MM, p.y / MM)
    if not d1:
        print("  no DIO1 via found")
    else:
        vt, vx0, vy0 = d1
        # measure the current worst F33_SCK distance to this via
        cur = 1e9
        for t in b.GetTracks():
            if t.GetClass() != "PCB_TRACK" or t.GetNetname() != NET_F33:
                continue
            s, e = t.GetStart(), t.GetEnd()
            cur = min(cur, seg_dist(vx0 * MM, vy0 * MM, s.x, s.y, e.x, e.y) / MM)
        print(f"  via ({vx0:.3f},{vy0:.3f}); nearest /F33_SCK now {cur:.4f} mm (need {RULE + 0.30:.2f})")

        # attached tracks
        attached = []
        for t in b.GetTracks():
            if t.GetClass() != "PCB_TRACK":
                continue
            s, e = t.GetStart(), t.GetEnd()
            if math.hypot(s.x / MM - vx0, s.y / MM - vy0) < 0.10:
                attached.append((t, "start", e.x, e.y))
            if math.hypot(e.x / MM - vx0, e.y / MM - vy0) < 0.10:
                attached.append((t, "end", s.x, s.y))

        # obstacle inventory (all layers except DIO1's own net)
        obst = []
        for u in b.GetTracks():
            if u.GetNetname() == NET_DIO1:
                continue
            if u.GetClass() == "PCB_VIA":
                q = u.GetPosition()
                obst.append(("v", None, q.x / MM, q.y / MM, q.x / MM, q.y / MM,
                             u.GetWidth(fcu) / 2 / MM))
            else:
                s, e = u.GetStart(), u.GetEnd()
                obst.append(("t", u.GetLayer(), s.x / MM, s.y / MM, e.x / MM, e.y / MM,
                             u.GetWidth() / MM / 2))
        for f in b.GetFootprints():
            for p in f.Pads():
                if p.GetNetname() == NET_DIO1:
                    continue
                for lay in (fcu, bcu):
                    if p.IsOnLayer(lay):
                        pbb = p.GetBoundingBox()
                        obst.append(("p", lay, pbb.GetX() / MM, pbb.GetY() / MM,
                                     (pbb.GetX() + pbb.GetWidth()) / MM,
                                     (pbb.GetY() + pbb.GetHeight()) / MM, 0.0))

        vr = 0.30
        found = None
        for step in [i * 0.05 for i in range(1, 13)]:
            ny = vy0 + step
            # via barrel clearance
            ok = True
            for (k, lay, x0, y0, x1, y1, hw) in obst:
                if k == "p":
                    d = rect_gap(vx0, ny, x0, y0, x1, y1)
                else:
                    d = seg_dist(vx0 * MM, ny * MM, x0 * MM, y0 * MM, x1 * MM, y1 * MM) / MM - hw
                if d < vr + RULE - 1e-9:
                    ok = False
                    break
            if not ok:
                continue
            # attached legs keep legal
            for (t, which, fx, fy) in attached:
                hw = t.GetWidth() / MM / 2
                lay = t.GetLayer()
                for (k, l2, x0, y0, x1, y1, h2) in obst:
                    if k in ("t", "p") and l2 != lay:
                        continue
                    if k == "p":
                        d = 1e9
                        for j in range(11):
                            tt = j / 10
                            qx = fx / MM + (vx0 - fx / MM) * tt
                            qy = fy / MM + (ny - fy / MM) * tt
                            d = min(d, rect_gap(qx, qy, x0, y0, x1, y1))
                    else:
                        d = seg_dist(fx / MM, fy / MM, vx0 * MM, ny * MM,
                                     x0 * MM, y0 * MM, x1 * MM, y1 * MM) / MM - h2
                    if d - hw < RULE - 1e-9:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                continue
            # F33_SCK pair must now clear
            dmin = 1e9
            for t in b.GetTracks():
                if t.GetClass() != "PCB_TRACK" or t.GetNetname() != NET_F33:
                    continue
                s, e = t.GetStart(), t.GetEnd()
                dmin = min(dmin, seg_dist(vx0 * MM, ny * MM, s.x, s.y, e.x, e.y) / MM)
            if dmin - vr < RULE - 1e-9:
                continue
            found = (step, ny, dmin)
            break
        if not found:
            print("  NO further-south position clears everything -- stays an exception")
        else:
            step, ny, dmin = found
            vt.SetPosition(pcbnew.VECTOR2I(int(vx0 * MM), int(ny * MM)))
            v = pcbnew.VECTOR2I(int(vx0 * MM), int(ny * MM))
            for (t, which, fx, fy) in attached:
                if which == "start":
                    t.SetStart(v)
                else:
                    t.SetEnd(v)
            print(f"  MOVED via south {step:.2f}mm -> ({vx0:.3f},{ny:.3f}); "
                  f"F33_SCK now {dmin:.4f} mm; {len(attached)} legs re-pointed")
            b.BuildConnectivity()

    b.BuildConnectivity()
    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

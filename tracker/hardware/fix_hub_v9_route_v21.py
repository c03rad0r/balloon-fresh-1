#!/usr/bin/env python3
"""fix_hub_v9_route_v21.py -- clear the 6 actionable grazes (2 new I2C + 4 PRE).

MEASURED remaining (v17):
  0.1648 x2  /F33_SCK (mine) vs /I2C_SCL  -- the A* anchor-connector segments
             (A_PT/B_PT -> first grid cell) bypassed the obstacle check; that
             is the bug, not the path itself.
  0.1416     +3V3 via vs /SX1280_SCK  (PRE)
  0.0938     +3V3 via vs /SX1280_RESET_N (PRE)
  0.0450     /ANT1_433_TX via vs /SCAP_MID (PRE)
  0.0143     +3V3 via vs /SCAP_MID (PRE)

Method (proven family: move the intruder, verify before write):
  For each (via, foreign-track) pair, find the track vertex nearest the via and
  push it perpendicular away until the pair clears 0.20 edge-to-edge AND every
  other foreign obstacle on that layer still clears 0.20. Refuse if no spot.
"""
import argparse
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
TRACK_W = 0.20
RULE = 0.20

# (track_net, [via positions to clear]) -- the 6 actionable pairs
JOBS = [
    ("/F33_SCK", [(47.389, 8.888), (52.061, 7.052)]),   # I2C_SCL vias + SCAP_MID via
    ("/SX1280_SCK", None),        # any +3V3 via it grazes
    ("/SX1280_RESET_N", None),
    ("/SCAP_MID", None),
]


def seg_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def seg_seg(ax, ay, bx, by, cx, cy, dx, dy):
    return min(seg_dist(ax, ay, cx, cy, dx, dy), seg_dist(bx, by, cx, cy, dx, dy),
               seg_dist(cx, cy, ax, ay, bx, by), seg_dist(dx, dy, ax, ay, bx, by))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()
    b = pcbnew.LoadBoard(args.inp)

    # ---- collect all copper per layer
    def obstacles(exclude_net=None):
        vias, trks, pads = [], [], []
        for t in b.GetTracks():
            if t.GetNetname() == exclude_net:
                continue
            if t.GetClass() == "PCB_VIA":
                p = t.GetPosition()
                r = t.GetWidth(pcbnew.F_Cu) / 2 / MM
                vias.append((p.x / MM, p.y / MM, r, t.GetNetname()))
            else:
                s, e = t.GetStart(), t.GetEnd()
                trks.append((t.GetLayer(), s.x / MM, s.y / MM, e.x / MM, e.y / MM,
                             t.GetWidth() / MM / 2, t.GetNetname()))
        for f in b.GetFootprints():
            for p in f.Pads():
                if p.GetNetname() == exclude_net:
                    continue
                for lay in (b.GetLayerID("F.Cu"), b.GetLayerID("B.Cu")):
                    if p.IsOnLayer(lay):
                        bb = p.GetBoundingBox()
                        pads.append((lay, bb.GetX() / MM, bb.GetY() / MM,
                                     (bb.GetX() + bb.GetWidth()) / MM,
                                     (bb.GetY() + bb.GetHeight()) / MM, p.GetNetname()))
        return vias, trks, pads

    fixed_total = 0
    for (net, targets) in JOBS:
        # find the segments of this net that actually graze something
        grazes = []
        for t in b.GetTracks():
            if t.GetClass() != "PCB_TRACK" or t.GetNetname() != net:
                continue
            lay = t.GetLayer()
            s, e = t.GetStart(), t.GetEnd()
            sx, sy, ex, ey = s.x / MM, s.y / MM, e.x / MM, e.y / MM
            hw = t.GetWidth() / MM / 2
            # vs every foreign via on any layer (through vias)
            for u in b.GetTracks():
                if u.GetClass() != "PCB_VIA" or u.GetNetname() == net:
                    continue
                p = u.GetPosition()
                d = seg_dist(p.x / MM * MM, p.y / MM * MM, sx * MM, sy * MM, ex * MM, ey * MM) / MM
                gr = (u.GetWidth(pcbnew.F_Cu) / 2 / MM) + hw + RULE
                if d < gr - 1e-9:
                    grazes.append((t, (p.x / MM, p.y / MM, u.GetWidth(pcbnew.F_Cu) / 2 / MM), d, gr, "via"))
            # vs foreign tracks on the SAME layer
            for u in b.GetTracks():
                if u.GetClass() != "PCB_TRACK" or u.GetNetname() == net or u.GetLayer() != lay:
                    continue
                us, ue = u.GetStart(), u.GetEnd()
                d = seg_seg(sx * MM, sy * MM, ex * MM, ey * MM,
                            us.x, us.y, ue.x, ue.y) / MM
                gr = hw + u.GetWidth() / MM / 2 + RULE
                if d < gr - 1e-9:
                    grazes.append((t, None, d, gr, "track"))
        if not grazes:
            print(f"{net}: no grazes found")
            continue
        for (t, via, d, gr, kind) in grazes[:4]:
            s, e = t.GetStart(), t.GetEnd()
            sx, sy, ex, ey = s.x / MM, s.y / MM, e.x / MM, e.y / MM
            lay = t.GetLayer()
            hw = t.GetWidth() / MM / 2
            need = gr - d + 0.05  # push needed + margin
            vias, trks, pads = obstacles(exclude_net=net)

            def clear_all(ax_, ay_):
                for (vx, vy, r, nm) in vias:
                    if seg_dist(vx * MM, vy * MM, ax_ * MM, ay_ * MM, ex * MM, ey * MM) / MM < r + hw + RULE - 1e-9:
                        return False
                    if seg_dist(vx * MM, vy * MM, sx * MM, sy * MM, ax_ * MM, ay_ * MM) / MM < r + hw + RULE - 1e-9:
                        return False
                for (l2, tx0, ty0, tx1, ty1, uhw, nm) in trks:
                    if l2 != lay:
                        continue
                    if seg_seg(ax_ * MM, ay_ * MM, ex * MM, ey * MM, tx0 * MM, ty0 * MM, tx1 * MM, ty1 * MM) / MM < hw + uhw + RULE - 1e-9:
                        return False
                    if seg_seg(sx * MM, sy * MM, ax_ * MM, ay_ * MM, tx0 * MM, ty0 * MM, tx1 * MM, ty1 * MM) / MM < hw + uhw + RULE - 1e-9:
                        return False
                for (l2, px0, py0, px1, py1, nm) in pads:
                    if l2 != lay:
                        continue
                    for k in range(9):
                        tt = k / 8
                        qx = sx + (ax_ - sx) * tt
                        qy = sy + (ay_ - sy) * tt
                        ddx = max(px0 - qx, 0, qx - px1)
                        ddy = max(py0 - qy, 0, qy - py1)
                        if math.hypot(ddx, ddy) < hw + RULE - 1e-9:
                            return False
                return True

            # try moving the endpoint NEAREST the obstacle
            if via:
                dn_s = math.hypot(sx - via[0], sy - via[1])
                dn_e = math.hypot(ex - via[0], ey - via[1])
                move_pt, other = ((sx, sy), (ex, ey)) if dn_s <= dn_e else ((ex, ey), (sx, sy))
            else:
                move_pt, other = (sx, sy), (ex, ey)
            vx_, vy_ = move_pt
            # perpendicular direction away from the obstacle
            if via:
                ux, uy = vx_ - via[0], vy_ - via[1]
            else:
                # away from the other endpoint (lengthen)
                ux, uy = other[0] - vx_, other[1] - vy_
            n = math.hypot(ux, uy) or 1.0
            ux, uy = ux / n, uy / n
            placed = False
            for dist in [0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]:
                for sgn in (1, -1):
                    nx_ = vx_ + sgn * ux * dist
                    ny_ = vy_ + sgn * uy * dist
                    if clear_all(nx_, ny_):
                        if move_pt == (sx, sy):
                            t.SetStart(pcbnew.VECTOR2I(int(nx_ * MM), int(ny_ * MM)))
                        else:
                            t.SetEnd(pcbnew.VECTOR2I(int(nx_ * MM), int(ny_ * MM)))
                        placed = True
                        fixed_total += 1
                        print(f"  {net}: {kind} graze {d:.4f}-> moved vertex by {dist:.2f} (sgn {sgn:+d})")
                        break
                if placed:
                    break
            if not placed:
                print(f"  {net}: {kind} graze {d:.4f} -- NO verified move, left")
        b.BuildConnectivity()

    print(f"total vertex moves: {fixed_total}")
    b.BuildConnectivity()
    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

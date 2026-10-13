#!/usr/bin/env python3
"""fix_hub_v9_route_v22.py -- clear the remaining grazes by MOVING THE INTRUDER
(consultant's method; v21 vertex-push failed on 3 of 4 PRE grazes).

v19 board of record grazes (10 total, 6 actionable):
  0.1648 x2  /F33_SCK (mine) vs /I2C_SCL  -- approach: move the I2C_SCL B.Cu
             vertices away (I2C is a slow bus, unlimited detour tolerance)
  0.1416     +3V3 via vs /SX1280_SCK   (PRE): move the SCK B.Cu vertex
  0.0938     +3V3 via vs /SX1280_RESET_N (PRE): move the RESET_N vertex
  0.0450     /ANT1_433_TX via vs /SCAP_MID (PRE): move the SCAP_MID vertex
  0.0143     +3V3 via vs /SCAP_MID    (PRE): same SCAP_MID vertex most likely
  5 preserved: via-in-pad neighbours (documentation, not geometry)

Method: for each (anchoring foreign VIA, grazed track), push the track's
NEAREST VERTEX perpendicular to the via by escalating distance until that
pair AND all other foreign copper on the layer clear 0.20. Refuse otherwise.
"""
import argparse
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
TRACK_W = 0.20
RULE = 0.20

# grazed track net -> list of anchoring foreign via coords (from the DRC text)
JOBS = [
    ("/I2C_SCL", []),        # vs my F33_SCK: has TWO grazes (0.1648 x2)
    ("/SX1280_SCK", []),     # vs a +3V3 via
    ("/SX1280_RESET_N", []), # vs a +3V3 via
    ("/SCAP_MID", []),       # vs /ANT1_433_TX via AND a +3V3 via
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

    moves = 0
    for (net, _) in JOBS:
        # --- find every (segment-of-net, foreign-via) graze
        grazes = []
        for t in b.GetTracks():
            if t.GetClass() != "PCB_TRACK" or t.GetNetname() != net:
                continue
            s, e = t.GetStart(), t.GetEnd()
            sx, sy, ex, ey = s.x / MM, s.y / MM, e.x / MM, e.y / MM
            hw = t.GetWidth() / MM / 2
            for u in b.GetTracks():
                if u.GetClass() != "PCB_VIA" or u.GetNetname() == net:
                    continue
                p = u.GetPosition()
                if not (min(sx, ex) - 2 <= p.x / MM <= max(sx, ex) + 2
                        and min(sy, ey) - 2 <= p.y / MM <= max(sy, ey) + 2):
                    continue
                d = seg_dist(p.x / MM * MM, p.y / MM * MM, sx * MM, sy * MM, ex * MM, ey * MM) / MM
                gr = (u.GetWidth(pcbnew.F_Cu) / 2 / MM) + hw + RULE
                if d < gr - 1e-9:
                    grazes.append((t, (p.x / MM, p.y / MM, u.GetWidth(pcbnew.F_Cu) / 2 / MM), d, gr))
        if not grazes:
            print(f"{net}: no via grazes")
            continue
        for (t, via, d, gr) in grazes[:3]:
            lay = t.GetLayer()
            s, e = t.GetStart(), t.GetEnd()
            sx, sy, ex, ey = s.x / MM, s.y / MM, e.x / MM, e.y / MM
            hw = t.GetWidth() / MM / 2
            # villa: the vertex nearer the via is the one to move
            dn_s = math.hypot(sx - via[0], sy - via[1])
            dn_e = math.hypot(ex - via[0], ey - via[1])
            is_start = dn_s <= dn_e
            mx, my = (sx, sy) if is_start else (ex, ey)
            ox, oy = (ex, ey) if is_start else (sx, sy)
            ux, uy = mx - via[0], my - via[1]
            n = math.hypot(ux, uy) or 1.0
            ux, uy = ux / n, uy / n

            i2c_ok = None
            for dist in (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60, 0.80):
                for sgn in (1, -1):
                    nx_, ny_ = mx + sgn * ux * dist, my + sgn * uy * dist
                    # verify: new segment clears THIS via + all foreign copper on lay
                    if seg_dist(via[0] * MM, via[1] * MM, nx_ * MM, ny_ * MM, ox * MM, oy * MM) / MM < via[2] + hw + RULE - 1e-9:
                        continue
                    bad = False
                    for u in b.GetTracks():
                        if u.GetClass() != "PCB_TRACK" or u.GetNetname() == net or u.GetLayer() != lay:
                            continue
                        us, ue = u.GetStart(), u.GetEnd()
                        if seg_seg(nx_ * MM, ny_ * MM, ox * MM, oy * MM, us.x, us.y, ue.x, ue.y) / MM < hw + u.GetWidth() / MM / 2 + RULE - 1e-9:
                            bad = True
                            break
                    if bad:
                        continue
                    for u in b.GetTracks():
                        if u.GetClass() != "PCB_VIA" or u.GetNetname() == net:
                            continue
                        p = u.GetPosition()
                        if seg_dist(p.x / MM * MM, p.y / MM * MM, nx_ * MM, ny_ * MM, ox * MM, oy * MM) / MM < (u.GetWidth(pcbnew.F_Cu) / 2 / MM) + hw + RULE - 1e-9:
                            bad = True
                            break
                    if bad:
                        continue
                    i2c_ok = (nx_, ny_, dist, sgn)
                    break
                if i2c_ok:
                    break
            if i2c_ok:
                nx_, ny_, dist, sgn = i2c_ok
                if is_start:
                    t.SetStart(pcbnew.VECTOR2I(int(nx_ * MM), int(ny_ * MM)))
                else:
                    t.SetEnd(pcbnew.VECTOR2I(int(nx_ * MM), int(ny_ * MM)))
                moves += 1
                print(f"  {net}: graze {d:.4f} -> moved vertex {dist:.2f}mm (sgn {sgn:+d})")
            else:
                print(f"  {net}: graze {d:.4f} -- NO verified move (dense locality)")
        b.BuildConnectivity()

    print(f"total moves: {moves}")
    b.BuildConnectivity()
    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

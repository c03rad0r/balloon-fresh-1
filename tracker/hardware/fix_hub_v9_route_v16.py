#!/usr/bin/env python3
"""fix_hub_v9_route_v16.py -- final polish: vias to 0.50/0.20 + fine-grid bulge.

v15 state: hole_clearance 0, via_diameter 2 (0.45 < board min 0.50). Corridor
slack now: 1.262 - 0.60 (DIO1 foreign) - 0.55 (my 0.50 dia keep) = 0.112mm.
The v15 apex grid (0.35 min offset) was too coarse; v16 searches perpendicular
offsets 0.15..0.90 at 0.025mm steps, splits 0.40..0.75 at 0.025 -- fine
enough for the 0.112mm slack channel.
"""
import argparse
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
TRACK_W = 0.20
RULE = 0.20
NET = "/F33_SCK"
A_PT = (51.498, 5.557)
B_PT = (48.989, 8.066)
MY_BARRELS = {(50.00, 7.20), (49.00, 7.20)}
VIA_D, VIA_DRILL = 0.50, 0.20


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
    bcu = b.GetLayerID("B.Cu")

    # 1. vias 0.45 -> 0.50 (board min), drill stays 0.20
    fixed = 0
    for t in b.GetTracks():
        if t.GetClass() != "PCB_VIA":
            continue
        p = t.GetPosition()
        if (round(p.x / MM, 2), round(p.y / MM, 2)) in MY_BARRELS:
            t.SetWidth(int(VIA_D * MM))
            t.SetDrill(int(VIA_DRILL * MM))
            fixed += 1
    print(f"1. my in-pad vias -> 0.50/0.20: {fixed}")

    # 2. fine-grid bulge on the restored F33_SCK line
    vias, trks, pads = [], [], []
    for t in b.GetTracks():
        if t.GetNetname() == NET:
            continue
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            r = VIA_D / 2 if (round(p.x / MM, 2), round(p.y / MM, 2)) in MY_BARRELS else 0.30
            vias.append((p.x / MM, p.y / MM, r))
        elif t.GetLayer() == bcu:
            s, e = t.GetStart(), t.GetEnd()
            trks.append((s.x / MM, s.y / MM, e.x / MM, e.y / MM, t.GetWidth() / MM / 2))
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() != NET and p.IsOnLayer(bcu):
                bb = p.GetBoundingBox()
                pads.append((bb.GetX() / MM, bb.GetY() / MM,
                             (bb.GetX() + bb.GetWidth()) / MM,
                             (bb.GetY() + bb.GetHeight()) / MM))

    def legs_ok(ax_, ay_):
        for (lx0, ly0, lx1, ly1) in ((A_PT[0], A_PT[1], ax_, ay_),
                                     (ax_, ay_, B_PT[0], B_PT[1])):
            for (vx, vy, r) in vias:
                d = seg_dist(vx * MM, vy * MM, lx0 * MM, ly0 * MM, lx1 * MM, ly1 * MM) / MM - r
                if d < TRACK_W / 2 + RULE - 1e-9:
                    return False
            for (tx0, ty0, tx1, ty1, hw) in trks:
                d = seg_seg(lx0 * MM, ly0 * MM, lx1 * MM, ly1 * MM,
                            tx0 * MM, ty0 * MM, tx1 * MM, ty1 * MM) / MM - hw
                if d < TRACK_W / 2 + RULE - 1e-9:
                    return False
            for (x0, y0, x1, y1) in pads:
                for k in range(11):
                    tt = k / 10
                    px = lx0 + (lx1 - lx0) * tt
                    py = ly0 + (ly1 - ly0) * tt
                    ddx = max(x0 - px, 0, px - x1)
                    ddy = max(y0 - py, 0, py - y1)
                    if math.hypot(ddx, ddy) < TRACK_W / 2 + RULE - 1e-9:
                        return False
        for (vx, vy, r) in vias:
            if math.hypot(ax_ - vx, ay_ - vy) - r < TRACK_W / 2 + RULE - 1e-9:
                return False
        return True

    dxl, dyl = B_PT[0] - A_PT[0], B_PT[1] - A_PT[1]
    L = math.hypot(dxl, dyl)
    px_, py_ = -dyl / L, dxl / L
    found = None
    ts_vals = [round(0.40 + i * 0.025, 3) for i in range(15)]
    ds_vals = [round(0.15 + i * 0.025, 3) for i in range(31)]
    for t_split in ts_vals:
        sx = A_PT[0] + dxl * t_split
        sy = A_PT[1] + dyl * t_split
        for dist in ds_vals:
            for sgn in (1, -1):
                ax_ = sx + sgn * px_ * dist
                ay_ = sy + sgn * py_ * dist
                if legs_ok(ax_, ay_):
                    cost = dist + abs(t_split - 0.625)
                    if found is None or cost < found[0]:
                        found = (cost, ax_, ay_, t_split, sgn, dist)
    if not found:
        print("2. no verified bulge at fine grid -- via fix kept, line restored straight? NO -- keeping v15 dogleg")
        b.Save(args.out)
        return 2
    _, nax, nay, ts, sg, ds = found
    print(f"2. bulge: t={ts:.3f} dir={sg:+d} dist={ds:.3f} apex ({nax:.3f},{nay:.3f})")

    victims = []
    for t in b.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetLayer() != bcu or t.GetNetname() != NET:
            continue
        s, e = t.GetStart(), t.GetEnd()
        midx, midy = (s.x + e.x) / 2 / MM, (s.y + e.y) / 2 / MM
        if 47.0 <= midx <= 53.5 and 4.0 <= midy <= 9.5:
            victims.append(t)
    for t in victims:
        b.Remove(t)
    b.BuildConnectivity()
    netcode = None
    for code, ni in b.GetNetInfo().NetsByNetcode().items():
        if ni.GetNetname() == NET:
            netcode = code
    for (x0, y0, x1, y1) in ((A_PT[0], A_PT[1], nax, nay), (nax, nay, B_PT[0], B_PT[1])):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(int(x0 * MM), int(y0 * MM)))
        t.SetEnd(pcbnew.VECTOR2I(int(x1 * MM), int(y1 * MM)))
        t.SetWidth(int(TRACK_W * MM))
        t.SetLayer(bcu)
        t.SetNetCode(netcode)
        b.Add(t)
    b.BuildConnectivity()
    b.Save(args.out)
    print("3. written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

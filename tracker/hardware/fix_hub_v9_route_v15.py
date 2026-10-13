#!/usr/bin/env python3
"""fix_hub_v9_route_v15.py -- shrink MY 2 in-pad vias + bulge with 0.525 keeps.

Measured corridor (v14 probe): original F33_SCK line passes DIO1 via 0.602
(left side) and MISO barrel 0.605 (right side) -- OPPOSITE sides, corridor
1.262mm wide vs 0.60+0.60 keeps = ZERO slack; my DIO2 barrel sits 0.103 off
the line. DIO1 is FOREIGN (keep 0.60 fixed), but DIO2/MISO barrels are MY
in-pad vias: resizing 0.60/0.25 -> 0.45/0.20 (JLCPCB min via) drops their
keeps to 0.525 (0.225+0.1+0.2) and opens ~0.14mm slack for a bulge.

Also fixes the 5 'inherent' hole_clearance/pad grazes partially: drill 0.25
-> 0.20 adds 0.025/side.
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
MY_BARRELS = {(50.00, 7.20): "/SX1280_DIO2", (49.00, 7.20): "/SX1280_MISO"}
SMALL_D, SMALL_DRILL = 0.45, 0.20
KEEP_SMALL = SMALL_D / 2 + TRACK_W / 2 + RULE   # 0.525
KEEP_BIG = 0.30 + TRACK_W / 2 + RULE            # 0.60


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

    # --- 1. shrink MY in-pad vias (readback verified)
    shrunk = 0
    for t in b.GetTracks():
        if t.GetClass() != "PCB_VIA":
            continue
        p = t.GetPosition()
        key = (round(p.x / MM, 2), round(p.y / MM, 2))
        if key in MY_BARRELS and t.GetNetname() == MY_BARRELS[key]:
            t.SetWidth(int(SMALL_D * MM))
            t.SetDrill(int(SMALL_DRILL * MM))
            shrunk += 1
    ok = all(
        abs(t.GetWidth(pcbnew.F_Cu) / MM - SMALL_D) < 0.01
        and abs(t.GetDrillValue() / MM - SMALL_DRILL) < 0.01
        for t in b.GetTracks()
        if t.GetClass() == "PCB_VIA"
        and (round(t.GetPosition().x / MM, 2), round(t.GetPosition().y / MM, 2)) in MY_BARRELS
        and t.GetNetname() == MY_BARRELS.get((round(t.GetPosition().x / MM, 2), round(t.GetPosition().y / MM, 2)))
    )
    print(f"1. in-pad vias shrunk to 0.45/0.20: {shrunk}; readback OK: {ok}")
    if not ok:
        print("   FATAL resize failed -- abort")
        b.Save(args.out)
        return 1

    # --- 2. bulge search with per-via keeps (mine 0.525, foreign 0.60)
    vias, trks, pads = [], [], []
    for t in b.GetTracks():
        if t.GetNetname() == NET:
            continue
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            key = (round(p.x / MM, 2), round(p.y / MM, 2))
            r = SMALL_D / 2 if key in MY_BARRELS else 0.30
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
    for t_split in (0.675, 0.65, 0.625, 0.60, 0.575, 0.55, 0.70, 0.50, 0.45, 0.40):
        sx = A_PT[0] + dxl * t_split
        sy = A_PT[1] + dyl * t_split
        for dist in (0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.80, 0.90):
            for sgn in (1, -1):
                ax_ = sx + sgn * px_ * dist
                ay_ = sy + sgn * py_ * dist
                if legs_ok(ax_, ay_):
                    cost = dist + abs(t_split - 0.625)
                    if found is None or cost < found[0]:
                        found = (cost, ax_, ay_, t_split, sgn, dist)
    if not found:
        print("2. no verified bulge even with 0.525 keeps -- board unchanged (resize kept)")
        b.Save(args.out)
        return 2
    _, nax, nay, ts, sg, ds = found
    print(f"2. bulge: split t={ts:.3f} dir={sg:+d} dist={ds:.2f} apex ({nax:.3f},{nay:.3f})")

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
    print("3. written: restored line + bulge, small in-pad vias")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

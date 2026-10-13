#!/usr/bin/env python3
"""fix_hub_v9_route_v14.py -- restore original F33_SCK + single verified bulge.

ARCHAEOLOGY (v8-v13 refuted; see aae8b082): the ORIGINAL straight segment
(51.50,5.56)-(48.99,8.07) was LEGAL (absent from the fm5-baseline DRC; edge
gap to the DIO1 via ~0.198-0.248mm >= 0.20 rule). My v2 U4-barrel dogleg
landed 0.0012mm from the DIO1 via. The corridor at keeps 0.60/0.40 is
fragmented (10 free cells, isolated anchor pockets) -- full re-route is
impossible; a two-segment bulge on the RESTORED line only needs the apex
neighbourhood free.

Plan: delete my v2 doglegs in the box, restore the straight A->B, split at
t in {0.55..0.70}, apex = perpendicular offset (both sides) 0.45..1.20mm,
verified vs ALL foreign B.Cu copper (via keep 0.60 centre, track 0.40
centre, pad 0.30 edge). Box-restricted (v8 bug: apex search picked a vertex
at x=59.6, a different F33_SCK run outside this box).
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
BARREL = (50.00, 7.20)          # my DIO2 U4 via-in-pad barrel
BOX = (47.0, 4.5, 53.0, 9.5)


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

    # foreign B.Cu obstacles
    vias, trks, pads = [], [], []
    for t in b.GetTracks():
        if t.GetNetname() == NET:
            continue
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            vias.append((p.x / MM, p.y / MM, t.GetWidth(pcbnew.F_Cu) / 2 / MM))
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
        """Both legs A->apex and apex->B clear of ALL foreign B.Cu copper."""
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
        # apex cell itself clear of vias
        for (vx, vy, r) in vias:
            if math.hypot(ax_ - vx, ay_ - vy) - r < TRACK_W / 2 + RULE:
                return False
        return True

    # apex search: split points along the restored line near the barrel,
    # perpendicular offsets both directions
    dxl, dyl = B_PT[0] - A_PT[0], B_PT[1] - A_PT[1]
    L = math.hypot(dxl, dyl)
    ux, uy = dxl / L, dyl / L           # along
    px_, py_ = -uy, ux                   # perpendicular
    found = None
    for t_split in (0.675, 0.65, 0.625, 0.60, 0.575, 0.55, 0.70, 0.725):
        sx = A_PT[0] + dxl * t_split
        sy = A_PT[1] + dyl * t_split
        for dist in (0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.80, 0.90, 1.00, 1.10, 1.20):
            for sgn in (1, -1):
                ax_ = sx + sgn * px_ * dist
                ay_ = sy + sgn * py_ * dist
                # must clear MY barrel too (that's the point of the bulge)
                d_bar = seg_dist(BARREL[0] * MM, BARREL[1] * MM,
                                 sx * MM, sy * MM, ax_ * MM, ay_ * MM) / MM
                # approximate: barrel clearance checked via legs_ok (it's in vias)
                if legs_ok(ax_, ay_):
                    # extra: apex-side leg must clear the barrel by keep
                    d_leg = min(
                        seg_dist(BARREL[0] * MM, BARREL[1] * MM, A_PT[0] * MM, A_PT[1] * MM, ax_ * MM, ay_ * MM),
                        seg_dist(BARREL[0] * MM, BARREL[1] * MM, ax_ * MM, ay_ * MM, B_PT[0] * MM, B_PT[1] * MM),
                    ) / MM
                    if d_leg - 0.30 >= 0.60 - 1e-9:   # barrel centre-dist keep
                        cost = dist + abs(t_split - 0.625)
                        if found is None or cost < found[0]:
                            found = (cost, ax_, ay_, t_split, sgn, dist)
    if not found:
        print("no verified bulge -- board unchanged")
        b.Save(args.out)
        return 1
    _, nax, nay, ts, sg, ds = found
    print(f"bulge: split t={ts:.3f} dir={sg:+d} dist={ds:.2f} -> apex ({nax:.3f},{nay:.3f})")

    # delete my old doglegs in the box (collect-then-remove)
    victims = []
    for t in b.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetLayer() != bcu or t.GetNetname() != NET:
            continue
        s, e = t.GetStart(), t.GetEnd()
        midx, midy = (s.x + e.x) / 2 / MM, (s.y + e.y) / 2 / MM
        if BOX[0] <= midx <= BOX[2] and BOX[1] <= midy <= BOX[3]:
            victims.append(t)
    for t in victims:
        b.Remove(t)
    print(f"old doglegs removed: {len(victims)}")
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
    print(f"written: restored line + verified bulge around the DIO2 barrel")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

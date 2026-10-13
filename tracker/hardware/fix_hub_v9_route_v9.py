#!/usr/bin/env python3
"""fix_hub_v9_route_v9.py -- kill the 1.2um DIO1-via /F33_SCK graze (v8 found
the wrong vertex; this one targets the exact segment).

MEASURED: DIO1 via (49.590,8.316) dia 0.60; my dogleg leg
(50.458,7.658)->(48.989,8.066) passes 0.4012mm centre-dist = 0.0012mm edge
gap vs 0.20 required. 1.2um is sub-etch-tolerance -> must move.

Fix: shift the leg's APEX-SIDE endpoint (50.458,7.658) perpendicular away
from the via. Search offsets on a 0.05mm grid until BOTH legs (apex->ORIG_A
(51.498,5.557) and apex->ORIG_B (48.989,8.066)) clear EVERY foreign B.Cu
item by 0.20 edge-to-edge. Verify-before-write; refusal = no change.
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
APEX_CUR = (50.458, 7.658)
ORIG_B = (48.989, 8.066)
ORIG_A = (51.498, 5.557)     # the other far endpoint stays fixed
DIO1_VIA = (49.590, 8.316)


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
    trks, vias, pads = [], [], []
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
        for (lx0, ly0, lx1, ly1) in ((ORIG_A[0], ORIG_A[1], ax_, ay_),
                                     (ax_, ay_, ORIG_B[0], ORIG_B[1])):
            for (tx0, ty0, tx1, ty1, hw) in trks:
                d = (seg_seg(lx0 * MM, ly0 * MM, lx1 * MM, ly1 * MM,
                             tx0 * MM, ty0 * MM, tx1 * MM, ty1 * MM) / MM) - hw - TRACK_W / 2
                if d < RULE - 1e-9:
                    return False
            for (vx, vy, r) in vias:
                d = seg_dist(vx * MM, vy * MM, lx0 * MM, ly0 * MM, lx1 * MM, ly1 * MM) / MM - r - TRACK_W / 2
                if d < RULE - 1e-9:
                    return False
            for (x0, y0, x1, y1) in pads:
                for k in range(9):
                    tt = k / 8
                    px = lx0 + (lx1 - lx0) * tt
                    py = ly0 + (ly1 - ly0) * tt
                    ddx = max(x0 - px, 0, px - x1)
                    ddy = max(y0 - py, 0, py - y1)
                    if math.hypot(ddx, ddy) < TRACK_W / 2 + RULE - 1e-9:
                        return False
        return True

    found = None
    for dyy in range(-30, 31):
        for dxx in range(-30, 31):
            ax_ = APEX_CUR[0] + dxx * 0.05
            ay_ = APEX_CUR[1] + dyy * 0.05
            if legs_ok(ax_, ay_):
                dist = math.hypot(dxx * 0.05, dyy * 0.05)
                if found is None or dist < found[0]:
                    found = (dist, ax_, ay_)
    if not found:
        print("no verified apex within 1.5mm -- SKIP")
        b.Save(args.out)
        return 1
    _, nax, nay = found
    moved = 0
    for t in b.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetLayer() != bcu or t.GetNetname() != NET:
            continue
        for getter, setter in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
            pt = getter()
            if abs(pt.x / MM - APEX_CUR[0]) < 0.05 and abs(pt.y / MM - APEX_CUR[1]) < 0.05:
                setter(pcbnew.VECTOR2I(int(nax * MM), int(nay * MM)))
                moved += 1
    b.BuildConnectivity()
    b.Save(args.out)
    print(f"apex endpoint {APEX_CUR} -> ({nax:.3f},{nay:.3f}) "
          f"({found[0]:.2f}mm move, verified vs ALL foreign B.Cu copper); writes: {moved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

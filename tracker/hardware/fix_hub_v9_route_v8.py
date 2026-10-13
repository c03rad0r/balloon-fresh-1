#!/usr/bin/env python3
"""fix_hub_v9_route_v8.py -- re-place the /F33_SCK dogleg apex against ALL copper.

v7 clearance 11 classified:
  4 PRE (fm5 baseline: +3V3/SCK 0.1416, +3V3/RESET_N 0.0938, ANT1/SCAP_MID
    0.045, +3V3/SCAP_MID 0.0143)
  5 INHERENT via-in-pad family (U4 0.5mm-pitch QFN: DIO1 pad 0.075, MOSI pad
    0.075, DIO1 trk 0.100, MOSI trk 0.100, DIO3 trk 0.100) -- the via is INSIDE
    the pad by design (same IPC-4761 as the existing +3V3 in-pads); unfixable.
  2 ACTIONABLE, both from my v2 /F33_SCK dogleg:
    #1 Via [/SX1280_DIO1] vs /F33_SCK  0.0012  (apex landed ON DIO1's via)
    #7 Via [/SX1280_DIO2] vs /F33_SCK  0.1638  (needs 0.60, got 0.56)

Why v6 failed: its apex search checked ONLY the target barrel, so the apex
landed on DIO1 copper -> 2 shorts. v8 searches the apex against EVERY foreign
B.Cu item (tracks w/ width, vias w/ radius).
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
ORIG_A = (51.50, 5.56)      # original segment endpoints (pre-dogleg)
ORIG_B = (48.99, 8.07)
KEEP_TRK = TRACK_W / 2 + TRACK_W / 2 + RULE   # 0.40 (leg vs foreign track)
KEEP_VIA = TRACK_W / 2 + 0.30 + RULE          # 0.60 (leg vs foreign via)
KEEP_PAD = TRACK_W / 2 + RULE                 # 0.30 (leg vs pad edge)


def seg_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()
    b = pcbnew.LoadBoard(args.inp)
    bcu = b.GetLayerID("B.Cu")

    # ---- identify my dogleg: the F33_SCK B.Cu vertices not at ORIG_A/ORIG_B
    verts = {}
    segs = []
    for t in b.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetLayer() != bcu or t.GetNetname() != NET:
            continue
        s, e = t.GetStart(), t.GetEnd()
        segs.append((t, (s.x / MM, s.y / MM), (e.x / MM, e.y / MM)))
        for p in (s, e):
            key = (round(p.x / MM, 2), round(p.y / MM, 2))
            verts[key] = verts.get(key, 0) + 1
    if len(segs) < 2:
        print("no dogleg found (F33_SCK has <2 B.Cu segments) -- nothing to do")
        b.Save(args.out)
        return 0
    apex = None
    for key, cnt in verts.items():
        if cnt >= 2 and math.hypot(key[0] - ORIG_A[0], key[1] - ORIG_A[1]) > 0.3 \
                and math.hypot(key[0] - ORIG_B[0], key[1] - ORIG_B[1]) > 0.3:
            apex = key
            break
    if apex is None:
        print("apex vertex not identified -- aborting")
        b.Save(args.out)
        return 1
    print(f"dogleg apex found at {apex}")

    # ---- foreign B.Cu obstacles (everything except F33_SCK itself)
    trks, vias, pads = [], [], []
    for t in b.GetTracks():
        if t.GetNetname() == NET:
            continue
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            vias.append((p.x / MM, p.y / MM, t.GetWidth(pcbnew.F_Cu) / 2 / MM, t.GetNetname()))
        elif t.GetLayer() == bcu:
            s, e = t.GetStart(), t.GetEnd()
            trks.append((s.x / MM, s.y / MM, e.x / MM, e.y / MM,
                         t.GetWidth() / MM / 2, t.GetNetname()))
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() == NET:
                continue
            if p.IsOnLayer(bcu):
                bb = p.GetBoundingBox()
                pads.append((bb.GetX() / MM, bb.GetY() / MM,
                             (bb.GetX() + bb.GetWidth()) / MM,
                             (bb.GetY() + bb.GetHeight()) / MM, p.GetNetname()))

    def legs_ok(ax_, ay_):
        for (lx0, ly0, lx1, ly1) in ((ORIG_A[0], ORIG_A[1], ax_, ay_),
                                     (ax_, ay_, ORIG_B[0], ORIG_B[1])):
            for (tx0, ty0, tx1, ty1, hw, nm) in trks:
                if seg_dist(ax_ * MM, ay_ * MM, tx0 * MM, ty0 * MM, tx1 * MM, ty1 * MM) < 0 and False:
                    pass
                # leg vs foreign track
                d = min(seg_dist(lx0 * MM, ly0 * MM, tx0 * MM, ty0 * MM, tx1 * MM, ty1 * MM),
                        seg_dist(lx1 * MM, ly1 * MM, tx0 * MM, ty0 * MM, tx1 * MM, ty1 * MM),
                        seg_dist(tx0 * MM, ty0 * MM, lx0 * MM, ly0 * MM, lx1 * MM, ly1 * MM),
                        seg_dist(tx1 * MM, ty1 * MM, lx0 * MM, ly0 * MM, lx1 * MM, ly1 * MM))
                if d / MM - hw < TRACK_W / 2 + RULE - 1e-9:
                    return False
            for (vx, vy, r, nm) in vias:
                d = seg_dist(vx * MM, vy * MM, lx0 * MM, ly0 * MM, lx1 * MM, ly1 * MM) / MM
                if d - r < TRACK_W / 2 + RULE - 1e-9:
                    return False
            for (x0, y0, x1, y1, nm) in pads:
                for k in range(9):
                    tt = k / 8
                    px = (lx0 + (lx1 - lx0) * tt) * MM
                    py = (ly0 + (ly1 - ly0) * tt) * MM
                    ddx = max(x0 * MM - px, 0, px - x1 * MM)
                    ddy = max(y0 * MM - py, 0, py - y1 * MM)
                    if math.hypot(ddx, ddy) < (TRACK_W / 2 + RULE) * MM - 1e-9:
                        return False
        return True

    found = None
    for dyy in range(-40, 41):
        for dxx in range(-40, 41):
            ax_ = apex[0] + dxx * 0.1
            ay_ = apex[1] + dyy * 0.1
            if legs_ok(ax_, ay_):
                dist = math.hypot(dxx, dyy) * 0.1
                if found is None or dist < found[0]:
                    found = (dist, ax_, ay_)
    if not found:
        print("no verified apex within 4mm -- SKIP (documented)")
        b.Save(args.out)
        return 1
    _, nax, nay = found
    # move the apex vertex on both segments
    moved = 0
    for (t, s_mm, e_mm) in segs:
        for getter, setter, pt in ((t.GetStart, t.SetStart, s_mm), (t.GetEnd, t.SetEnd, e_mm)):
            if abs(pt[0] - apex[0]) < 0.05 and abs(pt[1] - apex[1]) < 0.05:
                setter(pcbnew.VECTOR2I(int(nax * MM), int(nay * MM)))
                moved += 1
    b.BuildConnectivity()
    b.Save(args.out)
    print(f"apex {apex} -> ({nax:.2f},{nay:.2f}) verified vs ALL B.Cu copper "
          f"(tracks/vias/pads), {found[0]:.1f}mm move; {moved} vertex write(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

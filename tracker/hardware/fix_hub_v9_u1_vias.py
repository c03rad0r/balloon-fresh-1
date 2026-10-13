#!/usr/bin/env python3
"""fix_hub_v9_u1_vias.py -- final defect: move the 2 U1-side vias to spots
verified clear on ALL THREE layers (F.Cu copper + B.Cu tracks + In2 barrels+transits).

MEASURED remaining:
  DIO2 via @ (58.85,15.65) pierces /SX1280_BUSY B.Cu track (short)
  MISO via @ (58.85,13.11) grazes /SX1280_DIO1 track on B.Cu (clearance)
Search: 0.1mm grid, ring 2.0mm around each U1 pad (58.95,15.65)/(58.95,13.11),
require: clear of every B.Cu track/via (r=0.55 via-equiv), every F.Cu foreign
pad, and every In2 obstacle; then the short F.Cu leg pad<->via must also clear.
"""
import argparse
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
TRACK_W = 0.20
RULE = 0.15
VIA_D = 0.60
KEEP_VIA = VIA_D / 2 + RULE          # 0.45 to track obstacle edge... use center-dist
BARREL_KEEP = 0.30 + TRACK_W / 2 + RULE  # 0.55

JOBS = [
    ("/SX1280_DIO2", (58.95, 15.65), (58.85, 15.65)),
    ("/SX1280_MISO", (58.95, 13.11), (58.85, 13.11)),
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
    fcu = b.GetLayerID("F.Cu")
    bcu = b.GetLayerID("B.Cu")
    in2 = b.GetLayerID("In2.Cu")

    # obstacles per layer (foreign only)
    def foreign(layer_id, include_pads=True):
        out = []
        for t in b.GetTracks():
            if t.GetClass() == "PCB_VIA":
                p = t.GetPosition()
                out.append((p.x, p.y, p.x, p.y, t.GetWidth(pcbnew.F_Cu) / 2, t.GetNetname(), "via"))
            elif t.GetLayer() == layer_id:
                s, e = t.GetStart(), t.GetEnd()
                out.append((s.x, s.y, e.x, e.y, t.GetWidth() / 2, t.GetNetname(), "trk"))
        if include_pads:
            for f in b.GetFootprints():
                for p in f.Pads():
                    if p.IsOnLayer(layer_id):
                        bb = p.GetBoundingBox()
                        cx, cy = bb.GetX() + bb.GetWidth() / 2, bb.GetY() + bb.GetHeight() / 2
                        r = max(bb.GetWidth(), bb.GetHeight()) / 2
                        out.append((cx, cy, cx, cy, r, p.GetNetname(), "pad"))
        return out

    fobs = foreign(fcu)
    bobs = foreign(bcu)
    iobs = foreign(in2, include_pads=False)

    def spot_ok(net, vx, vy):
        vxmm, vymm = vx / MM, vy / MM
        for obs in (fobs, bobs, iobs):
            for (ox, oy, ox2, oy2, r, nm, kind) in obs:
                if nm == net:
                    continue
                need = (VIA_D / 2 + r + RULE) if kind != "trk" else (VIA_D / 2 + r + RULE)
                d = seg_seg(vxmm * MM, vymm * MM, vxmm * MM, vymm * MM, ox, oy, ox2, oy2) - r
                if d < (VIA_D / 2 + RULE) * MM:
                    return False
        return True

    def leg_ok(net, ax_, ay_, bx_, by_):
        for obs in (fobs,):
            for (ox, oy, ox2, oy2, r, nm, kind) in obs:
                if nm == net:
                    continue
                d = seg_seg(ax_ * MM, ay_ * MM, bx_ * MM, by_ * MM, ox, oy, ox2, oy2) - r
                if d < (TRACK_W / 2 + RULE) * MM:
                    return False
        return True

    moved = 0
    for (net, pad, cur) in JOBS:
        pxmm, pymm = pad
        found = None
        for dyy in range(-20, 21):
            for dxx in range(-20, 21):
                if dxx == 0 and dyy == 0:
                    continue
                vx = (pxmm + dxx * 0.1) * MM
                vy = (pymm + dyy * 0.1) * MM
                if spot_ok(net, vx, vy) and leg_ok(net, pxmm * MM, pymm * MM, vx, vy):
                    dist = math.hypot(dxx, dyy) * 0.1
                    if found is None or dist < found[0]:
                        found = (dist, vx / MM, vy / MM)
        if not found:
            print(f"{net}: NO verified spot within 2.0mm -- SKIP")
            continue
        # move my via + rewrite the F.Cu leg endpoint + In2 transit endpoint
        newx, newy = found[1], found[2]
        for t in b.GetTracks():
            if t.GetClass() == "PCB_VIA" and t.GetNetname() == net:
                p = t.GetPosition()
                if abs(p.x / MM - cur[0]) < 0.05 and abs(p.y / MM - cur[1]) < 0.05:
                    t.SetPosition(pcbnew.VECTOR2I(int(newx * MM), int(newy * MM)))
        # F.Cu leg: the one ending at the OLD via pos
        for t in b.GetTracks():
            if t.GetClass() == "PCB_TRACK" and t.GetLayer() == fcu and t.GetNetname() == net:
                for pt_name in ("GetStart", "GetEnd"):
                    pt = getattr(t, pt_name)()
                    if abs(pt.x / MM - cur[0]) < 0.05 and abs(pt.y / MM - cur[1]) < 0.05:
                        t.SetStart(pcbnew.VECTOR2I(int(newx * MM), int(newy * MM))) if pt_name == "GetStart" else t.SetEnd(pcbnew.VECTOR2I(int(newx * MM), int(newy * MM)))
        # In2 transit endpoint at old via pos
        for t in b.GetTracks():
            if t.GetClass() == "PCB_TRACK" and t.GetLayer() == in2 and t.GetNetname() == net:
                s, e = t.GetStart(), t.GetEnd()
                if abs(e.x / MM - cur[0]) < 0.05 and abs(e.y / MM - cur[1]) < 0.05:
                    t.SetEnd(pcbnew.VECTOR2I(int(newx * MM), int(newy * MM)))
                elif abs(s.x / MM - cur[0]) < 0.05 and abs(s.y / MM - cur[1]) < 0.05:
                    t.SetStart(pcbnew.VECTOR2I(int(newx * MM), int(newy * MM)))
        moved += 1
        print(f"{net}: via {cur} -> ({newx:.2f},{newy:.2f}) (all-3-layer verified, {found[0]:.1f}mm from pad)")

    b.BuildConnectivity()
    b.Save(args.out)
    print(f"moved: {moved}/2; written: {args.out}")
    return 0 if moved == 2 else 1


if __name__ == "__main__":
    raise SystemExit(main())

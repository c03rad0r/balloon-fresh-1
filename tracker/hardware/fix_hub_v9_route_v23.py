#!/usr/bin/env python3
"""fix_hub_v9_route_v23.py -- relocate the ANCHORING vias for the 3 dense grazes.

v22 board of record grazes needing via relocation (vertex-push refused: no
single vertex move clears all neighbours):
  0.0938  +3V3 via        vs /SX1280_RESET_N  (B.Cu)
  0.0450  /ANT1_433_TX via vs /SCAP_MID       (B.Cu)
  0.0143  +3V3 via        vs /SCAP_MID        (B.Cu)

Method (v17 precedent: DIO1 via +0.30mm south fixed a 0.0012 graze):
for each anchoring VIA, scan a ring of candidate positions (0.05mm grid,
2.0mm radius) requiring the via to clear ALL foreign copper on EVERY layer
by 0.20 edge-to-edge, then re-point all tracks attached to it.
Refuse if no position verifies. Verify-before-write.
"""
import argparse
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
TRACK_W = 0.20
RULE = 0.20

# the grazed track nets -> we relocate the FOREIGN via that anchors each graze
TARGETS = [
    ("/SX1280_RESET_N", "+3V3"),
    ("/SCAP_MID", "/ANT1_433_TX"),
    ("/SCAP_MID", "+3V3"),
]


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
    fcu, bcu, in2 = (b.GetLayerID(n) for n in ("F.Cu", "B.Cu", "In2.Cu"))

    def all_copper(exclude_via_pos=None):
        """(kind, x0,y0,x1,y1, halfwidth, netname, layer_id)"""
        out = []
        for t in b.GetTracks():
            if t.GetClass() == "PCB_VIA":
                p = t.GetPosition()
                if exclude_via_pos and (round(p.x / MM, 2), round(p.y / MM, 2)) == exclude_via_pos:
                    continue
                out.append(("via", p.x / MM, p.y / MM, p.x / MM, p.y / MM,
                            t.GetWidth(pcbnew.F_Cu) / 2 / MM, t.GetNetname(), None))
            else:
                s, e = t.GetStart(), t.GetEnd()
                out.append(("trk", s.x / MM, s.y / MM, e.x / MM, e.y / MM,
                            t.GetWidth() / MM / 2, t.GetNetname(), t.GetLayer()))
        for f in b.GetFootprints():
            for p in f.Pads():
                for lay in (fcu, bcu):
                    if p.IsOnLayer(lay):
                        bb = p.GetBoundingBox()
                        out.append(("pad", bb.GetX() / MM, bb.GetY() / MM,
                                    (bb.GetX() + bb.GetWidth()) / MM,
                                    (bb.GetY() + bb.GetHeight()) / MM,
                                    0.0, p.GetNetname(), lay))
        return out

    relocations = 0
    for (grazed_net, via_net) in TARGETS:
        # find the graze pair on the board
        best = None
        for t in b.GetTracks():
            if t.GetClass() != "PCB_TRACK" or t.GetNetname() != grazed_net:
                continue
            s, e = t.GetStart(), t.GetEnd()
            sx, sy, ex, ey = s.x / MM, s.y / MM, e.x / MM, e.y / MM
            hw = t.GetWidth() / MM / 2
            for u in b.GetTracks():
                if u.GetClass() != "PCB_VIA" or u.GetNetname() != via_net:
                    continue
                p = u.GetPosition()
                px, py = p.x / MM, p.y / MM
                d = seg_dist(px * MM, py * MM, sx * MM, sy * MM, ex * MM, ey * MM) / MM
                need = (u.GetWidth(pcbnew.F_Cu) / 2 / MM) + hw + RULE
                if d < need - 1e-9:
                    if best is None or (need - d) > best[0]:
                        best = (need - d, u, px, py, t, d, need)
        if not best:
            print(f"{grazed_net} vs {via_net}: no graze found")
            continue
        deficit, via_obj, vx0, vy0, seg, d0, need0 = best
        print(f"{grazed_net} vs {via_net} via ({vx0:.3f},{vy0:.3f}): "
              f"d={d0:.4f} need={need0:.4f} deficit={deficit:.4f}")

        # tracks attached to this via (endpoint within 0.35mm, any layer)
        attached = []   # (track, "start"|"end", far_x_mm, far_y_mm)
        for t in b.GetTracks():
            if t.GetClass() != "PCB_TRACK":
                continue
            s_pt, e_pt = t.GetStart(), t.GetEnd()
            if math.hypot(s_pt.x / MM - vx0, s_pt.y / MM - vy0) < 0.10:
                attached.append((t, "start", e_pt.x, e_pt.y))
            if math.hypot(e_pt.x / MM - vx0, e_pt.y / MM - vy0) < 0.10:
                attached.append((t, "end", s_pt.x, s_pt.y))
        print(f"   attached tracks: {len(attached)}")

        copper = all_copper(exclude_via_pos=(round(vx0, 2), round(vy0, 2)))

        def spot_ok(nx, ny):
            """new via position: clear ALL foreign copper on all layers 0.20, and
            every attached track's new leg must also stay legal."""
            vr = 0.30  # via radius (0.60 dia standard)
            for (kind, x0, y0, x1, y1, hw, nm, lay) in copper:
                if nm == via_net:
                    continue
                if kind == "via":
                    if math.hypot(nx - x0, ny - y0) - vr - hw < RULE - 1e-9:
                        return False
                elif kind == "pad":
                    ddx = max(x0 - nx, 0, nx - x1)
                    ddy = max(y0 - ny, 0, ny - y1)
                    if math.hypot(ddx, ddy) - vr < RULE - 1e-9:
                        return False
                else:
                    if seg_dist(nx * MM, ny * MM, x0 * MM, y0 * MM, x1 * MM, y1 * MM) / MM - hw - vr < RULE - 1e-9:
                        return False
            # the grazed segment must clear this new position too
            s, e = seg.GetStart(), seg.GetEnd()
            if seg_dist(nx * MM, ny * MM, s.x, s.y, e.x, e.y) / MM - vr - seg.GetWidth() / MM / 2 < RULE - 1e-9:
                return False
            # attached legs
            for (t, which, fx, fy) in attached:
                hw2 = t.GetWidth() / MM / 2
                for (kind, x0, y0, x1, y1, hw, nm, lay) in copper:
                    if nm == t.GetNetname():
                        continue
                    if kind in ("trk", "pad") and lay != t.GetLayer():
                        continue
                    if kind == "via":
                        d = seg_dist(x0 * MM, y0 * MM, fx, fy, nx * MM, ny * MM) / MM - hw
                    elif kind == "pad":
                        d = 1e9
                        for k in range(9):
                            tt = k / 8
                            qx = fx / MM + (nx - fx / MM) * tt
                            qy = fy / MM + (ny - fy / MM) * tt
                            d = min(d, math.hypot(max(x0 - qx, 0, qx - x1),
                                                  max(y0 - qy, 0, qy - y1)))
                    else:
                        d = seg_dist(fx, fy, nx * MM, ny * MM,
                                     x0 * MM, y0 * MM, x1 * MM, y1 * MM) / MM - hw
                    if d - hw2 < RULE - 1e-9:
                        return False
            return True

        found = None
        for dyy in range(-40, 41):
            for dxx in range(-40, 41):
                if dxx == 0 and dyy == 0:
                    continue
                nx, ny = vx0 + dxx * 0.05, vy0 + dyy * 0.05
                if spot_ok(nx, ny):
                    dist = math.hypot(dxx * 0.05, dyy * 0.05)
                    if found is None or dist < found[0]:
                        found = (dist, nx, ny)
        if not found:
            print("   NO verified new position within 2.0mm -- SKIP")
            continue
        _, nx, ny = found
        via_obj.SetPosition(pcbnew.VECTOR2I(int(nx * MM), int(ny * MM)))
        for (t, which, fx, fy) in attached:
            v = pcbnew.VECTOR2I(int(nx * MM), int(ny * MM))
            if which == "start":
                t.SetStart(v)
            else:
                t.SetEnd(v)
        relocations += 1
        print(f"   RELOCATED via ({vx0:.3f},{vy0:.3f}) -> ({nx:.3f},{ny:.3f}) "
              f"({found[0]:.2f}mm); {len(attached)} legs re-pointed")
        b.BuildConnectivity()

    print(f"via relocations: {relocations}")
    b.BuildConnectivity()
    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

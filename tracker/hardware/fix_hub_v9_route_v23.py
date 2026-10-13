#!/usr/bin/env python3
"""fix_hub_v9_route_v23.py (clean rewrite) -- relocate anchoring vias for the 3
dense-locality grazes, per the Astra final-2 verdict.

REQUIREMENT (Astra): "evaluate the complete local clearance graph before
committing the move. A good relocation should clear all neighboring objects
with margin rather than merely moving the violation to another pair."

METHOD
  For each (grazed track net, anchoring foreign via):
    1. Find the worst graze pair.
    2. Collect ALL copper on ALL layers (vias w/ radius, tracks w/ halfwidth,
       pads w/ rect extents).
    3. For each candidate new via position (0.05mm grid, 2.0mm radius):
       build the COMPLETE local clearance graph = for every item in the local
       neighbourhood (3mm), compute the new edge-to-edge clearance and require
       >= RULE + MARGIN for EVERY pair, including:
         - new via vs every foreign via/track/pad (all layers)
         - every ATTACHED track's new leg vs every foreign item on its layer
         - the previous grazing segment vs the new via position
       MARGIN = 0.05mm so the move clears with headroom, not exactly at rule.
    4. Refuse if no position achieves the margin (report instead).
  Then re-point the via and all attached track endpoints.
"""
import argparse
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
TRACK_W = 0.20
RULE = 0.20
MARGIN = 0.05          # Astra: "clear all neighboring objects WITH MARGIN"
REQUIRED = RULE + MARGIN   # 0.25

# grazed net -> the foreign via net that anchors its graze
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


def seg_seg(ax, ay, bx, by, cx, cy, dx, dy):
    return min(seg_dist(ax, ay, cx, cy, dx, dy), seg_dist(bx, by, cx, cy, dx, dy),
               seg_dist(cx, cy, ax, ay, bx, by), seg_dist(dx, dy, ax, ay, bx, by))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()
    b = pcbnew.LoadBoard(args.inp)

    # ---- one flat copper inventory (kind, x0,y0,x1,y1, half/rad, net, layer)
    def inventory(skip_via=None, skip_net=None):
        inv = []
        for t in b.GetTracks():
            nm = t.GetNetname()
            if t.GetClass() == "PCB_VIA":
                p = t.GetPosition()
                if skip_via and (round(p.x / MM, 2), round(p.y / MM, 2)) == skip_via:
                    continue
                if skip_net and nm == skip_net:
                    continue
                inv.append(["via", p.x / MM, p.y / MM, p.x / MM, p.y / MM,
                            t.GetWidth(pcbnew.F_Cu) / 2 / MM, nm, None])
            else:
                if skip_net and nm == skip_net:
                    continue
                s, e = t.GetStart(), t.GetEnd()
                inv.append(["trk", s.x / MM, s.y / MM, e.x / MM, e.y / MM,
                            t.GetWidth() / MM / 2, nm, t.GetLayer()])
        for f in b.GetFootprints():
            for p in f.Pads():
                nm = p.GetNetname()
                if skip_net and nm == skip_net:
                    continue
                for lay in (b.GetLayerID("F.Cu"), b.GetLayerID("B.Cu")):
                    if p.IsOnLayer(lay):
                        bb = p.GetBoundingBox()
                        inv.append(["pad", bb.GetX() / MM, bb.GetY() / MM,
                                    (bb.GetX() + bb.GetWidth()) / MM,
                                    (bb.GetY() + bb.GetHeight()) / MM, 0.0, nm, lay])
        return inv

    relocated = 0
    for (grazed_net, via_net) in TARGETS:
        # 1. worst graze pair
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
                if d < need - 1e-9 and (best is None or (need - d) > best[0]):
                    best = (need - d, u, px, py, t, d, need)
        if not best:
            print(f"{grazed_net} vs {via_net}: no graze")
            continue
        deficit, via_obj, vx0, vy0, seg, d0, need0 = best
        print(f"{grazed_net} vs {via_net} ({vx0:.3f},{vy0:.3f}): d={d0:.4f} need={need0:.4f} deficit={deficit:.4f}")

        # 2. attached tracks: (track, which, far_x_mm, far_y_mm)
        attached = []
        for t in b.GetTracks():
            if t.GetClass() != "PCB_TRACK":
                continue
            sp, ep = t.GetStart(), t.GetEnd()
            if math.hypot(sp.x / MM - vx0, sp.y / MM - vy0) < 0.10:
                attached.append((t, "start", ep.x, ep.y))
            if math.hypot(ep.x / MM - vx0, ep.y / MM - vy0) < 0.10:
                attached.append((t, "end", sp.x, sp.y))
        print(f"   attached tracks: {len(attached)}")

        inv = inventory(skip_via=(round(vx0, 2), round(vy0, 2)))

        def graph_ok(nx, ny):
            """COMPLETE local clearance graph at the new via position, with MARGIN."""
            vr = 0.30  # via radius (0.60 dia)
            # segments to test: (layer_or_None, x0,y0,x1,y1, halfwidth, own_net)
            locals_ = [(None, nx, ny, nx, ny, vr, via_net)]
            for (t, which, fx, fy) in attached:
                hw = t.GetWidth() / MM / 2
                locals_.append((t.GetLayer(), fx, fy, nx, ny, hw, t.GetNetname()))
            # the previously-grazing segment, new geometry (unchanged endpoint)
            sp, ep = seg.GetStart(), seg.GetEnd()
            locals_.append((seg.GetLayer(), sp.x / MM, sp.y / MM, ep.x / MM, ep.y / MM,
                            seg.GetWidth() / MM / 2, seg.GetNetname()))

            for (lay, ax, ay, bx, by, hw, own) in locals_:
                for (kind, x0, y0, x1, y1, h2, nm, l2) in inv:
                    if nm == own:
                        continue
                    if kind == "via":
                        if lay is not None and False:
                            continue
                        d = seg_dist(x0 * MM, y0 * MM, ax * MM, ay * MM, bx * MM, by * MM) / MM - h2
                    elif kind == "pad":
                        # layer gate: pads exist on F/B; a via (lay None) sees both
                        d = 1e9
                        for k in range(11):
                            tt = k / 10
                            qx = ax + (bx - ax) * tt
                            qy = ay + (by - ay) * tt
                            d = min(d, math.hypot(max(x0 - qx, 0, qx - x1),
                                                  max(y0 - qy, 0, qy - y1)))
                    else:
                        if lay is not None and l2 != lay:
                            continue
                        d = seg_seg(ax * MM, ay * MM, bx * MM, by * MM,
                                    x0 * MM, y0 * MM, x1 * MM, y1 * MM) / MM - h2
                    if d - hw < REQUIRED - 1e-9:
                        return False
            return True

        found = None
        for dyy in range(-40, 41):
            for dxx in range(-40, 41):
                if dxx == 0 and dyy == 0:
                    continue
                nx, ny = vx0 + dxx * 0.05, vy0 + dyy * 0.05
                if graph_ok(nx, ny):
                    dist = math.hypot(dxx * 0.05, dyy * 0.05)
                    if found is None or dist < found[0]:
                        found = (dist, nx, ny)
        if not found:
            print(f"   NO position clears the full graph with {MARGIN}mm margin -- 'relocation cannot provide margin'; fallback ladder required")
            continue
        _, nx, ny = found
        via_obj.SetPosition(pcbnew.VECTOR2I(int(nx * MM), int(ny * MM)))
        v = pcbnew.VECTOR2I(int(nx * MM), int(ny * MM))
        for (t, which, fx, fy) in attached:
            if which == "start":
                t.SetStart(v)
            else:
                t.SetEnd(v)
        relocated += 1
        print(f"   RELOCATED ({vx0:.3f},{vy0:.3f}) -> ({nx:.3f},{ny:.3f}); {found[0]:.2f}mm; {len(attached)} legs; full graph + {MARGIN}mm margin OK")
        b.BuildConnectivity()

    print(f"relocations: {relocated}")
    b.BuildConnectivity()
    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

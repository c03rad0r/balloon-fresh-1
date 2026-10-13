#!/usr/bin/env python3
"""hand_route_hub_v9_dio2_miso.py -- measured hand-route of the 2 stuck nets.

Consultant verdict (2026-10-13): hand-route + verify is the sanctioned path.
Measured prerequisites:
  - In2.Cu is EMPTY (zones=[], 0 tracks) after the D1-corrected restack.
  - F.Cu free via-spots scanned at 0.1 mm resolution around all 4 pads
    (clear of every track/via/pad by via-r + 0.15 mm):
      U4.11 (50.00,7.20): nearest (+0.2,+1.6)   U1.11 (58.95,15.65): (+1.2,0.0)
      U4.9  (49.00,7.20): nearest (-2.0,+0.2)   U1.9  (58.95,13.11): (-1.2,0.0)

Route shape per net: pad --F.Cu--> viaA --In2.Cu--> viaB --F.Cu--> pad.
Every F.Cu segment is verified against all foreign copper BEFORE writing
(0.2 mm track, 0.15 mm clearance rule). In2.Cu transit is on an empty layer.
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

# (net, padA(x,y), viaA(x,y), viaB(x,y), padB(x,y)) -- all measured above
ROUTES = [
    ("/SX1280_DIO2", (50.00, 7.20), (50.20, 8.80), (60.15, 15.65), (58.95, 15.65)),
    ("/SX1280_MISO", (49.00, 7.20), (47.00, 7.40), (57.75, 13.11), (58.95, 13.11)),
]


def seg_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def seg_seg_dist(ax, ay, bx, by, cx, cy, dx, dy):
    def pt_seg(p, a, b):
        return seg_dist(p[0], p[1], a[0], a[1], b[0], b[1])
    A, B, C, D = (ax, ay), (bx, by), (cx, cy), (dx, dy)
    return min(pt_seg(A, C, D), pt_seg(B, C, D),
               pt_seg(C, A, B), pt_seg(D, A, B))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.inp)
    fcu = b.GetLayerID("F.Cu")
    in2 = b.GetLayerID("In2.Cu")

    # foreign F.Cu obstacles for segment verification
    fobs = []
    for t in b.GetTracks():
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            fobs.append(("via", p.x, p.y, p.x, p.y, t.GetWidth() / 2 + VIA_D / 2))
        elif t.GetLayer() == fcu:
            s, e = t.GetStart(), t.GetEnd()
            fobs.append(("trk", s.x, s.y, e.x, e.y, t.GetWidth() / 2 + TRACK_W / 2))
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.IsOnLayer(fcu):
                bb = p.GetBoundingBox()
                cx, cy = bb.GetX() + bb.GetWidth() / 2, bb.GetY() + bb.GetHeight() / 2
                r = max(bb.GetWidth(), bb.GetHeight()) / 2
                fobs.append(("pad", cx, cy, cx, cy, r + TRACK_W / 2))

    netcodes = {}
    for code, ni in b.GetNetInfo().NetsByNetcode().items():
        netcodes[ni.GetNetname()] = code

    def add_track(net, x0, y0, x1, y1, layer):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(int(x0 * MM), int(y0 * MM)))
        t.SetEnd(pcbnew.VECTOR2I(int(x1 * MM), int(y1 * MM)))
        t.SetWidth(int(TRACK_W * MM))
        t.SetLayer(layer)
        t.SetNetCode(netcodes[net])
        b.Add(t)

    def add_via(net, x, y):
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(pcbnew.VECTOR2I(int(x * MM), int(y * MM)))
        v.SetWidth(int(VIA_D * MM), int((VIA_D - 0.30) * MM))
        v.SetLayer(pcbnew.F_Cu)
        v.SetNetCode(netcodes[net])
        b.Add(v)

    for (net, padA, viaA, viaB, padB) in ROUTES:
        print(f"--- {net}: {padA} -> via{viaA} -> via{viaB} -> {padB}")
        # verify the two F.Cu escape segments against ALL foreign copper
        for (label, seg) in (("escape A", (padA, viaA)), ("escape B", (viaB, padB))):
            bad = 0
            for (kind, ox, oy, ox2, oy2, r) in fobs:
                d = seg_seg_dist(seg[0][0]*MM, seg[0][1]*MM, seg[1][0]*MM, seg[1][1]*MM,
                                 ox, oy, ox2, oy2) - r
                if d < RULE * MM:
                    bad += 1
            print(f"    {label}: {'CLEAR' if bad == 0 else f'{bad} OBSTACLES < {RULE}mm'}")
            if bad:
                print(f"    REFUSED: {net} {label} violates clearance -- nothing written")
                return 1
        add_track(net, padA[0], padA[1], viaA[0], viaA[1], fcu)
        add_via(net, viaA[0], viaA[1])
        # In2.Cu transit: L-shape to keep it simple and away from the vias' antipads
        add_track(net, viaA[0], viaA[1], viaA[0], viaB[1], in2)
        add_track(net, viaA[0], viaB[1], viaB[0], viaB[1], in2)
        add_via(net, viaB[0], viaB[1])
        add_track(net, viaB[0], viaB[1], padB[0], padB[1], fcu)
        print("    written: 2 F.Cu escapes + 2 vias + 2 In2.Cu transit tracks")

    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

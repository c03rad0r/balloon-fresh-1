#!/usr/bin/env python3
"""fix_hub_v9_route_v24.py -- Astra fallback #1: change the LAYER TRANSITION of
the two dense-locality grazes (via relocation REFUTED at exact rule, see v23).

MEASURED (v23): relocating the anchoring vias cannot clear the full local graph
even at exactly 0.20mm -> B.Cu at those spots is structurally over-constrained.

ASTRA FALLBACK #1 (from docs/CONSULT-astra-final2-2026-10-13.txt): "reroute the
escape and change the layer transition location." The hub's In2.Cu was freed
(D1-corrected) and carries only 2 signal nets -- it has room.

TARGETS (from drc_v22):
  /SX1280_RESET_N vs +3V3 via (58.950,4.220) at 0.4938 (need 0.6000)
  /SCAP_MID       vs /ANT1_433_TX via (38.583,30.308) at 0.4450 (need 0.6000)

Method: move the grazed B.Cu segment to In2.Cu with a via pair (existing
supported 0.60/0.30 size) at its ends. Verify the In2 copy clears all In2
copper and both new barrels clear all foreign vias before writing. Refuse
otherwise (report the fallback ladder stage).
"""
import argparse
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
TRACK_W = 0.20
RULE = 0.20
VIA_D, VIA_DRILL = 0.60, 0.30

TARGETS = [("/SX1280_RESET_N", "+3V3"), ("/SCAP_MID", "/ANT1_433_TX")]


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
    in2 = b.GetLayerID("In2.Cu")
    nets = {ni.GetNetname(): code for code, ni in b.GetNetInfo().NetsByNetcode().items()}

    moved = 0
    for (grazed_net, via_net) in TARGETS:
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
                d = seg_dist(p.x / MM * MM, p.y / MM * MM, sx * MM, sy * MM, ex * MM, ey * MM) / MM
                need = (u.GetWidth(pcbnew.F_Cu) / 2 / MM) + hw + RULE
                if d < need - 1e-9 and (best is None or (need - d) > best[0]):
                    best = (need - d, t, sx, sy, ex, ey, p.x / MM, p.y / MM, d)
        if not best:
            print(f"{grazed_net}: no graze vs {via_net}")
            continue
        deficit, seg, sx, sy, ex, ey, vx, vy, d0 = best
        print(f"{grazed_net}: d={d0:.4f} def={deficit:.4f} seg ({sx:.3f},{sy:.3f})-({ex:.3f},{ey:.3f}) vs {via_net} ({vx:.3f},{vy:.3f})")

        # In2 copper for verifying the In2 copy
        in2_items = []
        for t in b.GetTracks():
            if t.GetNetname() == grazed_net:
                continue
            if t.GetClass() == "PCB_VIA":
                p = t.GetPosition()
                in2_items.append((p.x / MM, p.y / MM, p.x / MM, p.y / MM,
                                  t.GetWidth(pcbnew.F_Cu) / 2 / MM))
            elif t.GetLayer() == in2:
                s, e = t.GetStart(), t.GetEnd()
                in2_items.append((s.x / MM, s.y / MM, e.x / MM, e.y / MM,
                                  t.GetWidth() / MM / 2))

        bad = False
        for (x0, y0, x1, y1, h2) in in2_items:
            d = seg_seg(sx * MM, sy * MM, ex * MM, ey * MM, x0 * MM, y0 * MM, x1 * MM, y1 * MM) / MM - h2
            if d < TRACK_W / 2 + RULE - 1e-9:
                bad = True
                print(f"   In2 copy would graze In2 copper ({d:.4f}) -- SKIP")
                break
        if bad:
            continue

        # new barrels must clear foreign vias (all layers)
        fvias = [(u.GetPosition().x / MM, u.GetPosition().y / MM,
                  u.GetWidth(pcbnew.F_Cu) / 2 / MM)
                 for u in b.GetTracks()
                 if u.GetClass() == "PCB_VIA" and u.GetNetname() != grazed_net]
        via_ok = True
        for (nx, ny) in ((sx, sy), (ex, ey)):
            for (ox, oy, r) in fvias:
                if math.hypot(nx - ox, ny - oy) - r < VIA_D / 2 + RULE - 1e-9:
                    via_ok = False
                    break
            if not via_ok:
                break
        if not via_ok:
            print("   new barrel would graze a foreign via -- SKIP")
            continue

        netcode = nets[grazed_net]
        for (nx, ny) in ((sx, sy), (ex, ey)):
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(pcbnew.VECTOR2I(int(nx * MM), int(ny * MM)))
            v.SetWidth(int(VIA_D * MM), int(VIA_DRILL * MM))
            v.SetNetCode(netcode)
            b.Add(v)
        nt = pcbnew.PCB_TRACK(b)
        nt.SetStart(pcbnew.VECTOR2I(int(sx * MM), int(sy * MM)))
        nt.SetEnd(pcbnew.VECTOR2I(int(ex * MM), int(ey * MM)))
        nt.SetWidth(int(TRACK_W * MM))
        nt.SetLayer(in2)
        nt.SetNetCode(netcode)
        b.Add(nt)
        victims = [x for x in b.GetTracks()
                   if x.GetClass() == "PCB_TRACK" and x.GetNetname() == grazed_net
                   and abs(x.GetStart().x / MM - sx) < 0.02
                   and abs(x.GetStart().y / MM - sy) < 0.02
                   and abs(x.GetEnd().x / MM - ex) < 0.02
                   and abs(x.GetEnd().y / MM - ey) < 0.02]
        for x in victims:
            b.Remove(x)
        moved += 1
        print(f"   MOVED to In2.Cu (+2 vias 0.60/0.30), removed {len(victims)} B.Cu seg")
        b.BuildConnectivity()

    print(f"layer moves: {moved}")
    b.BuildConnectivity()
    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

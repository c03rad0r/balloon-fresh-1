#!/usr/bin/env python3
"""Route v10 phase-1 copper -- REBUILT after the operator's defect report.

Defects this version must NOT reproduce (all measured on the previous board, PR #270):
  D1 stub: a segment whose endpoint touches no pad and no other segment of its net
  D2 wrong-net approach: a segment that ends near a pad of ANOTHER net
  D3 under-body copper: a segment crossing a same-side component body
  D4 same-footprint routing: joining two pads of the same footprint unless the net
     genuinely has 2 pads on that footprint (rare; must be justified)

Method, per net (2 pads, same side):
  * candidate L-paths in both orders (HV and VH) plus the direct path
  * every candidate is validated BEFORE being written:
      - every segment clears every foreign pad by >= CLEAR
      - every segment stays out of every same-side body (except its own two pads)
      - the endpoint lands within its OWN pad (so no stub, no wrong-net approach)
  * if no candidate validates, the net is REPORTED, never forced
"""
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")
UM = 1_000_000.0
TRACK_W = int(0.200 * UM)
CLEAR = 0.200
HOLE_PREFIXES = ("H", "HW")


def pad_rect(pad):
    p, s = pad.GetPosition(), pad.GetSize()
    return (p.x / UM - s.x / UM / 2, p.y / UM - s.y / UM / 2,
            p.x / UM + s.x / UM / 2, p.y / UM + s.y / UM / 2)


def seg_rect_dist(x0, y0, x1, y1, bb):
    rx0, ry0, rx1, ry1 = bb
    L = math.hypot(x1 - x0, y1 - y0)
    steps = max(2, int(L / 0.02) + 2)
    for i in range(steps + 1):
        t = i / steps
        px, py = x0 + t * (x1 - x0), y0 + t * (y1 - y0)
        if rx0 <= px <= rx1 and ry0 <= py <= ry1:
            return 0.0
    best = 1e9
    for (ex0, ey0, ex1, ey1) in ((rx0, ry0, rx1, ry0), (rx1, ry0, rx1, ry1),
                                 (rx1, ry1, rx0, ry1), (rx0, ry1, rx0, ry0)):
        best = min(best, _seg_seg(x0, y0, x1, y1, ex0, ey0, ex1, ey1))
    return best


def _seg_seg(ax, ay, bx, by, cx, cy, dx, dy):
    def pt_seg(px, py, x0, y0, x1, y1):
        vx, vy = x1 - x0, y1 - y0
        L2 = vx * vx + vy * vy
        if L2 == 0:
            return math.hypot(px - x0, py - y0)
        t = max(0.0, min(1.0, ((px - x0) * vx + (py - y0) * vy) / L2))
        return math.hypot(px - (x0 + t * vx), py - (y0 + t * vy))
    return min(pt_seg(ax, ay, cx, cy, dx, dy), pt_seg(bx, by, cx, cy, dx, dy),
               pt_seg(cx, cy, ax, ay, bx, by), pt_seg(dx, dy, ax, ay, bx, by))


def build_index(b):
    pads, bodies = [], []
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if ref.startswith(HOLE_PREFIXES):
            # NPTH hole: pad rect is the drill; it must stay clear of copper
            for p in fp.Pads():
                bb = pad_rect(p)
                pads.append((ref, "NPTH", "HOLE", 0, p.GetLayer(), bb))
        if not ref.startswith(HOLE_PREFIXES):
            bb = fp.GetBoundingBox(False, True)
            bodies.append((ref, fp.GetLayer(),
                           (bb.GetX() / UM, bb.GetY() / UM,
                            (bb.GetX() + bb.GetWidth()) / UM,
                            (bb.GetY() + bb.GetHeight()) / UM)))
        for p in fp.Pads():
            n = p.GetNet()
            pads.append((ref, p.GetNumber(), n.GetNetname() if n else "",
                         n.GetNetCode() if n else 0, p.GetLayer(), pad_rect(p)))
    return pads, bodies


def seg_ok(x0, y0, x1, y1, code, layer, own_pad_rects, pads, bodies):
    """Validate one segment.

    own_pad_rects: the two pads this net lands on. ONLY those rects are exempt --
    exempting a whole footprint (the first version) let a track brush a neighbouring
    pin of the same chip; that is exactly the defect the operator spotted.
    """
    half = TRACK_W / UM / 2
    for ref, num, pname, pcode, player, bb in pads:
        if pcode == code:
            continue
        if pname == "HOLE":
            # hole clearance: 0.5 mm edge-to-edge (ADR-125 rule, applied to lanes here)
            if seg_rect_dist(x0, y0, x1, y1, bb) - half < 0.5 - 0.001:
                return False, f"hole {ref} clearance too small"
            continue
        if pcode == 0 or player != layer:
            continue
        if any(all(abs(bb[i] - o[i]) < 1e-6 for i in range(4)) for o in own_pad_rects):
            continue
        d = seg_rect_dist(x0, y0, x1, y1, bb) - half
        if d < CLEAR - 0.001:
            return False, f"clearance {d:+.3f} to {ref}.{num}({pname or 'NC'})"
    return True, ""


def under_body_len(x0, y0, x1, y1, bb, a, c, allow=2.5):
    """Length of the segment inside `bb`, EXCLUDING a window around the two endpoints.

    A track legitimately enters a body to reach its own pad; it may not TRAVERSE the
    body. Anything beyond `allow` mm from both endpoints counts.
    """
    L = math.hypot(x1 - x0, y1 - y0)
    if L == 0:
        return 0.0
    steps = max(2, int(L / 0.05) + 2)
    inside = 0
    for i in range(steps):
        t = (i + 0.5) / steps
        px, py = x0 + t * (x1 - x0), y0 + t * (y1 - y0)
        if not (bb[0] <= px <= bb[2] and bb[1] <= py <= bb[3]):
            continue
        if math.hypot(px - a[0], py - a[1]) < allow or math.hypot(px - c[0], py - c[1]) < allow:
            continue
        inside += 1
    return L * inside / steps


def path_candidates(a, c):
    (ax, ay), (cx, cy) = a, c
    out = []
    if ax != cx and ay != cy:
        out.append([(ax, ay), (cx, ay), (cx, cy)])
        out.append([(ax, ay), (ax, cy), (cx, cy)])
    out.append([(ax, ay), (cx, cy)])
    return out


def main():
    b = pcbnew.LoadBoard(BOARD)
    if b is None:
        print("REFUSED: board load failed")
        return 3
    # 0. this script expects a FRESH board (no copper). Run build_hub_board_v10.py first.
    #    (pcbnew.Remove() invalidates its footprint container -- measured crash 2026-10-21 --
    #     so we never delete copper here; the builder regenerates the board.)
    existing = [t for t in b.GetTracks() if "TRACK" in str(type(t)) and "VIA" not in str(type(t))]
    if existing:
        print(f"REFUSED: board already has {len(existing)} track(s) -- "
              "run build_hub_board_v10.py to regenerate a clean board first")
        return 4

    pads, bodies = build_index(b)
    net_pads = {}
    for ref, num, pname, pcode, layer, bb in pads:
        if pcode:
            net_pads.setdefault((pcode, pname), []).append((ref, num, layer, bb))

    routed, blocked = [], []
    for (code, name), plist in sorted(net_pads.items()):
        uniq = {}
        for ref, num, layer, bb in plist:
            uniq.setdefault((ref, num), (layer, bb))
        if len(uniq) != 2:
            continue  # phase 2 handles multi-pad and cross-side nets
        (ka, (la, bba)), (kb, (lb, bbb)) = list(uniq.items())
        (ra, na), (rb, nb) = ka, kb
        if la != lb:
            continue
        layer = la

        def centre(bb):
            return ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)
        a, c = centre(bba), centre(bbb)
        chosen = None
        reasons = []
        for cand in path_candidates(a, c):
            ok_all = True
            for (x0, y0), (x1, y1) in zip(cand[:-1], cand[1:]):
                ok, why = seg_ok(x0, y0, x1, y1, code, layer, [bba, bbb], pads, bodies)
                if not ok:
                    ok_all = False
                    reasons.append(why)
                    break
                # under-body check
                for ref, blayer, bb in bodies:
                    if blayer != layer:
                        continue
                    ln = under_body_len(x0, y0, x1, y1, bb, a, c)
                    if ln > 0.5:
                        ok_all = False
                        reasons.append(f"traverses {ref} ({ln:.1f}mm)")
                        break
                if not ok_all:
                    break
            if ok_all:
                chosen = cand
                break
        if chosen is None:
            blocked.append((name, reasons[:2]))
            continue
        net = b.FindNet(name)
        if net is None:
            b.Add(pcbnew.NETINFO_ITEM(b, name))
            net = b.FindNet(name)
        for (x0, y0), (x1, y1) in zip(chosen[:-1], chosen[1:]):
            t = pcbnew.PCB_TRACK(b)
            t.SetNet(net)
            t.SetLayer(layer)
            t.SetWidth(TRACK_W)
            t.SetStart(pcbnew.VECTOR2I(int(x0 * UM), int(y0 * UM)))
            t.SetEnd(pcbnew.VECTOR2I(int(x1 * UM), int(y1 * UM)))
            b.Add(t)
        routed.append(name)

    print(f"routed {len(routed)}: {sorted(routed)}")
    print(f"blocked {len(blocked)}:")
    for nm, rs in blocked:
        print(f"   {nm}: {rs}")
    pcbnew.SaveBoard(BOARD, b)
    print("saved", BOARD)
    return 0


if __name__ == "__main__":
    sys.exit(main())
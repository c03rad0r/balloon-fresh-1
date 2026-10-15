#!/usr/bin/env python3
"""Can C0's ORIENTATION be changed so its GND pad stops blocking the path to L1?

THE BLOCKER, measured: C0 is a two-terminal shunt on /SX1280_RF with pad1 = RF and pad2 = GND. At the
current site its GND pad (pad2) faces toward L1, so every route from U4.pad22 to L1's series pad must
pass C0's ground terminal. That is a geometry problem about ORIENTATION, not about FIT -- and the two
prior placement scripts only ever tested fit.

Prior work used a crude hand-built pad model for the rotated case, so its negative result is not
trustworthy. This reads the ACTUAL pad geometry of C0 and L1 from the board, then evaluates all four
90-degree orientations of C0 at candidate sites, testing the real connecting legs.

For each candidate: the node is  pad22 -- C0.RF_pad -- L1.RF_pad  and the legs must be clear at the
target width. C0's GND pad is a legal obstacle for those legs (it must be cleared), which is exactly
the constraint that failed before.

Read-only. Prints ranked candidates.
"""
import math
import sys

import pcbnew

CLEAR = 0.20
NECK = 0.300
WIDE = 0.364
ROTATIONS = [0, 90, 180, 270]
GRID = 0.20


def mm(v):
    return pcbnew.ToMM(v)


def pad_geom(board, ref):
    """Real pad geometry, relative to the footprint origin, with nets."""
    fp = board.FindFootprintByReference(ref)
    o = fp.GetPosition()
    ox, oy = mm(o.x), mm(o.y)
    out = []
    for p in fp.Pads():
        c = p.GetPosition()
        s = p.GetSize()
        out.append((str(p.GetNumber()), p.GetNetname(),
                    mm(c.x) - ox, mm(c.y) - oy, mm(s.x), mm(s.y)))
    return out, (ox, oy)


def rotate(dx, dy, deg):
    r = math.radians(deg)
    # KiCad rotates counter-clockwise in board coords where +y is DOWN, so use -sin for y
    return (dx * math.cos(r) + dy * math.sin(r),
            -dx * math.sin(r) + dy * math.cos(r))


def pad_boxes_at(pg, origin, deg):
    """Absolute pad boxes for a part placed at `origin` rotated by deg."""
    ox, oy = origin
    boxes = []
    for num, net, dx, dy, sx, sy in pg:
        rdx, rdy = rotate(dx, dy, deg)
        cx, cy = ox + rdx, oy + rdy
        if deg in (90, 270):
            sx, sy = sy, sx
        boxes.append((num, net, cx - sx / 2, cy - sy / 2, cx + sx / 2, cy + sy / 2))
    return boxes


def seg_clear(seg, width, own_net, obs, clearance):
    half = width / 2.0
    (ax, ay), (bx, by) = seg
    vx, vy = bx - ax, by - ay
    worst = None
    for ref, num, net, x0, y0, x1, y1 in obs:
        if net == own_net:
            continue
        for i in range(41):
            t = i / 40.0
            px, py = ax + t * vx, ay + t * vy
            dx = max(0.0, max(x0 - px, px - x1))
            dy = max(0.0, max(y0 - py, py - y1))
            d = math.hypot(dx, dy)
            need = clearance + half
            if d < need:
                pen = need - d
                if worst is None or pen > worst[0]:
                    worst = (pen, f"{ref}.{num} {net}")
    return worst


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"
    b = pcbnew.LoadBoard(path)
    fp22 = b.FindFootprintByReference("U4")
    p22 = next(p for p in fp22.Pads() if str(p.GetNumber()) == "22")
    a = (mm(p22.GetPosition().x), mm(p22.GetPosition().y))
    cy = fp22.GetCourtyard(pcbnew.F_CrtYd)
    bb = cy.BBox()
    ux0, uy0, ux1, uy1 = mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())
    print(f"board: {path}")
    print(f"U4.pad22 {a}   courtyard y bottom {uy1:.2f}\n")

    c0_pg, c0_o = pad_geom(b, "C0")
    l1_pg, l1_o = pad_geom(b, "L1")
    print("C0 pads (num, net, dx, dy, sx, sy):")
    for t in c0_pg:
        print(f"   {t}")
    print("L1 pads (num, net, dx, dy, sx, sy):")
    for t in l1_pg:
        print(f"   {t}")

    # obstacles = everything except C0 and L1
    obs_base = []
    for fp in b.GetFootprints():
        if fp.GetReference() in ("C0", "L1"):
            continue
        for p in fp.Pads():
            r = p.GetBoundingBox()
            obs_base.append((fp.GetReference(), str(p.GetNumber()), p.GetNetname(),
                             mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom())))

    results = []
    # scan a band below U4's courtyard; x both sides of pad22
    ys = [uy1 + 0.60 + GRID * k for k in range(0, 16)]
    xs = [a[0] + GRID * k for k in range(-14, 15)]
    for c0deg in ROTATIONS:
        for c0x in xs:
            for c0y in ys:
                c0b = pad_boxes_at(c0_pg, (c0x, c0y), c0deg)
                # C0 must be outside U4's courtyard
                cb = (min(t[2] for t in c0b), min(t[3] for t in c0b),
                      max(t[4] for t in c0b), max(t[5] for t in c0b))
                inside = not (cb[2] + CLEAR <= ux0 or cb[0] - CLEAR >= ux1
                              or cb[3] + CLEAR <= uy0 or cb[1] - CLEAR >= uy1)
                if inside:
                    continue
                # C0's own pads must clear everything except the RF net and their own GND
                ok = True
                for num, net, x0, y0, x1, y1 in c0b:
                    w = seg_clear(((x0, y0), (x1, y1)), 0.0, net, obs_base, CLEAR) if False else None
                    worst = None
                    for ref, rnum, rnet, ax, ay, bx, by in obs_base:
                        if rnet == net:
                            continue
                        dx = max(0.0, max(ax - x1, x0 - bx))
                        dy = max(0.0, max(ay - y1, y0 - by))
                        if math.hypot(dx, dy) < CLEAR:
                            ok = False
                            break
                    if not ok:
                        break
                if not ok:
                    continue
                rf_pad_c0 = next((t for t in c0b if t[1] == "/SX1280_RF"), None)
                if rf_pad_c0 is None:
                    continue
                c0rf = ((rf_pad_c0[2] + rf_pad_c0[4]) / 2, (rf_pad_c0[3] + rf_pad_c0[5]) / 2)
                # now try L1 sites to the right of C0
                for l1deg in ROTATIONS:
                    for l1x in [c0x + GRID * k for k in range(3, 22)]:
                        for l1y in [c0y - 0.4, c0y, c0y + 0.4]:
                            l1b = pad_boxes_at(l1_pg, (l1x, l1y), l1deg)
                            lb = (min(t[2] for t in l1b), min(t[3] for t in l1b),
                                  max(t[4] for t in l1b), max(t[5] for t in l1b))
                            if not (0.6 < lb[0] and lb[2] < 69.4 and 0.6 < lb[1] and lb[3] < 69.4):
                                continue
                            if not (lb[2] + CLEAR <= ux0 or lb[0] - CLEAR >= ux1
                                    or lb[3] + CLEAR <= uy0 or lb[1] - CLEAR >= uy1):
                                continue
                            if (not (cb[2] + CLEAR <= lb[0] or cb[0] - CLEAR >= lb[2]
                                     or cb[3] + CLEAR <= lb[1] or cb[1] - CLEAR >= lb[3])):
                                continue
                            l1rf = next((t for t in l1b if t[1] == "/SX1280_RF"), None)
                            if l1rf is None:
                                continue
                            l1p = ((l1rf[2] + l1rf[4]) / 2, (l1rf[3] + l1rf[5]) / 2)
                            obs = list(obs_base) + [("C0", t[0], t[1], t[2], t[3], t[4], t[5])
                                                    for t in c0b] \
                                                + [("L1", t[0], t[1], t[2], t[3], t[4], t[5])
                                                   for t in l1b]
                            w1 = seg_clear((a, c0rf), NECK, "/SX1280_RF", obs, CLEAR)
                            if w1:
                                continue
                            w2 = seg_clear((c0rf, l1p), WIDE, "/SX1280_RF", obs, CLEAR)
                            if w2:
                                continue
                            span = math.hypot(l1p[0] - a[0], l1p[1] - a[1])
                            results.append((span, c0deg, c0x, c0y, l1deg, l1x, l1y, c0rf, l1p))
    results.sort()
    print(f"\nroutable combinations found: {len(results)}")
    for r in results[:5]:
        span, c0deg, c0x, c0y, l1deg, l1x, l1y, c0rf, l1p = r
        print(f"  span {span:5.2f} mm  C0 rot {c0deg:3d} at ({c0x:.2f},{c0y:.2f}) rf@({c0rf[0]:.2f},{c0rf[1]:.2f})"
              f"   L1 rot {l1deg:3d} at ({l1x:.2f},{l1y:.2f}) rf@({l1p[0]:.2f},{l1p[1]:.2f})")
    if results:
        r = results[0]
        print("\nSITES (footprint origins) FOR move_rf_match.py:")
        print(f'    "C0": ({r[2]:.2f}, {r[3]:.2f}),   # rotation {r[1]} deg')
        print(f'    "L1": ({r[5]:.2f}, {r[6]:.2f}),   # rotation {r[4]} deg')
    return 0


if __name__ == "__main__":
    sys.exit(main())

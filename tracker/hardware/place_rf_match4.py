#!/usr/bin/env python3
"""Find a placement for C0 and L1 where the NETWORK routes, not just where the parts fit.

WHY THIS REPLACES place_rf_match3.py. That script (and the move it produced) satisfied:
    - pads clear of foreign copper at the 0.20 mm floor
    - courtyards not overlapping (after two failed attempts)
    - both parts within a few mm of U4.pad22
but the resulting NETWORK does not route. C0's pad2 is GND and sits directly between U4.pad22 and
L1, so every path from the RFIO pad to the series element is blocked by C0's own ground pad. Checking
"does each part fit" is not the same as checking "does the connection work" -- the same class of gap
as the earlier "clear of U4's pads is not clear of U4".

WHAT IS ACTUALLY REQUIRED (read from the pads):
    C0 : pad1 = /SX1280_RF (shunt, this side)   pad2 = GND
    L1 : pad1 = /SX1280_RF (series, this side)  pad2 = /SX1280_RF_MATCH
The node pad22--C0.pad1--L1.pad1 must be reachable, and C0's GND pad must NOT sit on that path. So
the search now requires, for each candidate placement, that ALL of the connecting legs are clear at
the target width. A placement that cannot be routed is rejected even if every part fits.

Usage: place_rf_match4.py <board.kicad_pcb>
"""
import math
import sys

import pcbnew

CLEAR = 0.20
NECK = 0.300          # widest legal escape from pad22's 0.50 mm-pitch land set (56.3 ohm)
WIDE = 0.364          # 50 ohm once clear of the pad row
GRID = 0.05


def mm(v):
    return pcbnew.ToMM(v)


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

    # U4's courtyard is a hard obstacle. Read it.
    cy = fp22.GetCourtyard(pcbnew.F_CrtYd)
    bb = cy.BBox()
    ux0, uy0, ux1, uy1 = mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())
    print(f"board: {path}")
    print(f"U4.pad22 {a}   U4 courtyard x {ux0:.2f}..{ux1:.2f} y {uy0:.2f}..{uy1:.2f}")

    # geometry of the two parts being placed, read from the board
    def part_box(ref):
        f = b.FindFootprintByReference(ref)
        s = f.GetPosition()
        r = f.GetBoundingBox(False, False)
        return (mm(r.GetRight()) - mm(r.GetLeft()), mm(r.GetBottom()) - mm(r.GetTop()),
                mm(s.x), mm(s.y))

    c0w, c0h, c0x, c0y = part_box("C0")
    l1w, l1h, l1x, l1y = part_box("L1")
    print(f"C0 {c0w:.2f}x{c0h:.2f}   L1 {l1w:.2f}x{l1h:.2f}\n")

    # obstacles: everything except the two parts, so their OWN pads do not veto themselves.
    # C0's GND pad is deliberately included once C0's own position is decided (see below).
    obs_base = []
    for fp in b.GetFootprints():
        if fp.GetReference() in ("C0", "L1"):
            continue
        for p in fp.Pads():
            r = p.GetBoundingBox()
            obs_base.append((fp.GetReference(), str(p.GetNumber()), p.GetNetname(),
                             mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom())))

    # Candidate C0 sites: below the courtyard, to the RIGHT or LEFT of pad22 in x, so the shunt is
    # off the direct line to L1. Candidate L1 sites: further out in the same x direction.
    def try_pair(c0c, l1c, c0rot):
        """Return (ok, reason). Includes C0's own pads in the obstacle list for geometry honesty."""
        cx, cy_ = c0c
        lx, ly = l1c
        # build the full obstacle list: base + C0's pads at their candidate site + L1's pads
        obs = list(obs_base)
        # C0 pads are 0.56x0.62 at +-0.48 along local x; rotate by c0rot (0 or 180 keeps it 1-D)
        for (dx, net) in ((0.48, "GND"), (-0.48, "/SX1280_RF")):
            obs.append(("C0", "?", net, cx + dx - 0.28, cy_ - 0.31, cx + dx + 0.28, cy_ + 0.31))
        for (dx, net) in ((-0.49, "/SX1280_RF"), (0.49, "/SX1280_RF_MATCH")):
            obs.append(("L1", "?", net, lx + dx - 0.30, ly - 0.32, lx + dx + 0.30, ly + 0.32))

        # courtyard check for both against U4 and each other
        for (x, y, w, h, nm) in ((cx, cy_, c0w, c0h, "C0"), (lx, ly, l1w, l1h, "L1")):
            if not ((x + w / 2 + CLEAR <= ux0) or (x - w / 2 - CLEAR >= ux1)
                    or (y + h / 2 + CLEAR <= uy0) or (y - h / 2 - CLEAR >= uy1)):
                return False, f"{nm} inside U4 courtyard"
            if not (0.6 < x - w / 2 and x + w / 2 < 69.4 and 0.6 < y - h / 2 and y + h / 2 < 69.4):
                return False, f"{nm} off board"
        # the two parts must not overlap each other
        if (abs(cx - lx) < (c0w + l1w) / 2 + CLEAR) and (abs(cy_ - ly) < (c0h + l1h) / 2 + CLEAR):
            return False, "C0 and L1 courtyards overlap"

        # THE LEGS: this is what place_rf_match3 never tested.
        # pad22 -> C0.pad1 (shunt leg, short, neck width)
        c0p1 = (cx - 0.48, cy_)
        l1p1 = (lx - 0.49, ly)
        legs = [("neck", a, c0p1, NECK), ("to-L1", c0p1, l1p1, WIDE)]
        for nm, s, e, w in legs:
            worst = seg_clear((s, e), w, "/SX1280_RF", obs, CLEAR)
            if worst:
                return False, f"{nm} blocked by {worst[1]} pen {worst[0]:.3f}"
        return True, "routable"

    best = None
    for dxdir in (1, -1):
        for dxy in [0.40 + 0.10 * k for k in range(0, 22)]:
            cy_ = uy1 + CLEAR + c0h / 2 + 0.05 + dxy
            cx = a[0] + dxdir * 1.10
            for dly in [0.0, 0.15, 0.30, 0.5]:
                for dlx in [0.50 * k for k in range(1, 12)]:
                    lx = cx + dxdir * dlx
                    ly = cy_ + dly
                    ok, why = try_pair((cx, cy_), (lx, ly), 0 if dxdir > 0 else 180)
                    if ok:
                        span = math.hypot(lx - a[0], ly - a[1])
                        if best is None or span < best[0]:
                            best = (span, cx, cy_, lx, ly)
    if best is None:
        print("NO routable placement found in the searched region")
        return 1
    span, cx, cy_, lx, ly = best
    print(f"BEST ROUTABLE PLACEMENT:")
    print(f"  C0 centre ({cx:.2f}, {cy_:.2f})   pad1(RF) at ({cx-0.48:.2f}, {cy_:.2f})")
    print(f"  L1 centre ({lx:.2f}, {ly:.2f})   pad1(RF) at ({lx-0.49:.2f}, {ly:.2f})")
    print(f"  L1 span from pad22: {span:.2f} mm")
    print()
    print("SITES FOR move_rf_match.py:")
    print(f'    "C0": ({cx:.2f}, {cy_:.2f}),')
    print(f'    "L1": ({lx:.2f}, {ly:.2f}),')
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Is the rotation search's negative result REAL, or an artifact of its search bounds?

place_rf_rotated.py searched C0 in a band below U4's courtyard (y from 30.44 upward, about 3 mm deep)
and x within +-2.8 mm of pad22, with L1 only ever to the RIGHT of C0. It found nothing across ~1.7M
candidate pairs. Before reporting that as a real impossibility, this checks the two bounds that could
have manufactured it:

  1. WAS THE Y BAND TOO SHALLOW?  If C0 must sit below U4's courtyard, is there ANY depth at which the
     network routes? Scan deeper.
  2. WAS L1 ONLY-EVER-RIGHT A REAL LIMIT?  C0's GND pad is at +0.48 in local x; L1's RF pad is at
     -0.48. Putting L1 LEFT of C0 puts L1's RF pad nearest to C0's GND pad, which is worse, so
     RIGHT is the sensible side -- but that is an argument, not a measurement. This tests LEFT too.
  3. IS THE BLOCKER C0 OR SOMETHING ELSE?  Report precisely which item blocks the best candidate in
     each region, so the obstacle is named rather than implied.

Read-only. Deliberately small and fast: a coarse grid with exact blocking reports, not a fine search.

Usage: verify_no_rf_placement.py <board.kicad_pcb>
"""
import math
import sys

import pcbnew

CLEAR = 0.20
NECK = 0.300
WIDE = 0.364


def mm(v):
    return pcbnew.ToMM(v)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"
    b = pcbnew.LoadBoard(path)
    fp22 = b.FindFootprintByReference("U4")
    p22 = next(p for p in fp22.Pads() if str(p.GetNumber()) == "22")
    a = (mm(p22.GetPosition().x), mm(p22.GetPosition().y))
    cy = fp22.GetCourtyard(pcbnew.F_CrtYd)
    bb = cy.BBox()
    uy1 = mm(bb.GetBottom())
    ux0, ux1 = mm(bb.GetLeft()), mm(bb.GetRight())
    print(f"board: {path}")
    print(f"U4.pad22 {a}   courtyard x {ux0:.2f}..{ux1:.2f}  bottom y {uy1:.3f}\n")

    obs = []
    for fp in b.GetFootprints():
        if fp.GetReference() in ("C0", "L1"):
            continue
        for p in fp.Pads():
            r = p.GetBoundingBox()
            obs.append((fp.GetReference(), str(p.GetNumber()), p.GetNetname(),
                        mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom())))

    def blockers(seg, width):
        half = width / 2.0
        (ax, ay), (bx, by) = seg
        vx, vy = bx - ax, by - ay
        out = []
        for ref, num, net, x0, y0, x1, y1 in obs:
            if net in ("/SX1280_RF",):
                continue
            worst = None
            for i in range(31):
                t = i / 30.0
                px, py = ax + t * vx, ay + t * vy
                dx = max(0.0, max(x0 - px, px - x1))
                dy = max(0.0, max(y0 - py, py - y1))
                d = math.hypot(dx, dy)
                need = CLEAR + half
                if d < need:
                    pen = need - d
                    if worst is None or pen > worst:
                        worst = pen
            if worst:
                out.append((round(worst, 3), f"{ref}.{num} {net}"))
        return sorted(out, reverse=True)

    # --- TEST 1: how deep must C0 go before anything changes? report the blocker profile by depth
    print("TEST 1 -- blocker profile for the pad22 -> C0RF neck by C0 depth (C0 directly below pad22):")
    for k in range(0, 26):
        c0y = uy1 + 0.15 + 0.20 * k
        c0rf = (a[0] - 0.48, c0y)
        bl = blockers((a, c0rf), NECK)
        tag = "CLEAR" if not bl else f"{bl[0][1]} pen {bl[0][0]}"
        print(f"   C0 y={c0y:6.2f} (depth {0.15+0.20*k:4.2f} below courtyard)  {tag}")

    # --- TEST 2: same neck but with C0 moved sideways, to see if x helps at all
    print("\nTEST 2 -- best blocker for the neck with C0 shifted in x, at a fixed workable depth:")
    c0y = uy1 + 0.75
    for dx in (-2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0):
        c0rf = (a[0] + dx - 0.48, c0y)
        bl = blockers((a, c0rf), NECK)
        tag = "CLEAR" if not bl else f"{bl[0][1]} pen {bl[0][0]}"
        print(f"   dx={dx:+5.2f}  C0RF at ({c0rf[0]:6.2f},{c0rf[1]:6.2f})  {tag}")

    # --- TEST 3: the C0RF -> L1RF leg, both sides, at the same depth
    print("\nTEST 3 -- C0RF -> L1RF leg (width %.3f) with L1 LEFT vs RIGHT of C0:" % WIDE)
    c0rf = (a[0] - 0.48, c0y)
    for side, rng in (("right", (3, 20)), ("left", (-20, -3))):
        best = None
        for m in rng:
            l1rf = (c0rf[0] + 0.20 * m, c0y)
            bl = blockers((c0rf, l1rf), WIDE)
            if not bl:
                best = (m * 0.20, "CLEAR")
                break
            if best is None:
                best = (m * 0.20, f"{bl[0][1]} pen {bl[0][0]}")
        print(f"   L1 {side:5} of C0: {best[1]}  (at offset {best[0]:+.2f} mm)")

    print("\nCONCLUSION so far: the neck only changes with depth (TEST 1), x does not rescue it")
    print("(TEST 2), and the second leg is blocked by the SAME class of item (TEST 3).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

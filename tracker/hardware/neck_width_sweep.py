#!/usr/bin/env python3
"""What is the widest neck that ACTUALLY clears U4's flanking GND pads, and does it route?

verify_no_rf_placement.py named the blocker precisely: the neck from U4.pad22 to C0's RF pad is
stopped by U4.pad23 (and pad21 on the other side) -- the GND pads that flank pad22 on a 0.50 mm pitch
land set. The previous search failed while using NECK = 0.300 mm, but a 0.300 mm trace out of a
0.50 mm-pitch land leaves only 0.100 mm clearance, BELOW the board's 0.20 mm floor. So that search
was testing an impossible width and its negative result says nothing about a legal width.

This script sweeps the neck width DOWNWARD from the pitch limit and reports, for each width, the
best depth and the residual penetration. The width at zero penetration is the answer.

Pitch limit (measured earlier): pad22 is 0.30 mm wide, neighbours are 0.30 mm wide, centre spacing
0.50 mm, so centre-to-neighbour-edge = 0.150 + 0.200 = 0.350 mm and
    w_max = 2 * (0.350 - 0.20) = 0.300 mm  <-- but that assumed the trace runs in the pad's own row.
Running DOWNWARD out of the pad, the constraint is the pad's own 0.30 mm width plus the gap to the
neighbour's edge, which is what this sweep measures directly.

Read-only.

Usage: neck_width_sweep.py <board.kicad_pcb>
"""
import math
import sys

import pcbnew

CLEAR = 0.20
WIDTHS = [0.300, 0.280, 0.260, 0.240, 0.220, 0.200, 0.180, 0.160, 0.150, 0.140]


def mm(v):
    return pcbnew.ToMM(v)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"
    b = pcbnew.LoadBoard(path)
    fp22 = b.FindFootprintByReference("U4")
    p22 = next(p for p in fp22.Pads() if str(p.GetNumber()) == "22")
    c = p22.GetPosition()
    a = (mm(c.x), mm(c.y))
    s = p22.GetSize()
    print(f"board: {path}")
    print(f"U4.pad22 {a}  size {mm(s.x):.2f} x {mm(s.y):.2f} mm  (so the pad's own y extent is "
          f"{a[1]-mm(s.y)/2:.2f}..{a[1]+mm(s.y)/2:.2f})\n")

    obs = []
    for fp in b.GetFootprints():
        if fp.GetReference() in ("C0", "L1"):
            continue
        for p in fp.Pads():
            r = p.GetBoundingBox()
            obs.append((fp.GetReference(), str(p.GetNumber()), p.GetNetname(),
                        mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom())))

    # a "neck" leaves pad22 downward. Model it as a vertical segment from the pad's bottom edge.
    pad_bottom = a[1] + mm(s.y) / 2.0
    print("neck leaves pad22 DOWNWARD from the pad's bottom edge "
          f"y={pad_bottom:.3f}, at x={a[0]:.2f}\n")
    print(f"  {'width':>7} {'y_end':>7} {'penetration':>12}  blocker")
    for w in WIDTHS:
        half = w / 2.0
        best = None
        for k in range(1, 61):
            y_end = pad_bottom + 0.05 * k
            seg = ((a[0], pad_bottom), (a[0], y_end))
            worst = None
            for ref, num, net, x0, y0, x1, y1 in obs:
                if net == "/SX1280_RF":
                    continue
                for i in range(21):
                    t = i / 20.0
                    px, py = a[0], pad_bottom + (y_end - pad_bottom) * t
                    # treat the trace as its own rectangle
                    tx0, tx1 = px - half, px + half
                    ty0, ty1 = py, py
                    dx = max(0.0, max(x0 - tx1, tx0 - x1))
                    dy = max(0.0, max(y0 - ty1, ty0 - y1))
                    d = math.hypot(dx, dy)
                    need = CLEAR
                    if d < need:
                        pen = need - d
                        if worst is None or pen > worst[0]:
                            worst = (pen, f"{ref}.{num} {net}", d)
            pen = worst[0] if worst else 0.0
            if pen <= 0.0:
                best = (0.0, y_end, "CLEAR", y_end - pad_bottom)
                break
            if best is None or pen < best[0]:
                best = (pen, y_end, worst[1], y_end - pad_bottom)
        pen, y_end, tag, length = best
        mark = "  <-- CLEAR" if pen <= 0 else ""
        print(f"  {w:7.3f} {y_end:7.2f} {pen:12.3f}  {tag}{mark}")
    print()
    print("INTERPRETATION: the first CLEAR row is the widest neck that can escape at the 0.20 mm")
    print("floor. If NO row is clear, pad22 cannot be escaped downward at any width and the match")
    print("must reach it by another layer or by a different local arrangement.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

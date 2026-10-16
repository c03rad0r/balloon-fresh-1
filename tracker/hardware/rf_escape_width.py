#!/usr/bin/env python3
"""What is the MAXIMUM RF trace width that can ESCAPE U4.pad22 within the 0.20 mm floor?

Self-correction check. An earlier claim in this session was "a 0.364 mm trace centred on pad22 leaves
0.318 mm edge clearance". That number came from centre-to-centre spacing (0.50 mm) minus half the
width, which treats the neighbour's CENTRE as its edge. The correct quantity is the EDGE-to-EDGE gap
between pad22 and its neighbours.

U4's land set is a 0.50 mm pitch with 0.30 mm pads, so the true edge gap is much smaller than 0.50 mm.
This measures it and reports the largest width that fits at the 0.20 mm floor.

Read-only.
"""
import sys

import pcbnew


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"
    b = pcbnew.LoadBoard(path)
    fp = b.FindFootprintByReference("U4")

    boxes = {}
    for p in fp.Pads():
        r = p.GetBoundingBox()
        boxes[str(p.GetNumber())] = (
            pcbnew.ToMM(r.GetLeft()), pcbnew.ToMM(r.GetTop()),
            pcbnew.ToMM(r.GetRight()), pcbnew.ToMM(r.GetBottom()),
            p.GetNetname(),
        )

    p22 = boxes["22"]
    print(f"board: {path}")
    print(f"U4.pad22 {p22[4]}  x {p22[0]:.3f}..{p22[2]:.3f}  y {p22[1]:.3f}..{p22[3]:.3f}")
    print()

    # Compare against every other pad on the SAME y row (the escape direction is +y, so the
    # constraint is the lateral neighbours).
    row = []
    for num, (x0, y0, x1, y1, net) in boxes.items():
        if num == "22":
            continue
        # same row: vertical overlap with pad22
        if not (y1 < p22[1] or y0 > p22[3]):
            if x1 <= p22[0]:
                row.append((p22[0] - x1, num, net, "left"))
            elif x0 >= p22[2]:
                row.append((x0 - p22[2], num, net, "right"))
    row.sort()
    print("lateral neighbours on pad22's row (edge-to-edge gap):")
    for gap, num, net, side in row:
        print(f"  pad {num:4} {net:16} {side:5} gap = {gap:.3f} mm")

    print()
    if not row:
        print("no lateral neighbours in the row")
        return 0
    tightest = row[0][0]
    print(f"tightest lateral gap: {tightest:.3f} mm (pad {row[0][1]} {row[0][2]})")
    print()
    # BUG FIXED HERE. The first version computed w_max = 2*(gap - clearance), using the gap between
    # the two pads' EDGES. That understates the room by a whole pad width: the trace is centred on
    # pad22, so the limiting distance is from pad22's CENTRE to the neighbour's edge, i.e.
    #     centre_to_edge = half of pad22's width + the edge gap
    # Version 1 reported "NO WIDTH FITS" for a geometry that does admit a 0.30 mm trace.
    half22 = (p22[2] - p22[0]) / 2.0
    centre_to_edge = half22 + tightest
    print(f"pad22 half-width {half22:.3f} mm + edge gap {tightest:.3f} mm "
          f"= centre-to-neighbour-edge {centre_to_edge:.3f} mm")
    w_max = 2 * (centre_to_edge - 0.20)
    print(f"maximum trace width centred on pad22 at a 0.20 mm floor:")
    print(f"  w_max = 2*({centre_to_edge:.3f} - 0.20) = {w_max:.3f} mm")
    print()
    print("what each candidate width gives:")
    for w in (0.364, 0.35, 0.30, 0.25, 0.20):
        clear = centre_to_edge - w / 2.0
        verdict = "OK" if clear >= 0.20 else "BELOW the 0.20 mm floor"
        print(f"  w = {w:.3f} mm -> clearance {clear:.3f} mm   {verdict}")
    print()
    print("IMPLICATION: if w_max < 0.364 mm then a 50-ohm trace CANNOT escape pad22 while it sits on a")
    print("0.50 mm pitch land set, and the impedance fix must come from the STACKUP (thinner dielectric")
    print("between L1 and L2) or from routing the match on a layer whose reference height differs --")
    print("not from widening the trace on F.Cu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

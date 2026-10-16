#!/usr/bin/env python3
"""Apply the DRC-confirmed C0 rotation and re-gate the whole thing.

CONFIRMED BY MEASUREMENT (test_c0_rotation.py, graded by kicad-cli):

    variant             errors  delta  shorting_items  clearance  legs (mm)
    control (no tracks)   235     --        0            110          --
    rot0  (as placed)     240     +5        1            113      (1.62, 3.00, 2.96)
    rot180                238     +3        0            113      (1.62, 2.04, 2.96)

So rotating C0 by 180 degrees:
  - removes the `shorting_items` fault that the as-placed arrangement created
  - reduces the error delta from +5 to +3
  - shortens the C0.RF -> L1.RF leg from 3.00 mm to 2.04 mm

WHY IT WORKS, in one line: C0 is a two-terminal shunt whose GND pad sat between U4.pad22 and L1's
series pad; rotating it moves that GND pad off the path.

WHAT THIS SCRIPT DOES NOT DO: it does not lay tracks. The board keeps 0 tracks on /SX1280_RF. The
rotation fixes the PLACEMENT so the net CAN be routed; routing it is a separate step, and the required
width is still unknown because the 0.6 mm stackup is undeclared.

Usage: apply_c0_rotation.py <in.kicad_pcb> <out.kicad_pcb>
"""
import sys

import pcbnew

ROT = 180.0


def mm(v):
    return pcbnew.ToMM(v)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    b = pcbnew.LoadBoard(src)

    c0 = b.FindFootprintByReference("C0")
    if c0 is None:
        print("C0 absent")
        return 1
    before = c0.GetOrientationDegrees()

    # Capture the RF pads before, to prove afterwards that the RF pad moved.
    def rfpad(fp):
        for p in fp.Pads():
            if p.GetNetname() == "/SX1280_RF":
                c = p.GetPosition()
                return (round(mm(c.x), 3), round(mm(c.y), 3))
        return None

    pre = rfpad(c0)
    c0.SetOrientationDegrees(before + ROT)
    post = rfpad(c0)
    print(f"C0 orientation {before:.1f} -> {c0.GetOrientationDegrees():.1f} deg")
    print(f"C0 RF pad position {pre} -> {post}")
    if pre == post:
        print("  WARNING: the RF pad did not move; orientation change may not have applied")

    # report the resulting node geometry
    hub = rfpad(b.FindFootprintByReference("U4"))
    l1 = rfpad(b.FindFootprintByReference("L1"))
    import math
    print(f"\nnode geometry after the rotation:")
    print(f"  U4.pad22 {hub}   C0.RF {post}   L1.RF {l1}")
    print(f"  pad22->C0.RF  {math.dist(hub, post):.2f} mm")
    print(f"  C0.RF->L1.RF  {math.dist(post, l1):.2f} mm")

    pcbnew.SaveBoard(dst, b)
    print(f"\nwrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

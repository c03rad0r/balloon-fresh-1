#!/usr/bin/env python3
"""fix_hub_v9_route_v30.py -- align the board's via minimum with JLCPCB's
DOCUMENTED 4-layer standard capability, cleared by the v29 measurement.

FINDING (v29, measured):
  Signal vias 0.50 -> 0.40 took clearance 6 -> 3 (both order-blocking items
  cleared: the via-in-pad overhang shrinks, and the DIO1 escape via drops
  below the 0.20 gap requirement). The residual `via_diameter: 3` is a
  BOARD-FILE rule violation, not a fab limit:
     board file  : min via 0.50 mm, min through-drill 0.30 mm (defaults)
     JLCPCB 4L std: min via 0.40 mm dia / 0.20 mm drill  <-- the actual limit
  So the file was stricter than the fabricator. Aligning it is the correct,
  evidence-backed action -- and it is exactly the class of change ADR-051/055
  says to make deliberately, in the design rules, with the fab citation.

This script:
  1. Sets m_ViasMinSize = 0.40 mm and m_MinThroughDrill = 0.20 mm
     (JLCPCB 4-layer standard minimums; documented in FAB-READINESS).
  2. Prints the before/after values with READBACK so the change is verified.
"""
import argparse
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
VIA_MIN, DRILL_MIN = 0.40, 0.20


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()
    b = pcbnew.LoadBoard(args.inp)
    ds = b.GetDesignSettings()

    def show(label):
        try:
            v = ds.m_ViasMinSize / MM
        except Exception as e:
            v = f"?({e})"
        try:
            d = ds.m_MinThroughDrill / MM
        except Exception as e:
            d = f"?({e})"
        print(f"  {label}: min via = {v} mm, min through-drill = {d} mm")

    show("BEFORE")
    try:
        ds.m_ViasMinSize = int(VIA_MIN * MM)
    except Exception as e:
        print(f"  set m_ViasMinSize failed: {e}")
    try:
        ds.m_MinThroughDrill = int(DRILL_MIN * MM)
    except Exception as e:
        print(f"  set m_MinThroughDrill failed: {e}")
    show("AFTER")

    b.BuildConnectivity()
    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

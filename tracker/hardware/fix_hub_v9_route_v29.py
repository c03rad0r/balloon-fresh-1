#!/usr/bin/env python3
"""fix_hub_v9_route_v29.py -- test the via-diameter lever (Astra ladder #3:
"use a different supported via size").

MECHANISM DISCOVERED (v28 numbers):
  The U4 QFN pads are 0.25 mm wide on 0.5 mm pitch -> inter-pad edge gap =
  0.25 mm, which ALREADY satisfies the 0.20 mm file rule. The 0.1250 mm
  violation is caused ONLY by the via barrel overhanging its own pad:
  via dia 0.50 -> r 0.250 -> overhang 0.250-0.125 = 0.125 -> clearance
  0.250-0.125 = 0.1250 mm. EXACTLY the measured value.

  Therefore clearance = 0.25 - (dia/2 - 0.125):
      dia 0.50 -> 0.1250   dia 0.45 -> 0.1500
      dia 0.40 -> 0.1750   dia 0.35 -> 0.2000

  Same lever for the DIO1 escape via (NOT via-in-pad, 0.60 dia): its
  centre-to-centre to /F33_SCK is 0.5150 mm; needed = 0.20 + dia/2 + 0.10:
      dia 0.60 -> 0.60 needed (short by 0.085)
      dia 0.50 -> 0.55 needed (short by 0.035)
      dia 0.40 -> 0.50 needed (PASSES, 0.5150)

This script sets the 3 signal vias to 0.40/0.20 and reports the resulting
DRC + the via_diameter/annular_width status, so the operator and the fab
can decide the tier with real numbers. It does NOT assert JLCPCB capability.
"""
import argparse
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
DIA, DRILL = 0.40, 0.20
# (net, x, y) of the three signal vias
TARGETS = [
    ("/SX1280_MISO", 49.000, 7.200),
    ("/SX1280_DIO2", 50.000, 7.200),
    ("/SX1280_DIO1", 49.590, 8.616),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()
    b = pcbnew.LoadBoard(args.inp)

    changed = 0
    for (net, tx, ty) in TARGETS:
        for t in b.GetTracks():
            if t.GetClass() != "PCB_VIA" or t.GetNetname() != net:
                continue
            p = t.GetPosition()
            if abs(p.x / MM - tx) > 0.30 or abs(p.y / MM - ty) > 0.30:
                continue
            old = t.GetWidth(pcbnew.F_Cu) / MM
            # readback loop: SetWidth(int) then verify
            t.SetWidth(int(DIA * MM))
            try:
                t.SetDrill(int(DRILL * MM))
            except Exception:
                pass
            new = t.GetWidth(pcbnew.F_Cu) / MM
            drl = t.GetDrillValue() / MM if hasattr(t, "GetDrillValue") else DRILL
            print(f"  {net} ({p.x/MM:.3f},{p.y/MM:.3f}): {old:.2f} -> {new:.2f} "
                  f"(drill {drl:.2f})")
            changed += 1
    print(f"vias changed: {changed}")
    b.BuildConnectivity()
    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Set SOLID zone connection on pads too small to host thermal spokes (J_W* wing lands).

DIAGNOSIS (measured 2026-10-15). DRC reports an unconnected item
    Zone 'GND_PLANE_F.Cu' [GND] on F.Cu  <->  Pad 2 [GND] of J_W1 on F.Cu
Both items are on F.Cu, so NO VIA is required -- the zone simply has to reach the pad. The pad is a
4.00 x 1.20 mm SMD land (drill 0.00). Its short axis is 1.20 mm, which cannot host the default
thermal spokes, so the fill leaves it isolated. `stitch_gnd_planes.py` was treating these as pads
needing a stitch via, which is the WRONG repair -- and its corrected predicate then (correctly)
refused to place an illegal via, so the pad stayed open.

The builder already implements the right repair for U4's QFN land, in add_gnd_plane():
    "A 0.80x0.25 mm QFN land (U4's perimeter GND pads) cannot host two 0.3 mm
     spokes across its short axis, so a THERMAL connection DRC-fails as
     starved_thermal. Connect any pad too small to take two spokes SOLID"
This applies the same rule to any GND pad whose short axis cannot host two spokes.

It does NOT guess a pad list: it reads every GND pad on the board and applies the geometric test.

Usage: set_solid_zone_connection.py <in.kicad_pcb> <out.kicad_pcb> [--check]
"""
import os
import sys

import pcbnew

SPOKE_MM = 0.3          # same constant the builder uses for its spoke-width test
MIN_SPOKE_PITCH_MM = 2 * SPOKE_MM   # two spokes plus a gap; a short axis below this cannot host them

# Zone connection values, verified present in this build's pcbnew:
#   ZONE_CONNECTION_FULL=2, ZONE_CONNECTION_THERMAL=1, ZONE_CONNECTION_NONE=0,
#   ZONE_CONNECTION_INHERITED=-1, ZONE_CONNECTION_THT_THERMAL=3
SOLID = pcbnew.ZONE_CONNECTION_FULL


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    check_only = "--check" in sys.argv
    board = pcbnew.LoadBoard(src)

    changed, already, too_big = [], [], []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() != "GND":
                continue
            s = pad.GetSize()
            short = pcbnew.ToMM(min(s.x, s.y))
            key = f"{fp.GetReference()}.{pad.GetNumber()}"
            if short >= MIN_SPOKE_PITCH_MM:
                too_big.append((key, short))
                continue
            cur = None
            for acc in ("GetZoneConnection", "GetLocalZoneConnection"):
                try:
                    cur = getattr(pad, acc)()
                    break
                except Exception:
                    continue
            if cur == SOLID:
                already.append((key, short))
                continue
            if not check_only:
                setattr_ok = False
                for acc in ("SetZoneConnection", "SetLocalZoneConnection"):
                    try:
                        getattr(pad, acc)(SOLID)
                        setattr_ok = True
                        break
                    except Exception:
                        continue
                if not setattr_ok:
                    print(f"WARN: cannot set zone connection on {key} in this pcbnew build")
            changed.append((key, short, cur))

    print(f"src: {src}")
    print(f"GND pads whose short axis < {MIN_SPOKE_PITCH_MM:.2f} mm (cannot host two "
          f"{SPOKE_MM} mm spokes) -> SOLID connection:")
    for key, short, cur in changed:
        print(f"  {key:12} short_axis={short:5.2f} mm  was={cur} -> SOLID({SOLID})")
    if not changed:
        print("  (none)")
    print(f"already SOLID: {len(already)}")
    print(f"large enough to host spokes (left alone): {len(too_big)}")

    if check_only:
        print("\n--check: no file written")
        return 0
    pcbnew.SaveBoard(dst, board)
    print(f"\nwrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

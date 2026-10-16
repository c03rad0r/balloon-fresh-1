#!/usr/bin/env python3
"""Report the two remaining test failures' causes: C2 (packaged vs committed hub board) and F (base station)."""
import os

import pcbnew

HW = "tracker/hardware"
COMMITTED = os.path.join(HW, "hub_board_v9.kicad_pcb")
PACKAGED = os.path.join("docs", "fab", "hub-v9", "gerbers", "hub_v9.kicad_pcb")
BS = os.path.join(HW, "base_station", "output")


def refs(p):
    if not os.path.exists(p):
        return None
    b = pcbnew.LoadBoard(p)
    return set(f.GetReference() for f in b.GetFootprints()) if b else None


print("=== C2: packaged vs committed hub board ===")
print(f"  committed {COMMITTED} exists: {os.path.exists(COMMITTED)}")
print(f"  packaged  {PACKAGED} exists: {os.path.exists(PACKAGED)}")
c, p = refs(COMMITTED), refs(PACKAGED)
if c and p:
    print(f"  committed {len(c)} footprints | packaged {len(p)} footprints")
    miss = sorted(c - p)
    print(f"  missing from the package: {len(miss)} -> {miss[:12]}")
elif c and not p:
    print("  the packaged board file is ABSENT -> C2 fails for that reason alone")

print()
print("=== F: the base-station route artifacts the test expects ===")
for f, expect in (("bs_v1_routed.kicad_pcb", "must measure DIRTY (rejected route)"),
                  ("bs_v1_strict.kicad_pcb", "must measure CLEAN (good route)")):
    path = os.path.join(BS, f)
    print(f"  {f:28} exists={os.path.exists(path)}   expects: {expect}")
print(f"  base_station/output listing: {sorted(os.listdir(BS)) if os.path.isdir(BS) else 'DIR ABSENT'}")

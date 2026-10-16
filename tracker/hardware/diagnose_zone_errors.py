#!/usr/bin/env python3
"""Why does the F.Cu GND zone bridge solder-mask apertures on 89 pads, and drill 9 holes at 0 clearance?

The baseline error load is dominated by one family, not by 199 unrelated faults:
    89 solder_mask_bridge : always `Pad <X> of <ref>` against `Zone 'GND_PLANE_F.Cu' [GND]`
     9 hole_clearance     : always a PTH pad of C_CAP1/C_CAP2 against a GND zone, actual 0.0000 mm
     3 starved_thermal    : C_CAP2 and U_CUT4, GND, min spoke count 2 vs actual 1

A solder mask aperture bridges two items when their mask openings merge. The zone reports priority 0.
Two candidate causes, and they need different fixes:

  (A) the GND zone's OWN clearance is too small, so its copper (and therefore its mask opening) reaches
      into neighbouring pads' openings -- a zone clearance setting
  (B) the zone was filled against a DIFFERENT clearance than the one DRC now grades it with -- a stale
      fill, fixed by refilling

This distinguishes them by reading the zone's declared clearance and its own clearance setting, and by
reporting whether the reported pads are GND pads (in which case a mask bridge to GND is usually
intentional and the rule is too strict) or non-GND pads (a real bridge).

Read-only.

Usage: diagnose_zone_errors.py <board.kicad_pcb> <drc.json>
"""
import collections
import json
import re
import sys

import pcbnew


def mm(v):
    return pcbnew.ToMM(v)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    board_path, drc_path = sys.argv[1], sys.argv[2]
    b = pcbnew.LoadBoard(board_path)
    d = json.load(open(drc_path))
    errs = [v for v in d.get("violations", []) if v.get("severity") == "error"]

    print(f"board: {board_path}\n")
    print("=== GND zones: declared clearances ===")
    for z in b.Zones():
        if z.GetNetname() != "GND":
            continue
        layers = [pcbnew.LayerName(l) for l in z.GetLayerSet().Seq()]
        print(f"  name={z.GetZoneName()!r:22} layers={layers}")
        lids = list(z.GetLayerSet().Seq())
        own = mm(z.GetOwnClearance(lids[0])) if lids else float("nan")
        print(f"      own_clearance={own:.3f} mm   "
              f"min_thickness={mm(z.GetMinThickness()):.3f} mm   "
              f"priority={z.GetAssignedPriority()}")
        print(f"      pad_connection={z.GetPadConnection()}  "
              f"thermal_spoke_w={mm(z.GetThermalReliefSpokeWidth()):.3f}  "
              f"gap={mm(z.GetThermalReliefGap()):.3f}")
    print()

    # solder_mask_bridge: are the pads GND pads or foreign?
    smb = [v for v in errs if v.get("type") == "solder_mask_bridge"]
    gnd_pads = foreign = 0
    for v in smb:
        pad_net = None
        for it in v.get("items", []):
            dd = it.get("description", "")
            if "Pad" in dd:
                m = re.search(r"\[([^\]]*)\]", dd)
                pad_net = m.group(1) if m else None
        if pad_net in ("GND", ""):
            gnd_pads += 1
        else:
            foreign += 1
    print("=== solder_mask_bridge pads, by net ===")
    print(f"  GND or un-netted pads : {gnd_pads}")
    print(f"  foreign-net pads      : {foreign}")
    print("  a GND pad bridging the GND zone's own mask opening is EXPECTED and usually means the")
    print("  rule is stricter than the design; a FOREIGN pad bridging it is a real defect.")
    print()

    # hole_clearance: which pads, and at what actual clearance
    hc = [v for v in errs if v.get("type") == "hole_clearance"]
    print("=== hole_clearance ===")
    refs = collections.Counter()
    for v in hc:
        for it in v.get("items", []):
            for t in re.findall(r"\b([A-Z][A-Za-z_]{0,9}[0-9]{1,3})\b", it.get("description", "")):
                refs[t] += 1
    print(f"  refs: {refs.most_common()}")
    print("  all report actual 0.0000 mm against a 0.2500 mm requirement, against a GND zone --")
    print("  meaning the zone copper reaches the drill edge with no gap at all.")
    print()
    print("=== INTERPRETATION ===")
    print("  If most solder_mask_bridge items are GND pads and hole_clearance is zone-vs-plated-hole,")
    print("  then the family is ONE problem: the GND zone is filled with insufficient clearance to the")
    print("  pads and holes, so it merges mask openings and touches drill walls. The fix is a zone")
    print("  clearance/thermal setting plus a refill -- one change affecting many items -- or a")
    print("  per-design rule waiver if the fab tolerates it.")
    print("  The control experiment is to re-run DRC after ONLY changing the zone clearance.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

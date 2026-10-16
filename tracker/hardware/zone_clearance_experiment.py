#!/usr/bin/env python3
"""Control experiment: does raising the GND zone clearance remove the solder_mask_bridge family?

THE MEASURED FAMILY (from the routed control board's DRC):
    89 solder_mask_bridge : ALL against `Pad <X> of <ref>` with a FOREIGN net. ZERO are GND pads, so
                            none of them is benign -- 89 foreign pads have mask openings merging with
                            the GND zone's opening, which on an assembled board means solder can bridge
                            to ground.
     9 hole_clearance     : always a PTH pad of C_CAP1/C_CAP2 against a GND zone at actual 0.0000 mm
                            against a 0.2500 mm requirement.
     3 starved_thermal    : C_CAP2 and U_CUT4, min spoke count 2 vs actual 1.

The zones as configured:
    own_clearance 0.200 mm   min_thickness 0.250 mm   priority 0
    pad_connection THERMAL   spoke width 0.300 mm      thermal gap 0.500 mm

HYPOTHESIS: the mask openings merge because the zone's clearance to foreign copper (0.200 mm) is
smaller than the sum of the mask expansion plus what the apertures need to stay separate. Raising the
zone's own clearance should separate the openings.

CONTROL EXPERIMENT, and it is deliberately SINGLE-VARIABLE: change ONLY the GND zones' own clearance,
refill, re-run DRC, and compare the error classes. If solder_mask_bridge falls and nothing else rises,
the cause is confirmed and the fix is established. If it does not move, the cause is elsewhere and this
hypothesis is killed -- which is the point of running it rather than asserting it.

This script does NOT save a board back to the repo. It writes to /tmp and reports.

Usage: zone_clearance_experiment.py <board.kicad_pcb> [--clearance-mm 0.30]
"""
import json
import os
import shutil
import subprocess
import sys

import pcbnew

WD = "/tmp/zoneexp"


def mm(v):
    return pcbnew.ToMM(v)


def drc(bp):
    oj = bp.replace(".kicad_pcb", "_drc.json")
    subprocess.run(["kicad-cli", "pcb", "drc", bp, "--format", "json", "-o", oj,
                    "--severity-all"], capture_output=True, text=True)
    try:
        d = json.load(open(oj))
    except Exception:
        return None
    c = {}
    for v in d.get("violations", []):
        if v.get("severity") == "error":
            k = v.get("type", "?")
            c[k] = c.get(k, 0) + 1
    return c


def report(tag, c):
    if c is None:
        print(f"  {tag:22} DRC unreadable")
        return None
    tot = sum(c.values())
    print(f"  {tag:22} total {tot:>4}  {json.dumps(c, sort_keys=True)}")
    return tot


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"
    new_clear = 0.30
    if "--clearance-mm" in sys.argv:
        new_clear = float(sys.argv[sys.argv.index("--clearance-mm") + 1])
    os.makedirs(WD, exist_ok=True)
    print(f"board: {src}")
    print(f"single variable under test: GND zones' own clearance -> {new_clear} mm\n")

    # baseline: current clearances, refilled
    base = os.path.join(WD, "base.kicad_pcb")
    b = pcbnew.LoadBoard(src)
    for z in b.Zones():
        if z.GetNetname() == "GND":
            pass
    pcbnew.SaveBoard(base, b)
    for ext in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
        s = src.replace(".kicad_pcb", ext)
        if os.path.exists(s):
            shutil.copy(s, base.replace(".kicad_pcb", ext))
    print("BEFORE:")
    cb = report("as-is (not refilled)", drc(base))

    # refill the baseline, so the comparison is like-for-like
    base_f = os.path.join(WD, "base_f.kicad_pcb")
    subprocess.run(["python3", "tracker/hardware/refill_zones.py", base, base_f],
                   capture_output=True, text=True)
    print()
    report("refilled, clearance unchanged", drc(base_f))

    # the experiment
    exp = os.path.join(WD, f"clr_{int(new_clear*100)}.kicad_pcb")
    b2 = pcbnew.LoadBoard(src)
    n = 0
    for z in b2.Zones():
        if z.GetNetname() != "GND":
            continue
        for lay in z.GetLayerSet().Seq():
            z.SetOwnClearance(lay, int(round(new_clear * 1e6)))
            n += 1
            break
    print(f"\nset clearance on {n} GND zone(s)")
    pcbnew.SaveBoard(exp, b2)
    for ext in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
        s = src.replace(".kicad_pcb", ext)
        if os.path.exists(s):
            shutil.copy(s, exp.replace(".kicad_pcb", ext))
    exp_f = os.path.join(WD, f"clr_{int(new_clear*100)}_f.kicad_pcb")
    subprocess.run(["python3", "tracker/hardware/refill_zones.py", exp, exp_f],
                   capture_output=True, text=True)
    report(f"refilled, clearance {new_clear} mm", drc(exp_f))
    print()
    print("VERDICT RULE: the cause is confirmed only if solder_mask_bridge falls and no other class")
    print("rises by a comparable amount. Otherwise the cause is elsewhere and this hypothesis is dead.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

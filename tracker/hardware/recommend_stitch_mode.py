#!/usr/bin/env python3
"""Compare stitcher modes PER SHAPE and recommend the better one.

WHY NOT A FIXED TABLE. A previous hardcoded pad list in fix_starved_thermal.py was a stale snapshot
of one board revision and silently missed the real error. A hardcoded "offset mode is safe" table
would be the same defect one level up: the answer depends on how much room the CURRENT placement
gives, which changes every time parts move. So measure it.

Decision rule, stated up front: offset mode is recommended ONLY if it strictly reduces unconnected
items AND introduces no error class absent from the centre-only shape. Otherwise centre-only wins,
because on this board the copper_edge_clearance delta is already the largest single error class and
nothing may be allowed to inflate it.

Usage: recommend_stitch_mode.py <strict_routed_board.kicad_pcb> [workdir]
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
KICAD_PY = os.path.expanduser("~/venvs/kicad/bin/python")
DRU = os.path.join(HERE, "jlcpcb-s1-frozen.kicad_dru")
PRO = os.path.join(HERE, "hub_board_v9.kicad_pro")


def run(mode, src, work):
    """Route-free: stitch in `mode`, refill, DRC. Returns (shape_dict, truth_dict)."""
    out = os.path.join(work, f"st_{mode}.kicad_pcb")
    filled = os.path.join(work, f"st_{mode}_filled.kicad_pcb")
    args = [KICAD_PY, os.path.join(HERE, "stitch_gnd_planes.py"), src, out]
    if mode == "offset":
        args.append("--offset")
    r = subprocess.run(args, capture_output=True, text=True, timeout=900)
    shape = {}
    for line in r.stdout.splitlines():
        for k in ("vias at pad centre", "vias OFFSET + GND stub", "pads already stitched",
                  "UNRESOLVABLE"):
            if line.strip().startswith(k):
                shape[k] = int(line.split(":")[1])
    subprocess.run([PY, os.path.join(HERE, "refill_zones.py"), out, filled],
                   capture_output=True, text=True, timeout=900)
    shutil.copy(PRO, filled[:-len(".kicad_pcb")] + ".kicad_pro")
    shutil.copy(DRU, filled[:-len(".kicad_pcb")] + ".kicad_dru")
    jf = os.path.join(work, f"st_{mode}_drc.json")
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all",
                    "-o", jf, filled], capture_output=True, text=True, timeout=900)
    d = json.load(open(jf))
    v = d.get("violations", [])
    truth = {
        "unconnected": len(d.get("unconnected_items", [])),
        "errors": sum(1 for x in v if x.get("severity") == "error"),
        "warnings": sum(1 for x in v if x.get("severity") == "warning"),
        "types": dict(Counter(x.get("type") for x in v)),
    }
    return shape, truth


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = sys.argv[1]
    work = sys.argv[2] if len(sys.argv) > 2 else tempfile.mkdtemp(prefix="stitchcmp-")

    centre = run("centre", src, work)
    offset = run("offset", src, work)

    print("=== stitcher mode comparison (measured on THIS board) ===")
    print(f"  board: {src}")
    print()
    hdr = f"  {'metric':30} {'centre-only':>13} {'offset':>10}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for k, label in (("vias at pad centre", "vias at pad centre"),
                     ("vias OFFSET + GND stub", "vias offset + stub"),
                     ("pads already stitched", "pads already stitched"),
                     ("UNRESOLVABLE", "unresolvable pads")):
        print(f"  {label:30} {centre[0].get(k, 0):>13} {offset[0].get(k, 0):>10}")
    print(f"  {'unconnected items':30} {centre[1]['unconnected']:>13} {offset[1]['unconnected']:>10}")
    print(f"  {'errors':30} {centre[1]['errors']:>13} {offset[1]['errors']:>10}")
    print(f"  {'warnings':30} {centre[1]['warnings']:>13} {offset[1]['warnings']:>10}")
    print()
    alltypes = sorted(set(centre[1]["types"]) | set(offset[1]["types"]))
    print(f"  {'violation type':30} {'centre':>8} {'offset':>8}")
    print("  " + "-" * (len("violation type") + 18))
    for t in alltypes:
        print(f"  {t:30} {centre[1]['types'].get(t,0):>8} {offset[1]['types'].get(t,0):>8}")

    new_types = [t for t in offset[1]["types"] if t not in centre[1]["types"]]
    better_unc = offset[1]["unconnected"] < centre[1]["unconnected"]

    print()
    if offset[1]["errors"] > centre[1]["errors"] and not better_unc:
        rec = "centre-only (offset adds errors and saves nothing)"
    elif new_types:
        rec = f"centre-only (offset introduces NEW error classes: {new_types})"
    elif better_unc and offset[1]["errors"] <= centre[1]["errors"]:
        rec = "offset (fewer unconnected, no new error classes, no more errors)"
    elif better_unc:
        rec = (f"offset is a TRADE ({centre[1]['unconnected']}->{offset[1]['unconnected']} unconnected "
               f"but errors {centre[1]['errors']}->{offset[1]['errors']}) -- operator's call")
    else:
        rec = "centre-only (offset saves nothing)"

    print(f"RECOMMEND: {rec}")
    print()
    print("NOTE: this is a per-run measurement, not a rule. The answer depends on how much room the")
    print("      current placement gives, so it must be re-measured after parts move. A hardcoded")
    print('      "offset is safe" claim would repeat the stale-snapshot defect found in')
    print("      fix_starved_thermal.py (a fixed pad list that missed the pad that was actually broken).")
    print(f"\nartifacts: {work}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Prepare the GUI handoff board: everything fixed except the two nets the operator will route by hand.

TARGET STATE for the handed-over board:
  - 57 of 59 nets routed (the full-route result, 281 vias)
  - starved_thermal cleared (the SOLID-zone-connection rule)
  - the amended CONDITIONLESS edge rule in force, so copper_edge_clearance reads 16 not 30
  - ONLY outstanding: /SX1280_MOSI and /SX1280_SCK unrouted, i.e. 2 unconnected pad pairs

Output goes to a COMMITTABLE path (docs/fab/handoff/) because tracker/hardware/output/ is gitignored
(.gitignore:90) and the operator needs an actual file to open in the GUI.

Also writes the .kicad_dru next to the board under the PROJECT NAME, because that is the filename KiCad
auto-loads; the repo stores the canonical copy as jlcpcb-s1-frozen.kicad_dru and the grade script copies
it into place, so a bare board opened from a new directory would otherwise load NO custom rules.

Usage: prepare_gui_handoff.py [routed_board] [outdir]
"""
import json
import os
import shutil
import subprocess
import sys

import pcbnew

DEFAULT_SRC = "tracker/hardware/output/fabgrade_rfrouted/hub_board_v9_stitched.kicad_pcb"
DEFAULT_OUT = "docs/fab/handoff"
DRU_SRC = "tracker/hardware/jlcpcb-s1-frozen.kicad_dru"


def here():
    return os.path.dirname(os.path.abspath(__file__))


def refill(src, dst):
    subprocess.run(["python3", os.path.join(here(), "refill_zones.py"), src, dst],
                   capture_output=True, text=True)
    return os.path.exists(dst)


def drc(bp):
    oj = bp.replace(".kicad_pcb", "_drc.json")
    subprocess.run(["kicad-cli", "pcb", "drc", bp, "--format", "json", "-o", oj,
                    "--severity-all"], capture_output=True, text=True)
    try:
        d = json.load(open(oj))
    except Exception:
        return None, {}, 0
    c = {}
    for v in d.get("violations", []):
        if v.get("severity") == "error":
            k = v.get("type", "?")
            c[k] = c.get(k, 0) + 1
    return sum(c.values()), c, len(d.get("unconnected_items", []))


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    out = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT
    if not os.path.exists(src):
        print(f"routed source missing: {src}")
        return 1
    os.makedirs(out, exist_ok=True)
    stem = "hub_board_v9"
    print(f"source : {src}")
    print(f"handoff: {out}\n")

    # 1. clear starved_thermal on the routed board
    st_raw = os.path.join(out, f"{stem}_st_raw.kicad_pcb")
    r = subprocess.run(["python3", os.path.join(here(), "clear_starved_thermal.py"),
                        src, st_raw], capture_output=True, text=True)
    if not os.path.exists(st_raw):
        print("  starved_thermal pass produced nothing; continuing from the routed board")
        st_raw = src
    else:
        tail = [l for l in r.stdout.splitlines() if "GATE" in l or "RESULT" in l]
        for l in tail:
            print(f"  {l.strip()}")

    # 2. refill, and place the project + the AMENDED dru under the project name
    final = os.path.join(out, f"{stem}.kicad_pcb")
    if not refill(st_raw, final):
        print("  refill failed")
        return 1
    shutil.copy(DRU_SRC, os.path.join(out, f"{stem}.kicad_dru"))
    for ext in (".kicad_pro", ".kicad_prl"):
        s = src.replace(".kicad_pcb", ext)
        if os.path.exists(s):
            shutil.copy(s, os.path.join(out, stem + ext))
        else:
            s2 = "tracker/hardware/" + stem + ext
            if os.path.exists(s2):
                shutil.copy(s2, os.path.join(out, stem + ext))
    if os.path.exists(st_raw) and st_raw != src:
        os.remove(st_raw)

    # 3. report the handed-over state
    n, c, unc = drc(final)
    print(f"\nHANDOFF BOARD STATE (refilled, amended rule in force):")
    print(f"  errors          : {n}  {json.dumps(c, sort_keys=True)}")
    print(f"  unconnected     : {unc} pad pairs   <- the two nets to route by hand")

    # 4. the two nets' exact pin coordinates, plus the B.Cu escape data
    b = pcbnew.LoadBoard(final)
    print("\nTHE TWO NETS TO ROUTE, with exact pin coordinates:")
    for ref, num in (("U1", "8"), ("U4", "17"), ("U1", "22"), ("U4", "18")):
        fp = b.FindFootprintByReference(ref)
        p = next((q for q in fp.Pads() if str(q.GetNumber()) == num), None)
        if p is None:
            continue
        c2 = p.GetPosition()
        sz = p.GetSize()
        print(f"  {ref}.{num:3} {p.GetNetname():16} at ({pcbnew.ToMM(c2.x):6.2f},"
              f"{pcbnew.ToMM(c2.y):6.2f})  size {pcbnew.ToMM(sz.x):.2f}x{pcbnew.ToMM(sz.y):.2f} mm"
              f"  layer {pcbnew.LayerName(p.GetLayer())}")

    files = sorted(os.listdir(out))
    print(f"\nfiles written to {out}:")
    for f in files:
        print(f"  {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

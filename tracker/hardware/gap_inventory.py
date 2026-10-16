#!/usr/bin/env python3
"""Live inventory of every board in the end-to-end system, measured from the tree.

WHY THIS EXISTS. docs/fab/END-TO-END-BOARD-INVENTORY.md (dated 2026-10-14) asserts:
    - "there is no .kicad_pcb, no .kicad_sch, no netlist" for the base station
    - "no assembled STEP for any board"
Both are FALSE as of today:
    find . -name '*.kicad_pcb' | grep -icE 'station|ground'   -> 3
    tracker/hardware/base_station/base_station_v1.net          -> exists
    docs/fab/hub-v9/3d/hub_v9.step, wing_v9.step               -> exist
That is the same defect class the repo's own ADR guidance warns about: a record asserting a value with
nothing surfacing the competing reality. So this measures the tree instead of quoting a document.

Reports, per board: presence of a board file, a schematic, a netlist, a STEP/3D model, gerbers, and a
routing verdict measured from the board itself.

Read-only.

Usage: gap_inventory.py [repo_root]
"""
import glob
import os
import re
import subprocess
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."

# boards that ARE the end-to-end system, by the goal statement
FAMILIES = {
    "hub v9 (flight)": ["tracker/hardware/hub_board_v9.kicad_pcb"],
    "wing v9 (flight)": ["tracker/hardware/wing_board/wing_board_v9.kicad_pcb"],
    "base station": None,          # discovered below
}


def find_all(pattern):
    hits = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        if ".git" in dirpath:
            continue
        for f in filenames:
            if re.search(pattern, f, re.I):
                hits.append(os.path.join(dirpath, f))
    return sorted(hits)


def routes_count(path):
    """tracks / vias / nets with copper, using the KiCad venv if available."""
    py = os.path.expanduser("~/venvs/kicad/bin/python")
    if not os.path.exists(py) or not os.path.exists(path):
        return None
    code = (
        "import pcbnew,sys;b=pcbnew.LoadBoard(sys.argv[1]);"
        "t=list(b.GetTracks());tr=[x for x in t if x.Type()!=pcbnew.PCB_VIA_T];"
        "vi=[x for x in t if x.Type()==pcbnew.PCB_VIA_T];"
        "print(len(tr),len(vi),len(set(x.GetNetname() for x in tr)),b.GetNetCount()-1)"
    )
    r = subprocess.run([py, "-c", code, path], capture_output=True, text=True, timeout=180)
    out = r.stdout.strip()
    if not out or len(out.split()) != 4:
        return None
    tr, vi, nc, tot = out.split()
    return {"tracks": int(tr), "vias": int(vi), "nets_routed": int(nc), "nets_total": int(tot)}


def main():
    print("=" * 78)
    print("LIVE BOARD INVENTORY -- measured from the tree, not quoted from a document")
    print("=" * 78)

    pcbs = find_all(r"\.kicad_pcb$")
    schs = find_all(r"\.kicad_sch$")
    nets = find_all(r"\.net$")
    steps = find_all(r"\.(step|stp)$")
    gerbs = find_all(r"\.(gbr|gtl|gbl|gts|gbs|gto|gbo|drl)$")
    print(f"\nfile counts in the tree:")
    print(f"  .kicad_pcb   {len(pcbs)}")
    print(f"  .kicad_sch   {len(schs)}")
    print(f"  .net         {len(nets)}")
    print(f"  .step/.stp   {len(steps)}")
    print(f"  gerber/drill {len(gerbs)}")

    print("\n--- BASE STATION (the ground half of the bent pipe) ---")
    bs = [p for p in pcbs if re.search(r"station|ground", p, re.I)]
    print(f"  board files: {bs if bs else 'NONE'}")
    for b in bs:
        rc = routes_count(b)
        print(f"    {b}: {rc}")
    bs_net = [n for n in nets if re.search(r"station|ground", n, re.I)]
    bs_sch = [s for s in schs if re.search(r"station|ground", s, re.I)]
    print(f"  netlists   : {bs_net if bs_net else 'NONE'}")
    print(f"  schematics : {bs_sch if bs_sch else 'NONE'}")

    print("\n--- FLIGHT HUB v9 ---")
    h = "tracker/hardware/hub_board_v9.kicad_pcb"
    if os.path.exists(h):
        rc = routes_count(h)
        print(f"  {h}: {rc}")
    print(f"  gerbers    : {[g for g in gerbs if 'hub' in g.lower()][:3]} ..."
          f" ({len([g for g in gerbs if 'hub' in g.lower()])} files)")
    print(f"  STEP       : {[s for s in steps if 'hub' in s.lower()]}")

    print("\n--- FLIGHT WING v9 ---")
    w = "tracker/hardware/wing_board/wing_board_v9.kicad_pcb"
    if os.path.exists(w):
        rc = routes_count(w)
        print(f"  {w}: {rc}")
    print(f"  STEP       : {[s for s in steps if 'wing' in s.lower()]}")

    print("\n--- what the stale document claims vs what is measured ---")
    claims = [
        ("no base-station .kicad_pcb", len(bs) == 0, f"{len(bs)} found"),
        ("no base-station netlist", len(bs_net) == 0, f"{len(bs_net)} found"),
        ("no assembled STEP for any board", len(steps) == 0, f"{len(steps)} found"),
    ]
    for claim, still_true, measured in claims:
        verdict = "STILL TRUE" if still_true else "*** STALE -- FALSE ***"
        print(f"  {claim:38} {verdict}   (measured: {measured})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

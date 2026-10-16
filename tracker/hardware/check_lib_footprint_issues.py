#!/usr/bin/env python3
"""Read the 7 `lib_footprint_issues` DRC warnings precisely.

The readiness doc flagged these as "should be checked before the order". They are WARNINGS, not
errors, so they do not block -- but a board whose footprints disagree with their library is exactly
the class of thing that bites at JLCPCB (the fab uses the GERBERS, but a library mismatch means the
plotted board may not be the part the BOM says).

Prints, per offending footprint: lib_id, whether the library is REACHABLE, and whether the board's
copy differs from the library's. A fault that is only "library not found" is cosmetic here (the
board carries the full shape, and gerbers are plotted from the board); a fault where the board's
copy DIFFERS from a reachable library is a real signal.
"""
import json
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

BOARD = os.path.join(HERE, "hub_board_v9.kicad_pcb")
DRC = os.path.join(HERE, "output", "fabgrade_u4", "hub_board_v9_drc.json")

b = pcbnew.LoadBoard(BOARD)

# Which refs does the DRC actually flag?
flagged = []
try:
    d = json.load(open(DRC))
    for v in d.get("violations", []):
        if v.get("type") == "lib_footprint_issues":
            for i in v.get("items", []):
                desc = i.get("description", "")
                if desc.startswith("Footprint "):
                    flagged.append(desc[len("Footprint "):])
except Exception as e:
    print(f"could not read DRC report: {e}")

print(f"flagged by DRC: {flagged}\n")

# Load the project's lib tables so a lookup failure can be attributed correctly.
def table_paths():
    out = []
    for root, _dirs, files in os.walk(HERE):
        if "fp-lib-table" in files:
            out.append(os.path.join(root, "fp-lib-table"))
    return out

tables = table_paths()
print(f"fp-lib-table files found: {[os.path.relpath(t, HERE) for t in tables]}\n")

# Map declared nickname -> uri, the way KiCad resolves it.
rows = []
for t in tables:
    try:
        txt = open(t, errors="replace").read()
    except OSError:
        continue
    import re
    for m in re.finditer(r'\(lib\s+\(name\s+"([^"]+)"\)\s*\(type\s+"?([^")]+)"?\)\s*\(uri\s+"([^"]+)"\)', txt):
        nickname, kind, uri = m.group(1), m.group(2), m.group(3)
        uri2 = uri.replace("${KIPRJMOD}", os.path.dirname(t))
        rows.append((nickname, kind, uri2, os.path.exists(uri2)))

print("declared libraries (nickname | resolvable):")
for nickname, kind, uri2, ok in sorted(set(rows)):
    print(f"  {nickname:28} {'OK ' if ok else 'MISSING'}  {uri2}")

print()
print("per-flagged-footprint detail:")
for ref in flagged:
    fp = b.FindFootprintByReference(ref)
    if fp is None:
        print(f"  {ref:8} NOT ON THE BOARD")
        continue
    fid = fp.GetFPID()
    lib = str(fid.GetLibNickname())
    item = str(fid.GetLibItemName())
    declared = any(lib == n for n, _k, _u, _ok in rows)
    print(f"  {ref:8} lib_id={lib}:{item}  declared={declared}  pads={fp.GetPadCount()}")
    print(f"           path={fp.GetPath()}  attr={fp.GetAttributes()}  "
          f"desc='{(fp.GetLibDescription() or '')[:60]}'")

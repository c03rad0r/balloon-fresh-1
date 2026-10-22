#!/usr/bin/env python3
"""KiCad DRC gate for the v10 board (and any board passed via --board).

WHY THIS EXISTS (operator, 2026-10-22): the operator saw two same-coloured lanes crossing in a
render and asked whether that was a short, and whether a DRC check existed. It did not. Eight
custom gates reported all-zero while KiCad's own DRC reported 48 violations on the same board --
including /E28_BUSY running along the board edge at 0.000mm clearance, a class none of the custom
gates covered. KiCad's engine is the AUTHORITY for copper-vs-copper, copper-vs-edge, silk and
parity; the custom gates encode project-specific rules (the registry, the E28 keep-out, layer
semantics). BOTH must pass.

WHAT IT ENFORCES:
  * copper_edge_clearance   -- a track/pad closer to Edge.Cuts than the board rule
  * clearance               -- different nets too close (THIS IS THE SHORT CHECK)
  * shorting_items          -- copper of two nets actually touching
  * track_dangling / via_dangling -- a lane ending on nothing
  * silk_over_copper, silk_overlap -- silkscreen legibility
  * unconnected_items       -- reported but not failed by default (routing is in progress)

Exit 0 = no ERROR-severity violations outside the allow-list.
Exit 1 = violations, each named with its type and coordinates.

DEFAULT ALLOW-LIST: none for copper. Warnings that are never-blockers on this project must be
listed explicitly in ALLOW with a reason -- an empty allow-list is the safe default.

Usage: check_drc.py [--board B] [--json] [--no-exit-code]
"""
import argparse
import collections
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")

# Violation types that DO NOT fail the build, each with a reason. Copper matters: nothing
# copper-related is allowed here without a measured justification.
ALLOW = {
    # silkscreen crossing over copper is cosmetic; it never changes connectivity and is
    # routinely accepted. Recorded 2026-10-22: 18 instances, all on the board's own silk.
    "silk_over_copper": "cosmetic only; no electrical effect (32 such items recorded on v9 too)",
    "silk_overlap": "cosmetic only; silk-to-silk, no electrical effect",
}

# Violation types that ALWAYS fail, listed so the intent is explicit.
HARD = (
    "clearance",            # different nets too close -- the short check
    "shorting_items",       # nets touching
    "copper_edge_clearance",
    "track_dangling",
    "via_dangling",
    "isolated_copper",
    "starved_thermal",
    "lib_footprint_issues",
    "lib_footprint_mismatch",
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default=BOARD)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-exit-code", action="store_true")
    ap.add_argument("--allow-unconnected", action="store_true",
                    help="unconnected_items is a WARNING during routing; pass this to fail on it")
    args = ap.parse_args()

    if not shutil.which("kicad-cli"):
        print("REFUSED: kicad-cli not found -- a gate that cannot run must not look green")
        return 3
    if not os.path.exists(args.board):
        print(f"REFUSED: board not found: {args.board}")
        return 3

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "drc.txt")
        r = subprocess.run(
            ["kicad-cli", "pcb", "drc", "--format", "report", "--units", "mm",
             "--all-track-errors", "--severity-all", "-o", out, args.board],
            capture_output=True, text=True, timeout=900)
        if r.returncode not in (0, 5):        # kicad-cli returns 5 when violations exist
            print(f"REFUSED: kicad-cli pcb drc failed (rc={r.returncode}): "
                  f"{(r.stderr or r.stdout or '')[:300]}")
            return 3
        if not os.path.exists(out):
            print("REFUSED: kicad-cli produced no report")
            return 3
        txt = open(out).read()

    counts = collections.Counter(re.findall(r"^\[(\w+)\]", txt, re.M))
    unconnected = 0
    m = re.search(r"Found (\d+) unconnected", txt)
    if m:
        unconnected = int(m.group(1))

    failing, allowed = [], []
    for vtype, n in sorted(counts.items()):
        if vtype in ALLOW:
            allowed.append((vtype, n, ALLOW[vtype]))
        elif vtype == "unconnected_items" and not args.allow_unconnected:
            allowed.append((vtype, n, "warning during routing; --allow-unconnected to enforce"))
        else:
            # collect the individual entries for a failing type
            for blk in re.finditer(r"^\[" + vtype + r"\]:.*?(?=^\[|\Z)", txt, re.M | re.S):
                first = blk.group(0).strip().splitlines()
                failing.append((vtype, " | ".join(x.strip() for x in first[:3])))

    if args.json:
        print(json.dumps({"failing": len(failing), "counts": counts,
                          "allowed": [a[0] for a in allowed]}, indent=1))
    else:
        for vtype, n, reason in allowed:
            print(f"   ALLOW    {vtype}: {n}  ({reason})")
        for vtype, detail in failing[:40]:
            print(f"   FAIL     {vtype}: {detail[:150]}")
        if len(failing) > 40:
            print(f"   ... and {len(failing) - 40} more")
        print(f"DRC: {len(failing)} failing violation(s); "
              f"{sum(a[1] for a in allowed)} allowed; {unconnected} unconnected items")

    if args.no_exit_code:
        return 0
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())

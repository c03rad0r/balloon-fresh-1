#!/usr/bin/env python3
"""Silk legibility gate -- the board's silkscreen must be READABLE.

Operator directive (2026-10-22): "please make sure that the silk screen is legible and doesn't
overlap with parts or other silk screens before you start routing the board."

Why this is a gate and not a convention: a designator the assembler cannot read is a real
assembly defect -- it is how a part gets fitted in the wrong place. It is also the class of
defect that survives every other gate we have: copper is correct, connectivity is correct,
placement is legal, and the board is still hard to build.

AUTHORITY: kicad-cli pcb drc. This gate does NOT re-implement silk geometry -- it reads the
violations KiCad already computed. Per AGENTS.md section 14, when a custom check and kicad-cli
disagree, the custom check is wrong until proven otherwise; so we simply do not write one.

FAILS on, with NO allow-list:
    silk_overlap          silk-on-silk -- two markings in the same place, one of them unreadable
    silk_over_copper      silk over a pad/copper -- the ink is not printed there, so the marking
                          is missing exactly where it is needed
    silk_edge_clearance   silk clipped by the board edge -- the marking runs off the board

Deliberately NOT allowed, unlike check_drc.py's clearance classes: there is no engineering
reason to print two designators on top of each other. An empty allow-list is the point.

REFUSES (never passes) when:
  * kicad-cli is missing, or
  * the DRC report is absent / unparseable, or
  * the board file does not exist.

A gate that cannot run must not look green (AGENTS.md section 13).

Usage:
    check_silk.py [--board PATH] [--json PATH]
Exit: 0 = legible, 1 = violations, 2 = could not run.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")

# Silk classes that must be ZERO. No counts, no allow-lists, no ref scoping.
SILK_FAIL = ("silk_overlap", "silk_over_copper", "silk_edge_clearance")

# Printed once so the operator can see we know about them and are not silently ignoring them.
SILK_INFO = ("silk_over_copper",)  # also listed here purely for the summary line


def run_drc(board, out_json):
    if not os.path.exists(board):
        return None, f"board not found: {board}"
    exe = shutil.which("kicad-cli")
    if not exe:
        return None, ("kicad-cli not found on PATH -- REFUSING to pass. Install KiCad or run this "
                      "gate where it is available; a silk gate that cannot run is not a pass.")
    r = subprocess.run([exe, "pcb", "drc", "--format", "json", "-o", out_json, board],
                       capture_output=True, text=True)
    # NOTE: kicad-cli pcb drc returns 0 whether or not violations exist unless
    # --exit-code-violations is passed; we parse the report, so the exit code is not the signal.
    if not os.path.exists(out_json):
        return None, (f"kicad-cli produced no report (rc={r.returncode}): "
                      f"{(r.stderr or r.stdout or '').strip()[:300]}")
    try:
        with open(out_json, encoding="utf-8") as fh:
            return json.load(fh), ""
    except Exception as exc:  # noqa: BLE001
        return None, f"report not parseable: {exc}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default=DEFAULT_BOARD)
    ap.add_argument("--json", default="/tmp/check_silk_drc.json")
    args = ap.parse_args()

    doc, err = run_drc(args.board, args.json)
    if doc is None:
        print(f"SILK: CANNOT RUN -- {err}")
        return 2

    violations = doc.get("violations", []) or []
    by_type = {}
    for v in violations:
        by_type.setdefault(v.get("type", "?"), []).append(v)

    total = sum(len(by_type.get(t, [])) for t in SILK_FAIL)
    if total == 0:
        # still report the classes we watched, so "0" is auditable rather than assumed
        print("SILK: LEGIBLE -- 0 silk_overlap, 0 silk_over_copper, 0 silk_edge_clearance")
        return 0

    print(f"SILK: {total} violation(s) -- the silkscreen is not fully legible")
    for t in SILK_FAIL:
        vs = by_type.get(t, [])
        if not vs:
            continue
        print(f"   FAIL  {t}: {len(vs)}")
        # Show the distinct ITEM PAIRS, collapsed, because one crowded cluster can produce
        # hundreds of individual violations and the pair is what the fix acts on.
        seen = {}
        for v in vs:
            items = tuple(sorted(i.get("description", "?") for i in v.get("items", [])))
            seen[items] = seen.get(items, 0) + 1
        for items, n in sorted(seen.items(), key=lambda kv: -kv[1])[:12]:
            lhs = items[0] if items else "?"
            rhs = items[1] if len(items) > 1 else ""
            print(f"         {n:4d}x  {lhs}  <->  {rhs}")
        if len(seen) > 12:
            print(f"         ... and {len(seen) - 12} more distinct pair(s)")
    print("   Fix by moving the PART or its reference field. There is no allow-list: two "
          "designators in the same place is never correct.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

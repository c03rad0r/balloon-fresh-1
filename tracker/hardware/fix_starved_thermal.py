#!/usr/bin/env python3
"""Fix the 3 starved_thermal errors on the hub board.

MEASURED: `Pad 2 [GND]` of U_CUT3, U7 and one more connect to the F.Cu GND plane with 1 thermal
spoke where the board rule requires 2. A starved thermal is a real (if minor) assembly issue: one
spoke carries all the heat and current, and it is also the first thing to fail on a reflow.

FIX: set those pads to a SOLID zone connection (zone_connect = 0), which is the standard remedy for a
GND pad whose thermal spokes are pinched by neighbouring copper. Solid connection is strictly BETTER
electrically and thermally than 1 spoke; it is not a rule relaxation, and it does not touch the rule
that detected the problem.

Usage:  ~/venvs/kicad/bin/python fix_starved_thermal.py <board> <out> [--check]
"""
import os
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

SRC = sys.argv[1]
DST = sys.argv[2]
CHECK = "--check" in sys.argv

# ---------------------------------------------------------------------------------------------
# STALE-LIST DEFECT (fixed here, 2026-10-15)
# ---------------------------------------------------------------------------------------------
# This file used to carry a HARDCODED pad list: [("U_CUT3","2"), ("U7","2"), ("U5","12")].
# Measured consequence on the re-placed board: the real starved pads were Q1.2 (the newly added
# SX1280 crystal) and U5.12, while U_CUT3.2 and U7.2 were no longer starved at all. The script
# would therefore have "fixed" two pads that did not need it and MISSED the one that did -- a
# silent no-op dressed as a repair, which is the same failure class as the generator reverting
# operator work and the case-keyed library lookup inventing a false FAIL.
#
# A hardcoded target list is a snapshot of one board revision. The authority for WHICH pads are
# starved is the DRC report itself, so read it there. Accepts either an explicit list
# (--pads REF.NUM ...) or a DRC JSON (--drc path.json); prefers the report when given.
TARGETS: list[tuple[str, str]] = []


def _targets_from_drc(path: str) -> list[tuple[str, str]]:
    """Every `Pad N [GND] of REF` named by a starved_thermal violation, in report order."""
    import json as _json
    import re as _re
    d = _json.load(open(path, encoding="utf-8", errors="replace"))
    out: list[tuple[str, str]] = []
    for v in d.get("violations", []):
        if v.get("type") != "starved_thermal":
            continue
        for it in v.get("items", []):
            m = _re.search(r"Pad (\S+) \[[^\]]*\] of (\S+)", it.get("description", ""))
            if m:
                pair = (m.group(2), m.group(1))
                if pair not in out:
                    out.append(pair)
    return out


def _targets_from_argv() -> list[tuple[str, str]]:
    """--drc <report.json>, or --pads REF.NUM [REF.NUM ...]"""
    a = sys.argv
    if "--drc" in a:
        return _targets_from_drc(a[a.index("--drc") + 1])
    if "--pads" in a:
        vals = []
        for tok in a[a.index("--pads") + 1:]:
            if tok.startswith("--"):
                break
            ref, _, num = tok.partition(".")
            if ref and num:
                vals.append((ref, num))
        return vals
    return []


TARGETS = _targets_from_argv()
if not TARGETS:
    sys.exit(
        "REFUSING: no targets. A hardcoded pad list is a stale snapshot of one board revision --\n"
        "  the authority for WHICH pads are starved is the DRC report. Pass one of:\n"
        "    --drc  <path/to/*_drc.json>          (preferred; reads the real violations)\n"
        "    --pads U_CUT3.2 U7.2 U5.12 ...       (explicit, when you know the set)\n"
        "  Repro: kicad-cli pcb drc --format json --severity-all -o r.json <board>"
    )

# (reference, pad number) -- the authority is the DRC report (see _targets_from_drc above).
# The old hardcoded [("U_CUT3","2"), ("U7","2"), ("U5","12")] is DELETED: it was a snapshot of one
# board revision and silently missed Q1.2 after the U4 parts were placed.

board = pcbnew.LoadBoard(SRC)

# ---- discover EVERY GND pad on F.Cu whose zone connection is thermal, so nothing is guessed -------
print("=== pads with a thermal zone connection (candidates) ===")
cands = []
for fp in board.GetFootprints():
    for p in fp.Pads():
        if p.GetNetname() != "GND":
            continue
        zc = p.GetLocalZoneConnection()
        if zc != pcbnew.ZONE_CONNECTION_FULL:
            cands.append((fp.GetReference(), p.GetNumber(), zc, p.GetLayerSet().Seq()))
for ref, num, zc, layers in cands[:20]:
    print(f"  {ref:10s} pad {num:>3s}  zone_connect={zc}")

print()
print(f"=== applying SOLID zone connection to {len(TARGETS)} named pads ===")
changed = []
for ref, num in TARGETS:
    fp = board.FindFootprintByReference(ref)
    if fp is None:
        print(f"  {ref}: FOOTPRINT NOT FOUND")
        continue
    hit = False
    for p in fp.Pads():
        if p.GetNumber() == num:
            p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
            changed.append(f"{ref}.{num}")
            hit = True
    if not hit:
        print(f"  {ref}.{num}: PAD NOT FOUND")

print(f"  changed: {changed}")

if CHECK:
    print("\n(check mode -- nothing written)")
    sys.exit(0)

pcbnew.SaveBoard(DST, board)
print(f"  wrote {os.path.relpath(DST)}")

# ---- verify -------------------------------------------------------------------------------------
b2 = pcbnew.LoadBoard(DST)
ok = 0
for ref, num in TARGETS:
    fp = b2.FindFootprintByReference(ref)
    if fp:
        for p in fp.Pads():
            if p.GetNumber() == num and p.GetLocalZoneConnection() == pcbnew.ZONE_CONNECTION_FULL:
                ok += 1
print(f"  verified solid: {ok}/{len(TARGETS)}")

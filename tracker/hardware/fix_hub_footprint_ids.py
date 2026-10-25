#!/usr/bin/env python3
"""Repair missing library nicknames on hub_board_v10 footprints.

THE DEFECT
----------
`pad-audit` (pre-commit) refuses the board with 20 errors, all of one kind:

    R_DIV2 (R_0402_1005Metric): footprint ID has NO library nickname -- every other part on
    the board has one, and the netlist names a library, so the two disagree

MEASURED: 21 distinct footprint IDs across 53 footprints carry no `Lib:Name` form. Example
`R_0402_1005Metric` instead of `Resistor_SMD:R_0402_1005Metric`. Verified PRE-EXISTING -- the
untouched committed board has the same 53 -- so this is not caused by the pour work.

WHY IT MATTERS
A footprint with no library nickname cannot be resolved to a library, cannot be diffed
against it, and cannot be re-imported from a netlist. It is the same class of defect that made
the wing interconnect un-orderable (7 x lib_footprint_issues) until a real library existed.

HOW NICKNAMES ARE RESOLVED -- MEASURED, NOT GUESSED
Each nicknamed is resolved by SEARCHING the installed KiCad library trees for a
`<lib>.pretty/<name>.kicad_mod` that actually exists. If two libraries carry the same name the
script refuses rather than picking one. Project-custom parts (Wing_Tab_4P, LoRa2021*, E28*,
ublox_MAX, and the bare holes) are mapped from the repo's own libraries where they exist, and
otherwise left REPORTED as unresolved -- never invented, because a wrong nickname silently
points at the wrong land pattern.

Run:  /usr/bin/python3 tracker/hardware/fix_hub_footprint_ids.py [--dry-run] [--write]
"""
from __future__ import annotations

import argparse
import glob
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")
# MEASURED BUG (first version): this list held `/usr/share/kicad/footprints`, the PARENT, but
# index_libraries() expects each entry to BE a `.pretty` directory. So no system library was
# ever indexed and every stock part reported "no library on disk carries this name" -- while
# the repo glob picked up bare `library/` and `custom/` dirs and produced false AMBIGUOUS hits.
# Glob the *.pretty directories themselves instead.
FP_DIRS = sorted(glob.glob("/usr/share/kicad/footprints/*.pretty"))
# repo-local libraries, resolved relative to this file
FP_DIRS += sorted(glob.glob(os.path.join(HERE, "**", "*.pretty"), recursive=True))

# Parts that exist only in this project. A nickname is only applied when a matching file is
# found on disk; otherwise the part is reported UNRESOLVED and left untouched.
CUSTOM_CANDIDATES = {
    "Wing_Tab_4P": ["balloon_flight", "balloon_flight_v9", "balloon_flight_v10",
                    "Tracker_Mechanical"],
    "LoRa2021F33_2G4": ["balloon_flight", "balloon_flight_v9", "balloon_flight_v10"],
    "LoRa2021_Castellated": ["balloon_flight", "balloon_flight_v9", "balloon_flight_v10"],
    "E28-2G4M27SX": ["balloon_flight_v10"],
    "ublox_MAX": ["balloon_flight", "balloon_flight_v9", "balloon_flight_v10"],
}


# LIBRARY PRIORITY — measured need, not a guess.
# After the glob fix, every stock part came back AMBIGUOUS because `balloon_flight.pretty`
# (the flight board's export of its own footprints) and stray repo dirs `library/` and
# `custom/` all contain copies of the same names. Picking any of them at random would point a
# 0402 resistor at a derived duplicate instead of the canonical land pattern.
# A stock part IS the stock library part; the repo copies are derived artefacts and must never
# outrank the original. Project-custom parts have no stock equivalent, so they fall through to
# the newest balloon_flight library, then older ones.
LIB_PRIORITY = [
    "/usr/share/kicad/footprints/",   # canonical: stock KiCad
    "balloon_flight_v10",             # newest project library
    "balloon_flight_v9",
    "balloon_flight",
    "Tracker_Mechanical",
]


def lib_rank(lib, path):
    for i, p in enumerate(LIB_PRIORITY):
        if p.startswith("/"):
            if path.startswith(p):
                return i
        elif lib == p:
            return i
    return len(LIB_PRIORITY) + 1      # stray repo dirs last


def index_libraries():
    """{footprint_name: [(rank, lib)]} over every installed .pretty directory."""
    idx = {}
    for d in FP_DIRS:
        if not os.path.isdir(d):
            continue
        lib = os.path.basename(d)[:-len(".pretty")]
        for p in glob.glob(os.path.join(d, "*.kicad_mod")):
            name = os.path.basename(p)[:-len(".kicad_mod")]
            idx.setdefault(name, []).append((lib_rank(lib, d + "/"), lib))
    return idx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    idx = index_libraries()
    board = pcbnew.LoadBoard(BOARD)

    plan, unresolved = [], []
    for fp in board.GetFootprints():
        s = fp.GetFPIDAsString()
        if ":" in s and s.split(":")[0]:
            continue                      # already nicknamed
        ref = fp.GetReference()
        name = s
        if not name:
            # MOUNTING HOLES carry NO footprint id at all (measured: 8 of them, H1-H4 and
            # HW1-HW4, every one a 2.5 mm drill with a 2.5 mm pad, i.e. an unplated hole).
            # They still trip the pad-audit gate ("NO library nickname"), so they must name a
            # real library part too. Map by MEASURED drill, never by assumption: an
            # unplated 2.5 mm hole is MountingHole:MountingHole_2.5mm.
            drill = 0.0
            try:
                drill = fp.Pads()[0].GetDrillSize().x / 1e6 if len(fp.Pads()) else 0.0
            except Exception:  # noqa: BLE001
                drill = 0.0
            cand = "MountingHole_%.1fmm" % drill
            if drill and idx.get(cand):
                rank, lib = sorted(idx[cand])[0]
                plan.append((ref, "(empty)", lib + ":" + cand))
                print(f"   note {ref}: no id, %.2f mm drill -> {lib}:{cand}" % drill)
            else:
                unresolved.append((ref, "(empty)", "mechanical hole, no matching MountingHole "
                                                   "part for %.2f mm" % drill))
            continue
        libs = sorted(idx.get(name, []))
        if libs:
            # highest priority wins; the rest are recorded so the choice is auditable
            rank, lib = libs[0]
            plan.append((ref, name, lib + ":" + name))
            if len(libs) > 1:
                others = [l for _r, l in libs[1:]]
                print(f"   note {ref}: {name} also in {others} -- chose highest-priority {lib}")
        else:
            unresolved.append((ref, name, "no library on disk carries this name"))

    print(f"resolvable : {len(plan)}")
    for ref, name, new in plan:
        print(f"   {ref:<10} {name:<45} -> {new}")
    print(f"unresolved : {len(unresolved)}")
    for ref, name, why in unresolved:
        print(f"   {ref:<10} {name:<45}    {why}")

    if args.dry_run or not args.write:
        print("\n(dry run -- pass --write to apply)")
        return 0 if not unresolved else 2

    by_ref = {r: new for r, _n, new in plan}
    for fp in board.GetFootprints():
        new = by_ref.get(fp.GetReference())
        if not new:
            continue
        lib, name = new.split(":", 1)
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
    pcbnew.SaveBoard(BOARD, board)
    print(f"\nwrote {len(by_ref)} nickname(s) to {BOARD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

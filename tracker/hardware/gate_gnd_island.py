#!/usr/bin/env python3
"""PASS/FAIL gate for the J_W* GND-zone-island fix. Defined BEFORE the fix was written.

WHY THIS EXISTS. Four diagnoses on this board were wrong in sequence this session, and each was an
assertion that a cheap test could have killed. So the acceptance test for this fix is written first,
recorded here, and it must be run against a REBUILT board with zones REFILLED -- never against the
pre-fix file, and never graded on a subset of the DRC.

Baseline, measured on /tmp/stitch_v5_filled.kicad_pcb (pre-fix, zones filled):

    unconnected items : 6
    of which GND      : 2   (J_W1 pad 2 vs the F.Cu plane, and J_W1 pad 2 F.Cu vs its own B.Cu pad)
    error total       : 46

THE FIX PASSES ONLY IF ALL OF THESE HOLD:

  1. GND unconnected items drop from 2 to 0   (the thing the fix targets)
  2. total unconnected does not RISE        (no new opens anywhere)
  3. error total does not RISE              (46 or fewer -- the fix must not buy GND by breaking
                                             clearance, hole-to-hole, shorting or edge rules)
  4. no new error CLASS appears that was absent before (in particular no shorting_items, no
     hole_to_hole, no tracks_crossing, no solder_mask_bridge)

If 1 passes but 3 fails, the fix is REJECTED: that is the exact shape of the failed offset-stitch
experiment earlier this session (unconnected 10->6 but errors 29->56 with 5 real shorts).

THE FAILURE MODE THIS IS BUILT TO CATCH. A "fix" that improves the metric it targets while
introducing a class of defect nobody counted. The offset-stitch run looked like a win on
'unresolvable pads' and would have shipped five shorts.

Usage: gate_gnd_island.py <board_after_fix.kicad_pcb> <drc_after.json> <drc_before.json>
"""
import json
import sys

# Baseline recorded OUTSIDE the fix tool, from the pre-fix filled board.
BASELINE = {
    "unconnected": 6,
    "gnd_unconnected": 2,
    "errors": 46,
}
FORBIDDEN_NEW_CLASSES = [
    "shorting_items",
    "hole_to_hole",
    "tracks_crossing",
    "solder_mask_bridge",
    "holes_co_located",
]


def counts(drc_path):
    d = json.load(open(drc_path))
    unc = d.get("unconnected_items", []) or []
    gnd = 0
    for it in unc:
        if any("GND" in (i.get("description") or "") for i in it.get("items", [])):
            gnd += 1
    classes = {}
    for v in d.get("violations", []) or []:
        if v.get("severity") == "error":
            classes[v.get("type", "?")] = classes.get(v.get("type", "?"), 0) + 1
    return {"unconnected": len(unc), "gnd_unconnected": gnd,
            "errors": sum(classes.values()), "classes": classes}


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    after_path, before_path = sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None
    a = counts(after_path)
    b = counts(before_path) if before_path else {**BASELINE, "classes": {}}

    print(f"baseline : unconnected={b['unconnected']} gnd={b['gnd_unconnected']} "
          f"errors={b['errors']}")
    print(f"after fix: unconnected={a['unconnected']} gnd={a['gnd_unconnected']} "
          f"errors={a['errors']}")
    print()

    results = []
    results.append(("1. GND unconnected -> 0",
                    a["gnd_unconnected"] == 0,
                    f"{b['gnd_unconnected']} -> {a['gnd_unconnected']}"))
    results.append(("2. total unconnected not rising",
                    a["unconnected"] <= b["unconnected"],
                    f"{b['unconnected']} -> {a['unconnected']}"))
    results.append(("3. error total not rising",
                    a["errors"] <= b["errors"],
                    f"{b['errors']} -> {a['errors']}"))
    new_classes = [c for c in FORBIDDEN_NEW_CLASSES
                   if a["classes"].get(c, 0) > 0 and b["classes"].get(c, 0) == 0]
    results.append(("4. no new forbidden error class",
                    not new_classes,
                    f"new: {new_classes}" if new_classes else "none"))

    ok = True
    for name, passed, detail in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name:38} {detail}")
        ok = ok and passed

    print()
    if ok:
        print("GATE: PASS -- island fix accepted.")
    else:
        print("GATE: FAIL -- REJECT the island fix. If check 1 passed but 3 failed, that is the")
        print("      offset-stitch failure shape (target metric improved, a new defect class")
        print("      introduced) and the change must not ship.")
    print()
    print("error classes after:", json.dumps(a["classes"], sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

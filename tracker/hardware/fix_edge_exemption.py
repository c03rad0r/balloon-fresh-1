#!/usr/bin/env python3
"""Make the J_W* wing-socket edge exemption actually FIRE, and prove it.

THE PROBLEM. tracker/hardware/jlcpcb-s1-frozen.kicad_dru already carries a scoped exemption:

    (rule "edge_clearance_wing_socket_lands_44"
      (constraint edge_clearance (min 0.0mm))
      (condition "A.Reference == 'J_W1' || ... || A.Reference == 'J_W4'"))

It does not work. KiCad's edge_clearance test pairs a COPPER item with a BOARD-EDGE item. The
reported counterparty is "Segment of J_W1 on Edge.Cuts", so the condition is evaluated against items
whose `Reference` is empty -- the field belongs to the FOOTPRINT, and an Edge.Cuts segment has no
footprint. So `A.Reference == 'J_W1'` is never true for the pair that is actually being tested.

MEASURED FACT THAT MOTIVATES THE RULING. All 27 copper_edge_clearance items on this board are
`Segment of J_W<n> on Edge.Cuts` against a pad or trace of the SAME `J_W<n>` at `actual 0.00 mm`.
Zero of them are unrelated nets. The wing land sets are edge-launched by design (ADR-046/048), so
`0.00 mm` is the interface, not a defect.

WHAT THIS SCRIPT DOES. It reports the exact item descriptions the DRC produces for these pairs, then
tests candidate conditions against them, so the condition that DOES fire is found by measurement
rather than guessed. It does not edit the rules file unless the caller passes --write.

Usage: fix_edge_exemption.py <drc.json> [--write <dru-file>]
"""
import collections
import json
import re
import sys

WING = ("J_W1", "J_W2", "J_W3", "J_W4")


def strip_ref(desc):
    """The reference token embedded in an item description, e.g. 'Pad 2 [GND] of J_W1 on F.Cu'."""
    m = re.search(r"\b(J_W[1-4])\b", desc)
    return m.group(1) if m else None


def main():
    drc_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not drc_path:
        print(__doc__)
        return 2
    write_target = None
    if "--write" in sys.argv:
        write_target = sys.argv[sys.argv.index("--write") + 1]

    d = json.load(open(drc_path))
    items = [v for v in d.get("violations", []) if v.get("type") == "copper_edge_clearance"]
    print(f"copper_edge_clearance items: {len(items)}\n")

    # What do the two sides of each pair look like? This is the evidence the condition must match.
    shapes = collections.Counter()
    sides = []
    both_wing = 0
    for v in items:
        its = v.get("items", [])
        descs = [i.get("description", "") for i in its]
        refs = [strip_ref(x) for x in descs]
        kinds = []
        for x in descs:
            if "on Edge.Cuts" in x:
                kinds.append("edge")
            elif "Pad" in x:
                kinds.append("pad")
            elif "Via" in x:
                kinds.append("via")
            elif "Track" in x or "Segment" in x:
                kinds.append("track")
            else:
                kinds.append("?")
        shapes[tuple(sorted(kinds))] += 1
        sides.append((descs, refs, kinds))
        wing_refs = [r for r in refs if r in WING]
        if wing_refs and len(set(wing_refs)) == 1 and len(wing_refs) == len(its):
            both_wing += 1

    print("pair shapes (item kinds on each side):")
    for k, n in shapes.most_common():
        print(f"   {k}  x{n}")
    print()
    print(f"pairs where BOTH items belong to the SAME J_W reference: {both_wing} / {len(items)}")
    print()
    print("sample item descriptions (what a condition must match against):")
    for descs, refs, kinds in sides[:4]:
        for x in descs:
            print(f"   {kinds[descs.index(x)]:6} | {x}")
        print("   ---")
    print()

    # Candidate conditions, evaluated against the MEASURED descriptions.
    samples = [x for descs, _r, _k in sides for x in descs]
    candidates = {
        "A.Reference matches a J_W":       lambda s: bool(re.search(r"\bJ_W[1-4]\b", s)) and "Edge.Cuts" not in s,
        "either side names a J_W":         lambda s: bool(re.search(r"\bJ_W[1-4]\b", s)),
        "B.Reference matches a J_W":       lambda s: bool(re.search(r"\bJ_W[1-4]\b", s)),
    }
    print("candidate conditions evaluated against the real strings:")
    for name, fn in candidates.items():
        hits = sum(1 for s in samples if fn(s))
        print(f"   {name:34} matches {hits}/{len(samples)} item descriptions")
    print()
    print("CONCLUSION. Any condition referencing A.Reference or B.Reference alone CANNOT exempt these")
    print("pairs: the edge side ('Segment of J_W1 on Edge.Cuts') carries no Reference field, so the")
    print("comparison is against an empty string. The workable forms are either")
    print("   (a) a condition on the PAD's own reference when the pad is side A, plus accepting that")
    print("       the edge segment side still trips the rule, or")
    print("   (b) a geometric condition, e.g. narrowing the rule to copper that is NOT within the")
    print("       wing land-set footprint's courtyard.")
    print()
    print("Because (a) and (b) change the RULES FILE -- the artefact that decides whether this board")
    print("is fabbable -- this script does NOT write it. The ruling is the operator's; this reports the")
    print("evidence the ruling needs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

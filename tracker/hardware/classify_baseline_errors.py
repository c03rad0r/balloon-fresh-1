#!/usr/bin/env python3
"""Characterise the 235 baseline DRC errors, grouped so a ruling is possible.

The RF work is not what blocks this board. On the routed board the load is:
    clearance            110
    solder_mask_bridge    89
    copper_edge_clearance  24   (already characterised: the wing-socket edge interface, 0 real defects)
    hole_clearance         9
    starved_thermal        3

110 + 89 is 199 of 235 errors and nothing in this session has established what they are. This groups
them by the ITEMS involved and the measured shortfall, so it becomes a decision about objects rather
than a count.

Read-only.

Usage: classify_baseline_errors.py <drc.json>
"""
import collections
import json
import re
import sys


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        print(__doc__)
        return 2
    d = json.load(open(path))
    errs = [v for v in d.get("violations", []) if v.get("severity") == "error"]
    print(f"error items: {len(errs)}\n")

    by_type = collections.defaultdict(list)
    for v in errs:
        by_type[v.get("type", "?")].append(v)

    for t in sorted(by_type, key=lambda k: -len(by_type[k])):
        vs = by_type[t]
        print(f"=== {t}: {len(vs)} ===")

        # measured magnitude, if the description carries one
        mags = collections.Counter()
        for v in vs:
            m = re.search(r"actual ([0-9.]+) mm", v.get("description", ""))
            if m:
                mags[float(m.group(1))] += 1
        if mags:
            top = sorted(mags.items())[:6]
            print(f"   measured values: {[f'{a}mm x{n}' for a, n in top]}")

        # which items are involved
        refs = collections.Counter()
        nets = collections.Counter()
        for v in vs:
            for it in v.get("items", []):
                dd = it.get("description", "")
                for tok in re.findall(r"\b([A-Z][A-Za-z_]{0,9}[0-9]{1,3})\b", dd):
                    refs[tok] += 1
                for n in re.findall(r"\[([^\]]+)\]", dd):
                    nets[n] += 1
        print(f"   top refs: {refs.most_common(8)}")
        print(f"   top nets: {nets.most_common(8)}")

        # a couple of verbatim samples
        print("   samples:")
        for v in vs[:2]:
            print(f"     {v.get('description','')[:96]}")
            for it in v.get("items", []):
                print(f"       - {it.get('description','')[:96]}")
        print()

    print("=== summary of what a ruling would need to decide ===")
    for t in sorted(by_type, key=lambda k: -len(by_type[k])):
        vs = by_type[t]
        refs = collections.Counter()
        for v in vs:
            for it in v.get("items", []):
                for tok in re.findall(r"\b([A-Z][A-Za-z_]{0,9}[0-9]{1,3})\b",
                                      it.get("description", "")):
                    refs[tok] += 1
        distinct = len(refs)
        print(f"  {t:24} {len(vs):>4} items across ~{distinct:>3} distinct refs")
    return 0


if __name__ == "__main__":
    sys.exit(main())

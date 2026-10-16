#!/usr/bin/env python3
"""Read a KiCad ERC JSON report CORRECTLY.

MY BUG THIS REPLACES. run_erc.sh's first version did:
    viol = d.get("violations", d.get("sheets", []))
and the report's shape is {..., "sheets": [ {"violations": [ ... ]} ]}, so it read a LIST OF SHEETS and
then found no "severity" key on the sheet objects -- reporting "no ERROR-severity findings" while the
file contained several severity=="error" items. A gate that reads the wrong nesting depth and prints
green is worse than no gate.

KiCad's real shape:
    { "$schema": ..., "sheets": [ { "path": ..., "violations": [ {"severity": ..., ...} ] } ] }

Usage: read_erc.py <erc.json>
Exit 0 = no ERROR-severity findings, 1 = errors present, 2 = could not read.
"""
import json
import sys


def collect(d):
    """Every violation object, at whatever depth KiCad nests it."""
    out = []

    def walk(node):
        if isinstance(node, dict):
            if "severity" in node and ("description" in node or "type" in node):
                out.append(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(d)
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    try:
        d = json.load(open(sys.argv[1]))
    except Exception as e:
        print(f"read_erc: cannot read {sys.argv[1]} ({e})")
        return 2
    vs = collect(d)
    sev = {}
    for v in vs:
        s = v.get("severity", "?")
        sev[s] = sev.get(s, 0) + 1
    print(f"read_erc: {len(vs)} finding(s) across all nesting levels  {sev}")

    errs = [v for v in vs if v.get("severity") == "error"]
    for v in errs:
        print(f"   ERROR [{v.get('type','?')}] {v.get('description','')[:100]}")
        for it in v.get("items", [])[:3]:
            print(f"          - {it.get('description','')[:100]}")
    if len(errs) > 20:
        print(f"   ... and {len(errs)-20} more")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())

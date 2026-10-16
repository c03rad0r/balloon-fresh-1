#!/usr/bin/env python3
"""Report the single `clearance` violation the RF route created, with the geometry.

route_rf_and_gate.py laid the two RF legs at 0.20 mm and the DRC returned exactly one new error class,
`clearance`, count 1. shorting_items was 0 and the total delta was +1. The gate refused to promote the
route because it created a new class -- correctly, since "no new error class" was the stated rule.

This finds that one violation and reports both items and the measured gap, so the fix is a decided
local edit rather than another guess. Read-only.

Usage: find_route_violation.py <routed_drc.json> [<control_drc.json>]
"""
import json
import sys


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    d = json.load(open(sys.argv[1]))
    errs = [v for v in d.get("violations", []) if v.get("severity") == "error"]
    targets = [v for v in errs if v.get("type") == "clearance"]
    print(f"{sys.argv[1]}: {len(errs)} errors, {len(targets)} of type `clearance`\n")
    for v in targets:
        print(f"  description: {v.get('description','')}")
        for it in v.get("items", []):
            print(f"    - {it.get('description','')}")
            pos = it.get("pos") or {}
            if pos:
                print(f"        at ({pos.get('x')}, {pos.get('y')})")
        print()

    # if a control was passed, confirm the violation is genuinely new
    if len(sys.argv) > 2:
        c = json.load(open(sys.argv[2]))
        cn = sum(1 for v in c.get("violations", [])
                 if v.get("severity") == "error" and v.get("type") == "clearance")
        print(f"control `clearance` count: {cn}   -> this one is {'NEW' if cn == 0 else 'not new'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

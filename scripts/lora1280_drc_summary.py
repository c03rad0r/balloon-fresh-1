#!/usr/bin/env python3
"""Summarise a kicad-cli DRC report for the LoRa1280 site and fail on rule-breaking copper.

The baseline on hub v10 with the LoRa1280 fitted is 79 violations, all pre-existing:
34 hole-size (0.20/0.25 mm holes against a 0.30 mm minimum), 16 copper-edge, 19 library,
7 silk, 3 thermal/courtyard. Those are not this task's business.

Three classes are: `clearance`, `shorting_items`, `solder_mask_bridge`. They must stay at zero,
because they are the ones that mean copper breaks a rule. Everything else may be counted and
reported; these may not appear at all.
"""
from __future__ import annotations

import collections
import json
import sys

ZERO = ("clearance", "shorting_items", "solder_mask_bridge")
BASELINE = 79


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: lora1280_drc_summary.py <drc.json>", file=sys.stderr)
        return 2
    try:
        d = json.load(open(sys.argv[1]))
    except (OSError, json.JSONDecodeError) as e:
        print(f"FAIL: cannot read report: {e}", file=sys.stderr)
        return 2

    v = d.get("violations", [])
    c = collections.Counter(x.get("type", "?") for x in v)
    print(f"total violations {len(v)}  (baseline {BASELINE})")
    for k, n in c.most_common():
        print(f"  {k:26s} {n}")

    bad = [k for k in ZERO if c.get(k)]
    if bad:
        print("FAIL: rule-breaking copper present -> " + ", ".join(bad))
        for x in v:
            if x.get("type") in ZERO:
                print(f"  {x.get('type')}: {x.get('description', '')[:120]}")
        return 1

    print("ok: clearance / shorting / mask bridges all zero")
    return 0


if __name__ == "__main__":
    sys.exit(main())

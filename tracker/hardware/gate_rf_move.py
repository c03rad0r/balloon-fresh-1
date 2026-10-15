#!/usr/bin/env python3
"""Gate the RF match move: did it fix the dispersion WITHOUT introducing a new error class?

Written BEFORE the move was applied, because two earlier attempts at this same move each produced a
NEW DRC error that only the grade caught:

  attempt 1 -> courtyards_overlap 1 (C0 vs L1, 0.15 mm)  : assumed a 1.5 mm separation constant while
               the real match courtyards are 1.91x1.01 and 1.95x1.03 mm
  attempt 2 -> courtyards_overlap 1 (U4 vs L1)           : excluded U4 from the obstacle set, so a
               site 2.5 mm from U4.pad22 landed inside U4's own 6.19x6.19 mm courtyard

So this is the acceptance test for attempt 3, and it is deliberately conservative: it requires the
RF span to collapse AND every error class to stay at or below the pre-move baseline.

MEASURED BASELINE (pre-move, placed-only board, zones refilled):
    copper_edge_clearance  24
    courtyards_overlap      0
    total errors           24

TARGET (post-move): the /SX1280_RF three-pad span must fall from 66.74 mm to under 5 mm, with
copper_edge_clearance <= 24 and courtyards_overlap == 0.

Usage: gate_rf_move.py <board_after.kicad_pcb> <drc_after.json>
"""
import json
import math
import sys

import pcbnew

BASELINE = {"copper_edge_clearance": 24, "courtyards_overlap": 0, "errors": 24}
MAX_RF_SPAN_MM = 5.0


def rf_span(path):
    b = pcbnew.LoadBoard(path)
    pads = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == "/SX1280_RF":
                c = p.GetPosition()
                pads.append((fp.GetReference(), pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)))
    spans = []
    for i in range(len(pads)):
        for j in range(i + 1, len(pads)):
            a, b_ = pads[i], pads[j]
            spans.append((f"{a[0]}-{b_[0]}", math.hypot(a[1] - b_[1], a[2] - b_[2])))
    return pads, spans


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    board, drc = sys.argv[1], sys.argv[2]
    pads, spans = rf_span(board)
    d = json.load(open(drc))
    cls = {}
    for v in d.get("violations", []):
        if v.get("severity") == "error":
            cls[v.get("type", "?")] = cls.get(v.get("type", "?"), 0) + 1
    total = sum(cls.values())

    print(f"RF pads on /SX1280_RF: {[(r, round(x, 2), round(y, 2)) for r, x, y in sorted(pads)]}")
    worst = 0.0
    for name, s in spans:
        print(f"  {name:10} {s:7.2f} mm")
        worst = max(worst, s)
    print()

    results = [
        (f"RF span collapsed (< {MAX_RF_SPAN_MM} mm)", worst < MAX_RF_SPAN_MM, f"worst {worst:.2f} mm"),
        ("courtyards_overlap == baseline",
         cls.get("courtyards_overlap", 0) <= BASELINE["courtyards_overlap"],
         f"{BASELINE['courtyards_overlap']} -> {cls.get('courtyards_overlap', 0)}"),
        ("copper_edge_clearance <= baseline",
         cls.get("copper_edge_clearance", 0) <= BASELINE["copper_edge_clearance"],
         f"{BASELINE['copper_edge_clearance']} -> {cls.get('copper_edge_clearance', 0)}"),
        ("total errors <= baseline",
         total <= BASELINE["errors"], f"{BASELINE['errors']} -> {total}"),
    ]
    ok = True
    for name, passed, detail in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name:38} {detail}")
        ok = ok and passed
    print()
    print("GATE: " + ("PASS -- RF move accepted." if ok else
                      "FAIL -- REJECT the move."))
    print(f"error classes: {json.dumps(cls, sort_keys=True)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Board-wide lane-crossing audit for hub v10.

Why this exists: the LoRa1280 site was placed at the WORST of eight orientations (26 lane
crossings) when the best was 10. That raised the question the operator asked — is this a
one-off, or is the placement process blind to crossings in general?

Method
------
For every footprint with >= 4 netted pads:
  * each net appearing on that footprint becomes one line, from the pad on this footprint to
    the centroid of the SAME net's pads on all OTHER footprints,
  * count pairwise intersections among those lines,
  * normalise by the maximum possible n(n-1)/2 so footprints with different pin counts are
    comparable.

A high normalised score means the part is oriented/placed such that its nets' natural paths
tangle with each other — i.e. the same defect class as the LoRa1280 at B.Cu/-90.

This measures GEOMETRY ONLY. It is not a routability verdict; a tangled part can still route
with enough layers and doglegs. It is a placement-quality signal.
"""
from __future__ import annotations

import sys
from collections import defaultdict

import pcbnew

MM = 1_000_000


def orient(ax, ay, bx, by, cx, cy):
    v = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    return 0 if abs(v) < 1e-9 else (1 if v > 0 else -1)


def cross(a, b):
    x1, y1, x2, y2 = a
    x3, y3, x4, y4 = b
    o1 = orient(x1, y1, x2, y2, x3, y3)
    o2 = orient(x1, y1, x2, y2, x4, y4)
    o3 = orient(x3, y3, x4, y4, x1, y1)
    o4 = orient(x3, y3, x4, y4, x2, y2)
    return o1 != o2 and o3 != o4


def main() -> int:
    board = pcbnew.LoadBoard(sys.argv[1] if len(sys.argv) > 1
                             else "tracker/hardware/hub_board_v10.kicad_pcb")

    # net -> list of (ref, x, y)
    netpads = defaultdict(list)
    for f in board.GetFootprints():
        for p in f.Pads():
            n = p.GetNetname()
            if n:
                netpads[n].append((f.GetReference(), p.GetPosition().x / MM,
                                   p.GetPosition().y / MM))

    # Rails have no meaningful centroid: GND/+3V3 go to pours, not to a point. Counting
    # them as point-to-point lanes inflates every large part and makes the metric useless.
    POWER = {"GND", "+3V3", "+5V", "VCC", "VSCAP", "+3.3V", "VDD", "VBAT"}
    rows = []
    for f in board.GetFootprints():
        ref = f.GetReference()
        mine = {}
        for p in f.Pads():
            n = p.GetNetname()
            if n and n not in POWER:
                mine.setdefault(n, []).append((p.GetPosition().x / MM,
                                               p.GetPosition().y / MM))
        if len(mine) < 4:
            continue
        lines = []
        for n, pads in mine.items():
            others = [(x, y) for (r, x, y) in netpads[n] if r != ref]
            if not others:
                continue
            cx = sum(o[0] for o in others) / len(others)
            cy = sum(o[1] for o in others) / len(others)
            px = sum(p[0] for p in pads) / len(pads)
            py = sum(p[1] for p in pads) / len(pads)
            lines.append((n, (px, py, cx, cy)))
        if len(lines) < 2:
            continue
        k = 0
        pairs = 0
        for i in range(len(lines)):
            for j in range(i + 1, len(lines)):
                pairs += 1
                if cross(lines[i][1], lines[j][1]):
                    k += 1
        rows.append((ref, f.GetValue(), len(lines), k, k / pairs if pairs else 0.0))

    rows.sort(key=lambda r: -r[4])
    print(f"{'ref':<12}{'nets':>6}{'cross':>7}{'ratio':>8}  value")
    for ref, val, n, k, ratio in rows:
        bar = "#" * int(ratio * 24)
        print(f"{ref:<12}{n:>6}{k:>7}{ratio:>8.2f}  {bar:<24} {val[:34]}")
    if rows:
        worst = rows[0]
        mean = sum(r[4] for r in rows) / len(rows)
        print(f"\nparts audited: {len(rows)}   mean ratio {mean:.2f}   "
              f"worst {worst[0]} {worst[4]:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

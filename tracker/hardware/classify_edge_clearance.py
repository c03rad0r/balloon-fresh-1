#!/usr/bin/env python3
"""Classify the copper_edge_clearance items by WHAT the offending copper actually is.

WHY. The board reports 27 `copper_edge_clearance` items and they have been carried as an "open
operator ruling" without anyone establishing what they are. A ruling cannot be given on a count. This
groups them by which item is the copper and how far it actually is from the outline, so the ruling
becomes a decision about specific objects.

The board's floor is 0.20 mm copper-to-edge; the repo's older execution plan states 0.50 mm. Most of
these are likely the GND PLANE reaching the outline, which is a normal and deliberate choice on a
grounded board -- but that has to be read, not assumed.

Usage: classify_edge_clearance.py <drc.json> <board.kicad_pcb>
"""
import collections
import json
import sys

import pcbnew


def mm(v):
    return pcbnew.ToMM(v)


def main():
    drc_path = sys.argv[1] if len(sys.argv) > 1 else None
    board_path = sys.argv[2] if len(sys.argv) > 2 else None
    if not drc_path or not board_path:
        print(__doc__)
        return 2
    d = json.load(open(drc_path))
    b = pcbnew.LoadBoard(board_path)

    items = [v for v in d.get("violations", []) if v.get("type") == "copper_edge_clearance"]
    print(f"copper_edge_clearance items: {len(items)}\n")

    # group by the description of the copper-carrying item
    groups = collections.Counter()
    samples = {}
    for v in items:
        desc = v.get("description", "")
        its = v.get("items", [])
        kind = "?"
        for it in its:
            dd = it.get("description", "")
            if "Zone" in dd:
                kind = "ZONE (copper pour)"
                break
            if "Pad" in dd:
                kind = "PAD"
                break
            if "Track" in dd or "Segment" in dd or "Via" in dd:
                kind = "TRACK/VIA"
                break
            kind = dd[:40] or "?"
        groups[kind] += 1
        samples.setdefault(kind, []).append(desc or " | ".join(i.get("description", "") for i in its))

    for kind, n in groups.most_common():
        print(f"  {kind:24} {n}")
    print()
    for kind, ex in samples.items():
        print(f"  examples for {kind}:")
        for e in ex[:3]:
            print(f"     {e[:150]}")
    print()

    # how far is the board outline from the offending zones, in actual numbers?
    print("board geometry:")
    bb = b.GetBoardEdgesBoundingBox()
    print(f"  outline bbox x {mm(bb.GetLeft()):.2f}..{mm(bb.GetRight()):.2f} "
          f"y {mm(bb.GetTop()):.2f}..{mm(bb.GetBottom()):.2f}")
    gnd = [z for z in b.Zones() if z.GetNetname() == "GND"]
    print(f"  GND zones: {len(gnd)}")
    for z in gnd:
        for lay in z.GetLayerSet().Seq():
            f = z.GetFilledPolysList(lay)
            if not f.OutlineCount():
                continue
            zb = f.BBox()
            print(f"    net={z.GetNetname()} layer={pcbnew.LayerName(lay)} "
                  f"filled x {mm(zb.GetLeft()):.2f}..{mm(zb.GetRight()):.2f} "
                  f"y {mm(zb.GetTop()):.2f}..{mm(zb.GetBottom()):.2f} "
                  f"own_clearance={mm(z.GetOwnClearance())}")
    print()
    print("INTERPRETATION GUIDANCE (to be confirmed against the list above, not assumed):")
    print("  - if the items are ZONES reaching the outline, the ruling is about the plane's edge")
    print("    pull-back, a single number, not 27 separate defects")
    print("  - if they are PADS or TRACKS, they are 27 real part-placement/route items")
    return 0


if __name__ == "__main__":
    sys.exit(main())

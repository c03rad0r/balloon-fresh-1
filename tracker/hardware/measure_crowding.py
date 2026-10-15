#!/usr/bin/env python3
"""R-FLOOR-1: the crowding metric that decides whether a re-placement actually worked.

WHY THIS EXISTS. Two controlled routing experiments this session showed that a "fix" can move the
failure rather than remove it: routing the two congested nets FIRST connected them and broke three
others, including /SX1280_VDD (the radio's internal regulator loop). A placement change judged only
by "does MOSI route now" would therefore be a false pass -- the same class of error as the isolation
test, where a net handed the whole board routes fine and the full board does not.

So a placement is only PROVEN better if the count of unrouted nets at the FROZEN FLOOR drops. This
script prints the numbers that gate that, all READ from the board, none hand-typed:

  - free channel width in the U1<->U4 corridor on each copper layer
  - the support-cluster bounding box (how clumped it is)
  - the count of unrouted nets (from an optional route JSON), so a "fix" that relocates shows up

FLOOR RECORDED OUTSIDE THE TOOL: the repo's frozen floor is clearance 0.2 mm / track 0.2 mm /
via 0.6 mm / drill 0.3 mm (tracker/hardware/jlcpcb-s1-frozen.kicad_dru and the route args in
fab_grade.sh). The metric asserts the routed run used exactly that floor, because a run at a narrowed
floor would read clean and mean nothing.

Usage:
  measure_crowding.py <board.kicad_pcb> [route.json]
"""
import json
import os
import sys

import pcbnew

FLOOR = {"clearance": 0.2, "track": 0.2, "via": 0.6, "drill": 0.3}

# The corridor of interest: between the ESP32-S3 module and the SX1280.
CORRIDOR = {"x0": 44.0, "x1": 62.0, "y0": 20.0, "y1": 42.0}

# The support cluster under judgement (from the U4 rewire; D_HUB1/D_HUB2 are the harvester diode
# pair on /HUB_PV_P and /HUB_PV_N, NOT RF -- verified from v9_flight.net).
CLUSTER = ["C4", "C5", "C2", "L4", "TH_NTC1", "R15", "C8", "C9", "C10",
           "D_HUB1", "D_HUB2"]


def mm(v):
    return pcbnew.ToMM(v)


def fp_box(board, ref):
    fp = board.FindFootprintByReference(ref)
    if fp is None:
        return None
    r = fp.GetBoundingBox(False, False)
    return (mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom()))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    board = pcbnew.LoadBoard(sys.argv[1])
    print(f"board: {sys.argv[1]}")
    print(f"footprints: {len(list(board.GetFootprints()))}")
    print()

    u1 = fp_box(board, "U1")
    u4 = fp_box(board, "U4")
    u2 = fp_box(board, "U2")
    print("=== the three constrained parts ===")
    for name, bb in (("U1 ESP32-S3", u1), ("U4 SX1280", u4), ("U2 LoRa2021F33", u2)):
        if bb:
            print(f"  {name:18} x {bb[0]:7.2f}..{bb[2]:7.2f}  y {bb[1]:7.2f}..{bb[3]:7.2f}"
                  f"  ({bb[2]-bb[0]:5.2f} x {bb[3]-bb[1]:5.2f} mm)")

    # Gaps between the constrained parts: the numbers a re-placement must widen.
    print()
    print("=== gaps between constrained parts (mm) ===")
    if u1 and u4:
        gap_x = u1[0] - u4[2]
        print(f"  U4.right -> U1.left : {gap_x:7.2f}   (negative = overlapping in x)")
    if u1 and u2:
        print(f"  U2.right -> U1.left : {u1[0]-u2[2]:7.2f}")
        print(f"  U2.bottom->U1.top   : {u1[1]-u2[3]:7.2f}")
    if u4 and u2:
        print(f"  U2.right -> U4.left : {u4[0]-u2[2]:7.2f}")

    # Support cluster spread: how clumped is it, and how much of it is inside the corridor?
    print()
    print("=== support cluster spread ===")
    boxes = [(r, fp_box(board, r)) for r in CLUSTER]
    boxes = [(r, b) for r, b in boxes if b]
    if boxes:
        x0 = min(b[0] for _r, b in boxes)
        y0 = min(b[1] for _r, b in boxes)
        x1 = max(b[2] for _r, b in boxes)
        y1 = max(b[3] for _r, b in boxes)
        print(f"  cluster bbox        x {x0:7.2f}..{x1:7.2f}  y {y0:7.2f}..{y1:7.2f}"
              f"  ({x1-x0:5.2f} x {y1-y0:5.2f} mm)")
        print(f"  cluster area        {(x1-x0)*(y1-y0):8.1f} mm^2")
        inside = [r for r, b in boxes
                  if b[0] >= CORRIDOR["x0"] and b[2] <= CORRIDOR["x1"]
                  and b[1] >= CORRIDOR["y0"] and b[3] <= CORRIDOR["y1"]]
        print(f"  inside the U1<->U4 corridor ({len(inside)}/{len(boxes)}): {', '.join(inside)}")

    # Copper occupancy in the corridor, per layer: how much room is actually LEFT?
    print()
    print("=== free channel width in the corridor, per layer ===")
    for layer, lname in ((pcbnew.F_Cu, "F.Cu"), (pcbnew.In1_Cu, "In1.Cu"),
                         (pcbnew.In2_Cu, "In2.Cu"), (pcbnew.B_Cu, "B.Cu")):
        xs = []
        for t in board.GetTracks():
            if t.GetLayer() != layer:
                continue
            for pt in (t.GetStart(), t.GetEnd()):
                px, py = mm(pt.x), mm(pt.y)
                if (CORRIDOR["x0"] <= px <= CORRIDOR["x1"]
                        and CORRIDOR["y0"] <= py <= CORRIDOR["y1"]):
                    xs.append(px)
        if not xs:
            print(f"  {lname:7} EMPTY in the corridor ({CORRIDOR['x1']-CORRIDOR['x0']:.1f} mm free)")
        else:
            print(f"  {lname:7} {len(xs)} track vertices span x {min(xs):.2f}..{max(xs):.2f}"
                  f"  -> occupancy {100.0*(max(xs)-min(xs))/(CORRIDOR['x1']-CORRIDOR['x0']):5.1f}%")

    # The gating number: unrouted nets, and the floor the run used.
    if len(sys.argv) > 2:
        print()
        print("=== routing outcome (the number that GATES the placement) ===")
        try:
            d = json.load(open(sys.argv[2]))
        except Exception as e:
            print(f"  could not read {sys.argv[2]}: {e}")
            return 1
        used = d.get("min_clearance_used")
        print(f"  min_clearance_used  {used}")
        for k, want in FLOOR.items():
            print(f"  floor {k:10} {want} (recorded outside this tool; {d.get(k, 'not reported')} in json)")
        if used is not None and abs(float(used) - FLOOR["clearance"]) > 1e-9:
            print(f"  !! FLOOR NOT HONOURED: routed at {used} but the frozen floor is "
                  f"{FLOOR['clearance']}. A narrowed floor reads clean and means NOTHING.")
        print(f"  routed              {d.get('routed')}")
        print(f"  failed_single       {d.get('failed_single')}")
        print(f"  pad_pairs_open      {d.get('pad_pairs_open')}")
        print(f"  vias                {d.get('vias')}")
        nfail = len(d.get("failed_single") or [])
        print()
        print(f"  R-FLOOR-1 GATE: unrouted single nets = {nfail}. A placement is PROVEN better only")
        print("  if this DROPS. Equal or higher = the failure was relocated, not removed.")
    else:
        print()
        print("R-FLOOR-1 GATE: no route JSON given, so the gating count is unchecked.")
        print("  Re-run with the routed JSON to gate the placement (clearance, routed, failed_single).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Obstacle classifier that separates STATIC copper from a re-pourable POUR and from a KEEPOUT.

=== A HYPOTHESIS I PROPOSED, TESTED, AND REFUTED -- recorded so it is not re-proposed ===

Three filled GND zones exist on this board (F.Cu, B.Cu, In1.Cu), none of them rule areas (keepouts):

    zone net=GND  layer=F.Cu   filled=True  rule_area=False
    zone net=GND  layer=B.Cu   filled=True  rule_area=False
    zone net=GND  layer=In1.Cu filled=True  rule_area=False

I then claimed this was the explanation for "router says boxed_in_static but the probe says the corridor
is clear", on the theory that the earlier scripts were counting the poured polygon as a static wall.

THAT CLAIM WAS WRONG, and the test was one command: `grep -n 'Zone\|zone' pad_reachability.py` returns
NO zone references at all. The earlier scripts counted tracks and vias only. And this classifier, run on
the same board, reports the SAME counts:

    F.Cu STATIC=593  B.Cu STATIC=381  In1.Cu STATIC=430  In2.Cu STATIC=574

So the pour was never in the obstacle count, and the "pour as wall" explanation is dead. The real defect
in the earlier script is different and is documented in fcu_escape_feasibility.py: its verdict line
compared obstacle distance against the TRACK clearance (0.300 mm) instead of the distance actually needed
for a PAD escape, which for a 1.50x0.90 mm pad is half-diagonal + clearance = 0.875 + 0.200 = 1.075 mm.
So it printed "PAD ESCAPE CLEAR (nearest 0.970 mm >= 0.300 mm)" while listing obstacles at 0.970 mm as
BLOCKING -- both statements came from the same comparison and only one could be right.

This module is still useful: it is the correct classifier, and it proves the pour is not a wall.
It just is NOT the explanation for the routing failures. Keep the distinction clear.

Usage:  ~/venvs/kicad/bin/python tracker/hardware/obstacle_model.py
"""
from __future__ import annotations

import math

import pcbnew

UM = 1_000_000.0

STATIC, POUR, KEEPOUT = "STATIC", "POUR", "KEEPOUT"


def classify_zone(z) -> str:
    """A zone is only a hard obstacle when it is a RULE AREA (keepout)."""
    if z.GetIsRuleArea():
        return KEEPOUT
    return POUR


def obstacles_on(board, layer_name: str, exclude_net_codes=()):
    """Return (static, pours, keepouts) for one copper layer.

    STATIC  = tracks and vias of other nets -- real copper that will not move
    POUR    = filled zones -- will retreat/re-pour around a new route
    KEEPOUT = rule areas -- genuinely impassable
    """
    static, pours, keepouts = [], [], []
    for t in board.GetTracks():
        if t.GetNetCode() in exclude_net_codes:
            continue
        if t.Type() == pcbnew.PCB_TRACE_T:
            if board.GetLayerName(t.GetLayer()) != layer_name:
                continue
            s, e = t.GetStart(), t.GetEnd()
            static.append(("track", min(s.x, e.x), min(s.y, e.y), max(s.x, e.x), max(s.y, e.y),
                           t.GetNetname()))
        elif t.Type() == pcbnew.PCB_VIA_T:
            p = t.GetPosition()
            r = t.GetWidth(pcbnew.F_Cu) / 2
            static.append(("via", p.x - r, p.y - r, p.x + r, p.y + r, t.GetNetname()))

    for z in board.Zones():
        kind = classify_zone(z)
        entry = ("zone", z.GetLayerName() if hasattr(z, "GetLayerName") else "?", z.GetNetname())
        if kind == KEEPOUT:
            keepouts.append(entry)
        else:
            pours.append(entry)
    return static, pours, keepouts


def circle_rect_distance(cx, cy, x0, y0, x1, y1) -> float:
    """Distance from a point to an axis-aligned rect (0 if inside). Internal units."""
    dx = max(x0 - cx, 0.0, cx - x1)
    dy = max(y0 - cy, 0.0, cy - y1)
    return math.hypot(dx, dy)


def demonstrate():
    board = pcbnew.LoadBoard("tracker/hardware/hub_board_v9.kicad_pcb")
    print("=== CORRECTED OBSTACLE MODEL ===")
    for layer in ("F.Cu", "B.Cu", "In1.Cu", "In2.Cu"):
        static, pours, keepouts = obstacles_on(board, layer)
        print(f"  {layer:7s} STATIC={len(static):4d}  POUR={len(pours)}  KEEPOUT={len(keepouts)}")

    print()
    print("=== WHAT THIS PROVES, AND WHAT IT DOES NOT ===")
    print("  POUR is NOT a wall: three GND zones are filled but not rule areas, so a filled zone")
    print("  retreats around foreign copper and connects to its own net. A router must not treat the")
    print("  poured polygon as static, and none of the earlier scripts did.")
    print()
    print("  REFUTED: the hypothesis that counting pours explained 'boxed_in_static'. The static")
    print("  counts here are identical to the earlier scripts' counts, which never read zones.")
    print()
    print("  NOT ANSWERED HERE: whether any specific corridor is DRC-legal end to end. That needs the")
    print("  per-pad escape feasibility measurement (fcu_escape_feasibility.py).")


if __name__ == "__main__":
    demonstrate()

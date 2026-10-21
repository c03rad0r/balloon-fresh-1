#!/usr/bin/env python3
"""Layer-aware lane-vs-pad audit: is a lane crossing a pin actually a problem?

The operator asked (2026-10-21): "on what layer are the lanes? They still seem to cross
pins that they shouldn't touch sometimes. Please help me to reason about whether it's a
problem."

The answer depends ENTIRELY on the layer, so this tool reports each crossing in the only
categories that matter:

  SHORT      lane and pad are on the SAME copper layer, different nets, and their copper
             overlaps  -> a real electrical short. FIX.
  TOUCH-NC   lane and pad share a layer, the pad has NO net, copper overlaps -> the lane
             bonds to unconnected metal. Usually harmless for a mechanical/NC pad, but it
             means the lane runs through metal it does not own. REVIEW.
  NEAR       same layer, different nets, no overlap but clearance below the 0.200 mm rule
             -> not yet a short, but a fab/etch risk. REVIEW.
  OK-CROSS   lane passes over the pad's footprint but on the OPPOSITE layer, and the pad is
             SMD (no copper on the lane's layer) -> NOT a problem. This is normal routing.
  THT-CROSS  lane passes over a THROUGH-HOLE pad (or a pad with a drilled barrel) on the
             other layer -> REAL problem: the barrel is copper on both layers. FIX.

Only SAME-LAYER overlap and THT crossings are defects. Everything else is the board doing
its job, and this tool exists so we stop arguing about screenshots.

Exit 0 when there are no SHORT / THT-CROSS. Exit 1 otherwise. NEAR/TOUCH-NC are reported
but do not fail the build.
"""
import argparse
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")
UM = 1_000_000.0
CLEAR = 0.200
F_CU, B_CU = pcbnew.F_Cu, pcbnew.B_Cu


def _pt_seg(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def _rect_dist(x0, y0, x1, y1, r):
    """Distance from segment to axis-aligned rect; 0 if they intersect."""
    # sample the segment; cheap and accurate enough at 0.05mm
    L = math.hypot(x1 - x0, y1 - y0)
    n = max(2, int(L / 0.05) + 2)
    best = 1e9
    for i in range(n + 1):
        t = i / n
        px, py = x0 + t * (x1 - x0), y0 + t * (y1 - y0)
        dx = max(r[0] - px, 0.0, px - r[2])
        dy = max(r[1] - py, 0.0, py - r[3])
        best = min(best, math.hypot(dx, dy))
        if best == 0.0:
            return 0.0
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default=BOARD)
    args = ap.parse_args()
    b = pcbnew.LoadBoard(args.board)
    if not b:
        print("REFUSED: board load failed")
        return 3

    # pads: keep their LAYER SET and whether they have a drilled barrel
    pads = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            ls = p.GetLayerSet()
            layers = tuple(l for l in (F_CU, B_CU) if ls.Contains(l))
            drilled = p.GetDrillSize().x > 0
            bb = p.GetBoundingBox()
            pads.append({
                "ref": fp.GetReference(), "num": p.GetNumber(),
                "net": p.GetNetname() or "",
                "layers": layers, "drilled": drilled,
                "rect": (bb.GetX() / UM, bb.GetY() / UM,
                         (bb.GetX() + bb.GetWidth()) / UM,
                         (bb.GetY() + bb.GetHeight()) / UM),
                "cx": p.GetPosition().x / UM, "cy": p.GetPosition().y / UM,
                "w": p.GetSize().x / UM, "h": p.GetSize().y / UM,
            })

    short, tht_cross, touch_nc, near, ok_cross = [], [], [], [], []
    n_tracks = 0
    for t in b.GetTracks():
        if "VIA" in str(type(t)):
            continue
        if "TRACK" not in str(type(t)):
            continue
        n_tracks += 1
        lay = t.GetLayer()
        net = t.GetNetname() or ""
        x0, y0 = t.GetStart().x / UM, t.GetStart().y / UM
        x1, y1 = t.GetEnd().x / UM, t.GetEnd().y / UM
        hw = t.GetWidth() / UM / 2

        for pd in pads:
            # skip the pads this track legitimately belongs to
            if pd["net"] and pd["net"] == net:
                continue
            d = _rect_dist(x0, y0, x1, y1, pd["rect"]) - hw
            on_this_layer = lay in pd["layers"]
            overlaps = d <= 0.0

            if on_this_layer and overlaps:
                if pd["net"]:
                    short.append(f"SHORT    {net} lane over {pd['ref']}.{pd['num']} "
                                 f"({pd['net']}) layer {lay}")
                else:
                    touch_nc.append(f"TOUCH-NC {net} lane bonds {pd['ref']}.{pd['num']} "
                                    f"(NC pad) layer {lay}")
            elif (not on_this_layer) and pd["drilled"] and overlaps:
                tht_cross.append(f"THT-CROSS {net} lane (layer {lay}) crosses drilled pad "
                                 f"{pd['ref']}.{pd['num']} ({pd['net'] or 'NC'})")
            elif on_this_layer and 0 < d < CLEAR:
                near.append(f"NEAR     {net} lane {d:.3f}mm from {pd['ref']}.{pd['num']} "
                            f"({pd['net'] or 'NC'}) layer {lay}")
            elif (not on_this_layer) and (not pd["drilled"]) and overlaps:
                # the operator's question, answered: a lane over an SMD pad on the OTHER
                # layer is normal routing -- there is no copper on the lane's layer there.
                ok_cross.append(f"OK-CROSS {net} lane (layer {lay}) passes a foreign SMD pad "
                                f"{pd['ref']}.{pd['num']} ({pd['net'] or 'NC'}) "
                                f"-- no copper on layer {lay}")

    def show(title, items, cap=25):
        print(f"--- {title}: {len(items)}")
        for m in items[:cap]:
            print("   " + m)
        if len(items) > cap:
            print(f"   ... and {len(items) - cap} more")

    print(f"tracks audited: {n_tracks}   pads: {len(pads)}")
    show("REAL SHORTS (same-layer copper overlap, different nets)", short)
    show("THT CROSSINGS (lane over a drilled pad on the other layer)", tht_cross)
    show("TOUCH-NC (lane bonds an unconnected pad, same layer)", touch_nc)
    show("NEAR (< 0.200mm clearance, same layer, not touching)", near)
    show("OK-CROSS (lane over a foreign SMD pad on the OTHER layer -- normal, not a defect)",
         ok_cross, cap=8)
    hard = len(short) + len(tht_cross)
    print(f"HARD DEFECTS: {hard}  (shorts {len(short)} + THT crossings {len(tht_cross)})")
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
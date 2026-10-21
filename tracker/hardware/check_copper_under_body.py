#!/usr/bin/env python3
"""Copper-under-body gate: does any track run beneath a footprint on the same side?

The v10 board places modules on both sides. Copper under a module (especially the
ESP32-S3 with its shield can + antenna keep-out, and the LoRa2021/E28 modules whose
datasheets forbid traces beneath) is a keep-out violation -- and visually it reads as
"a lane connecting two pins of the same chip", because the track enters the body and
emerges at a pad row.

Reports, per track, every footprint whose courtyard it crosses (same side only),
with the crossed length.
"""
import math
import sys

import pcbnew

import argparse, os
HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")
UM = 1_000_000.0
HOLE_PREFIXES = ("H", "HW")


def seg_rect_overlap_len(x0, y0, x1, y1, bb):
    """Approximate length of the segment inside the rectangle (25 um sampling)."""
    L = math.hypot(x1 - x0, y1 - y0)
    if L == 0:
        return 0.0
    steps = max(2, int(L / 0.025) + 2)
    inside = 0
    for i in range(steps):
        t = (i + 0.5) / steps
        px, py = x0 + t * (x1 - x0), y0 + t * (y1 - y0)
        if bb[0] <= px <= bb[2] and bb[1] <= py <= bb[3]:
            inside += 1
    return L * inside / steps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default=BOARD)
    args = ap.parse_args()
    b = pcbnew.LoadBoard(args.board)
    if not b:
        print("REFUSED: board load failed")
        return 3
    # own pads per net: a track legitimately enters a body to reach its own pad, so that
    # part of a crossing is subtracted before the 0.5mm threshold is applied.
    own = {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            n = p.GetNet()
            if n and n.GetNetCode():
                pb = p.GetBoundingBox()
                own.setdefault(n.GetNetname(), []).append(
                    (pb.GetX() / UM, pb.GetY() / UM,
                     (pb.GetX() + pb.GetWidth()) / UM, (pb.GetY() + pb.GetHeight()) / UM))
    fps = []
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if ref.startswith(HOLE_PREFIXES):
            continue
        bb = fp.GetBoundingBox(False, True)
        fps.append((ref, fp.GetLayer(),
                    (bb.GetX() / UM, bb.GetY() / UM,
                     (bb.GetX() + bb.GetWidth()) / UM, (bb.GetY() + bb.GetHeight()) / UM)))
    tracks = [t for t in b.GetTracks() if "TRACK" in str(type(t)) and "VIA" not in str(type(t))]
    bad = []
    for t in tracks:
        n = t.GetNet()
        name = n.GetNetname() if n else "?"
        x0, y0 = t.GetStart().x / UM, t.GetStart().y / UM
        x1, y1 = t.GetEnd().x / UM, t.GetEnd().y / UM
        for ref, layer, bb in fps:
            if layer != t.GetLayer():
                continue
            ln = seg_rect_overlap_len(x0, y0, x1, y1, bb)
            # subtract the part of the crossing that is merely reaching an own pad
            for (qx0, qy0, qx1, qy1) in own.get(name, []):
                ln -= seg_rect_overlap_len(x0, y0, x1, y1,
                                           (qx0 - 2.0, qy0 - 2.0, qx1 + 2.0, qy1 + 2.0))
            if ln > 0.5:   # more than half a mm of genuine traversal
                bad.append(f"UNDER BODY {ln:5.2f}mm: {name} track runs beneath {ref}")
    for v in bad:
        print("  ", v)
    print(f"tracks: {len(tracks)}  crossings: {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
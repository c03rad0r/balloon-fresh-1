#!/usr/bin/env python3
"""Verify the GUI handoff board and print the routing brief for the two remaining nets."""
import math
import sys

import pcbnew


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "docs/fab/handoff/hub_board_v9.kicad_pcb"
    b = pcbnew.LoadBoard(path)
    if b is None:
        print(f"COULD NOT LOAD {path}")
        return 1
    tracks = list(b.GetTracks())
    tr = [t for t in tracks if t.Type() != pcbnew.PCB_VIA_T]
    vi = [t for t in tracks if t.Type() == pcbnew.PCB_VIA_T]
    nets = set(t.GetNetname() for t in tr)
    print(f"board: {path}")
    print(f"  tracks {len(tr)}   vias {len(vi)}   nets with copper {len(nets)} of {b.GetNetCount()-1}")

    bb = b.GetBoardEdgesBoundingBox()
    print(f"  outline {pcbnew.ToMM(bb.GetWidth()):.2f} x {pcbnew.ToMM(bb.GetHeight()):.2f} mm")

    print("\nunrouted nets (the hand-route task):")
    for net in ("/SX1280_MOSI", "/SX1280_SCK"):
        n = len([t for t in tr if t.GetNetname() == net])
        pads = []
        for fp in b.GetFootprints():
            for p in fp.Pads():
                if p.GetNetname() == net:
                    c = p.GetPosition()
                    pads.append((fp.GetReference(), str(p.GetNumber()),
                                 pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)))
        print(f"  {net}: {n} track(s) on the board -- UNROUTED")
        for r, num, x, y in sorted(pads):
            print(f"      {r}.{num:3} at ({x:6.2f},{y:6.2f})")
        if len(pads) >= 2:
            (r1, n1, x1, y1), (r2, n2, x2, y2) = pads[0], pads[1]
            d = math.hypot(x2 - x1, y2 - y1)
            print(f"      straight-line span: {d:.2f} mm  "
                  f"(band: {'CROSS-BOARD, use B.Cu' if d > 12 else 'local'})")

    print("\nescape data measured earlier (find_pinch_point.py), for the B.Cu route:")
    print("  U4.17  F.Cu constrained (1.05 mm, blocked by +3V3) | B.Cu 12.00 mm, 7 dirs >= 2 mm")
    print("  U4.18  F.Cu 10.75 mm                               | B.Cu 12.00 mm, 7 dirs >= 2 mm")
    print("  => route both on B.Cu; F.Cu has no room at the U4 end.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

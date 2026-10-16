#!/usr/bin/env python3
"""Does hub_board_v9 implement ADR-046 Option A (a routed 0.9 x 6.0 mm slot) or Option B (plain pads)?

THE QUESTION THIS SETTLES. Astra reviewed the edge-launch drawing and said it shows "two boards
end-to-end with a solder bridge, not the claimed seated tab-and-slot interface". ADR-046 4.2 recommends
Option A for the first prototype: the hub's edge carries a ROUTED SLOT 0.9 mm wide x 6.0 mm deep, the
wing tab inserts 6.0 mm INTO it, and the lands are on the hub's EDGE FACES (soldered on both faces).
Option B is a plain pad pair on the top/bottom face beside the edge, no slot, joint carried by the
fillet alone.

A slot 0.9 x 6.0 mm cut into the board edge must appear in Edge.Cuts as an internal closed contour (or a
notch). The J_W* pads should then sit on more than one layer close to that contour. If Edge.Cuts carries
only the 70 x 70 rectangle and the pads are F.Cu only, the board is Option B and the ADR and the board
disagree -- which is the defect to report, not to draw around.

Run: introspect_edge_interface.py
"""
import builtins
import hashlib
import sys

import pcbnew

BOARD = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"


def main():
    print(f"board: {BOARD}")
    print(f"sha256: {hashlib.sha256(open(BOARD, 'rb').read()).hexdigest()}")
    b = pcbnew.LoadBoard(BOARD)

    # --- 1. Edge.Cuts geometry: how many closed contours, what sizes?
    print("\n=== Edge.Cuts contours ===")
    segs = [d for d in b.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    print(f"  {len(segs)} edge segments")
    # cluster segments into contours by connectivity
    pts = []
    for s in segs:
        try:
            pts.append((s.GetStart(), s.GetEnd()))
        except Exception:
            pass
    used = [False] * len(pts)
    contours = []
    for i in range(len(pts)):
        if used[i]:
            continue
        chain = [pts[i]]
        used[i] = True
        grew = True
        while grew:
            grew = False
            for j in range(len(pts)):
                if used[j]:
                    continue
                a, bb = pts[j]
                tail = chain[-1][1]
                if (abs(a.x - tail.x) < 1000 and abs(a.y - tail.y) < 1000):
                    chain.append(pts[j]); used[j] = True; grew = True
                elif (abs(bb.x - tail.x) < 1000 and abs(bb.y - tail.y) < 1000):
                    chain.append((bb, a)); used[j] = True; grew = True
        contours.append(chain)
    for k, c in enumerate(contours):
        xs = [pcbnew.ToMM(p.x) for seg in c for p in seg]
        ys = [pcbnew.ToMM(p.y) for seg in c for p in seg]
        w, h = builtins.max(xs) - builtins.min(xs), builtins.max(ys) - builtins.min(ys)
        kind = "POSSIBLE SLOT" if (w < 3 or h < 3) else "board outline"
        print(f"  contour {k}: {len(c)} segs  bbox {w:6.2f} x {h:6.2f} mm  "
              f"x[{builtins.min(xs):6.2f},{builtins.max(xs):6.2f}] "
              f"y[{builtins.min(ys):6.2f},{builtins.max(ys):6.2f}]  -> {kind}")

    # --- 2. the J_W* connectors: which layers are their pads on?
    print("\n=== J_W* pad layers (Option A lands on the slot FACES = several layers) ===")
    for ref in ("J_W1", "J_W2", "J_W3", "J_W4"):
        fp = b.FindFootprintByReference(ref)
        if fp is None:
            print(f"  {ref}: ABSENT")
            continue
        layers = {}
        for p in fp.Pads():
            ln = pcbnew.LayerName(p.GetLayer())
            layers.setdefault(ln, 0)
            layers[ln] += 1
        print(f"  {ref}: {layers}")

    # --- 3. verdict
    print("\n=== VERDICT ===")
    def _thin(c):
        xs = [pcbnew.ToMM(p.x) for seg in c for p in seg]
        ys = [pcbnew.ToMM(p.y) for seg in c for p in seg]
        return (builtins.max(xs) - builtins.min(xs)) < 3 or (builtins.max(ys) - builtins.min(ys)) < 3
    slot_like = [c for c in contours if _thin(c)]
    print(f"  Edge.Cuts contours that could be a 0.9 x 6.0 slot: {len(slot_like)}")
    if not slot_like:
        print("  => NO SLOT IN Edge.Cuts. The board implements OPTION B (plain pads on the face),")
        print("     while ADR-046 4.2 RECOMMENDS Option A for the first prototype.")
        print("     This is a BOARD-vs-ADR disagreement. It is a decision for the operator, and the")
        print("     drawing must not silently depict one while the other is built.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

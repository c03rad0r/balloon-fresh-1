#!/usr/bin/env python3
"""Place the RF match OUTSIDE U4's courtyard, then verify no courtyard overlap anywhere.

THIRD ATTEMPT, and the first one with the right obstacle set. The two failures before it, both
caught by DRC, are the reason this script exists in this form:

  ATTEMPT 1 used an assumed 1.5 mm separation constant while the match elements' real courtyards are
  1.91 x 1.01 and 1.95 x 1.03 mm. Result: C0 and L1 courtyards overlapped by 0.15 mm.

  ATTEMPT 2 fixed that pair but still excluded U4 from the obstacle set, so L1 at 2.50 mm from
  U4.pad22 landed INSIDE U4's own 6.19 x 6.19 mm courtyard. Result: courtyards_overlap U4 <-> L1.
  The lesson: "clear of U4's PADS" is not "clear of U4". pad22 sits 0.70 mm INSIDE the courtyard
  edge, so any site within a few mm of the pad is inside the courtyard by construction.

This version treats every footprint courtyard, INCLUDING U4's, as a hard obstacle, reads the match
elements' real courtyard sizes, and verifies the result by re-checking all pairs afterwards.

Usage: place_rf_match3.py <board.kicad_pcb>
"""
import math
import sys

import pcbnew

CLEAR = 0.20


def mm(v):
    return pcbnew.ToMM(v)


def courtyard(board, ref):
    fp = board.FindFootprintByReference(ref)
    cy = fp.GetCourtyard(pcbnew.F_CrtYd)
    if cy.OutlineCount():
        b = cy.BBox()
        return (mm(b.GetLeft()), mm(b.GetTop()), mm(b.GetRight()), mm(b.GetBottom())), "F.CrtYd"
    b = fp.GetBoundingBox(False, False)
    return (mm(b.GetLeft()), mm(b.GetTop()), mm(b.GetRight()), mm(b.GetBottom())), "bbox"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"
    b = pcbnew.LoadBoard(path)

    # U4's courtyard is a hard obstacle. Read it, do not assume.
    (ux0, uy0, ux1, uy1), usrc = courtyard(b, "U4")
    p22 = next(p for p in b.FindFootprintByReference("U4").Pads() if str(p.GetNumber()) == "22")
    c = p22.GetPosition()
    rx, ry = mm(c.x), mm(c.y)
    print(f"board: {path}")
    print(f"U4 courtyard x {ux0:.2f}..{ux1:.2f}  y {uy0:.2f}..{uy1:.2f}  [{usrc}]")
    print(f"U4.pad22 RFIO at ({rx:.2f},{ry:.2f})  (pad22 is {uy1-ry:.2f} mm inside the courtyard bottom)")
    print()

    matches = {r: courtyard(b, r)[0] for r in ("C0", "L1")}
    for r, box in matches.items():
        print(f"  {r} courtyard {(box[2]-box[0]):.2f} x {(box[3]-box[1]):.2f} mm")

    # Every footprint courtyard except the two being placed is an obstacle.
    court = []
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if ref in ("C0", "L1"):
            continue
        box, _src = courtyard(b, ref)
        court.append((ref, box))

    pads = []
    for fp in b.GetFootprints():
        if fp.GetReference() in ("C0", "L1"):
            continue
        for p in fp.Pads():
            r = p.GetBoundingBox()
            pads.append((fp.GetReference(), str(p.GetNumber()), p.GetNetname(),
                         mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom())))

    def rect_vs_rect(a, bx):
        dx = max(0.0, max(a[0] - bx[2], bx[0] - a[2]))
        dy = max(0.0, max(a[1] - bx[3], bx[1] - a[3]))
        return math.hypot(dx, dy)

    def legal(x0, y0, x1, y1, placed):
        if not (0.6 < x0 and x1 < 69.4 and 0.6 < y0 and y1 < 69.4):
            return False, "off board"
        for ref, box in court:
            if rect_vs_rect((x0, y0, x1, y1), box) < CLEAR:
                return False, f"courtyard {ref}"
        for ref, num, net, ax, ay, bx, by in pads:
            if rect_vs_rect((x0, y0, x1, y1), (ax, ay, bx, by)) < CLEAR:
                return False, f"pad {ref}.{num}"
        for (px0, py0, px1, py1) in placed:
            if rect_vs_rect((x0, y0, x1, y1), (px0, py0, px1, py1)) < CLEAR:
                return False, "other match element"
        return True, None

    placed = []
    plan = []
    # Search downward and sideways from the pad, but require being OUTSIDE U4's courtyard.
    for name in ("C0", "L1"):
        box = matches[name]
        w, h = box[2] - box[0], box[3] - box[1]
        best = None
        for k in range(1, 90):
            yy = uy1 + CLEAR + h / 2 + 0.15 * (k - 1)
            for dx in [0, 0.25, -0.25, 0.5, -0.5, 0.75, -0.75, 1.0, -1.0,
                       1.5, -1.5, 2.0, -2.0, 3.0, -3.0, 4.0, -4.0, 5.0, -5.0]:
                cx, cy = rx + dx, yy
                x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
                ok, why = legal(x0, y0, x1, y1, placed)
                if ok:
                    best = (cx, cy, d_ := math.hypot(cx - rx, cy - ry), (x0, y0, x1, y1))
                    break
            if best:
                break
        if not best:
            print(f"\n  {name}: NO LEGAL SITE FOUND below the U4 courtyard")
            return 1
        cx, cy, d, rr = best
        placed.append(rr)
        plan.append((name, cx, cy, d))
        print(f"\n  {name:4} site ({cx:6.2f},{cy:6.2f})  {d:5.2f} mm from RFIO  "
              f"courtyard x {rr[0]:.2f}..{rr[2]:.2f} y {rr[1]:.2f}..{rr[3]:.2f}  LEGAL")

    print("\nverification -- courtyard pairs:")
    ok_all = True
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            a, bb = placed[i], placed[j]
            ox = min(a[2], bb[2]) - max(a[0], bb[0])
            oy = min(a[3], bb[3]) - max(a[1], bb[1])
            v = "OVERLAP" if (ox > 0 and oy > 0) else "CLEAR"
            if v == "OVERLAP":
                ok_all = False
            print(f"  C0 vs L1: dx={ox:.3f} dy={oy:.3f} -> {v}")
    # and each against U4
    for (x0, y0, x1, y1), nm in zip(placed, [p[0] for p in plan]):
        ox = min(x1, ux1) - max(x0, ux0)
        oy = min(y1, uy1) - max(y0, uy0)
        v = "OVERLAP" if (ox > 0 and oy > 0) else "CLEAR"
        if v == "OVERLAP":
            ok_all = False
        print(f"  {nm} vs U4 courtyard: dx={ox:.3f} dy={oy:.3f} -> {v}")
    print(f"\nALL CLEAR: {ok_all}")
    print("\nSITES FOR move_rf_match.py:")
    for name, cx, cy, d in plan:
        print(f'    "{name}": ({cx:.2f}, {cy:.2f}),   # {d:.2f} mm from U4.pad22')
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())

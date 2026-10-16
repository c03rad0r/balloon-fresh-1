#!/usr/bin/env python3
"""Find two NON-FOULING legal sites for the RF match, using the parts' REAL courtyard sizes.

REPLACES the flawed search in place_rf_match.py, which used an assumed 1.5 mm separation constant
while the 0402 match elements are ~1.9 mm wide. Result: C0 and L1 were placed with courtyards
overlapping by 0.15 mm and DRC reported `courtyards_overlap`. That is an off-by-one of exactly the
kind this session keeps producing: a constant assumed instead of read.

This version READS each element's courtyard box from the board and enforces a true non-overlap test
between candidate sites. It also reports the courtyard size it used, so the assumption is visible.

Usage: place_rf_match2.py <board.kicad_pcb>
"""
import math
import sys

import pcbnew

CLEAR = 0.20
SEARCH_DIRS = [(0, 1), (1, 1), (-1, 1), (1, 0), (-1, 0), (0, -1)]
STEPS = [0.25 * k for k in range(1, 41)]     # 0.25 .. 10.0 mm


def mm(v):
    return pcbnew.ToMM(v)


def courtyard_box(board, ref):
    fp = board.FindFootprintByReference(ref)
    cy = fp.GetCourtyard(pcbnew.F_CrtYd)
    if cy.OutlineCount():
        b = cy.BBox()
        return (mm(b.GetLeft()), mm(b.GetTop()), mm(b.GetRight()), mm(b.GetBottom()))
    b = fp.GetBoundingBox(False, False)
    return (mm(b.GetLeft()), mm(b.GetTop()), mm(b.GetRight()), mm(b.GetBottom()))


def obstacles(board, skip=("C0", "L1")):
    out = []
    for fp in board.GetFootprints():
        if fp.GetReference() in skip:
            continue
        for p in fp.Pads():
            r = p.GetBoundingBox()
            out.append((fp.GetReference(), str(p.GetNumber()), p.GetNetname(),
                        mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom())))
    for t in board.GetTracks():
        a, c = t.GetStart(), t.GetEnd()
        out.append(("trk", "", t.GetNetname(), mm(a.x), mm(a.y), mm(c.x), mm(c.y)))
    return out


def rect_clear(x0, y0, x1, y1, obs, clearance):
    for ref, num, net, ax, ay, bx, by in obs:
        if ref == "trk":
            n = 14
            for i in range(n + 1):
                px = ax + (bx - ax) * i / n
                py = ay + (by - ay) * i / n
                dx = max(0.0, max(x0 - px, px - x1))
                dy = max(0.0, max(y0 - py, py - y1))
                if math.hypot(dx, dy) < clearance:
                    return False, (ref, num, net)
        else:
            dx = max(0.0, max(ax - x1, x0 - bx))
            dy = max(0.0, max(ay - y1, y0 - by))
            if math.hypot(dx, dy) < clearance:
                return False, (ref, num, net)
    return True, None


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"
    b = pcbnew.LoadBoard(path)
    fp = b.FindFootprintByReference("U4")
    p22 = next(p for p in fp.Pads() if str(p.GetNumber()) == "22")
    c = p22.GetPosition()
    rx, ry = mm(c.x), mm(c.y)

    # REAL courtyard sizes, read not assumed.
    cb = {r: courtyard_box(b, r) for r in ("C0", "L1")}
    print(f"board: {path}")
    print(f"U4.pad22 (RFIO) at ({rx:.2f}, {ry:.2f});  clearance {CLEAR} mm")
    for r, box in cb.items():
        print(f"  {r} courtyard: x {box[0]:.2f}..{box[2]:.2f}  y {box[1]:.2f}..{box[3]:.2f}"
              f"  ({(box[2]-box[0]):.2f} x {(box[3]-box[1]):.2f} mm)")
    print()

    obs = obstacles(b)
    print(f"obstacles (C0/L1 excluded, they are being placed): {len(obs)}\n")

    placed = []          # (cx, cy, w, h)
    for name in ("C0", "L1"):
        box = cb[name]
        w, h = box[2] - box[0], box[3] - box[1]
        # place the courtyard CENTRE at the candidate point
        found = None
        for d in STEPS:
            for ux, uy in SEARCH_DIRS:
                mag = math.hypot(ux, uy)
                cx = rx + ux / mag * d
                cy = ry + uy / mag * d
                x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
                if not (0.6 < x0 and x1 < 69.4 and 0.6 < y0 and y1 < 69.4):
                    continue
                ok, blocker = rect_clear(x0, y0, x1, y1, obs, CLEAR)
                if ok:
                    for (px, py, pw, ph) in placed:
                        # TRUE courtyard-vs-courtyard non-overlap with clearance
                        ox = min(x1 + CLEAR, px + pw / 2 + CLEAR) - max(x0 - CLEAR, px - pw / 2 - CLEAR)
                        oy = min(y1 + CLEAR, py + ph / 2 + CLEAR) - max(y0 - CLEAR, py - ph / 2 - CLEAR)
                        if ox > 0 and oy > 0:
                            ok = False
                            break
                if ok:
                    found = (cx, cy, d)
                    break
            if found:
                break
        if found:
            cx, cy, d = found
            placed.append((cx, cy, w, h))
            print(f"  {name:4} site ({cx:6.2f},{cy:6.2f})  {d:5.2f} mm from RFIO  "
                  f"courtyard x {cx-w/2:.2f}..{cx+w/2:.2f} y {cy-h/2:.2f}..{cy+h/2:.2f}  LEGAL")
        else:
            print(f"  {name:4} NO LEGAL SITE within {max(STEPS)} mm")

    # Prove the two courtyards do not overlap.
    if len(placed) == 2:
        (ax, ay, aw, ah), (bx, by, bw, bh) = placed
        ox = min(ax + aw / 2, bx + bw / 2) - max(ax - aw / 2, bx - bw / 2)
        oy = min(ay + ah / 2, by + bh / 2) - max(ay - ah / 2, by - bh / 2)
        print(f"\ncourtyard overlap C0 vs L1: dx={ox:.3f} mm  dy={oy:.3f} mm  "
              f"-> {'OVERLAP' if (ox > 0 and oy > 0) else 'CLEAR'}")
        print(f"centre-to-centre: {math.hypot(ax-bx, ay-by):.2f} mm")
    return 0


if __name__ == "__main__":
    sys.exit(main())

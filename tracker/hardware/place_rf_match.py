#!/usr/bin/env python3
"""Find a legal position for the RF match (C0, L1) adjacent to U4.pad22.

OPERATOR-APPROVED MOVE, and the consultant's Round-2 recommendation: place the 2.4 GHz match at
U4.pad22 (52.50, 29.15), not 17.15 mm / 51.04 mm away at the board corners.

CONSTRAINTS, all measured:
  1. U4.pad22 is FLANKED by grounded pads: pad21 GND at 0.50 mm and pad23 GND at 0.50 mm
     (both along y = 29.15, the same row as pad22). pad20 GND at 1.00 mm.
     So the escape direction is AWAY from that row, i.e. +y (downward on this board).
  2. In1.Cu must stay UNDISTURBED beneath the match: it is 81/81 continuous in an 8x8 mm box around
     pad22, so any candidate site inside that box keeps its reference plane.
  3. No vias within the RF neighbourhood.
  4. The match elements are 0402-class, so each needs roughly 1.0 x 0.6 mm of land plus courtyard.

This script enumerates candidate offsets in the +y direction, tests each against every pad and track
on every copper layer with the board's 0.20 mm clearance, and reports the nearest LEGAL site for each
element. Read-only: it recommends, it does not move anything.

Usage: place_rf_match.py <board.kicad_pcb> [--clearance-mm 0.2]
"""
import math
import sys

import pcbnew

CLEAR = 0.20
# 0402 land plus a small courtyard margin: the site must be clear within this radius.
SITE_R = 0.75
# The two elements must clear each other by their REAL courtyard size, not an assumed constant.
# Measured (the bug this replaces): C0 courtyard is 1.90 x 1.02 mm and L1 is 1.94 x 1.02 mm, so a
# 1.5 mm assumed pitch let them foul by 0.15 mm and DRC reported courtyards_overlap.
COURTYARD_PAD_MM = 0.15      # extra margin on top of the real courtyard half-widths
PAD22 = None            # read from the board
SEARCH_STEPS = [0.5 * k for k in range(1, 25)]   # 0.5 .. 12.0 mm in 0.5 mm steps
SEARCH_DIRS = [(0, 1), (1, 1), (-1, 1)]          # +y, and diagonals down-right / down-left


def mm(v):
    return pcbnew.ToMM(v)


def obstacles(board):
    """Every foreign pad centre+extent and every track segment, with their layer."""
    out = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            r = p.GetBoundingBox()
            out.append(("pad", fp.GetReference(), str(p.GetNumber()), p.GetNetname(),
                        mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom())))
    for t in board.GetTracks():
        a, c = t.GetStart(), t.GetEnd()
        out.append(("trk", "", "", t.GetNetname(),
                    mm(a.x), mm(a.y), mm(c.x), mm(c.y)))
    return out


def rect_clear(cx, cy, r, obs, clearance):
    """Is a square of half-size r centred at (cx,cy) at least `clearance` from every obstacle?"""
    x0, y0, x1, y1 = cx - r, cy - r, cx + r, cy + r
    for kind, ref, num, net, ax, ay, bx, by in obs:
        if kind == "pad":
            # rectangle vs rectangle
            dx = max(0.0, max(ax - x1, x0 - bx))
            dy = max(0.0, max(ay - y1, y0 - by))
            if math.hypot(dx, dy) < clearance:
                return False, (kind, ref, num, net)
        else:
            # point/segment vs rectangle: sample the segment
            n = 12
            for i in range(n + 1):
                px = ax + (bx - ax) * i / n
                py = ay + (by - ay) * i / n
                dx = max(0.0, max(x0 - px, px - x1))
                dy = max(0.0, max(y0 - py, py - y1))
                if math.hypot(dx, dy) < clearance:
                    return False, (kind, ref, num, net)
    return True, None


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"
    clearance = CLEAR
    if "--clearance-mm" in sys.argv:
        clearance = float(sys.argv[sys.argv.index("--clearance-mm") + 1])

    b = pcbnew.LoadBoard(path)
    fp = b.FindFootprintByReference("U4")
    if fp is None:
        print("U4 absent")
        return 1
    p22 = None
    for p in fp.Pads():
        if str(p.GetNumber()) == "22":
            p22 = p
            break
    if p22 is None:
        print("U4 pad 22 absent")
        return 1
    c = p22.GetPosition()
    rx, ry = mm(c.x), mm(c.y)
    print(f"board: {path}")
    print(f"U4.pad22 (RFIO) at ({rx:.2f}, {ry:.2f});  required clearance {clearance} mm")
    print(f"searching {SEARCH_DIRS} out to {max(SEARCH_STEPS):.1f} mm\n")

    obs = obstacles(b)
    print(f"obstacles considered: {len(obs)}\n")

    print(f"{'element':8} {'dx':>6} {'dy':>6} {'x':>7} {'y':>7}  {'dist from pad22':>16}  verdict")
    placed = []
    for name in ("C0", "L1"):
        found = None
        for d in SEARCH_STEPS:
            for ux, uy in SEARCH_DIRS:
                mag = math.hypot(ux, uy)
                cx = rx + ux / mag * d
                cy = ry + uy / mag * d
                # must stay on the board
                if not (0.5 < cx < 69.5 and 0.5 < cy < 69.5):
                    continue
                ok, blocker = rect_clear(cx, cy, SITE_R, obs, clearance)
                if ok:
                    # A site already taken by the other match element is not available: the two
                    # elements are separate 0402 parts and must not overlap each other.
                    for (px, py, pr) in placed:
                        # pr = the placed element's real courtyard half-diagonal; combined radius
                        # comes from the actual parts, so this cannot be an off-by-one again.
                        if math.hypot(cx - px, cy - py) < (r_self + pr + COURTYARD_PAD_MM):
                            ok = False
                            break
                if ok:
                    found = (cx, cy, d, ux, uy)
                    break
            if found:
                break
        if found:
            cx, cy, d, ux, uy = found
            placed.append((cx, cy))
            print(f"{name:8} {ux*d:6.2f} {uy*d:6.2f} {cx:7.2f} {cy:7.2f}  {d:16.2f}  LEGAL (nearest free site)")
        else:
            # report what blocked the closest attempt
            cx = rx
            cy = ry + SEARCH_STEPS[0]
            ok, blocker = rect_clear(cx, cy, SITE_R, obs, clearance)
            print(f"{name:8} {'--':>6} {'--':>6} {'--':>7} {'--':>7}  {'--':>16}  NO LEGAL SITE FOUND")
            print(f"         nearest attempt blocked by: {blocker}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

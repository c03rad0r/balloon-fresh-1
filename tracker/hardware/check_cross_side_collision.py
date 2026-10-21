#!/usr/bin/env python3
"""CROSS-SIDE COLLISION gate (B19) -- the defect that invalidated a whole routing pass.

Why this exists (2026-10-21): the v10 board had U1 (ESP32, front) and U_E28 (E28 radio,
back) placed DIRECTLY ON TOP OF EACH OTHER:

    U1    courtyard x 10.03..29.57  y 32.42..52.62
    U_E28 courtyard x  9.97..27.23  y 25.43..47.58
    overlap 17.2 x 15.2 mm  -> 15 pad-to-pad physical overlaps, up to 1.5 x 0.39 mm

Measured shorted pairs: U1.1/E28.7, U1.2/E28.6, U1.3/E28.5, U1.4/E28.4, U1.5/E28.3,
U1.6/E28.2, U1.7/E28.1 -- every one of U1's first seven pins through overlapping copper.

WHY NO GATE CAUGHT IT: check_board_geometry.py compares courtyards but only within one
side. Every gate was single-sided. A two-sided board needs cross-side checks -- but the two
checks have DIFFERENT severities, corrected 2026-10-21 after over-claiming:

  * PAD vs PAD across sides -- HARD DEFECT. Both pads are copper; if their rectangles
    overlap they are the same node through the board. This is what caught U1/U_E28 (13
    shorts).
  * COURTYARD vs COURTYARD across sides -- INFORMATIONAL, NOT a defect. Parts on opposite
    faces sit at different Z. Sharing X-Y area is exactly what two-sided population MEANS:
    a module on the front over a module on the back is normal, assembles fine, and is how
    the v10 layout is specified (ADR-118 two-sided default). An earlier version of this
    gate failed on courtyard overlap and produced five FALSE positives -- e.g. U2 (F33,
    39x21mm per the vendor datasheet) over U3/U_C, which are on the opposite face.

Exit 0 = no PAD overlap. Exit 1 = at least one pad overlap. Courtyard overlaps are printed
as INFO and never fail the build.

Exit 0 = no cross-side collision. Exit 1 = collisions named with measured overlap.
"""
import argparse
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")
UM = 1_000_000.0
HOLE_PREFIXES = ("H1", "H2", "H3", "H4", "HW")
# pads may touch the board edge region; ignore nothing else.

F_CU = pcbnew.F_Cu
B_CU = pcbnew.B_Cu


def rect_overlap(a, b):
    """Return (dx, dy, area) of the positive overlap of two (x0,y0,x1,y1) rects."""
    dx = min(a[2], b[2]) - max(a[0], b[0])
    dy = min(a[3], b[3]) - max(a[1], b[1])
    if dx <= 0 or dy <= 0:
        return 0.0, 0.0, 0.0
    return dx, dy, dx * dy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default=BOARD)
    ap.add_argument("--min-area", type=float, default=0.01,
                    help="ignore overlaps smaller than this (mm^2) as numerical noise")
    args = ap.parse_args()
    b = pcbnew.LoadBoard(args.board)
    if not b:
        print("REFUSED: board load failed")
        return 3

    comps = []   # (ref, layer, rect)
    pads = []    # (ref, num, layer, rect)
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if ref.startswith(HOLE_PREFIXES):
            continue
        lay = fp.GetLayer()
        # B20 (2026-10-21): GetBoundingBox(False, True) returns the COURTYARD box only
        # when the footprint DEFINES one. Several v10 footprints define none (measured:
        # the F33 has 0 fp_rect entries), and pcbnew then falls back to the bbox of pads
        # + graphics -- for the F33 that is a fabricated 39.65 x 22.30mm slab, which
        # produced 5 phantom "stacked" reports. Only trust a courtyard the footprint
        # actually declares; otherwise fall back to the PAD FIELD (the real metal).
        has_courtyard = any(g.GetLayer() in (pcbnew.F_CrtYd, pcbnew.B_CrtYd)
                            for g in fp.GraphicalItems())
        if has_courtyard:
            bb = fp.GetBoundingBox(False, True)
            rect = (bb.GetX() / UM, bb.GetY() / UM,
                    (bb.GetX() + bb.GetWidth()) / UM,
                    (bb.GetY() + bb.GetHeight()) / UM)
        else:
            pbbs = [p.GetBoundingBox() for p in fp.Pads()]
            if pbbs:
                rect = (min(x.GetX() for x in pbbs) / UM, min(x.GetY() for x in pbbs) / UM,
                        max(x.GetX() + x.GetWidth() for x in pbbs) / UM,
                        max(x.GetY() + x.GetHeight() for x in pbbs) / UM)
            else:
                continue
        comps.append((ref, lay, rect))
        for p in fp.Pads():
            pb = p.GetBoundingBox()
            pads.append((ref, p.GetNumber(), lay,
                         (pb.GetX() / UM, pb.GetY() / UM,
                          (pb.GetX() + pb.GetWidth()) / UM,
                          (pb.GetY() + pb.GetHeight()) / UM)))

    problems = []
    info = []

    # 1. component courtyard vs component courtyard, DIFFERENT sides -- INFORMATIONAL
    for i in range(len(comps)):
        for j in range(i + 1, len(comps)):
            ra, la, ra_rect = comps[i]
            rb, lb, rb_rect = comps[j]
            if la == lb:
                continue                      # same-side handled by check_board_geometry
            dx, dy, area = rect_overlap(ra_rect, rb_rect)
            if area >= args.min_area:
                info.append(
                    f"INFO     {area:.1f}mm2 shared X-Y: {ra}({la}) over {rb}({lb}) "
                    f"{dx:.2f} x {dy:.2f} mm (opposite faces, no pad contact)")

    # 2. pad vs pad, DIFFERENT sides (these are literal shorts through the board)
    for i in range(len(pads)):
        for j in range(i + 1, len(pads)):
            ra, na, la, pa = pads[i]
            rb, nb, lb, pb = pads[j]
            if la == lb or ra == rb:
                continue
            dx, dy, area = rect_overlap(pa, pb)
            if area >= args.min_area:
                problems.append(
                    f"SHORTED {area:.3f}mm2: {ra}.{na}({la}) overlaps {rb}.{nb}({lb}) "
                    f"{dx:.2f} x {dy:.2f} mm")

    for msg in info[:12]:
        print("   " + msg)
    if len(info) > 12:
        print(f"   ... and {len(info) - 12} more shared-area pairs")
    for msg in problems[:40]:
        print("   " + msg)
    print(f"PAD SHORTS ACROSS SIDES: {len(problems)}   (shared-area pairs: {len(info)}, informational)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
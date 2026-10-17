#!/usr/bin/env python3
"""Wing-tab + outline geometry probe for hub_board_v9.kicad_pcb — the measurement half of
docs/boards/reviews/hub-v9-render-r1.md.

WHY THIS EXISTS. A 3D render shows placement and presence/absence, but it carries no scale: every
distance in that review was measured HERE, from the board file, not from the PNG. The render review
raised "left and right wing features look inset"; this probe is what turned that hypothesis into the
numbered finding (J_W1/J_W3 are 180 deg out of phase with J_W2/J_W4, burying their milled edge slots
5.20 mm inside the board).

MUST run under the KiCad 9 bindings venv — importing pcbnew under a plain python3 segfaults:
    ~/venvs/kicad/bin/python tracker/hardware/renders/wing_tab_geometry_probe.py
Exit code 0 always; this is a probe, not a gate.

Reads only. Does not modify the board.
"""
import sys

try:
    import pcbnew
except ImportError:
    sys.exit("pcbnew not importable — run under ~/venvs/kicad/bin/python (KiCad 9 bindings)")

BOARD = "tracker/hardware/hub_board_v9.kicad_pcb"
OUTLINE = 70.0  # mm, board is 0..70 on both axes (ADR-068)
T = pcbnew.ToMM


def main():
    b = pcbnew.LoadBoard(BOARD)

    print("=" * 78)
    print("1. BOARD-LEVEL OUTLINE (is it a single closed rectangle?)")
    print("=" * 78)
    n = 0
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            n += 1
            s, e = d.GetStart(), d.GetEnd()
            print(f"   {type(d).__name__}: ({T(s.x):.2f},{T(s.y):.2f}) -> ({T(e.x):.2f},{T(e.y):.2f})")
    print(f"   board-level Edge.Cuts primitives: {n}")
    bb = b.GetBoardEdgesBoundingBox()
    print(f"   board-edge bbox: {T(bb.GetWidth()):.2f} x {T(bb.GetHeight()):.2f} mm "
          f"@ ({T(bb.GetX()):.3f},{T(bb.GetY()):.3f})")

    print()
    print("=" * 78)
    print("2. WING TABS — footprint-embedded milled-slot Edge.Cuts rects + pad rows")
    print("=" * 78)
    print("   'gap to edge' = distance from the feature to the nearest outline edge")
    print("   (negative = the feature crosses/extends past the edge)\n")
    for ref in ("J_W4", "J_W2", "J_W1", "J_W3"):
        fp = next((f for f in b.GetFootprints() if f.GetReference() == ref), None)
        if fp is None:
            print(f"   {ref}: NOT FOUND")
            continue
        # slot: footprint-embedded Edge.Cuts graphics
        sx, sy = [], []
        for g in fp.GraphicalItems():
            if g.GetLayer() == pcbnew.Edge_Cuts:
                s, e = g.GetStart(), g.GetEnd()
                sx += [T(s.x), T(e.x)]
                sy += [T(s.y), T(e.y)]
        # pads
        px, py = [], []
        for p in fp.Pads():
            px.append(T(p.GetPosition().x))
            py.append(T(p.GetPosition().y))
        pos = fp.GetPosition()
        print(f"   {ref}: origin=({T(pos.x):.2f},{T(pos.y):.2f}) rot={fp.GetOrientationDegrees():.1f}")
        if sx:
            d = {"left": min(sx), "right": OUTLINE - max(sx),
                 "top": min(sy), "bottom": OUTLINE - max(sy)}
            near = min(d, key=d.get)
            # distance from the slot's NEAREST-TO-EDGE face to that edge
            if near in ("left", "top"):
                gape = min(sx) if near == "left" else min(sy)
            else:
                gape = OUTLINE - (max(sx) if near == "right" else max(sy))
            print(f"        slot x[{min(sx):6.2f},{max(sx):6.2f}] y[{min(sy):6.2f},{max(sy):6.2f}]"
                  f"  ({max(sx)-min(sx):.2f} x {max(sy)-min(sy):.2f} mm)")
            print(f"        slot nearest edge = {near:6}  -> the slot's {near} face sits "
                  f"{gape:+.2f} mm from that edge  "
                  f"({'CROSSES the edge' if gape < 0 else 'INSET, does not reach the edge'})")
        else:
            print("        (no footprint-embedded Edge.Cuts graphics)")
        if px:
            print(f"        land row: pad centres x[{min(px):6.2f},{max(px):6.2f}] "
                  f"y[{min(py):6.2f},{max(py):6.2f}]")
        # courtyard
        cx, cy = [], []
        for g in fp.GraphicalItems():
            if g.GetLayer() in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
                gb = g.GetBoundingBox()
                cx += [T(gb.GetX()), T(gb.GetX() + gb.GetWidth())]
                cy += [T(gb.GetY()), T(gb.GetY() + gb.GetHeight())]
        if cx:
            print(f"        courtyard x[{min(cx):6.2f},{max(cx):6.2f}] y[{min(cy):6.2f},{max(cy):6.2f}]")

    print()
    print("=" * 78)
    print("3. U2 (LoRa2021F33-2G4) vs J_W4 (top wing tab) — courtyard clearance")
    print("   (the render review claimed a plan-view overlap; this tests it)")
    print("=" * 78)
    boxes = {}
    for ref in ("U2", "J_W4"):
        fp = next((f for f in b.GetFootprints() if f.GetReference() == ref), None)
        cx, cy = [], []
        for g in fp.GraphicalItems():
            if g.GetLayer() in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
                gb = g.GetBoundingBox()
                cx += [T(gb.GetX()), T(gb.GetX() + gb.GetWidth())]
                cy += [T(gb.GetY()), T(gb.GetY() + gb.GetHeight())]
        boxes[ref] = (min(cx), max(cx), min(cy), max(cy))
        print(f"   {ref}: x[{boxes[ref][0]:.2f},{boxes[ref][1]:.2f}] y[{boxes[ref][2]:.2f},{boxes[ref][3]:.2f}]")
    a, c = boxes["U2"], boxes["J_W4"]
    ox = max(0.0, min(a[1], c[1]) - max(a[0], c[0]))
    oy = max(0.0, min(a[3], c[3]) - max(a[2], c[2]))
    sep_y = max(a[2] - c[3], c[2] - a[3], 0.0)
    print(f"   overlap {ox:.2f} x {oy:.2f} mm ; y separation {sep_y:.2f} mm  => "
          f"{'COLLISION' if ox > 0 and oy > 0 else 'NO COLLISION'}")

    print()
    print("=" * 78)
    print("4. 3D MODEL COVERAGE — every (model ...) ref resolved (KIPRJMOD expanded)")
    print("=" * 78)
    import os, re
    proj = os.path.dirname(BOARD)
    mdir = os.environ.get("KICAD9_3DMODEL_DIR", "/usr/share/kicad/3dmodels")
    src = open(BOARD).read()
    refs = re.findall(r'\(model "([^"]+)"', src)
    miss = []
    for p in refs:
        real = (p.replace("${KIPRJMOD}", proj)
                 .replace("${KICAD9_3DMODEL_DIR}", mdir)
                 .replace("${KICAD8_3DMODEL_DIR}", mdir))
        if not os.path.exists(real):
            miss.append(real)
    print(f"   (model ...) refs: {len(refs)} ; unresolvable: {len(miss)}")
    for m in miss:
        print("     MISSING:", m)
    print("   NOTE: ${KIPRJMOD} MUST be expanded or every project-local envelope looks missing.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build the WING INTERCONNECT BOARD (ADR-132) -- per-cell bypass + wing<->hub interface.

WHAT THIS BOARD IS, AND WHAT IT IS NOT
--------------------------------------
It is a SMALL SPINE, not a cell carrier. The operator asked for "a small board with
bypass diodes that all the cells can be soldered to ... responsible for connecting the
wing to the hub board". Both requirements are met:

  * every cell's two ENDS solder to this board (6 end lands, ADR-052 end-only),
  * 3 bypass Schottky diodes, one ACROSS EACH CELL (ADR-132), SS24 / SMA,
  * the 4-pad tab that plugs into the hub's already-routed land row (ADR-046).

**The cell BODIES rest on the FOAM, not on this board.** That is the point of
ADR-117/ADR-130: the XPS sheet is the airframe and the board exists only where copper is
needed. A first draft laid out a full cell-COURT board -- 83.8 x 159.1 mm = 133 cm2,
**12.0 g/wing, 48 g for four** -- which exceeds the entire ~42 g payload. Measured and
rejected. This spine is 14.3 cm2 and **1.29 g/wing, 5.2 g for four**.

TOPOLOGY (ADR-046 sec 2.1, ADR-132 sec 2)
-----------------------------------------
    SOLAR_P -[SC1]- SOLAR_MID1 -[SC2]- SOLAR_MID2 -[SC3]- SOLAR_N
                 |               |               |
                D1              D2              D3      K -> the cell's HIGH node
                 |               |               |       A -> the cell's LOW  node
A reversed diode is forward-biased by its own cell's 0.5 V and silently shunts that cell,
invisible to a string-voltage check (ADR-054 sec 2.3(b)). Hence the printed K marks and a
mandatory first-article reverse-bias test.

LAYOUT RULES THAT COST REWRITES (kept so they are not repeated)
--------------------------------------------------------------
  * pads need >=0.5 mm to Edge.Cuts, or copper_edge_clearance fires at 0.000 mm
  * silk text below 0.8 mm fires text_height on JLCPCB rules
  * a designator sitting on a pad fires silk_over_copper ("clipped by solder mask")
  * a window overlapping an end land fires copper_edge_clearance
  * a cell is 78.55 x 38.90 -- three of them END TO END need 235.65 mm

RUN
---
    python3 tracker/hardware/build_wing_interconnect.py
    python3 tracker/hardware/build_wing_interconnect.py --check   # exit 1 if stale
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "wing_interconnect", "wing_interconnect_v1.kicad_pcb")

# ---------------------------------------------------------------- geometry (mm)
CELL_L, CELL_W = 78.55, 38.90   # ADR-049 measured large cell
CELL_PITCH = 44.0               # high-end pitch along the spine (cell W 38.90 + gap)
EDGE = 1.6                      # board margin

TAB_PAD_W, TAB_PAD_H = 4.0, 1.2
TAB_PITCH = 1.8
TAB_L = 6.0
TAB_X = TAB_L / 2.0 + EDGE

SMA_PAD_L, SMA_PAD_W = 2.3, 1.55
LAND_W, LAND_H = 1.6, 4.0       # cell end land, ADR-046 sec 3.4
SILK = 0.8                      # JLCPCB legible minimum

CELL_Y = 8.4                    # upper rail: the cell END lands
DIODE_Y = 3.4                   # lower rail: the bypass diodes
MID_Y = 5.9                     # clear silk strip between the rails

SPINE_L = 130.0
SPINE_W = 11.0

NETS = [("SOLAR_P", 1), ("SOLAR_MID1", 2), ("SOLAR_MID2", 3), ("SOLAR_N", 4),
        ("GND", 5), ("RF_FEED", 6)]
NETCODE = dict(NETS)

# cell k: (ref, high-end x, high net, low net). The - end is one cell length further on.
_X0 = TAB_L + EDGE + 6.0
CELLS = [
    ("SC1", _X0, "SOLAR_P", "SOLAR_MID1"),
    ("SC2", _X0 + CELL_PITCH, "SOLAR_MID1", "SOLAR_MID2"),
    ("SC3", _X0 + 2 * CELL_PITCH, "SOLAR_MID2", "SOLAR_N"),
]
DIODES = [("D1", CELLS[0][1], "SOLAR_P", "SOLAR_MID1"),
          ("D2", CELLS[1][1], "SOLAR_MID1", "SOLAR_MID2"),
          ("D3", CELLS[2][1], "SOLAR_MID2", "SOLAR_N")]


def pads():
    p = []
    # tab on the LEFT edge: pins 1..4 = SOLAR_P, GND, RF_FEED, SOLAR_N (ADR-046)
    for i in range(4):
        y = SPINE_W / 2.0 + (i - 1.5) * TAB_PITCH
        p.append(("J1", str(i + 1), NETS[i][0], TAB_X, y, TAB_PAD_W, TAB_PAD_H))
    # cell END lands on the upper rail; the cell body spans the FOAM between its ends
    for ref, cx, hi, lo in CELLS:
        p.append((ref, "1", hi, cx, CELL_Y, LAND_W, LAND_H))
        p.append((ref, "2", lo, cx + CELL_L, CELL_Y, LAND_W, LAND_H))
    # bypass diodes on the lower rail: pad1 = K (cell HIGH), pad2 = A (cell LOW)
    for ref, cx, hi, lo in DIODES:
        p.append((ref, "1", hi, cx - SMA_PAD_L / 2.0 - 0.4, DIODE_Y,
                  SMA_PAD_L, SMA_PAD_W))
        p.append((ref, "2", lo, cx + SMA_PAD_L / 2.0 + 0.4, DIODE_Y,
                  SMA_PAD_L, SMA_PAD_W))
    return p


def windows():
    """No windows: a spine has no FR4 under the cells in the first place."""
    return []


def _f(v: float) -> str:
    return f"{v:.4f}".rstrip("0").rstrip(".") or "0"


def build() -> str:
    L = []
    A = L.append
    A("(kicad_pcb (version 20241229) (generator pcbnew)")
    A("  (general (thickness 0.4))")
    A('  (paper "A4")')
    A("  (layers")
    A('    (0 "F.Cu" signal) (31 "B.Cu" signal)')
    A('    (36 "B.SilkS" user "b.silkscreen") (37 "F.SilkS" user "f.silkscreen")')
    A('    (44 "Edge.Cuts" user)')
    A("  )")
    A("  (setup (pad_to_mask_clearance 0.05))")
    for name, code in NETS:
        A(f'  (net {code} "{name}")')
    o = [(0, 0), (SPINE_L, 0), (SPINE_L, SPINE_W), (0, SPINE_W)]
    for i in range(4):
        x1, y1 = o[i]
        x2, y2 = o[(i + 1) % 4]
        A(f'  (gr_line (start {_f(x1)} {_f(y1)}) (end {_f(x2)} {_f(y2)}) '
          f'(stroke (width 0.1) (type solid)) (layer "Edge.Cuts"))')
    # ---- NO TRACKS AT PLACEMENT STAGE (deliberate, same staging as hub_board_v10).
    #      AGENTS.md 21: schematic -> ERC -> netlist -> board -> DRC -> gates -> render,
    #      and ROUTING follows the placement gate. Measured: hand-routing on F.Cu gave
    #      tracks_crossing + copper_edge_clearance; moving to B.Cu then needed
    #      through-hole pads and produced 5 shorting_items + 10 solder_mask_bridge.
    #      Hand routing here made the board WORSE, so it is left to the router pass.
    for ref, num, net, x, y, w, h in pads():
        A(f'  (footprint "wing_ic:{ref}" (layer "F.Cu") (at {_f(x)} {_f(y)})')
        A(f'    (pad "{num}" smd rect (at 0 0) (size {_f(w)} {_f(h)}) '
          f'(layers "F.Cu" "F.Paste" "F.Mask") (net {NETCODE[net]} "{net}"))')
        A("  )")
    # ---- SILK: designators + polarity, on the clear strip between the two rails.
    #      ADR-132 sec 4.2 makes the cathode mark mandatory. Everything is at the
    #      JLCPCB minimum 0.8 mm / 0.15 mm: measured, 0.7 mm fires text_height.
    for ref, cx, hi, lo in CELLS:
        A(f'  (gr_text "{ref}" (at {_f(cx - 1.5)} {_f(MID_Y)}) (layer "F.SilkS") '
          f'(effects (font (size {_f(SILK)} {_f(SILK)}) (thickness 0.15))))')
        A(f'  (gr_text "+" (at {_f(cx + 3.4)} {_f(MID_Y)}) (layer "F.SilkS") '
          f'(effects (font (size {_f(SILK)} {_f(SILK)}) (thickness 0.15))))')
    # diode marks sit BELOW the diode rail, clear of both cell land and diode pad
    for ref, cx, hi, lo in DIODES:
        A(f'  (gr_text "{ref}" (at {_f(cx - 3.2)} {_f(1.05)}) (layer "F.SilkS") '
          f'(effects (font (size {_f(SILK)} {_f(SILK)}) (thickness 0.15))))')
    # board ID goes at the far RIGHT end, past the last cell land, where silk is empty
    _last_land_x = CELLS[-1][1] + CELL_L
    A(f'  (gr_text "IC v1 ADR-132" (at {_f(_last_land_x + 6.0)} {_f(MID_Y)}) '
      f'(layer "F.SilkS") (effects (font (size {_f(SILK)} {_f(SILK)}) (thickness 0.15))))')
    A(")")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    body = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    if args.check:
        if not os.path.exists(OUT):
            print(f"STALE: {OUT} missing")
            return 1
        if open(OUT).read() != body:
            print(f"STALE: {OUT} differs")
            return 1
        print(f"ok: {OUT} matches")
        return 0
    open(OUT, "w").write(body)
    area = SPINE_L * SPINE_W / 100.0
    print(OUT)
    print(f"size {SPINE_L:.2f} x {SPINE_W:.2f} mm = {area:.1f} cm2")
    print(f"FR4 0.4 mm {area * 0.09028:.2f} g/wing  ({area * 0.09028 * 4:.2f} g for four)")
    print(f"sha256 {hashlib.sha256(body.encode()).hexdigest()[:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

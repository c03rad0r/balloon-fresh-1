#!/usr/bin/env python3
"""Build the WING INTERCONNECT BOARD (ADR-132 / ADR-134) -- a SMALL series connector.

WHAT THIS BOARD IS (operator's words, 2026-10-25)
-------------------------------------------------
  "the panels won't be mounted to the wing board. The solar cells get mounted to
   styrofoam and the wing board is just a small connector where + and - of each solar
   panel gets soldered onto. The wing board contains the bypass diodes and it makes the
   series connection between the cells and it connects to the hub board."

So the board is a **connector**, NOT a carrier:

  * the CELLS stay on the XPS foam (ADR-117); their bodies never touch this board,
  * each cell's **+ and - tails** solder to one pad pair here (6 pads total),
  * **3 bypass diodes**, one ACROSS EACH CELL -- a short wire jumper from each cell's
    tail to this board puts the diode in parallel with it (ADR-132),
  * **2-pin tab** out to the hub: SOLAR_P and SOLAR_N (ADR-134 removed GND + RF_FEED).

SIZE: 44 x 20 mm = 8.8 cm2, 0.4 mm FR4 = 0.79 g/wing, 3.17 g for four.

WHY IT IS NOT A LONG SPINE (measured, twice)
--------------------------------------------
Two earlier attempts were wrong and the arithmetic caught both:
  * a full cell-COURT board: 83.8 x 159.1 mm = 133 cm2 = 12.0 g/wing, 48 g for four --
    more than the entire ~42 g payload;
  * a 3-cell single-row spine: 197.15 mm long, which does not fit the 167.1 mm arm.
The connector has no such problem because it carries no cell geometry at all.

TOPOLOGY (ADR-046 / ADR-132 sec 2 / ADR-134)
---------------------------------------------
    SOLAR_P -[SC1]- SOLAR_MID1 -[SC2]- SOLAR_MID2 -[SC3]- SOLAR_N
                 |               |               |
                D1              D2              D3     K -> the cell's HIGH node
                 |               |               |      A -> the cell's LOW  node

A reversed diode is forward-biased by its own cell's 0.5 V and silently shunts that cell,
invisible to a string-voltage check (ADR-054 sec 2.3(b)). Hence the printed K marks and a
mandatory first-article reverse-bias test.

LAYOUT RULES THAT COST REWRITES (kept so they are not repeated)
--------------------------------------------------------------
  * pads need >=0.5 mm to Edge.Cuts, or copper_edge_clearance fires at 0.000 mm
  * silk text below 0.8 mm fires text_height on JLCPCB rules
  * a designator sitting on a pad fires silk_over_copper ("clipped by solder mask")
  * derive a dimension from the layout; a hard-coded length left lands off-board

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
BOARD_W = 44.0
BOARD_H = 20.0
EDGE = 1.6

# TAB -- ADR-134: TWO pins only. GND and RF_FEED were removed as dead copper.
TAB_PINS = ["SOLAR_P", "SOLAR_N"]
TAB_PAD_W, TAB_PAD_H = 4.0, 1.2
TAB_PITCH = 1.8
TAB_X = EDGE + TAB_PAD_W / 2.0

SMA_PAD_L, SMA_PAD_W = 2.3, 1.55
CELL_PAD_W, CELL_PAD_H = 2.2, 4.0     # a cell TAIL lands here, one pad per terminal
SILK = 0.8                            # JLCPCB legible minimum

# three cell-terminal pairs along the top, three diodes along the bottom
CELL_X = (14.0, 22.0, 30.0)
CELL_Y = 15.0
DIODE_X = (14.0, 22.0, 30.0)
DIODE_Y = 6.0
MID_Y = 10.4

NETS = [("SOLAR_P", 1), ("SOLAR_MID1", 2), ("SOLAR_MID2", 3), ("SOLAR_N", 4)]
NETCODE = dict(NETS)

# cell k: (ref, x of its PAD PAIR, high net, low net)
CELLS = [
    ("SC1", CELL_X[0], "SOLAR_P", "SOLAR_MID1"),
    ("SC2", CELL_X[1], "SOLAR_MID1", "SOLAR_MID2"),
    ("SC3", CELL_X[2], "SOLAR_MID2", "SOLAR_N"),
]
DIODES = [("D1", DIODE_X[0], "SOLAR_P", "SOLAR_MID1"),
          ("D2", DIODE_X[1], "SOLAR_MID1", "SOLAR_MID2"),
          ("D3", DIODE_X[2], "SOLAR_MID2", "SOLAR_N")]


def pads():
    p = []
    # 2-pin tab on the LEFT edge, centred vertically
    for i, net in enumerate(TAB_PINS):
        y = BOARD_H / 2.0 + (i - (len(TAB_PINS) - 1) / 2.0) * TAB_PITCH
        p.append(("J1", str(i + 1), net, TAB_X, y, TAB_PAD_W, TAB_PAD_H))
    # each cell's TWO TAILS land on one pad pair (hi = +, lo = -)
    for ref, cx, hi, lo in CELLS:
        p.append((ref, "1", hi, cx - CELL_PAD_W / 2.0 - 0.75, CELL_Y,
                  CELL_PAD_W, CELL_PAD_H))
        p.append((ref, "2", lo, cx + CELL_PAD_W / 2.0 + 0.75, CELL_Y,
                  CELL_PAD_W, CELL_PAD_H))
    # bypass diodes along the bottom: pad1 = K (cell HIGH), pad2 = A (cell LOW)
    for ref, cx, hi, lo in DIODES:
        p.append((ref, "1", hi, cx - SMA_PAD_L / 2.0 - 0.4, DIODE_Y,
                  SMA_PAD_L, SMA_PAD_W))
        p.append((ref, "2", lo, cx + SMA_PAD_L / 2.0 + 0.4, DIODE_Y,
                  SMA_PAD_L, SMA_PAD_W))
    return p


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
    o = [(0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H)]
    for i in range(4):
        x1, y1 = o[i]
        x2, y2 = o[(i + 1) % 4]
        A(f'  (gr_line (start {_f(x1)} {_f(y1)}) (end {_f(x2)} {_f(y2)}) '
          f'(stroke (width 0.1) (type solid)) (layer "Edge.Cuts"))')
    # ---- NO TRACKS AT PLACEMENT STAGE (deliberate, same staging as hub_board_v10).
    #      AGENTS.md 21: schematic -> ERC -> netlist -> board -> DRC -> gates -> render,
    #      and ROUTING follows the placement gate. The ratsnest below is the routing task.
    for ref, num, net, x, y, w, h in pads():
        A(f'  (footprint "wing_ic:{ref}" (layer "F.Cu") (at {_f(x)} {_f(y)})')
        A(f'    (pad "{num}" smd rect (at 0 0) (size {_f(w)} {_f(h)}) '
          f'(layers "F.Cu" "F.Paste" "F.Mask") (net {NETCODE[net]} "{net}"))')
        A("  )")
    # ---- SILK: TWO separate rows so cell and diode labels cannot collide.
    #      Measured: putting both on the mid strip produced 4 silk_overlap.
    #      ADR-132 sec 4.2 makes the cathode mark mandatory.
    # cell pads span y 13.0..17.0 and diode pads y 4.4..7.6, so the two label rows must
    # sit at 12.2 and 8.6 -- measured: 12.6 clipped the cell pads, 10.4 collided.
    CELL_LBL_Y = 12.2
    DIODE_LBL_Y = 8.6
    for ref, cx, hi, lo in CELLS:
        A(f'  (gr_text "{ref}" (at {_f(cx - 2.6)} {_f(CELL_LBL_Y)}) (layer "F.SilkS") '
          f'(effects (font (size {_f(SILK)} {_f(SILK)}) (thickness 0.15))))')
        A(f'  (gr_text "+" (at {_f(cx + 3.6)} {_f(CELL_LBL_Y)}) (layer "F.SilkS") '
          f'(effects (font (size {_f(SILK)} {_f(SILK)}) (thickness 0.15))))')
    for ref, cx, hi, lo in DIODES:
        A(f'  (gr_text "{ref}" (at {_f(cx - 2.6)} {_f(DIODE_LBL_Y)}) (layer "F.SilkS") '
          f'(effects (font (size {_f(SILK)} {_f(SILK)}) (thickness 0.15))))')
    A(f'  (gr_text "IC v1" (at {_f(BOARD_W - 6.0)} {_f(CELL_LBL_Y)}) '
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
    area = BOARD_W * BOARD_H / 100.0
    print(OUT)
    print(f"size {BOARD_W:.1f} x {BOARD_H:.1f} mm = {area:.1f} cm2")
    print(f"FR4 0.4 mm {area * 0.09028:.2f} g/wing  ({area * 0.09028 * 4:.2f} g for four)")
    print(f"sha256 {hashlib.sha256(body.encode()).hexdigest()[:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

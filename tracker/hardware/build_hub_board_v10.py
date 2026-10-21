#!/usr/bin/env python3
"""v10 flight-hub builder -- PLACEMENT ONLY (ADR-120 R3: no routing before gate sign-off).

Builds hub_board_v10.kicad_pcb from:
  - the v10 netlist (make_v10_netlist.py output, ADR-119/121/123 applied)
  - the operator-APPROVED two-sided placement (GATE-LOG round 1, 53 x 62 mm)
  - ADR-085 wing-seat rotations (the corrected ones -- detector must read EXIT=0)
  - ADR-121 J_PROG + EN RC parts, ADR-124 tether holes (NPTH D2.5)

Outputs the board + a front/back render pair for the round-2 gate.
"""
import os
import sys

import pcbnew

UM = 1_000_000.0
W, H = 53.0, 62.0
HERE = os.path.dirname(os.path.abspath(__file__))
E28_LIB = os.path.join(HERE, "footprints", "e28")
V9_LIB = "/home/c08r4d0r/worktrees/master-check/tracker/hardware/schematics/flight_board/v9_lib/balloon_flight_v9.pretty"

# approved placement (mm, board coords, bottom-left origin) -- from GATE round 1
FRONT = {  # ref: (x, y, rot)
    "U2": (29.0, 48.0, 0),     # F33 courtyard x 9.2..48.8, y 36.85..59.15
    "U1": (12.8, 13.2, 0),      # ESP32-S3
    "U5": (30.0, 8.4, 0),       # GNSS
    "U_HUB_CVT": (29.5, 20.0, 0),
    "U7": (29.5, 24.0, 0),
    "C_CAP1": (42.4, 8.3, 0),
    "C_CAP2": (42.4, 20.3, 0),
    "U6": (26.0, 29.0, 0),
    "J_PROG": (50.0, 25.6, 90), # vertical along right edge (x 47.5..52.5, y 18..33.2)
    "J_W2": (26.5, 62.0, 0),    # north seat
    "J_W4": (26.5, 0.0, 0),     # south seat
}
BACK = {
    "U3": (13.9, 10.8, 0),      # LP Site B
    "U_C": (37.9, 10.8, 0),     # LP Site C (NEW)
    "U_E28": (11.25, 32.75, 0), # E28 ranging module (Site D)
    "J_W1": (0.0, 31.0, 0),     # west seat
    "J_W3": (53.0, 31.0, 0),    # east seat
}
TETHER = [  # (x, y) D2.5 NPTH (ADR-124) -- left of the centre line, clear of the F33
    # courtyard and the J_W2/J_W4 edge seats (which sit at x=26.5). 8mm pair spacing.
    (4.0, H - 4.5), (4.0, H - 12.5),    # H1 H2 top-left, VERTICAL pair 8mm apart (F33 starts x 9.2)
    (4.0, 4.5), (4.0, 12.5),             # H3 H4 bottom-left, vertical pair
]


def load_fp(lib, name):
    fp = pcbnew.FootprintLoad(lib, name)
    if fp is None:
        raise SystemExit(f"footprint load failed: {name} from {lib}")
    return fp


def place(board, fp, ref, value, x, y, rot, side):
    fp.SetReference(ref)
    fp.SetValue(value)
    board.Add(fp)                      # must be on the board BEFORE Flip (segfault otherwise)
    if side == "B":
        fp.Flip(pcbnew.VECTOR2I(0, 0), False)
    fp.SetPosition(pcbnew.VECTOR2I(int(x * UM), int(y * UM)))
    fp.SetOrientation(pcbnew.EDA_ANGLE(rot if side == "F" else -rot, pcbnew.DEGREES_T))


def main():
    out = os.path.join(HERE, "hub_board_v10.kicad_pcb")
    b = pcbnew.NewBoard(out)
    # outline 53x62
    edge = pcbnew.PCB_SHAPE(b)
    edge.SetShape(pcbnew.SHAPE_T_RECTANGLE)
    edge.SetLayer(pcbnew.Edge_Cuts)
    edge.SetStart(pcbnew.VECTOR2I(0, 0))
    edge.SetEnd(pcbnew.VECTOR2I(int(W * UM), int(H * UM)))
    b.Add(edge)

    # radios + digital from the v9 library
    def v9(name):
        return load_fp(V9_LIB, name)
    place(b, v9("LoRa2021F33_2G4"), "U2", "LoRa2021F33-2G4", *FRONT["U2"], "F")
    place(b, v9("LoRa2021_Castellated"), "U3", "LoRa2021 LP", *BACK["U3"], "B")
    place(b, v9("LoRa2021_Castellated"), "U_C", "LoRa2021 LP (Site C)", *BACK["U_C"], "B")
    e28 = load_fp(E28_LIB, "E28-2G4M27SX")
    place(b, e28, "U_E28", "E28-2G4M27SX", *BACK["U_E28"], "B")
    print("placed: U2 F / U3 B / U_C B / U_E28 B")

    # tether holes: NPTH -- pad hole 2.5, pad dia 2.5 (no annulus)
    for i, (hx, hy) in enumerate(TETHER, 1):
        import pcbnew as pn
        m = pn.FOOTPRINT(b)
        pad = pn.PAD(m)
        pad.SetSize(pn.VECTOR2I(int(2.5 * UM), int(2.5 * UM)))
        pad.SetDrillSize(pn.VECTOR2I(int(2.5 * UM), int(2.5 * UM)))
        pad.SetShape(pn.PAD_SHAPE_CIRCLE)
        pad.SetAttribute(pn.PAD_ATTRIB_NPTH)
        pad.SetNumber("1")
        m.Add(pad)
        m.SetReference(f"H{i}")
        m.SetValue("TETHER_NPTH_D2.5")
        m.SetPosition(pn.VECTOR2I(int(hx * UM), int(hy * UM)))
        b.Add(m)
    print("placed: 4 tether NPTH (H1..H4)")

    pcbnew.SaveBoard(out, b)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
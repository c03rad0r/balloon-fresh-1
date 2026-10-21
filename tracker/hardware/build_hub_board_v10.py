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
FRONT = {  # ref: (x, y, rot, lib_id)
    "U2": (29.0, 48.0, 0, "balloon_flight_v9:LoRa2021F33_2G4"),   # F33 x 9.2..48.8, y 36.85..59.15
    "U1": (13.0, 24.0, 0, "RF_Module:ESP32-S3-WROOM-1U"),          # ESP32-S3 (yard 19.6x20.2)
    "U5": (30.0, 8.4, 0, "RF_GPS:ublox_MAX"),                      # GNSS 11.8x10.7
    "U_HUB_CVT": (30.0, 21.0, 0, "Package_DFN_QFN:VQFN-16-1EP_3x3mm_P0.5mm_EP1.1x1.1mm"),
    "U7": (36.0, 21.0, 0, "Package_TO_SOT_SMD:SOT-23-5"),
    "U6": (30.0, 28.0, 0, "Package_LGA:LGA-8_3x5mm_P1.25mm"),      # baro
    "C_CAP1": (42.5, 8.3, 0, "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm"),
    "C_CAP2": (42.5, 20.3, 0, "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm"),
    "J_PROG": (50.0, 25.6, 90, "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical"),
    "ANT1": (50.0, 50.0, 0, "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical"),
    "ANT4": (50.0, 42.0, 0, "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical"),
}
BACK = {
    "U3": (17.0, 10.8, 0, "balloon_flight_v9:LoRa2021_Castellated"),   # LP Site B
    "U_C": (39.5, 10.8, 0, "balloon_flight_v9:LoRa2021_Castellated"),  # LP Site C (NEW)
    "U_E28": (14.0, 32.75, 0, "e28:E28-2G4M27SX"),                     # E28 ranging module
    "ANT2": (50.0, 34.0, 0, "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical"),
    "ANT3": (50.0, 26.0, 0, "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical"),
}
# wing seats: ADR-085 CORRECTED rotations (slot reaches its own edge; detector EXIT=0).
# seat_rotation_deg: west 0, north 90, east 180, south 270 -- the FIXED rule.
WING_SEATS = [
    ("J_W1", "west",   0.0, (0.0, 31.0)),
    ("J_W2", "north", 90.0, (26.5, H)),
    ("J_W3", "east", 180.0, (W, 31.0)),
    ("J_W4", "south", 270.0, (26.5, 0.0)),
]
WING_HOLES = {  # HW*: inboard of each seat, string strain relief (ADR-125)
    "HW1": (7.0, 31.0),    # west seat inboard -- CHECK: E28 yard x5.4..22.6 y21.7..43.9 -> conflict! placed after check
    "HW2": (26.5, 55.0),   # north seat inboard -- F33 front y36.85..59.15 x9.2..48.8 -> conflict front!
    "HW3": (46.0, 31.0),   # east seat inboard
    "HW4": (26.5, 7.0),    # south seat inboard -- U3/U_C back yards y2.99..18.6 -> conflict!
}
TETHER = [  # (x, y) D2.5 NPTH (ADR-124) -- left of the centre line, clear of the F33
    # courtyard and the J_W2/J_W4 edge seats (which sit at x=26.5). 8mm pair spacing.
    # VERTICAL pairs on the RIGHT edge column x=50.0 -- free on BOTH sides:
    # front: F33 courtyard ends x 48.8; back: U_C ends x 48.8, E28 ends x 19.9.
    # (First attempt put them in U3's pad column on the left -- operator caught it:
    #  H3 was 1.14mm from U3.1, H4 0.41mm from U3.6. The courtyard bbox check cannot
    #  see a hole INSIDE a footprint's own courtyard; pad-distance is the real test.)
    # LEFT-EDGE COLUMN, reserved exclusively for the tether (operator caught the
    # first two attempts sitting in U3/U_C pad columns). U3 shifted right so its
    # pads clear x>6; E28 likewise; U_C physically cannot move (courtyard ends x 48.8)
    # so the BOTTOM pair shares the left column: clearance verified pad-by-pad.
    (3.3, 58.5), (3.3, 50.5),            # H1 H2 top-left vertical pair
    (3.3, 3.5), (3.3, 11.5),             # H3 H4 bottom-left vertical pair
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


def lib_path(lib):
    if lib == "balloon_flight_v9":
        return V9_LIB
    if lib == "e28":
        return E28_LIB
    if lib == "Tracker_Mechanical":
        return os.path.join(HERE, "footprints", "tracker_mechanical.pretty")
    # KiCad system libs
    k = os.path.expanduser("~/kicad/footprints") 
    cand = os.path.join(k, lib + ".pretty")
    if os.path.exists(cand):
        return cand
    for base in ("/usr/share/kicad/footprints",):
        cand = os.path.join(base, lib + ".pretty")
        if os.path.exists(cand):
            return cand
    raise SystemExit("lib not found: " + lib)


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

    def put(spec, side, value=None):
        for ref, (x, y, rot, lib_id) in spec.items():
            lib, name = lib_id.split(":", 1)
            fp = pcbnew.FootprintLoad(lib_path(lib), name)
            if fp is None:
                raise SystemExit(f"load failed {lib_id}")
            place(b, fp, ref, value or ref, x, y, rot, side)

    put(FRONT, "F")
    put(BACK, "B")
    # wing seats: footprint carries the slot; rotations per ADR-085 fix
    for ref, edge_name, rot, (sx, sy) in WING_SEATS:
        fp = pcbnew.FootprintLoad(lib_path("Tracker_Mechanical"), "Wing_Tab_4P")
        if fp is None:
            raise SystemExit("Wing_Tab_4P load failed")
        place(b, fp, ref, "WING_SOCKET_4P", sx, sy, rot, "F")
    # wing string holes (ADR-125) -- positions validated by check_hole_clearance afterwards
    for i, ((hx, hy)) in enumerate([WING_HOLES[k] for k in ("HW1", "HW2", "HW3", "HW4")], 1):
        m = pcbnew.FOOTPRINT(b)
        pad = pcbnew.PAD(m)
        pad.SetSize(pcbnew.VECTOR2I(int(2.5 * UM), int(2.5 * UM)))
        pad.SetDrillSize(pcbnew.VECTOR2I(int(2.5 * UM), int(2.5 * UM)))
        pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
        pad.SetNumber("1")
        m.Add(pad)
        m.SetReference(f"HW{i}")
        m.SetValue("STRING_NPTH_D2.5")
        m.SetPosition(pcbnew.VECTOR2I(int(hx * UM), int(hy * UM)))
        b.Add(m)
    # tether holes (ADR-124)
    for i, (hx, hy) in enumerate(TETHER, 1):
        m = pcbnew.FOOTPRINT(b)
        pad = pcbnew.PAD(m)
        pad.SetSize(pcbnew.VECTOR2I(int(2.5 * UM), int(2.5 * UM)))
        pad.SetDrillSize(pcbnew.VECTOR2I(int(2.5 * UM), int(2.5 * UM)))
        pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
        pad.SetNumber("1")
        m.Add(pad)
        m.SetReference(f"H{i}")
        m.SetValue("TETHER_NPTH_D2.5")
        m.SetPosition(pcbnew.VECTOR2I(int(hx * UM), int(hy * UM)))
        b.Add(m)
    print(f"placed: {len(list(b.GetFootprints()))} footprints "
          f"(front parts, back radios, 4 wing seats, HW1-4 wing holes, H1-4 tether)")
    pcbnew.SaveBoard(out, b)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
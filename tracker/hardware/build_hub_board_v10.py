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
W, H = 72.0, 80.0
HERE = os.path.dirname(os.path.abspath(__file__))
E28_LIB = os.path.join(HERE, "footprints", "e28")
V9_LIB = "/home/c08r4d0r/worktrees/master-check/tracker/hardware/schematics/flight_board/v9_lib/balloon_flight_v9.pretty"

# approved placement (mm, board coords, bottom-left origin) -- from GATE round 1
FRONT = {  # solver: 72x80, TRUE seat margins (west/east x>=10, north/south y>=8.9)
    "U2": (29.8, 20.1, 0, "balloon_flight_v9:LoRa2021F33_2G4"),
    "U1": (19.8, 42.3, 0, "RF_Module:ESP32-S3-WROOM-1U"),
    "C_CAP1": (36.0, 37.5, 0, "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm"),
    "C_CAP2": (47.8, 37.5, 0, "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm"),
    "U5": (15.9, 58.8, 0, "RF_GPS:ublox_MAX"),
    "J_PROG": (31.0, 54.7, 0, "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical"),
    "U_HUB_CVT": (42.9, 56.0, 0, "Package_DFN_QFN:VQFN-16-1EP_3x3mm_P0.5mm_EP1.1x1.1mm"),
    "U7": (48.8, 55.2, 0, "Package_TO_SOT_SMD:SOT-23-5"),
    "U6": (54.4, 56.8, 0, "Package_LGA:LGA-8_3x5mm_P1.25mm"),
    "ANT1": (12.5, 67.6, 0, "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical"),
    "ANT4": (18.5, 67.6, 0, "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical"),
}
BACK = {  # solver: 72x80, TRUE seat margins (west/east x>=10, north/south y>=8.9)
    "U3": (20.9, 16.7, 0, "balloon_flight_v9:LoRa2021_Castellated"),
    "U_C": (43.7, 16.7, 0, "balloon_flight_v9:LoRa2021_Castellated"),
    "U_E28": (18.6, 36.5, 0, "e28:E28-2G4M27SX"),
    "ANT2": (30.7, 28.0, 0, "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical"),
    "ANT3": (36.7, 28.0, 0, "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical"),
}
# wing seats: ADR-085 CORRECTED rotations (slot reaches its own edge; detector EXIT=0).
# seat_rotation_deg: west 0, north 90, east 180, south 270 -- the FIXED rule.
WING_SEATS = [
    ("J_W1", "west",   0.0, (0.0, H / 2)),
    ("J_W2", "north", 90.0, (W / 2, H)),
    ("J_W3", "east", 180.0, (W, H / 2)),
    ("J_W4", "south", 270.0, (W / 2, 0.0)),
]
WING_HOLES = {  # clear of seat courtyards AND part rows (72x80, ADR-125)
    "HW1": (4.5, 50.5),    # west, north of west seat (yard ends y 44.1)
    "HW2": (36.0, 66.5),   # north, below north seat yard (starts y 71.9)
    "HW3": (67.5, 50.5),   # east, north of east seat
    "HW4": (66.0, 76.5),   # moved: south gap too tight; top-right corner free
}
TETHER = [  # reserved left column x=3.3 (ADR-124), 72x80
    (3.3, 76.5), (3.3, 68.5),            # H1 H2 top-left
    (3.3, 3.5), (3.3, 11.5),             # H3 H4 bottom-left
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


_FP_CACHE = {}


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



# ------------------------------------------------------------------ netlist nets
NETLIST = os.path.join(HERE, "schematics", "flight_board", "v10_flight.net")
EXTRA_PINMAPS = {
    "J_PROG": {"1": "GND", "2": "+3V3", "3": "/EN", "4": "/USB_DN", "5": "/USB_DP", "6": "/IO0"},
    "R_EN": {"1": "/EN", "2": "+3V3"},
    "C_EN": {"1": "/EN", "2": "GND"},
}


def read_netlist_nets(path):
    import re
    t = open(path, encoding="utf-8", errors="replace").read()
    net_sec = re.search(r"\(nets(.*)", t, re.S).group(1)
    out = []
    for b in re.split(r"\n    \(net ", net_sec)[1:]:
        name = re.search(r'\(name "([^"]+)"\)', b).group(1)
        nodes = re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', b)
        out.append((name, nodes))
    return out


def assign_nets(b):
    nets = read_netlist_nets(NETLIST)
    for name, _nodes in nets:
        if name and b.FindNet(name) is None:
            b.Add(pcbnew.NETINFO_ITEM(b, name))
    pin_net = {}
    for _n, nodes in nets:
        for r, p in nodes:
            pin_net[(r, p)] = _n
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        for pad in fp.Pads():
            nm = pin_net.get((ref, pad.GetNumber()))
            if nm:
                pad.SetNet(b.FindNet(nm))
    for ref, pmap in EXTRA_PINMAPS.items():
        fp = b.FindFootprintByReference(ref)
        if fp is None:
            continue
        for pad in fp.Pads():
            nm = pmap.get(pad.GetNumber())
            if nm:
                if b.FindNet(nm) is None:
                    b.Add(pcbnew.NETINFO_ITEM(b, nm))
                pad.SetNet(b.FindNet(nm))
    # U1 programming pads (ADR-121: pad3=EN, pad13=USB_DN, pad14=USB_DP; WROOM-1 pad25=IO0)
    u1 = b.FindFootprintByReference("U1")
    if u1 is not None:
        # IO0 intentionally NOT assigned: its U1 pad identity is UNVERIFIED (the netlist
        # maps pad 25 = IO48, not IO0). ADR-121 OPEN item. /IO0 stays on J_PROG pin 6 + R_EN.
        for pad_no, nm in (("3", "/EN"), ("13", "/USB_DN"), ("14", "/USB_DP")):
            if b.FindNet(nm) is None:
                b.Add(pcbnew.NETINFO_ITEM(b, nm))
            for pad in u1.Pads():
                if pad.GetNumber() == pad_no:
                    pad.SetNet(b.FindNet(nm))
    # ADR-123 bus partition: U3+U_C+E28 on SPI-1 (2.4GHz); F33 alone on SPI-2 (433MHz).
    # v9 netlist had U3 on the shared bus (now /SPI2_*); move the LP radios to /SPI1_*.
    for ref in ("U3", "U_C"):
        fp = b.FindFootprintByReference(ref)
        if fp is None:
            continue
        for pad in fp.Pads():
            n = pad.GetNet()
            if n is None or n.GetNetCode() == 0:
                continue
            nm = n.GetNetname()
            if nm in ("/SPI2_MISO", "/SPI2_MOSI", "/SPI2_SCK"):
                pad.SetNet(b.FindNet(nm.replace("SPI2", "SPI1")))
    # U_C: copy U3's pad nets; bus nets are shared (/SPI1_*), control nets get U_C names
    u3 = b.FindFootprintByReference("U3")
    uc = b.FindFootprintByReference("U_C")
    if u3 is not None and uc is not None:
        by_num = {p.GetNumber(): p for p in uc.Pads()}
        for p3 in u3.Pads():
            pc = by_num.get(p3.GetNumber())
            if pc is None:
                continue
            n = p3.GetNet()
            if n is not None and n.GetNetCode() != 0:
                name = n.GetNetname()
                if any(k in name for k in ("CS", "IRQ", "BUSY", "RESET")) and "U3" in name:
                    name = name.replace("U3", "U_C")
                    if b.FindNet(name) is None:
                        b.Add(pcbnew.NETINFO_ITEM(b, name))
                pc.SetNet(b.FindNet(name))
    # E28 module GND pads (sidecar authority: E28-2G4M27SX.md pins 2,7,10,16 = GND).
    # The netlist carried only the pins that existed on the bare QFN24, so these four
    # grounded module pads arrived UNASSIGNED -- floating metal. Found by the registry
    # (connectivity/v10_pinmap.reg) on 2026-10-21.
    e28 = b.FindFootprintByReference("U_E28")
    if e28 is not None:
        gnd = b.FindNet("GND")
        for pad in e28.Pads():
            if pad.GetNumber() in ("2", "7", "10", "16"):
                pad.SetNet(gnd)
    # U_C antenna: its own U.FL (ANT_C, ADR-119 site C) -- do NOT short to U3's /ANT3_2G4_RX
    uc = b.FindFootprintByReference("U_C")
    if uc is not None:
        for pad in uc.Pads():
            n = pad.GetNet()
            if n is not None and n.GetNetname() == "/ANT3_2G4_RX":
                if b.FindNet("/ANT_C_2G4") is None:
                    b.Add(pcbnew.NETINFO_ITEM(b, "/ANT_C_2G4"))
                pad.SetNet(b.FindNet("/ANT_C_2G4"))
    return len(pin_net)


def pool_load(specs):
    """Load every footprint ONCE into a pool BEFORE any board mutation.

    Measured (2026-10-21): FootprintLoad of an id that is ALREADY PLACED on a live
    board returns None mid-session (ANT1 placed -> identical ANT4 load -> None).
    Loading everything up front (no board in play) is reliable; place() then
    consumes pool copies."""
    pool = {}
    seen = set()
    for spec in specs:
        for ref, (x, y, rot, lib_id) in spec.items():
            if lib_id in seen:
                continue
            seen.add(lib_id)
            lib, name = lib_id.split(":", 1)
            d = lib_path(lib)
            fp = pcbnew.FootprintLoad(d, name)
            print(f"[pool] {lib_id} from {d} -> {fp is not None}", file=sys.stderr)
            if fp is None:
                raise SystemExit(f"pool load failed: {lib_id}")
            pool[lib_id] = fp
    return pool


def main():
    out = os.path.join(HERE, "hub_board_v10.kicad_pcb")
    pool = pool_load((FRONT, BACK, {"J_W": (0, 0, 0, "Tracker_Mechanical:Wing_Tab_4P")}))
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
            d = lib_path(lib)
            src = pool.get(lib_id)
            fp = src.Duplicate() if src else None
            if fp is None:
                raise SystemExit(f"pool copy failed: {lib_id}")
            place(b, fp, ref, value or ref, x, y, rot, side)

    put(FRONT, "F")
    put(BACK, "B")
    # wing seats: footprint carries the slot; rotations per ADR-085 fix
    for ref, edge_name, rot, (sx, sy) in WING_SEATS:
        src = pool.get("Tracker_Mechanical:Wing_Tab_4P")
        fp = src.Duplicate() if src else None
        if fp is None:
            raise SystemExit("Wing_Tab_4P pool copy failed")
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
    n_assigned = assign_nets(b)
    print(f"net assignments: {n_assigned} netlist pins")
    print(f"placed: {len(list(b.GetFootprints()))} footprints "
          f"(front parts, back radios, 4 wing seats, HW1-4 wing holes, H1-4 tether)")
    # CLOBBER GUARD (2026-10-21): a stray probe script overwrote this board three times
    # with a near-empty file (1 footprint / 8.6KB), silently invalidating measurements.
    # Refuse to write a board whose footprint count is implausible.
    nfps = len(b.GetFootprints())
    if nfps < 20:
        raise SystemExit(f"REFUSED: refusing to save a board with only {nfps} footprints "
                         "(clobber guard -- expected 28)")
    pcbnew.SaveBoard(out, b)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
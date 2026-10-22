#!/usr/bin/env python3
"""Deterministic seat-first placement solver for the v10 hub (ADR-129 additions).

WHY THIS EXISTS (2026-10-21, twice-burned): hand-nudging coordinates into
build_hub_board_v10.py produced, in order, holes sitting on pads, then 10-14
geometry-gate violations.  Both failures were invisible until a gate ran, and
both were "fixed" by moving one more part by 0.5 mm.  This solver replaces that
loop: it RESERVES the seat margins first, then walks a FIXED grid in a FIXED
deterministic order, and accepts a placement for a part only when BOTH gates
actually pass:

    check_board_geometry.py    containment + same-side courtyard overlap
    check_hole_clearance.py    hole <-> pad / lane / via / zone / edge / hole

ACCEPTANCE IS THE REAL GATE, not a model of it.  For every candidate that
survives the cheap in-process rule, the solver writes a geometric SHADOW board
(same outline, same footprint libraries, same positions/rotations) to a scratch
.kicad_pcb and runs BOTH gate scripts on it AS SUBPROCESSES.  Neither gate
reads nets (there are no tracks or zones on an unrouted board), so a shadow
verdict is exactly the verdict the real builder will get.  A candidate that
trips either gate is rejected and the scan advances.  No randomness: fixed part
order, fixed grid, fixed tie-breaks.

    ~/venvs/kicad/bin/python tracker/hardware/solve_v10_placement.py

It writes tracker/hardware/v10_adr129_placement.json -- the coordinates that
get baked into build_hub_board_v10.py's FRONT / BACK tables.

The FIXED_* tables below are a MIRROR of the operator-approved placement in
build_hub_board_v10.py.  They are duplicated (never imported) on purpose; the
`--verify` mode asserts they still match the real board footprint-for-footprint,
so the two cannot drift silently.
"""
import json
import math
import os
import subprocess
import sys
import tempfile

import pcbnew

UM = 1_000_000.0
HERE = os.path.dirname(os.path.abspath(__file__))
KICAD_PY = os.path.expanduser("~/venvs/kicad/bin/python")
BUILDER = os.path.join(HERE, "build_hub_board_v10.py")
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")
GATE_GEOM = os.path.join(HERE, "check_board_geometry.py")
GATE_HOLE = os.path.join(HERE, "check_hole_clearance.py")
OUT_JSON = os.path.join(HERE, "v10_adr129_placement.json")

W, H = 72.0, 80.0

# Footprint library resolution -- a MIRROR of build_hub_board_v10.lib_path().
V9_LIB = os.path.join(HERE, "schematics", "flight_board", "v9_lib",
                      "balloon_flight_v9.pretty")
E28_LIB = os.path.join(HERE, "footprints", "e28")


def lib_path(lib):
    if lib == "balloon_flight_v9":
        return V9_LIB
    if lib == "e28":
        return E28_LIB
    if lib == "Tracker_Mechanical":
        return os.path.join(HERE, "footprints", "tracker_mechanical.pretty")
    for base in ("/usr/share/kicad/footprints",):
        cand = os.path.join(base, lib + ".pretty")
        if os.path.exists(cand):
            return cand
    raise SystemExit("lib not found: " + lib)


# ---------------------------------------------------------------- FIXED layout.
FIXED_FRONT = {
    "U2": (29.8, 20.1, 0, "balloon_flight_v9:LoRa2021F33_2G4"),
    "U1": (19.8, 42.3, 0, "RF_Module:ESP32-S3-WROOM-1U"),
    "C_CAP1": (36.0, 37.5, 0, "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm"),
    "C_CAP2": (47.8, 37.5, 0, "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm"),
    "U5": (15.9, 58.8, 0, "RF_GPS:ublox_MAX"),
    "J_PROG": (31.0, 54.7, 0,
               "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical"),
    "U_HUB_CVT": (42.9, 56.0, 0,
                  "Package_DFN_QFN:VQFN-16-1EP_3x3mm_P0.5mm_EP1.1x1.1mm"),
    "U7": (48.8, 55.2, 0, "Package_TO_SOT_SMD:SOT-23-5"),
    "U6": (54.4, 56.8, 0, "Package_LGA:LGA-8_3x5mm_P1.25mm"),
    "ANT1": (12.5, 67.6, 0,
             "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical"),
    "ANT4": (18.5, 67.6, 0,
             "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical"),
}
FIXED_BACK = {
    "U3": (20.9, 16.7, 0, "balloon_flight_v9:LoRa2021_Castellated"),
    "U_C": (43.7, 16.7, 0, "balloon_flight_v9:LoRa2021_Castellated"),
    "U_E28": (53.0, 69.0, 90, "e28:E28-2G4M27SX"),
    "ANT2": (30.7, 27.5, 0,
             "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical"),
    "ANT3": (36.7, 28.0, 0,
             "Connector_Coaxial:U.FL_Molex_MCRF_73412-0110_Vertical"),
}
WING_SEATS = [
    ("J_W1", "west", 0.0, (0.0, H / 2)),
    ("J_W2", "north", 90.0, (W / 2, H)),
    ("J_W3", "east", 180.0, (W, H / 2)),
    ("J_W4", "south", 270.0, (W / 2, 0.0)),
]
WING_HOLES = {
    "HW1": (4.5, 50.5),
    "HW2": (36.0, 66.5),
    "HW3": (67.5, 50.5),
    "HW4": (66.0, 76.5),
}
TETHER = [
    (3.3, 76.5), (3.3, 68.5),
    (3.3, 3.5), (3.3, 11.5),
]
WING_FP = "Tracker_Mechanical:Wing_Tab_4P"

HOLE_R = 1.25          # D2.5 / 2
HOLE_PAD_GAP = 1.0     # check_hole_clearance.py's PAD_GAP
HOLE_MARGIN = 0.12     # safety, so the real verdict is not decided by rounding
XY_MARGIN = 0.12       # keep courtyards this far inside the outline
STEP = 0.5             # grid step, mm

_MASTERS = {}


def master(lib_id):
    """Load a footprint ONCE per process, then hand out copies."""
    if lib_id in _MASTERS:
        return _MASTERS[lib_id]
    lib, name = lib_id.split(":", 1)
    fp = pcbnew.FootprintLoad(lib_path(lib), name)
    if fp is None:
        raise SystemExit("footprint load failed: " + lib_id)
    _MASTERS[lib_id] = fp
    return fp


_XFORM = {}


def transform(lib_id, side, rot, x, y):
    """Return (bbox_rect, [(padnum, x, y, pad_radius), ...]) for a placed part.

    Mirrors build_hub_board_v10.place() exactly, including the Flip-before-
    SetPosition ordering that KiCad requires (segfault otherwise).  The
    0/0-anchored result is CACHED per (lib_id, side, rot): building a scratch
    board is far too expensive to do once per grid point.
    """
    key = (lib_id, side, rot)
    if key not in _XFORM:
        _XFORM[key] = _transform0(lib_id, side, rot)
    rect0, pads0 = _XFORM[key]
    rect = (rect0[0] + x, rect0[1] + y, rect0[2] + x, rect0[3] + y)
    return rect, [(n, px + x, py + y, pr) for (n, px, py, pr) in pads0]


def _transform0(lib_id, side, rot):
    scratch = pcbnew.NewBoard("scratch")
    fp = master(lib_id).Duplicate()
    scratch.Add(fp)
    if side == "B":
        fp.Flip(pcbnew.VECTOR2I(0, 0), False)
    fp.SetPosition(pcbnew.VECTOR2I(0, 0))
    fp.SetOrientation(
        pcbnew.EDA_ANGLE(rot if side == "F" else -rot, pcbnew.DEGREES_T))
    bb = fp.GetBoundingBox(False, True)      # exactly what the geometry gate reads
    rect = (bb.GetX() / UM, bb.GetY() / UM,
            bb.GetX() / UM + bb.GetWidth() / UM,
            bb.GetY() / UM + bb.GetHeight() / UM)
    pads = [(p.GetNumber(), p.GetPosition().x / UM,
             p.GetPosition().y / UM,
             math.hypot(p.GetSizeX() / UM, p.GetSizeY() / UM) / 2.0)
            for p in fp.Pads()]
    return rect, pads


def bbox_only(lib_id, side, rot):
    r, _p = transform(lib_id, side, rot, 0, 0)
    return (r[0], r[1], r[2] - r[0], r[3] - r[1])   # (ox, oy, w, h)


def overlaps(a, b):
    # gate: not (a.x1 <= b.x0 or b.x1 <= a.x0 or a.y1 <= b.y0 or b.y1 <= a.y0)
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def holes_clear(pads):
    """check_hole_clearance.py's hole <-> pad rule, plus a safety margin."""
    for _n, px, py, pr in pads:
        for (hx, hy) in list(WING_HOLES.values()) + list(TETHER):
            if math.hypot(px - hx, py - hy) - HOLE_R - pr < HOLE_PAD_GAP + HOLE_MARGIN:
                return False
    return True


# ------------------------------------------------------------------ new parts.
# (ref, footprint-lib_id, value, sides in preference order, rotations in
# preference order, intent-anchor (x, y)).  The anchor encodes the ADR-129 /
# ADR-054 / ADR-047 electrical requirement; the solver puts each part at the
# CLOSEST legal grid point to it.
R0402 = "Resistor_SMD:R_0402_1005Metric"
C0402 = "Capacitor_SMD:C_0402_1005Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"
DSMA = "Diode_SMD:D_SMA"
DSOD123 = "Diode_SMD:D_SOD-123"
SOLDER3 = "Jumper:SolderJumper-3_P1.3mm_Open_RoundedPad1.0x1.5mm"
HDR5 = "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical"
SOT236 = "Package_TO_SOT_SMD:SOT-23-6"

F33_VCC_PIN = (18.013, 9.6)      # U2 pad 1 (/F33_VCC), bottom edge of the F33
U5_POS = (15.9, 58.8)            # GNSS module
U_HUB_CVT_POS = (42.9, 56.0)     # hub-array converter input lands
SEAT_W = (0.0, 40.0)             # J_W1 west seat
SEAT_N = (36.0, 80.0)            # J_W2 north seat
SEAT_E = (72.0, 40.0)            # J_W3 east seat
SEAT_S = (36.0, 0.0)             # J_W4 south seat

NEW_PARTS = [
    # 1. the four per-interface bypass diodes, hub-side, hugging their seats
    ("D_BP1", DSMA, "SS24", ("B", "F"), (0, 90, 180, 270), SEAT_W),
    ("D_BP2", DSMA, "SS24", ("B", "F"), (0, 90, 180, 270), SEAT_N),
    ("D_BP3", DSMA, "SS24", ("B", "F"), (0, 90, 180, 270), SEAT_E),
    ("D_BP4", DSMA, "SS24", ("B", "F"), (0, 90, 180, 270), SEAT_S),
    # 2. F33 rail: bulk + HF AT the module pin, the selector jumper beside it
    ("C_BULK", C1206, "100uF", ("F", "B"), (0, 90), F33_VCC_PIN),
    ("C_HF", C0402, "100nF", ("F", "B"), (0, 90), F33_VCC_PIN),
    ("J_VCC", SOLDER3, "F33_VCC_SEL", ("F", "B"), (0, 90), F33_VCC_PIN),
    ("R_MON1", R0402, "4.7M", ("F", "B"), (0, 90), F33_VCC_PIN),
    ("R_MON2", R0402, "4.7M", ("F", "B"), (0, 90), F33_VCC_PIN),
    ("C_MON", C0402, "10nF", ("F", "B"), (0, 90), F33_VCC_PIN),
    # 3. GNSS rail RC: series R then bulk C, adjacent, at U5
    ("R_F1", R0402, "100R", ("F", "B"), (0, 90), U5_POS),
    ("C4", C0402, "10uF", ("F", "B"), (0, 90), U5_POS),
    # 4. the four nichrome cut channels, one per wing seat, fed from VSCAP
    ("U_CUT1", SOT236, "CUT_CH1", ("B", "F"), (0, 90, 180, 270), SEAT_W),
    ("U_CUT2", SOT236, "CUT_CH2", ("B", "F"), (0, 90, 180, 270), SEAT_N),
    ("U_CUT3", SOT236, "CUT_CH3", ("B", "F"), (0, 90, 180, 270), SEAT_E),
    ("U_CUT4", SOT236, "CUT_CH4", ("B", "F"), (0, 90, 180, 270), SEAT_S),
    # 5. hub panel: its two bypass diodes beside the converter lands
    ("D_HUB1", DSMA, "SS24", ("F", "B"), (0, 90, 180, 270), U_HUB_CVT_POS),
    ("D_HUB2", DSMA, "SS24", ("F", "B"), (0, 90, 180, 270), U_HUB_CVT_POS),
    # 6. the panel connector itself, on an edge, accessible
    ("J_HUB_PV", HDR5, "HUB_PV_5P", ("F", "B"), (90, 0), (69.0, 64.0)),
    # 7. supercap bank support: balancing pair + ADC divider (ADR-006)
    ("R_BAL1", R0402, "10k", ("F", "B"), (0, 90), (41.0, 37.5)),
    ("R_BAL2", R0402, "10k", ("F", "B"), (0, 90), (41.0, 37.5)),
    ("R_DIV1", R0402, "1M", ("F", "B"), (0, 90), (41.0, 37.5)),
    ("R_DIV2", R0402, "1M", ("F", "B"), (0, 90), (41.0, 37.5)),
    # 8. +3V3 bulk at the LDO output (ADR-129 D1: 10 uF, C_0402)
    ("C10", C0402, "10uF", ("F", "B"), (0, 90), (19.8, 42.3)),
    # 9. solar series blocking diode (ADR-129 D1 / ADR-006): sits between the west
    #    solar feed and the supercap bank, so it is anchored at the west seat it
    #    protects, not at the caps it feeds.
    ("D1", DSOD123, "BAT54", ("F", "B"), (0, 90, 180, 270), SEAT_W),
]


def fixed_rects():
    out = {"F": [], "B": []}
    for ref, (x, y, rot, lib_id) in FIXED_FRONT.items():
        out["F"].append((bbox_only(lib_id, "F", rot), ref, x, y))
    for ref, (x, y, rot, lib_id) in FIXED_BACK.items():
        out["B"].append((bbox_only(lib_id, "B", rot), ref, x, y))
    for ref, _e, rot, (x, y) in WING_SEATS:
        out["F"].append((bbox_only(WING_FP, "F", rot), ref, x, y))
    return out


def padded(ox, oy, w, h, x, y):
    return (ox + x, oy + y, ox + x + w, oy + y + h)


def legal(rect, pads, rects):
    if not (rect[0] >= XY_MARGIN and rect[1] >= XY_MARGIN
            and rect[2] <= W - XY_MARGIN and rect[3] <= H - XY_MARGIN):
        return False
    if not holes_clear(pads):
        return False
    for (ox, oy, w, h, _ref, px, py) in rects:
        if overlaps(rect, padded(ox, oy, w, h, px, py)):
            return False
    return True


def build_shadow(path, specs):
    """Write a net-irrelevant copy of the board: outline + specs + holes.

    specs: [(ref, value, lib_id, x, y, rot, side), ...]
    """
    b = pcbnew.NewBoard(path)
    edge = pcbnew.PCB_SHAPE(b)
    edge.SetShape(pcbnew.SHAPE_T_RECTANGLE)
    edge.SetLayer(pcbnew.Edge_Cuts)
    edge.SetStart(pcbnew.VECTOR2I(0, 0))
    edge.SetEnd(pcbnew.VECTOR2I(int(W * UM), int(H * UM)))
    b.Add(edge)
    for (ref, value, lib_id, x, y, rot, side) in specs:
        fp = master(lib_id).Duplicate()
        fp.SetReference(ref)
        fp.SetValue(value)
        b.Add(fp)
        if side == "B":
            fp.Flip(pcbnew.VECTOR2I(0, 0), False)
        fp.SetPosition(pcbnew.VECTOR2I(int(x * UM), int(y * UM)))
        fp.SetOrientation(
            pcbnew.EDA_ANGLE(rot if side == "F" else -rot, pcbnew.DEGREES_T))
    for name, (hx, hy) in sorted(WING_HOLES.items()):
        b.Add(_hole_fp(b, name, hx, hy, "STRING_NPTH_D2.5"))
    for i, (hx, hy) in enumerate(TETHER, 1):
        b.Add(_hole_fp(b, "H%d" % i, hx, hy, "TETHER_NPTH_D2.5"))
    pcbnew.SaveBoard(path, b)
    return b


def _hole_fp(b, ref, hx, hy, value):
    m = pcbnew.FOOTPRINT(b)
    pad = pcbnew.PAD(m)
    pad.SetSize(pcbnew.VECTOR2I(int(2.5 * UM), int(2.5 * UM)))
    pad.SetDrillSize(pcbnew.VECTOR2I(int(2.5 * UM), int(2.5 * UM)))
    pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
    pad.SetNumber("1")
    m.Add(pad)
    m.SetReference(ref)
    m.SetValue(value)
    m.SetPosition(pcbnew.VECTOR2I(int(hx * UM), int(hy * UM)))
    return m


def run_gate(gate, board_path):
    r = subprocess.run([KICAD_PY, gate, "--board", board_path],
                       capture_output=True, text=True, timeout=900)
    out = ((r.stdout or "") + (r.stderr or ""))
    out = "\n".join(ln for ln in out.splitlines() if "GetWidth" not in ln)
    return r.returncode == 0, out


def fixed_specs():
    out = []
    for ref, (x, y, rot, lib_id) in FIXED_FRONT.items():
        out.append((ref, ref, lib_id, x, y, rot, "F"))
    for ref, (x, y, rot, lib_id) in FIXED_BACK.items():
        out.append((ref, ref, lib_id, x, y, rot, "B"))
    for ref, _e, rot, (x, y) in WING_SEATS:
        out.append((ref, "WING_SOCKET_4P", WING_FP, x, y, rot, "F"))
    return out


def solve(verbose=True):
    tag = "shadow_%d" % os.getpid()
    counter = [0]

    def gate_ok(specs):
        counter[0] += 1
        p = os.path.join(tempfile.gettempdir(),
                         "%s_r%d.kicad_pcb" % (tag, counter[0]))
        build_shadow(p, specs)
        ok1, o1 = run_gate(GATE_GEOM, p)
        ok2, o2 = run_gate(GATE_HOLE, p) if ok1 else (False, "")
        try:
            os.unlink(p)
        except OSError:
            pass
        return ok1 and ok2, (o1 + o2)

    placed = []                      # [(ref, value, lib_id, x, y, rot, side)]
    rects = []                       # [(ox, oy, w, h, ref, px, py)]
    for ref, (x, y, rot, lib_id) in FIXED_FRONT.items():
        ox, oy, w, h = bbox_only(lib_id, "F", rot)
        rects.append((ox, oy, w, h, ref, x, y))
    for ref, (x, y, rot, lib_id) in FIXED_BACK.items():
        ox, oy, w, h = bbox_only(lib_id, "B", rot)
        rects.append((ox, oy, w, h, ref, x, y))
    for ref, _e, rot, (x, y) in WING_SEATS:
        ox, oy, w, h = bbox_only(WING_FP, "F", rot)
        rects.append((ox, oy, w, h, ref, x, y))
    placed = fixed_specs()

    for (ref, lib_id, value, sides, rots, anchor) in NEW_PARTS:
        cands = []
        for si, side in enumerate(sides):
            for ri, rot in enumerate(rots):
                ox, oy, w, h = bbox_only(lib_id, side, rot)
                hw, hh = w / 2.0, h / 2.0
                x0 = math.ceil((XY_MARGIN + hw) / STEP) * STEP
                x1 = math.floor((W - XY_MARGIN - hw) / STEP) * STEP
                y0 = math.ceil((XY_MARGIN + hh) / STEP) * STEP
                y1 = math.floor((H - XY_MARGIN - hh) / STEP) * STEP
                x = round(x0, 3)
                while x <= x1 + 1e-9:
                    y = round(y0, 3)
                    while y <= y1 + 1e-9:
                        if y + hh <= H - XY_MARGIN + 1e-9 and x + hw <= W - XY_MARGIN + 1e-9:
                            d = math.hypot(x - anchor[0], y - anchor[1])
                            cands.append((d, si, ri, x, y))
                        y = round(y + STEP, 3)
                    x = round(x + STEP, 3)
        cands.sort()
        got = None
        tried = 0
        for (_d, si, ri, x, y) in cands:
            side, rot = sides[si], rots[ri]
            r, pads = transform(lib_id, side, rot, x, y)
            if not legal(r, pads, rects):
                continue
            tried += 1
            ok, out = gate_ok(placed + [(ref, value, lib_id, x, y, rot, side)])
            if not ok:
                print("    rejected %s @ (%.2f,%.2f,%d,%s): %s"
                      % (ref, x, y, rot, side, out.strip().replace("\n", " | ")[:160]))
                continue
            got = (ref, lib_id, rot, side, x, y)
            break
        if got is None:
            print("  NO LEGAL PLACEMENT for %s (%d gate-confirmed tries) -- stopped"
                  % (ref, tried))
            return None
        ref, lib_id, rot, side, x, y = got
        ox, oy, w, h = bbox_only(lib_id, side, rot)
        rects.append((ox, oy, w, h, ref, x, y))
        placed.append((ref, value, lib_id, x, y, rot, side))
        if verbose:
            print("  %-8s %-3s x=%7.3f y=%7.3f rot=%3d  d=%6.2fmm"
                  % (ref, side, x, y, rot,
                     math.hypot(x - anchor[0], y - anchor[1])))
    n_fixed = len(FIXED_FRONT) + len(FIXED_BACK) + len(WING_SEATS)
    return {s[0]: s for s in placed[n_fixed:]}


def main():
    print("v10 ADR-129 placement solver -- seat-first, gate-verified")
    print("  board   : %.0f x %.0f mm, two-sided, outline unchanged" % (W, H))
    print("  gates   : check_board_geometry.py + check_hole_clearance.py")
    print("  placed  : %d fixed (20 parts + 4 seats + 8 holes) + %d ADR-129 refs"
          % (len(FIXED_FRONT) + len(FIXED_BACK) + len(WING_SEATS), len(NEW_PARTS)))
    sol = solve()
    if not sol:
        return 2
    # v = (ref, value, lib_id, x, y, rot, side)
    out = {ref: [round(v[3], 3), round(v[4], 3), v[5], v[6]]
          for ref, v in sol.items()}
    with open(OUT_JSON, "w") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print("wrote", OUT_JSON, "(%d refs)" % len(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

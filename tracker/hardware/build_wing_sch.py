#!/usr/bin/env python3
"""Generate the WING INTERCONNECT BOARD schematic (ADR-132 / ADR-134).

WHY THIS FILE EXISTS
--------------------
The board (`tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb`) was a
placement-stage artifact with **no schematic**, so it had no netlist. AGENTS.md §19-21
puts schematic -> ERC -> netlist before board routing, and the repo's router
(`route_v10_astar.py`, ADR-126) consumes a NETLIST, not a pad list. Six hand-routing
attempts failed on the board precisely because this file did not exist; the failures are
recorded in `docs/fab/wing-3d/ROUTING-STATUS.md`.

WHAT IT DESCRIBES (the circuit is three components deep)
-------------------------------------------------------
  3 x solar cell in SERIES  ->  6.0 V class wing string
  3 x SS24 Schottky, ONE ACROSS EACH CELL (per-cell bypass, ADR-132)
  1 x 2-pin tab to the hub  ->  SOLAR_P (pin 1) / SOLAR_N (pin 2) (ADR-134)

Per-cell bypass, not per-wing: on a soft shunt only a diode across the failing cell
clamps it (ADR-054 §2.3). Cathode to the cell's HIGH side, anode to its LOW side, so each
diode is reverse-biased in normal operation and forward-biased only when its own cell is
shaded or failing.

ELECTRICAL TOPOLOGY -- this is the whole circuit:

    SOLAR_P ──┬── SC1 + ─── SC1 - ──┬── SC2 + ─── SC2 - ──┬── SC3 + ─── SC3 - ── SOLAR_N
              │                     │                     │
             D1 K                  D2 K                  D3 K
             D1 A ─────────────────┘  D2 A ──────────────┘  D3 A ────────────────┘

Nets: SOLAR_P, SOLAR_MID1, SOLAR_MID2, SOLAR_N  -- 4 nets, matching the board exactly
(table in `wing_interconnect_v1.kicad_pcb`). ADR-134 removed GND and RF_FEED as dead
copper, so there are no other nets and no other parts.

DETERMINISM
-----------
Every UUID is uuid5(namespace, key), so two runs produce byte-identical output. The
flight-board generator had to be proven deterministic (AGENTS.md §25); this one is built
that way from the start. `--check` regenerates in memory and compares.

Run:  python3 tracker/hardware/build_wing_sch.py [--check]
"""
from __future__ import annotations

import os
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "schematics", "wing_interconnect")
OUT_SCH = os.path.join(OUTDIR, "wing_interconnect.kicad_sch")
OUT_SYMTAB = os.path.join(OUTDIR, "sym-lib-table")
OUT_ERC = os.path.join(OUTDIR, "wing_interconnect-erc.rpt")

SYMDIR = "/usr/share/kicad/symbols"
PROJECT = "wing_interconnect"
NS = uuid.UUID("6f1d9a3e-0b7c-5a41-9c2e-7d5b8a0c4e31")  # fixed: determinism

# ------------------------------------------------------------------ geometry (mm)
# EVERY coordinate is a multiple of 1.27 mm. That is KiCad's schematic grid: an off-grid
# wire endpoint is an ERC error (`endpoint_off_grid`) AND, worse, it silently fails to
# connect. Measured: my first draft used round numbers (60.0, 90.0) and produced 21
# endpoint_off_grid + 7 pin_not_connected + 7 unconnected_wire_endpoint.
G = 1.27
CELL_X = 48 * G      # 60.96
CELL_Y0 = 30 * G     # 38.10
CELL_STEP = 6 * G    # 7.62  == pin1..pin2 span, so adjacent cells SHARE a node
DIODE_X = 60 * G     # 76.20
TAB_X = 20 * G       # 25.40
TAB_Y = 40.64        # pin1 lands on y=40.64, pin2 on y=43.18 -- on the 1.27 grid

# PIN POSITIONS BELOW ARE MEASURED FROM ERC OUTPUT, NOT DERIVED FROM KICAD'S TRANSFORM.
# I got this wrong four times by reasoning about the transform matrix; each attempt was
# falsified by reading the pin coordinates ERC actually reports. The rule I finally
# confirmed: a schematic's screen y is the NEGATIVE of the symbol's local y.
#   Solar_Cell at rot 0  -> pin1 (+) at dy -5.08, pin2 (-) at dy +2.54   [measured]
#   D_Schottky at rot 0  -> pin1 (K) at dx -3.81, pin2 (A) at dx +3.81
#   D_Schottky at rot 90 -> pin1 (K) at dy +3.81, pin2 (A) at dy -3.81   [measured]
#   D_Schottky at rot 270-> pin1 (K) at dy -3.81, pin2 (A) at dy +3.81   [inferred+verified]
#   Conn_01x02 at rot 0  -> pin1 (dx -5.08, dy 0), pin2 (dx -5.08, dy +2.54) [measured]
CELL_ROT = 0
DIODE_ROT = 270       # K ABOVE A, so K lands on the cell's HIGH row
PIN1_DY = -5.08
PIN2_DY = +2.54

# Cells stack DOWNWARD (increasing y). MEASURED pin offsets make the chain exact:
# cell k pin2 (-) = CELL_Y0 + k*STEP + 2.54, and cell k+1 pin1 (+) = CELL_Y0 + (k+1)*STEP
# - 5.08. Those are equal iff STEP = 7.62, so with STEP = +7.62 the series chain needs no
# jumper wire. Measured: STEP = -7.62 left a 15.24 mm gap and SC1 pin2 dangling.
CELL_Y0 = 44 * G     # 55.88
CELL_STEP = 6 * G    # +7.62
Y_P = CELL_Y0 + PIN1_DY                      # 50.80  cell1 + (top)
Y_M1 = CELL_Y0 + PIN2_DY                     # 58.42  cell1 - == cell2 +
Y_M2 = CELL_Y0 + CELL_STEP + PIN2_DY         # 66.04  cell2 - == cell3 +
Y_N = CELL_Y0 + 2 * CELL_STEP + PIN2_DY      # 73.66  cell3 - (bottom)

# Each diode's own 7.62 K-A span equals one cell span, so a diode bridges its cell with no
# jumper: its origin is the midpoint of that cell's two node rows.
D1_Y = (Y_P + Y_M1) / 2.0                    # 57.15
D2_Y = (Y_M1 + Y_M2) / 2.0                   # 49.53
D3_Y = (Y_M2 + Y_N) / 2.0                    # 41.91

# SOLAR_N's escape lane -- deliberately NOT x=TAB_X, or it would land on the SOLAR_P wire
# that starts at that same x and short the two nets together in ERC.
N_LANE_X = 14 * G    # 17.78
N_RAIL_Y = 47 * G    # 59.69

# Stock KiCad symbols -- no custom library needed, so the schematic resolves in any
# stock install and ERC cannot fail on a missing lib_symbol.
LIBS = {
    "Device": ["Solar_Cell", "D_Schottky"],
    "Connector_Generic": ["Conn_01x02"],
}


def uid(*key: str) -> str:
    return str(uuid.uuid5(NS, "/".join(key)))


def _raw_symbol(lib: str, name: str) -> str:
    """Balanced-paren extraction of one symbol block from a stock .kicad_sym."""
    path = os.path.join(SYMDIR, lib + ".kicad_sym")
    text = open(path, errors="replace").read()
    head = '(symbol "%s"\n' % name
    i = text.find(head)
    if i < 0:
        raise KeyError("symbol %s:%s not found in %s" % (lib, name, path))
    depth, j = 0, i
    while j < len(text):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return text[i:j + 1]


def lib_symbols() -> str:
    parts = []
    for lib, names in LIBS.items():
        for nm in names:
            blk = _raw_symbol(lib, nm)
            head = '(symbol "%s"' % nm
            parts.append('(symbol "%s:%s"' % (lib, nm) + blk[len(head):])
    return "\n".join("\t\t" + p.replace("\n", "\n\t\t") for p in parts)


def symtab() -> str:
    rows = [
        '(sym_lib_table\n\t(version 7)',
    ]
    for lib in LIBS:
        rows.append(
            '\t(lib (name "%s")(type "KiCad")(uri "%s/%s.kicad_sym")'
            '(options "")(descr ""))' % (lib, SYMDIR, lib)
        )
    rows.append(")")
    return "\n".join(rows) + "\n"


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def place(lib_id, ref, value, x, y, rot=0, mirror=None, keys=()):
    """One placed symbol, with its two mandatory properties."""
    name = ref
    mir = "\n\t\t(mirror %s)" % mirror if mirror else ""
    pins = "".join(
        '\n\t\t(pin "%s"\n\t\t\t(uuid "%s")\n\t\t)' % (p, uid(ref, "pin", p))
        for p in keys
    )
    return """\t(symbol
\t\t(lib_id "%s")
\t\t(at %s %s %d)%s
\t\t(unit 1)
\t\t(exclude_from_sim no)
\t\t(in_bom yes)
\t\t(on_board yes)
\t\t(dnp no)
\t\t(fields_autoplaced yes)
\t\t(uuid "%s")
\t\t(property "Reference" "%s"
\t\t\t(at %s %s 0)
\t\t\t(effects (font (size 1.27 1.27)) (justify left))
\t\t)
\t\t(property "Value" "%s"
\t\t\t(at %s %s 0)
\t\t\t(effects (font (size 1.27 1.27)) (justify left))
\t\t)
\t\t(property "Footprint" ""
\t\t\t(at %s %s 0)
\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t)
\t\t(property "Datasheet" "~"
\t\t\t(at %s %s 0)
\t\t\t(effects (font (size 1.27 1.27)) (hide yes))
\t\t)%s
\t\t(instances
\t\t\t(project "%s"
\t\t\t\t(path "/%s"
\t\t\t\t\t(reference "%s") (unit 1)
\t\t\t\t)
\t\t\t)
\t\t)
\t)""" % (
        lib_id, _f(x), _f(y), rot, mir,
        uid(ref),
        ref, _f(x + 2.54), _f(y - 1.27),
        _esc(value), _f(x + 2.54), _f(y + 1.27),
        _f(x), _f(y), _f(x), _f(y),
        pins, PROJECT, ROOT_UUID, name,
    )


def _f(v: float) -> str:
    return ("%.4f" % v).rstrip("0").rstrip(".") or "0"


def wire(x1, y1, x2, y2, key):
    return ('\t(wire\n\t\t(pts (xy %s %s) (xy %s %s))\n\t\t(stroke (width 0) (type default))\n'
            '\t\t(uuid "%s")\n\t)' % (_f(x1), _f(y1), _f(x2), _f(y2), uid("wire", key)))


def label(name, x, y, rot=0, key=""):
    return ('\t(label "%s"\n\t\t(at %s %s %d)\n\t\t(effects (font (size 1.27 1.27)) (justify left bottom))\n'
            '\t\t(uuid "%s")\n\t)' % (name, _f(x), _f(y), rot, uid("label", name, key)))


def sections():
    out = []
    # ---- cells: series chain. Adjacent pins touch, so no jumper wire is needed.
    for i in range(3):
        y = CELL_Y0 + i * CELL_STEP
        out.append(place("Device:Solar_Cell", "SC%d" % (i + 1), "Solar_Cell",
                         CELL_X, y, CELL_ROT, None, keys=("1", "2")))
    # ---- bypass diodes, VERTICAL (rot 270) so K is above A: each spans exactly one cell
    #      with no jumper. K (pin 1) sits on the cell's HIGH row, A (pin 2) on its LOW row.
    for i, dy in enumerate((D1_Y, D2_Y, D3_Y)):
        out.append(place("Device:D_Schottky", "D%d" % (i + 1), "SS24",
                         DIODE_X, dy, DIODE_ROT, None, keys=("1", "2")))
    # ---- tab: the whole wing-to-hub interface (ADR-134: 2 pins, no GND/RF_FEED)
    out.append(place("Connector_Generic:Conn_01x02", "J1", "WING_TO_HUB",
                     TAB_X, TAB_Y, 0, None, keys=("1", "2")))

    # ---- node stubs. Each diode's own pins sit ON the node row, so a short horizontal
    #      stub from the cell row to the diode column joins them without any vertical run.
    out.append(wire(CELL_X, Y_P, DIODE_X, Y_P, "p-stub"))
    out.append(wire(CELL_X, Y_M1, DIODE_X, Y_M1, "m1-stub"))
    out.append(wire(CELL_X, Y_M2, DIODE_X, Y_M2, "m2-stub"))
    out.append(wire(CELL_X, Y_N, DIODE_X, Y_N, "n-stub"))

    # ---- tab escapes. The lanes must not cross the OTHER net's wire, so they take
    #      OPPOSITE sides: P escapes to the LEFT (x=7.62) and N to the RIGHT (x=88.90,
    #      past the diode column). Measured: putting both on the left shorted them -- N's
    #      vertical at x=12.70 crossed P's horizontal run at y=50.80 (`multiple_net_names`).
    px = TAB_X - 5.08
    p_pin_y = 40.64
    n_pin_y = 43.18
    p_rail_y = 24 * G            # 30.48  above the whole array
    p_lane_x = 6 * G             # 7.62   LEFT of everything
    n_lane_x = 70 * G            # 88.90  RIGHT of the diode column
    n_rail_y = 60 * G            # 76.20  below Y_N = 73.66
    out.append(wire(px, p_pin_y, px, p_rail_y, "p-up"))
    out.append(wire(px, p_rail_y, p_lane_x, p_rail_y, "p-back"))
    out.append(wire(p_lane_x, p_rail_y, p_lane_x, Y_P, "p-lane"))
    out.append(wire(p_lane_x, Y_P, CELL_X, Y_P, "p-in"))
    # N: right, down past the array, across the bottom, then up into the N row
    out.append(wire(px, n_pin_y, n_lane_x, n_pin_y, "n-out"))
    out.append(wire(n_lane_x, n_pin_y, n_lane_x, n_rail_y, "n-lane"))
    out.append(wire(n_lane_x, n_rail_y, DIODE_X, n_rail_y, "n-across"))
    out.append(wire(DIODE_X, n_rail_y, DIODE_X, Y_N, "n-in"))

    # ---- net names. Each sits MID-WIRE on exactly one wire: a label at a junction is
    #      `label_multiple_wires`, and a label not on a wire is `label_dangling`.
    out.append(label("SOLAR_P", 30 * G, Y_P, 0, "P"))          # mid p-in
    out.append(label("SOLAR_MID1", DIODE_X, Y_M1, 0, "M1"))    # on the diode K pin
    out.append(label("SOLAR_MID2", DIODE_X, Y_M2, 0, "M2"))
    #      Measured: 40*G (50.80) was OFF the N rail, which only spans x 76.20..88.90.
    out.append(label("SOLAR_N", 65 * G, n_rail_y, 0, "N"))     # 82.55, mid n-across
    return "\n".join(out)


ROOT_UUID = uid("root")


def build() -> str:
    return """(kicad_sch
\t(version 20250114)
\t(generator "build_wing_sch")
\t(generator_version "9.0")
\t(uuid "%s")
\t(paper "A4")
\t(title_block
\t\t(title "Wing interconnect -- per-cell bypass, 2-pin tab")
\t\t(rev "v1")
\t\t(comment 1 "ADR-132 per-cell bypass / ADR-134 2-pin tab")
\t\t(comment 2 "Generated by build_wing_sch.py -- do not hand-edit")
\t)
\t(lib_symbols
%s
\t)
%s
\t(sheet_instances
\t\t(path "/"
\t\t\t(page "1")
\t\t)
\t)
)
""" % (ROOT_UUID, lib_symbols(), sections())


def main() -> int:
    text = build()
    if "--check" in sys.argv:
        if not os.path.exists(OUT_SCH):
            print("MISSING: %s" % OUT_SCH)
            return 1
        on_disk = open(OUT_SCH, errors="replace").read()
        if on_disk != text:
            print("STALE: %s differs from the generator" % OUT_SCH)
            return 1
        print("ok: %s matches" % OUT_SCH)
        return 0
    os.makedirs(OUTDIR, exist_ok=True)
    with open(OUT_SCH, "w") as fh:
        fh.write(text)
    with open(OUT_SYMTAB, "w") as fh:
        fh.write(symtab())
    print("wrote %s (%d bytes)" % (OUT_SCH, len(text)))
    print("wrote %s" % OUT_SYMTAB)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""U4 (SX1280) WIRING REBUILD onto the real datasheet pinout -- the sheet of record.

WHY
    Commit b7b47df7 ("STEP 1") replaced U4's placeholder symbol with the REAL SX1280 pinout.
    KiCad connects by PIN NUMBER, so the pre-existing stub field re-landed on the real pins and
    U4's connectivity collapsed from 13 nets to 7, on functions that do not match the names:

        1  VR_PA    <- +3V3              VR_PA is a regulator OUTPUT; +3V3 shorts against it
        2  VDD_IN   <- /SX1280_RESET_N   reset drives a supply input
        3  NRESET   <- /SX1280_CS_N      CHIP SELECT RESETS THE RADIO
        4  XTA      <- /SX1280_MOSI      MOSI drives a crystal pin
        5  GND      <- /SX1280_DIO1      signal shorted to ground
        6  XTB      <- /SX1280_DIO3      DIO3 drives a crystal pin
       14  DCC_SW   <- GND               DISABLES the radio's internal regulator

    The old wiring is a 13-row stub field at 2.54 mm pitch (x = 314.96/320.04 and 350.52/355.60).
    The real part is 6 LEFT / 3 BOTTOM / 9 RIGHT / 6 TOP at 5.08 mm pitch, so the stub field
    CANNOT be reused. This script REBUILDS it against the absolute pin coordinates the SX1280
    symbol already carries, and adds the reference design's support + RF parts.

AUTHORITY
    docs/fab/U4-WIRING-REWORK-BRIEF.md + docs/fab/SX1280-WIRING-SPEC.json (net targets)
    docs/fab/SX1280-RF-SECTION.md (the 7-part RF network, vendor Table 15-1)
    docs/sx1280/SX1280-81_Rev3.2_Mar2020.pdf, Figure 15-1 (page 145) -- support parts + crystal

DEVIATIONS FROM THE BRIEF, each measured, each recorded in REPORT.md:
    1. Q1. The brief's spec.json says p1->XTA, p2->XTB, p3->GND, p4->GND. That is REFUTED by the
       vendor's own Figure 15-1: pins 1 and 3 are the two crystal ELECTRODES and pins 2 and 4 are
       the package GROUND pads. Wired as REFUTED would ground one electrode = dead oscillator.
       Two independent reads (pdftotext -bbox token coordinates on page 145, and a 3x zoomed
       visual read) agree. Implemented: pin1->XTA, pin3->XTB, pins2&4->GND (Device:Crystal_GND24).
    2. C4. The RF network's parallel 0.5 pF cap is the vendor's "C4", but the designator C4 is
       ALREADY TAKEN on this sheet by a populated 10 uF /GNSS_VCC decoupling cap. The RF part is
       therefore added as C7 (value, MPN and topology unchanged); the vendor mapping is recorded
       in REPORT.md and in docs/fab/SX1280-WIRING-SPEC.json.
    3. Two internal RF nodes need names because this sheet connects by LABEL, not by drawn wire:
       /SX1280_RF_MATCH (RFIO-C0-L1-C1 node) and /SX1280_RF_FILT (L2/C4-C2 node). The antenna-side
       node is the EXISTING /ANT2_2G4_RANGE net -- ADR-108 R1 re-pointed ANT2 at the SX1280 RFIO,
       and there is no "ANT5" part on this sheet.
    4. NO crystal load capacitors are added. Vendored Table 15-1 states Cload = 10 pF is
       INTERNALLY INTEGRATED. Their absence is deliberate.

METHOD (the rules that cost this campaign the most)
    * Whitespace is TEMPLATED from blocks that already parse; nothing is hand-indented.
    * `bidi` is not a KiCad pin type (the correct token is `bidirectional`) -- no new pin types
      are invented here; the EIGHT legal types were probed in b7b47df7.
    * Paren balance and the tab profile are ASSERTED before and after; the script REFUSES to write
      an unbalanced document.
    * The RESULT is validated, not the intent: after writing it exports the netlist with
      kicad-cli and asserts EVERY U4 pin (and every new part pin) against the target table.

Run:
    python3 tracker/hardware/rewrite_sch_u4_wiring.py            # dry run, prints the audit
    python3 tracker/hardware/rewrite_sch_u4_wiring.py --write    # write + export + validate
"""
import importlib.util
import os
import re
import subprocess
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
FB = os.path.join(HERE, "schematics", "flight_board")
SCH = os.path.join(FB, "v9_flight.kicad_sch")
NET = os.path.join(FB, "v9_flight.net")
GEN = os.path.join(FB, "build_flight_sch.py")
ROOT_UUID = "48a2cbfb-8edc-58cc-b464-7c0e74a94ee1"

NS = uuid.UUID("5b1f2c0e-9d3a-4a77-8a2c-0f6f0b7c4d21")
_uid_seen = set()


def uid(key):
    """Deterministic, unique UUIDv5 so a re-run is byte-identical."""
    assert key not in _uid_seen, "duplicate uid key %r" % key
    _uid_seen.add(key)
    return str(uuid.uuid5(NS, key))


def num(v):
    return ("%.2f" % v).rstrip("0").rstrip(".")


def balance(text):
    """(final depth, min depth) ignoring quoted strings -- lifted from rewrite_sch_sx1280.py."""
    inq = esc = False
    d = mind = 0
    for ch in text:
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            inq = not inq
            continue
        if inq:
            continue
        if ch == "(":
            d += 1
        elif ch == ")":
            d -= 1
            mind = min(mind, d)
    return d, mind


def top_children(text):
    """Spans [a, b] (inclusive, at the '(' and the matching ')') of every depth-1 child."""
    depth = 0
    inq = esc = False
    kids = []
    cur = None
    for i, ch in enumerate(text):
        if inq:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                inq = False
            continue
        if ch == '"':
            inq = True
            continue
        if ch == "(":
            depth += 1
            if depth == 2:
                cur = [i, None]
        elif ch == ")":
            if depth == 2 and cur:
                cur[1] = i
                kids.append((cur[0], cur[1]))
                cur = None
            depth -= 1
    return kids


def kind(text, a):
    m = re.match(r"([A-Za-z_0-9]+)", text[a + 1:a + 41])
    return m.group(1) if m else "?"


# ---------------------------------------------------------------- library loading


def _load_gen():
    spec = importlib.util.spec_from_file_location("_bfs", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GENMOD = _load_gen()
SYM_CACHE = {}


def lib_symbol(lib_id):
    """Raw block from the KiCad v9 libraries, renamed to LIB:NAME."""
    if lib_id not in SYM_CACHE:
        lib, name = lib_id.split(":", 1)
        SYM_CACHE[lib_id] = GENMOD.load_lib_symbol(lib, name)
    return SYM_CACHE[lib_id]


def lib_pins(lib_id):
    return GENMOD.symbol_pins(lib_symbol(lib_id))


def embedded_symbol(src, lib_id):
    """The lib_symbols block for lib_id as embedded in the sheet itself."""
    i = src.find('(symbol "%s"' % lib_id)
    assert i >= 0, "%s not embedded in the sheet" % lib_id
    d = 0
    inq = esc = False
    j = i
    while j < len(src):
        ch = src[j]
        if inq:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                inq = False
        elif ch == '"':
            inq = True
        elif ch == "(":
            d += 1
        elif ch == ")":
            d -= 1
            if d == 0:
                break
        j += 1
    return src[i:j + 1]


def embedded_pins(src, lib_id):
    return GENMOD.symbol_pins(embedded_symbol(src, lib_id))


def embed(block, depth=2):
    """Re-indent a library symbol block for embedding at `depth` inside lib_symbols.

    KiCad writes library symbols with the head at column 0, contents at 2 tabs and the close at
    1 tab; inside a schematic's lib_symbols the head sits at 2 tabs, contents at 3, close at 2.
    The whole block therefore shifts by exactly ONE tab, plus the head's extra tab.
    """
    lines = block.split("\n")
    return "\n".join(["\t" * depth + lines[0]] + ["\t" * (depth - 1) + l for l in lines[1:]])


# ---------------------------------------------------------------- block templates

DIR = {0.0: (1, 0), 90.0: (0, 1), 180.0: (-1, 0), 270.0: (0, -1)}


def pin_point(sx, sy, pin):
    return (sx + pin["x"], sy - pin["y"])


def stub_end(sx, sy, pin, length):
    ox, oy = DIR[pin["a"] % 360.0]
    px, py = pin_point(sx, sy, pin)
    return (px - ox * length, py + oy * length)


def wire(p1, p2, key):
    assert p1 != p2, key
    return ("\t(wire\n"
            "\t\t(pts\n"
            "\t\t\t(xy %s %s) (xy %s %s)\n"
            "\t\t)\n"
            "\t\t(stroke\n"
            "\t\t\t(width 0)\n"
            "\t\t\t(type default)\n"
            "\t\t)\n"
            "\t\t(uuid \"%s\")\n"
            "\t)" % (num(p1[0]), num(p1[1]), num(p2[0]), num(p2[1]), uid(key)))


def label(name, at, key):
    return ("\t(label \"%s\"\n"
            "\t\t(at %s %s 0)\n"
            "\t\t(effects\n"
            "\t\t\t(font\n"
            "\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t)\n"
            "\t\t\t(justify left bottom)\n"
            "\t\t)\n"
            "\t\t(uuid \"%s\")\n"
            "\t)" % (name, num(at[0]), num(at[1]), uid(key)))


def power_symbol(net, at, ref, key):
    """power:GND / power:+3V3 flag -- the ONLY way this sheet makes a power net."""
    hide = "%s" % ("\t\t\t\t(hide yes)\n")
    return ("\t(symbol\n"
            "\t\t(lib_id \"power:%s\")\n"
            "\t\t(at %s %s 0)\n"
            "\t\t(unit 1)\n"
            "\t\t(exclude_from_sim no)\n"
            "\t\t(in_bom yes)\n"
            "\t\t(on_board yes)\n"
            "\t\t(dnp no)\n"
            "\t\t(uuid \"%s\")\n"
            "\t\t(property \"Reference\" \"%s\"\n"
            "\t\t\t(at %s %s 0)\n"
            "\t\t\t(effects\n"
            "\t\t\t\t(font\n"
            "\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t)\n"
            "%s"
            "\t\t\t)\n"
            "\t\t)\n"
            "\t\t(property \"Value\" \"%s\"\n"
            "\t\t\t(at %s %s 0)\n"
            "\t\t\t(effects\n"
            "\t\t\t\t(font\n"
            "\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t)\n"
            "%s"
            "\t\t\t)\n"
            "\t\t)\n"
            "\t\t(property \"Footprint\" \"\"\n"
            "\t\t\t(at %s %s 0)\n"
            "\t\t\t(effects\n"
            "\t\t\t\t(font\n"
            "\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t)\n"
            "\t\t\t\t(hide yes)\n"
            "\t\t\t)\n"
            "\t\t)\n"
            "\t\t(pin \"1\"\n"
            "\t\t\t(uuid \"%s\")\n"
            "\t\t)\n"
            "\t\t(instances\n"
            "\t\t\t(project \"v9_flight\"\n"
            "\t\t\t\t(path \"/%s\"\n"
            "\t\t\t\t\t(reference \"%s\")\n"
            "\t\t\t\t\t(unit 1)\n"
            "\t\t\t\t)\n"
            "\t\t\t)\n"
            "\t\t)\n"
            "\t)" % (net, num(at[0]), num(at[1]), uid(key + ".sym"),
                    ref, num(at[0] + 2.54), num(at[1] + 2.54), hide,
                    net, num(at[0] + 2.54), num(at[1] - 2.54), hide,
                    num(at[0]), num(at[1]), uid(key + ".pin"),
                    uid(key + ".path"), ref))


def component(part, key):
    """A placed Device:C / Device:R / Device:L / Device:Crystal_GND24 instance."""
    lib_id = part["lib"]
    pins = lib_pins(lib_id)
    x, y = part["x"], part["y"]
    pin_blocks = "".join(
        "\t\t(pin \"%s\"\n\t\t\t(uuid \"%s\")\n\t\t)\n" % (p, uid(key + ".pin" + p))
        for p in sorted(pins, key=lambda s: int(s)))
    return ("\t(symbol\n"
            "\t\t(lib_id \"%s\")\n"
            "\t\t(at %s %s 0)\n"
            "\t\t(unit 1)\n"
            "\t\t(exclude_from_sim no)\n"
            "\t\t(in_bom yes)\n"
            "\t\t(on_board yes)\n"
            "\t\t(dnp no)\n"
            "\t\t(uuid \"%s\")\n"
            "\t\t(property \"Reference\" \"%s\"\n"
            "\t\t\t(at %s %s 0)\n"
            "\t\t\t(effects\n"
            "\t\t\t\t(font\n"
            "\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t)\n"
            "\t\t\t\t(justify left)\n"
            "\t\t\t)\n"
            "\t\t)\n"
            "\t\t(property \"Value\" \"%s\"\n"
            "\t\t\t(at %s %s 0)\n"
            "\t\t\t(effects\n"
            "\t\t\t\t(font\n"
            "\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t)\n"
            "\t\t\t\t(justify left)\n"
            "\t\t\t)\n"
            "\t\t)\n"
            "\t\t(property \"Footprint\" \"%s\"\n"
            "\t\t\t(at %s %s 0)\n"
            "\t\t\t(effects\n"
            "\t\t\t\t(font\n"
            "\t\t\t\t\t(size 1.27 1.27)\n"
            "\t\t\t\t)\n"
            "\t\t\t\t(hide yes)\n"
            "\t\t\t)\n"
            "\t\t)\n"
            "%s"
            "\t\t(instances\n"
            "\t\t\t(project \"v9_flight\"\n"
            "\t\t\t\t(path \"/%s\"\n"
            "\t\t\t\t\t(reference \"%s\")\n"
            "\t\t\t\t\t(unit 1)\n"
            "\t\t\t\t)\n"
            "\t\t\t)\n"
            "\t\t)\n"
            "\t)" % (lib_id, num(x), num(y), uid(key + ".sym"),
                    part["ref"], num(x + 2.54), num(y - 7.62),
                    part["val"], num(x + 2.54), num(y + 2.54),
                    part["fp"], num(x), num(y),
                    pin_blocks, uid(key + ".path"), part["ref"]))


# ================================================================ the REBUILD ==============

# ---- U4 pin -> target, straight from docs/fab/SX1280-WIRING-SPEC.json -----------------------
U4_TARGET = {
    "0":  ("gnd", None),
    "1":  ("label", "SX1280_VR_PA"),
    "2":  ("label", "SX1280_VDD"),
    "3":  ("label", "SX1280_RESET_N"),
    "4":  ("label", "SX1280_XTA"),
    "5":  ("gnd", None),
    "6":  ("label", "SX1280_XTB"),
    "7":  ("label", "SX1280_BUSY"),
    "8":  ("label", "SX1280_DIO1"),
    "9":  ("label", "SX1280_DIO2"),
    "10": ("label", "SX1280_DIO3"),
    "11": ("label", "SX1280_VBAT_IO"),
    "12": ("label", "SX1280_VDD"),
    "13": ("gnd", None),
    "14": ("label", "SX1280_DCC_SW"),
    "15": ("rail", None),
    "16": ("label", "SX1280_MISO"),
    "17": ("label", "SX1280_MOSI"),
    "18": ("label", "SX1280_SCK"),
    "19": ("label", "SX1280_CS_N"),
    "20": ("gnd", None),
    "21": ("gnd", None),
    "22": ("label", "SX1280_RF"),
    "23": ("gnd", None),
    "24": ("gnd", None),
}

# pin 0 is the exposed pad: the symbol puts its connectable end at the BODY CENTRE, so it cannot
# use the 5.08 mm stub -- it is wired straight out to the left (y = 50.8 crosses no left pin).
EP_WIRE = ((335.28, 50.80), (309.88, 50.80))

# ---- support + RF parts.  (x, y) are chosen inside canvas freed by removing the old grid.
C0402 = "Capacitor_SMD:C_0402_1005Metric"
R0402 = "Resistor_SMD:R_0402_1005Metric"
L0402 = "Inductor_SMD:L_0402_1005Metric"
L1210 = "Inductor_SMD:L_1210_3225Metric"       # DMBJ CD32-150M, LCSC C2826623, SMD 3.5x3 mm
CRYST = "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm"

PARTS = [
    # --- support (vendor Table 15-1 / Figure 15-1) -------------------------------------------
    dict(ref="C5",  lib="Device:C", val="10nF",  fp=C0402, x=297.18, y=95.25,
         conn={"1": ("label", "SX1280_VR_PA"),   "2": ("gnd", None)}),
    dict(ref="C6",  lib="Device:C", val="10nF",  fp=C0402, x=314.96, y=95.25,
         conn={"1": ("label", "SX1280_VDD"),     "2": ("gnd", None)}),
    dict(ref="C9",  lib="Device:C", val="470nF", fp=C0402, x=332.74, y=95.25,
         conn={"1": ("label", "SX1280_VDD"),     "2": ("gnd", None)}),
    dict(ref="C8",  lib="Device:C", val="100nF", fp=C0402, x=350.52, y=95.25,
         conn={"1": ("label", "SX1280_VBAT_IO"), "2": ("gnd", None)}),
    dict(ref="C10", lib="Device:C", val="100nF", fp=C0402, x=368.30, y=95.25,
         conn={"1": ("rail", None),              "2": ("gnd", None)}),
    dict(ref="R15", lib="Device:R", val="0R",    fp=R0402, x=386.08, y=95.25,
         conn={"1": ("rail", None),              "2": ("label", "SX1280_VBAT_IO")}),
    # DCC_SW -> L4 -> V_DCC(=VDD_IN/DCC_FB).  MANDATORY: the internal DC-DC is "considered
    # switched ON unless otherwise stated", so omitting L4/C9 leaves an open regulator loop.
    dict(ref="L4",  lib="Device:L", val="15uH",  fp=L1210, x=297.18, y=121.92,
         conn={"1": ("label", "SX1280_DCC_SW"),  "2": ("label", "SX1280_VDD")}),
    # Q1: vendor Figure 15-1 page 145 -- pins 1 & 3 are the electrodes, 2 & 4 the ground pads.
    # NO load capacitors (Cload = 10 pF is internally integrated).
    dict(ref="Q1",  lib="Device:Crystal_GND24", val="52MHz", fp=CRYST, x=314.96, y=121.92,
         conn={"1": ("label", "SX1280_XTA"), "3": ("label", "SX1280_XTB"),
               "2": ("gnd", None), "4": ("gnd", None)}),
    # --- RF network, vendor Table 15-1 ------------------------------------------------------
    # RFIO(22) -> C0|GND -> L1 -> C1|GND -> (L2 || C7) -> C2|GND -> C3 -> ANT2 (U.FL)
    dict(ref="C0",  lib="Device:C", val="0.8pF", fp=C0402, x=332.74, y=121.92,
         conn={"1": ("label", "SX1280_RF"),       "2": ("gnd", None)}),
    dict(ref="L1",  lib="Device:L", val="3.0nH", fp=L0402, x=350.52, y=121.92,
         conn={"1": ("label", "SX1280_RF"),       "2": ("label", "SX1280_RF_MATCH")}),
    dict(ref="C1",  lib="Device:C", val="1.2pF", fp=C0402, x=368.30, y=121.92,
         conn={"1": ("label", "SX1280_RF_MATCH"), "2": ("gnd", None)}),
    dict(ref="L2",  lib="Device:L", val="2.5nH", fp=L0402, x=386.08, y=121.92,
         conn={"1": ("label", "SX1280_RF_MATCH"), "2": ("label", "SX1280_RF_FILT")}),
    dict(ref="C7",  lib="Device:C", val="0.5pF", fp=C0402, x=297.18, y=148.59,
         conn={"1": ("label", "SX1280_RF_MATCH"), "2": ("label", "SX1280_RF_FILT")}),
    dict(ref="C2",  lib="Device:C", val="1.2pF", fp=C0402, x=314.96, y=148.59,
         conn={"1": ("label", "SX1280_RF_FILT"),  "2": ("gnd", None)}),
    dict(ref="C3",  lib="Device:C", val="100pF", fp=C0402, x=332.74, y=148.59,
         conn={"1": ("label", "SX1280_RF_FILT"),  "2": ("label", "ANT2_2G4_RANGE")}),
]

# ---- the old 13-row 2.54 mm stub field, removed wholesale ------------------------------------
def wkey(p1, p2):
    """Order-independent wire key on 2-decimal coordinates (the file writes 38.1, not 38.10)."""
    e = sorted([(round(float(p1[0]), 2), round(float(p1[1]), 2)),
                (round(float(p2[0]), 2), round(float(p2[1]), 2))])
    return tuple(e)


OLD_WIRES = set()
for _y in [35.56, 38.10, 40.64, 43.18, 45.72, 48.26, 50.80, 53.34, 55.88, 58.42, 60.96, 63.50, 66.04]:
    OLD_WIRES.add(wkey(("320.04", _y), ("314.96", _y)))
for _y in [35.56, 38.10, 40.64, 43.18, 45.72, 48.26, 50.80, 53.34, 55.88, 58.42, 60.96, 63.50]:
    OLD_WIRES.add(wkey(("350.52", _y), ("355.60", _y)))

OLD_LABELS = {
    ("SX1280_RESET_N", 314.96, 43.18), ("SX1280_BUSY", 314.96, 45.72),
    ("SX1280_CS_N", 314.96, 48.26),    ("SX1280_SCK", 314.96, 50.80),
    ("SX1280_MOSI", 314.96, 53.34),    ("SX1280_MISO", 314.96, 55.88),
    ("SX1280_DIO1", 314.96, 58.42),    ("SX1280_DIO2", 314.96, 60.96),
    ("SX1280_DIO3", 314.96, 63.50),    ("ANT2_2G4_RANGE", 355.60, 35.56),
}

OLD_PWR = {"#PWR%04d" % i for i in range(17, 31)}          # #PWR0017 .. #PWR0030

U4_TITLE_OLD = "U4 SX1280  (2.4 GHz ranging)  *** PINOUT UNVERIFIED ***"
U4_TITLE_NEW = ("U4 SX1280  (2.4 GHz ranging) - REAL pinout, OPEN-13 closed 2026-10-14 "
                "(docs/fab/OPEN-13-CLOSED-SX1280-PINOUT.md). Wiring REBUILT onto it 2026-10-15 "
                "from docs/fab/U4-WIRING-REWORK-BRIEF.md; support + RF parts from Figure 15-1 / "
                "Table 15-1.")

NEW_SECTION_TEXT = "U4 SX1280 SUPPORT + 2.4 GHz RF NETWORK (vendor Table 15-1 / Figure 15-1)"


# ================================================================ main =====================

def build(src):
    d0, m0 = balance(src)
    print("input  balance: final=%d min=%d  (%d chars)" % (d0, m0, len(src)))
    assert (d0, m0) == (0, 0), "input schematic does not balance -- refusing to touch it"
    kids = top_children(src)
    print("top-level children: %d" % len(kids))

    # ---------------------------------------------------------- 1. find the removals
    drop = []
    n_wire = n_label = n_pwr = 0
    u4_text = None
    libsym_block = None
    for a, b in kids:
        k = kind(src, a)
        seg = src[a:b + 1]
        if k == "lib_symbols":
            libsym_block = (a, b)
        elif k == "wire":
            pts = re.findall(r"\(xy ([-\d.]+) ([-\d.]+)\)", seg)
            if len(pts) == 2 and wkey(pts[0], pts[1]) in OLD_WIRES:
                drop.append((a, b))
                n_wire += 1
        elif k == "label":
            m = re.search(r"\(label \"([^\"]+)\"", seg)
            at = re.search(r"\(at ([-\d.]+) ([-\d.]+)", seg)
            if m and at and (m.group(1), float(at.group(1)), float(at.group(2))) in OLD_LABELS:
                drop.append((a, b))
                n_label += 1
        elif k == "symbol" and a > 5000:
            m = re.search(r"\(property \"Reference\" \"([^\"]+)\"", seg)
            if m and m.group(1) in OLD_PWR:
                drop.append((a, b))
                n_pwr += 1
        elif k == "text" and U4_TITLE_OLD in seg:
            u4_text = (a, b)

    print("removals: wires=%d/25  labels=%d/10  power_symbols=%d/14  u4_title_text=%s"
          % (n_wire, n_label, n_pwr, "found" if u4_text else "MISSING"))
    assert n_wire == 25 and n_label == 10 and n_pwr == 14, "removal set is not the one measured"
    assert u4_text, "the U4 section-title text was not found"
    assert libsym_block, "lib_symbols not found"

    # ---------------------------------------------------------- 2. the U4 rebuild
    add = []
    u4_pins = embedded_pins(src, "balloon_flight_v9:SX1280")
    u4_pos = (335.28, 50.80)
    wires = {}       # (key) -> (p1, p2)  deduplicated on coordinates
    targets = []     # (kind, name, at)
    for pnum, (tkind, tname) in sorted(U4_TARGET.items(), key=lambda kv: int(kv[0])):
        pin = u4_pins[pnum]
        if pnum == "0":
            p1, p2 = EP_WIRE
        else:
            p1 = pin_point(u4_pos[0], u4_pos[1], pin)
            p2 = stub_end(u4_pos[0], u4_pos[1], pin, 5.08)
        wires[(p1, p2)] = "u4.%s" % pnum
        targets.append((tkind, tname, p2))

    # ---------------------------------------------------------- 3. the new parts
    for part in PARTS:
        pins = lib_pins(part["lib"])
        assert set(pins) == set(part["conn"]), "%s: pin table %s != conn %s" % (
            part["ref"], sorted(pins), sorted(part["conn"]))
        for pnum, (tkind, tname) in sorted(part["conn"].items(), key=lambda kv: int(kv[0])):
            p1 = pin_point(part["x"], part["y"], pins[pnum])
            p2 = stub_end(part["x"], part["y"], pins[pnum], 5.08)
            wires[(p1, p2)] = "%s.%s" % (part["ref"], pnum)
            targets.append((tkind, tname, p2))

    for (p1, p2), key in wires.items():
        add.append(wire(p1, p2, "wire." + key))

    # one label / power flag per (kind, name, coordinate): Q1's pads 2 and 4 are the SAME point
    seen_t = set()
    pwr_i = 69
    for tkind, tname, at in targets:
        sig = (tkind, tname, round(at[0], 2), round(at[1], 2))
        if sig in seen_t:
            continue
        seen_t.add(sig)
        k = "target.%s.%s.%s_%s" % (tkind, tname or "", num(at[0]), num(at[1]))
        if tkind == "label":
            add.append(label(tname, at, k))
        elif tkind == "gnd":
            add.append(power_symbol("GND", at, "#PWR%04d" % pwr_i, k))
            pwr_i += 1
        elif tkind == "rail":
            add.append(power_symbol("+3V3", at, "#PWR%04d" % pwr_i, k))
            pwr_i += 1
        else:
            raise AssertionError(tkind)

    for part in PARTS:
        add.append(component(part, "part." + part["ref"]))

    add.append(
        "\t(text \"%s\"\n"
        "\t\t(exclude_from_sim no)\n"
        "\t\t(at 297.18 81.28 0)\n"
        "\t\t(effects\n"
        "\t\t\t(font\n"
        "\t\t\t\t(size 1.524 1.524)\n"
        "\t\t\t)\n"
        "\t\t\t(justify left bottom)\n"
        "\t\t)\n"
        "\t\t(uuid \"%s\")\n"
        "\t)" % (NEW_SECTION_TEXT, uid("text.newsection")))

    # ---------------------------------------------------------- 4. lib_symbols additions
    lib_add = []
    for lib_id in ("Device:L", "Device:Crystal_GND24"):
        assert lib_id not in src, "%s already embedded" % lib_id
        lib_add.append(embed(lib_symbol(lib_id)))
    la, lb = libsym_block
    # insert before lib_symbols' closing paren (its own line, "\t)")
    tail = src[la:lb + 1]
    close_at = tail.rfind("\n\t)")
    assert close_at > 0
    lib_src = src[la:lb + 1]
    new_lib = lib_src[:close_at] + "\n" + "\n".join(lib_add) + lib_src[close_at:]

    # ---------------------------------------------------------- 5. the U4 section text
    ta, tb = u4_text
    old_seg = src[ta:tb + 1]
    assert U4_TITLE_OLD in old_seg
    new_seg = old_seg.replace(U4_TITLE_OLD, U4_TITLE_NEW)
    assert balance(new_seg) == (0, 0)

    # ---------------------------------------------------------- 6. splice
    # apply edits from the END backwards so offsets stay valid
    edits = [(la, lb + 1, new_lib), (ta, tb + 1, new_seg)]
    for a, b in drop:
        # also swallow the "\n\t" that introduced the block, so no stray indentation remains
        s = a
        while s > 0 and src[s - 1] in " \t":
            s -= 1
        if s > 0 and src[s - 1] == "\n":
            s -= 1
        edits.append((s, b + 1, ""))
    edits.sort(key=lambda e: e[0], reverse=True)

    out = src
    for s, e, rep in edits:
        out = out[:s] + rep + out[e:]

    # append the new blocks just before (sheet_instances
    si = out.index("\n\t(sheet_instances")
    out = out[:si + 1] + "\n".join(add) + "\n" + out[si + 1:]

    d1, m1 = balance(out)
    print("output balance: final=%d min=%d  (%d -> %d chars, delta %+d)"
          % (d1, m1, len(src), len(out), len(out) - len(src)))
    assert d1 == 0, "REFUSING TO WRITE: document does not balance (final=%d)" % d1
    assert m1 == 0, "REFUSING TO WRITE: depth went negative (min=%d)" % m1
    bad = [i for i, l in enumerate(out.split("\n"), 1) if l.startswith(" ")]
    print("tab profile: lines starting with a SPACE = %d (must be 0)" % len(bad))
    assert not bad, bad[:5]

    stats = dict(wires=len(wires), labels=sum(1 for t in seen_t if t[0] == "label"),
                 power=sum(1 for t in seen_t if t[0] in ("gnd", "rail")),
                 parts=len(PARTS), removed=n_wire + n_label + n_pwr + 1)
    print("added: %(wires)d wires, %(labels)d labels, %(power)d power flags, %(parts)d parts"
          % stats)
    return out, stats


# ---------------------------------------------------------------- validation

TARGET_BY_PIN = {
    "0": "GND", "1": "/SX1280_VR_PA", "2": "/SX1280_VDD", "3": "/SX1280_RESET_N",
    "4": "/SX1280_XTA", "5": "GND", "6": "/SX1280_XTB", "7": "/SX1280_BUSY",
    "8": "/SX1280_DIO1", "9": "/SX1280_DIO2", "10": "/SX1280_DIO3", "11": "/SX1280_VBAT_IO",
    "12": "/SX1280_VDD", "13": "GND", "14": "/SX1280_DCC_SW", "15": "+3V3", "16": "/SX1280_MISO",
    "17": "/SX1280_MOSI", "18": "/SX1280_SCK", "19": "/SX1280_CS_N", "20": "GND", "21": "GND",
    "22": "/SX1280_RF", "23": "GND", "24": "GND",
}
PART_TARGET = {
    "C5":  {"1": "/SX1280_VR_PA", "2": "GND"},
    "C6":  {"1": "/SX1280_VDD", "2": "GND"},
    "C9":  {"1": "/SX1280_VDD", "2": "GND"},
    "C8":  {"1": "/SX1280_VBAT_IO", "2": "GND"},
    "C10": {"1": "+3V3", "2": "GND"},
    "R15": {"1": "+3V3", "2": "/SX1280_VBAT_IO"},
    "L4":  {"1": "/SX1280_DCC_SW", "2": "/SX1280_VDD"},
    "Q1":  {"1": "/SX1280_XTA", "2": "GND", "3": "/SX1280_XTB", "4": "GND"},
    "C0":  {"1": "/SX1280_RF", "2": "GND"},
    "L1":  {"1": "/SX1280_RF", "2": "/SX1280_RF_MATCH"},
    "C1":  {"1": "/SX1280_RF_MATCH", "2": "GND"},
    "L2":  {"1": "/SX1280_RF_MATCH", "2": "/SX1280_RF_FILT"},
    "C7":  {"1": "/SX1280_RF_MATCH", "2": "/SX1280_RF_FILT"},
    "C2":  {"1": "/SX1280_RF_FILT", "2": "GND"},
    "C3":  {"1": "/SX1280_RF_FILT", "2": "/ANT2_2G4_RANGE"},
}


def parse_netlist(path):
    """{(ref, pin): net_name}.  Scans each `(net ...)` block by paren depth -- a single-node net
    closes on the node's own line, so a line-anchored regex misses most of them."""
    s = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    n = 0
    for m in re.finditer(r'\(net \(code "\d+"\) \(name "([^"]+)"\)', s):
        name = m.group(1)
        d = 0
        i = m.start()
        inq = esc = False
        while i < len(s):
            ch = s[i]
            if inq:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    inq = False
            elif ch == '"':
                inq = True
            elif ch == "(":
                d += 1
            elif ch == ")":
                d -= 1
                if d == 0:
                    break
            i += 1
        body = s[m.start():i + 1]
        n += 1
        for mm in re.finditer(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', body):
            out[(mm.group(1), mm.group(2))] = name
    return out, (s, n)


def validate(net_path, expect, label):
    got, raw = parse_netlist(net_path)
    bad = []
    for ref, pins in expect.items():
        for pin, want in pins.items():
            have = got.get((ref, pin))
            if have != want:
                bad.append("%s.%s: want %s, got %s" % (ref, pin, want, have))
    print("  %-28s pins checked=%d  MISMATCHES=%d"
          % (label, sum(len(v) for v in expect.values()), len(bad)))
    for b in bad[:25]:
        print("      " + b)
    return bad


def main():
    src = open(SCH, encoding="utf-8").read()
    out, stats = build(src)
    if "--write" not in sys.argv:
        print("\nDRY RUN -- balanced OK, nothing written. Re-run with --write.")
        return 0

    open(SCH, "w", encoding="utf-8").write(out)
    print("\nWROTE %s" % SCH)

    tmp = "/tmp/u4_after.net"
    if os.path.exists(tmp):
        os.unlink(tmp)
    r = subprocess.run(["kicad-cli", "sch", "export", "netlist", "--output", tmp, SCH],
                       capture_output=True, text=True)
    print("kicad-cli sch export netlist: rc=%d" % r.returncode)
    print((r.stdout + r.stderr).strip())
    assert r.returncode == 0 and os.path.exists(tmp), "NETLIST EXPORT FAILED"
    # the committed netlist is a DERIVED artifact and must match the sheet
    open(NET, "w", encoding="utf-8").write(open(tmp, encoding="utf-8").read())
    print("WROTE %s" % NET)

    print("\n=== VALIDATION: every pin against the target table ===")
    bad = validate(tmp, {"U4": TARGET_BY_PIN}, "U4 (25 pins)")
    bad += validate(tmp, PART_TARGET, "support + RF parts")
    if bad:
        print("\nVALIDATION FAILED -- %d mismatches" % len(bad))
        return 1
    print("\nVALIDATION PASSED -- U4 on its target nets, zero mismatches;"
          " 8 support parts + 15-part RF/support set wired")
    return 0


if __name__ == "__main__":
    sys.exit(main())

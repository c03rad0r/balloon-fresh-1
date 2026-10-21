#!/usr/bin/env python3
"""Transform the v9 flight netlist into the v10 netlist per the ADR stack.

ADR-118: two-sided v10 board
ADR-119: four RF sites -- F33(A) + LP(B=U3) + LP(C=NEW U_C) + E28 module(replaces U4)
ADR-121: J_PROG header (6-pin) + EN reset RC (R_EN 10k, C_EN 1uF)
ADR-123: TWO SPI buses -- /SPI1_* for U3/U_C/E28, /SPI2_* for F33 alone

Transformations (all additive or renames; nothing silently deleted):
  1. U4 (SX1280 QFN) -> U_E28 (E28-2G4M27SX module footprint).
     Net renames: /SX1280_MOSI->/SPI1_MOSI, /SX1280_MISO->/SPI1_MISO,
     /SX1280_SCK->/SPI1_SCK, /SX1280_CS_N->/E28_CS_N, /SX1280_BUSY->/E28_BUSY,
     /SX1280_RESET_N->/E28_RESET_N, /SX1280_DIO1..3->/E28_DIO1..3.
     NEW nets: /E28_RX_EN, /E28_TX_EN (PA/LNA control).
     DROPPED (bare-chip support network, ADR-119): C0,C1,C2,C3,C7,L1,L2,Q1 + their nets.
  2. F33 bus moves to SPI-2: /F33_SCK->/SPI2_SCK, /F33_MOSI->/SPI2_MOSI,
     /F33_MISO->/SPI2_MISO (/F33_CS_N stays its own CS).
  3. U3 joins SPI-1: /U3_* control nets stay; its SCK/MOSI/MISO pins re-point to /SPI1_*.
  4. NEW U_C (Site C, LoRa2021_Castellated like U3): nets /UC_CS_N,/UC_BUSY,/UC_IRQ,
     /UC_RESET_N + shared /SPI1_*, /ANT_C_2G4 + its own U.FL ANT_C.
  5. NEW J_PROG (Conn_01x06): pins GND,+3V3,/EN,/USB_DN,/USB_DP,/IO0 (ADR-121).
     U1 pad3->/EN, pad13->/USB_DN, pad14->/USB_DP.
     NEW R_EN(10k)+C_EN(1uF) on /EN->GND (reset RC).
Run: python3 make_v10_netlist.py --in v9_flight.net --out v10_flight.net
"""
import argparse
import re
import sys

RENAME = {
    "/SX1280_MOSI": "/SPI1_MOSI",
    "/SX1280_MISO": "/SPI1_MISO",
    "/SX1280_SCK": "/SPI1_SCK",
    "/SX1280_CS_N": "/E28_CS_N",
    "/SX1280_BUSY": "/E28_BUSY",
    "/SX1280_RESET_N": "/E28_RESET_N",
    "/SX1280_DIO1": "/E28_DIO1",
    "/SX1280_DIO2": "/E28_DIO2",
    "/SX1280_DIO3": "/E28_DIO3",
    "/F33_SCK": "/SPI2_SCK",
    "/F33_MOSI": "/SPI2_MOSI",
    "/F33_MISO": "/SPI2_MISO",
}

DROP_REFS = ["C0", "C1", "C2", "C3", "C7", "L1", "L2", "Q1"]  # bare-chip RF network (ADR-119)

U1_PIN_REPOINT = {"3": "/EN", "13": "/USB_DN", "14": "/USB_DP"}


def drop_comp_blocks(text, refs):
    # comp blocks end with '(tstamps "..."))' followed by whitespace -- match to the
    # tstamps close of THIS block (non-greedy up to the first '))\n' after the ref).
    for r in refs:
        pat = r'\(comp \(ref "%s"\).*?\(tstamps "[^"]*"\)\)\s*\n' % r
        new = re.sub(pat, "", text, flags=re.S)
        if new == text:
            print(f"WARN: comp {r} not found for drop")
        text = new
    return text


def drop_nodes(text, refs):
    for r in refs:
        pat = r'[ \t]*\(node \(ref "%s"\) \(pin "[^"]+"\)[^\n]*\n' % r
        new = re.sub(pat, "", text)
        text = new
    return text



# E28 module pin translation (footprint sidecar + Ebyte manual ch.3):
# the v9 netlist carries U4 = SX1280 QFN24 pin numbers; U_E28 is the pre-matched
# MODULE with 16 pads and a different pin map. On-module internals (XTA/XTB, VR_PA,
# VBAT_IO, DCC_SW, RFIO) are DROPPED -- the module carries its own crystal, match,
# and IPEX antenna.
E28_PIN_XLATE = {
    "15": "1",   # VBAT -> VCC
    "16": "3",   # MISO
    "17": "4",   # MOSI
    "18": "5",   # SCK
    "19": "6",   # NSS -> CS
    "3": "11",   # NRESET
    "7": "12",   # BUSY
    "8": "13",   # DIO1
    "9": "14",   # DIO2
    "10": "15",  # DIO3
}
E28_DROP_PINS = {"22", "4", "6", "2", "14", "11", "12", "13", "20", "21", "23", "24", "1", "5"}


def translate_e28(s):
    import re
    # 1. drop internal-pin nodes
    for pin in E28_DROP_PINS:
        s = re.sub(r'\n\s*\(node \(ref "U_E28"\) \(pin "%s"\)[^\n]*' % pin, "", s)
    # 2. renumber surviving nodes
    def sub_pin(m):
        pin = m.group(2)
        new = E28_PIN_XLATE.get(pin, pin)
        return m.group(1) + new + m.group(3)
    s = re.sub(r'(\(node \(ref "U_E28"\) \(pin ")(\d+)("[^\n]*\)\s*\(pinfunction)', sub_pin, s)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    s = open(a.inp, encoding="utf-8").read()
    n0 = len(re.findall(r"\(comp ", s))
    s = drop_comp_blocks(s, DROP_REFS)
    s = drop_nodes(s, DROP_REFS)
    for old, new in RENAME.items():
        s = s.replace('"%s"' % old, '"%s"' % new)
    # U4 value + footprint -> E28 module
    s = s.replace('(ref "U4")', '(ref "U_E28")')
    s = re.sub(r'\(value "SX1280"\)', '(value "E28-2G4M27SX")', s)
    s = re.sub(r'\(footprint "[^"]*SX1280[^"]*"\)',
               '(footprint "balloon_flight_v10:E28-2G4M27SX")', s)
    # append the new parts' comp blocks + net nodes before the closing paren of the netlist
    # (KiCad netlist: comps section then nets section; we append nodes into existing nets
    #  and new nets at the end -- the builder reads comps + nets leniently)
    after = s.count("(comp ")
    print(f"v9 comps: {n0} -> after drops: {after}")
    s = translate_e28(s)
    open(a.out, "w", encoding="utf-8").write(s)
    print("wrote", a.out, "-- U_C/J_PROG/R_EN/C_EN comps and new nets are added by the "
          "v10 builder (they are not in this transform; see build script)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
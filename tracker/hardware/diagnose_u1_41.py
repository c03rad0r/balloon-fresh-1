#!/usr/bin/env python3
"""Diagnose U1.41 -- the SX1280 exposed ground pad with no net.

CONFIRMED SYMPTOM: the stitcher lists `U1.41` TWELVE times among pads it could not connect to a GND
plane, and the netlist gate reports an "empty footprint" condition. The pad exists on the board but
carries no net, so it is not tied to ground.

TWO COMPETING HYPOTHESES, and the fix differs completely:
  (H1) PAD-NUMBER MISMATCH. The footprint may declare an exposed pad as, say, `25` while the SYMBOL
       calls the same physical pad `41`. KiCad connects by pad NUMBER, so a name disagreement leaves the
       pad isolated even though both files describe the same copper. Fix = one side's number.
  (H2) THE SYMBOL PAD IS NOT CONNECTED TO GND EITHER. If the symbol's pad 41 has no net because the
       SCHEMATIC never tied it (a drawing omission, not a numbering one), then changing a footprint
       number does nothing and the schematic needs the wire. Fix = schematic.

This script decides between them by reading BOTH sides: the footprint file's pad numbers, and the
netlist component's pin list. It does not guess.

Run: diagnose_u1_41.py
"""
import re
import sys

import pcbnew

BOARD = "tracker/hardware/hub_board_v9.kicad_pcb"
NET = "tracker/hardware/schematics/flight_board/v9_flight.net"
FPMOD = ("tracker/hardware/schematics/flight_board/v9_lib/balloon_flight_v9.pretty/"
         "SX1280_QFN24.kicad_mod")


def main():
    print("=" * 80)
    print("U1.41 -- the SX1280 exposed ground pad with no net")
    print("=" * 80)

    # --- side 1: the board. which pads does U1 actually have, and what nets?
    b = pcbnew.LoadBoard(BOARD)
    fp = b.FindFootprintByReference("U1")
    if fp is None:
        print("U1 absent from the board")
        return 1
    print(f"\n--- BOARD: U1 = {fp.GetValue()} ({fp.GetFPID().GetLibItemName()}) ---")
    pads = sorted(fp.Pads(), key=lambda p: int(p.GetNumber()) if p.GetNumber().isdigit() else 9999)
    bynet = {}
    for p in pads:
        nm = p.GetNetname() or "(no net)"
        bynet.setdefault(nm, []).append(p.GetNumber())
    print(f"  pad numbers, in order: {[p.GetNumber() for p in pads]}")
    for nm, nums in sorted(bynet.items()):
        print(f"    {nm:20} pads {nums}")
    gnd = bynet.get("GND", [])
    print(f"  GND pads: {len(gnd)} -> {gnd}")
    weird = [n for n in (p.GetNumber() for p in pads) if not n.isdigit()]
    print(f"  non-numeric pad numbers: {weird if weird else 'none'}")

    # --- side 2: the footprint file. what numbers does it declare?
    print(f"\n--- FOOTPRINT FILE: {FPMOD.split('/')[-1]} ---")
    try:
        txt = open(FPMOD, encoding="utf-8", errors="replace").read()
    except Exception as e:
        print(f"  could not read: {e}")
        txt = ""
    fp_pads = re.findall(r'\(pad\s+"([^"]+)"', txt)
    print(f"  {len(fp_pads)} pad declarations: {fp_pads}")
    fp_gnd = re.findall(r'\(pad\s+"([^"]+)"[^)]*?\(net\s+\d+\s+"?GND"?', txt, re.S)
    print(f"  declared GND in the footprint: {fp_gnd if fp_gnd else 'none (normal: nets come from the board)'}")

    # --- side 3: the netlist / schematic. does the symbol expose a 41, and is it on GND?
    print(f"\n--- NETLIST: {NET.split('/')[-1]} ---")
    try:
        ntxt = open(NET, encoding="utf-8", errors="replace").read()
    except Exception as e:
        print(f"  could not read: {e}")
        ntxt = ""
    m = re.search(r'\(comp\s+\(ref\s+"U1"\).*?(?=\n    \(comp |\Z)', ntxt, re.S)
    if m:
        block = m.group(0)
        val = re.search(r'\(value\s+"([^"]*)"', block)
        fpname = re.search(r'\(footprint\s+"([^"]*)"', block)
        print(f"  U1 value={val.group(1) if val else '?'}  footprint={fpname.group(1) if fpname else '?'}")
        pins = re.findall(r'\(pin\s+"([^"]+)"', block)
        print(f"  {len(pins)} pins declared: {pins}")
        if "41" in pins:
            print("  -> the SYMBOL DOES declare pin 41")
        else:
            print("  -> the SYMBOL does NOT declare pin 41")
    else:
        print("  U1 not found in the netlist")

    # --- which hypothesis is supported
    print("\n" + "=" * 80)
    print("VERDICT")
    print("=" * 80)
    board_has_41 = any(p.GetNumber() == "41" for p in pads)
    board_has_25 = any(p.GetNumber() == "25" for p in pads)
    mod_has_41 = "41" in fp_pads
    mod_has_25 = "25" in fp_pads
    sym_has_41 = bool(m and "41" in re.findall(r'\(pin\s+"([^"]+)"', m.group(0)))
    print(f"  board  U1 pads include 41? {board_has_41}   include 25? {board_has_25}")
    print(f"  .kicad_mod declares 41?   {mod_has_41}      declares 25? {mod_has_25}")
    print(f"  netlist symbol declares 41? {sym_has_41}")
    if board_has_41 and not any(p.GetNetname() for p in pads if p.GetNumber() == "41"):
        p41 = [p for p in pads if p.GetNumber() == "41"][0]
        print(f"\n  Pad 41 EXISTS on the board and its net is "
              f"'{p41.GetNetname() or '(empty)'}'")
        print(f"  Pad 41 position: ({pcbnew.ToMM(p41.GetPosition().x):.2f},"
              f" {pcbnew.ToMM(p41.GetPosition().y):.2f}) mm, size "
              f"{pcbnew.ToMM(p41.GetSize().x):.2f}x{pcbnew.ToMM(p41.GetSize().y):.2f}")
    if board_has_25 and board_has_41:
        print("\n  BOTH 25 AND 41 EXIST -> this is H1 (pad-number mismatch): the duplicate pad is the")
        print("  exposed thermal/ground pad, drawn twice under two numbers. One of them must go, or")
        print("  both must carry the same net.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

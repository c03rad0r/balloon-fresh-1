#!/usr/bin/env python3
"""What is ACTUALLY wrong with U1's pad-41 duplicates? Measured, not assumed.

CORRECTS AN EARLIER CLAIM. The session summary said "U1.41 is the SX1280 exposed ground pad and has no
net". Both parts are wrong:
  - U1 is the ESP32-S3-WROOM-1U module. U4 is the SX1280.
  - All twelve pad-41 objects ARE on GND (measured: 15 GND pads incl. twelve '41's).

So the open question is not "is it unconnected" but: are the twelve pad-41 objects COINCIDENT duplicates
(same position, same size) or twelve DISTINCT pads that merely share a number? A number collision on
distinct copper is a real defect (KiCad cannot address them separately and DRC/parity can mis-resolve).
Coincident duplicates are cosmetic redundancy that also confuses the stitcher.

Also: the footprint file declares 1..24 plus '0'. There is no '41' in it, which means the '41's are NOT
from the footprint -- they are on the BOARD instance only. That is the thing to explain.

Run: inspect_u1_pads.py
"""
import sys
from collections import defaultdict

import pcbnew

BOARD = "tracker/hardware/hub_board_v9.kicad_pcb"


def main():
    b = pcbnew.LoadBoard(BOARD)
    fp = b.FindFootprintByReference("U1")
    pads = list(fp.Pads())
    print(f"U1 = {fp.GetValue()}  ({len(pads)} pad objects on the board)")

    # group by pad number, and within a number, by exact geometry
    groups = defaultdict(list)
    for p in pads:
        pos = p.GetPosition()
        siz = p.GetSize()
        groups[p.GetNumber()].append({
            "x": round(pcbnew.ToMM(pos.x), 4),
            "y": round(pcbnew.ToMM(pos.y), 4),
            "w": round(pcbnew.ToMM(siz.x), 4),
            "h": round(pcbnew.ToMM(siz.y), 4),
            "net": p.GetNetname() or "(none)",
            "shape": p.GetShape(),
            "layers": p.GetLayerSet().FmtHex()[:18],
        })

    print(f"\n{len(groups)} distinct pad NUMBERS")
    for num in sorted(groups, key=lambda n: (not n.isdigit(), int(n) if n.isdigit() else 0)):
        g = groups[num]
        if len(g) == 1:
            continue
        # are they geometrically identical?
        sig = {(d["x"], d["y"], d["w"], d["h"], d["net"]) for d in g}
        print(f"\n  pad number '{num}': {len(g)} objects, {len(sig)} distinct (x,y,w,h,net) combos")
        if len(sig) == 1:
            d = g[0]
            print(f"    ALL COINCIDENT: ({d['x']},{d['y']}) {d['w']}x{d['h']} net={d['net']}"
                  f"  -> pure duplicate copper")
        else:
            print(f"    DISTINCT POSITIONS -> a real number collision:")
            for d in sorted(sig):
                print(f"      ({d[0]},{d[1]}) {d[2]}x{d[3]} net={d[4]}")

    # the non-numeric empties the earlier script flagged
    empt = [p for p in pads if p.GetNumber() == ""]
    print(f"\n  pads with an EMPTY number: {len(empt)}")
    for p in empt:
        pos = p.GetPosition()
        s = p.GetSize()
        print(f"    ({pcbnew.ToMM(pos.x):8.3f},{pcbnew.ToMM(pos.y):8.3f}) "
              f"{pcbnew.ToMM(s.x):6.3f}x{pcbnew.ToMM(s.y):6.3f} "
              f"net={p.GetNetname() or '(none)'} shape={p.GetShape()}")

    # does the FOOTPRINT FILE agree?
    import re
    txt = open("tracker/hardware/schematics/flight_board/v9_lib/balloon_flight_v9.pretty/"
               "ESP32-S3-WROOM-1U.kicad_mod", encoding="utf-8", errors="replace").read() \
        if __import__("os").path.exists(
            "tracker/hardware/schematics/flight_board/v9_lib/balloon_flight_v9.pretty/"
            "ESP32-S3-WROOM-1U.kicad_mod") else ""
    if txt:
        fpn = re.findall(r'\(pad\s+"([^"]*)"', txt)
        print(f"\n  footprint FILE pad numbers: {fpn}")
    else:
        print("\n  footprint file for ESP32-S3-WROOM-1U not found at the expected path")

    print("\n" + "=" * 76)
    print("READING")
    print("=" * 76)
    dup41 = groups.get("41", [])
    sig41 = {(d["x"], d["y"], d["w"], d["h"], d["net"]) for d in dup41}
    if len(dup41) > 1 and len(sig41) == 1:
        print(f"  U1 has {len(dup41)} IDENTICAL pad-'41' objects at one position, all on "
              f"{dup41[0]['net']}.")
        print("  -> NOT an electrical defect. The copper is correct and grounded.")
        print("  -> It IS a modelling defect: 12 coincident pad objects where one would do, which")
        print("     (a) makes the stitcher report the same pad 12 times as UNRESOLVABLE, and")
        print("     (b) can mislead any tool that counts pads or enumerates connections.")
        print("  -> The fix is to de-duplicate to ONE pad-'41' object, not to add a net.")
    elif len(sig41) > 1:
        print(f"  U1 has {len(dup41)} pad-'41' objects at {len(sig41)} DISTINCT positions.")
        print("  -> real number collision; each needs its own number.")
    else:
        print("  pad 41 count is 1 or 0; nothing to de-duplicate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

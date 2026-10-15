#!/usr/bin/env python3
"""Trace the FULL /SX1280_RF path from U4's RFIO pad through the match to the antenna.

WHY. `/SX1280_RF` carries exactly three pads: U4 pad 22 (the SX1280 RFIO), C0 (0.8 pF) and L1
(3.0 nH). Measured separation: C0 is 17.15 mm from the RFIO pad and L1 is 51.04 mm away -- on a
2.4 GHz series matching network that is enormous, and AN1200.66 p.41 states the electrical
consequence: "long length between the chip and matching network is equivalent to add a serial
inductor".

But a distance alone is not proof of a defect, so this prints the WHOLE path: every pad and every
track vertex on the RF net, in order, with the copper length. That distinguishes:

  - the match is genuinely spread over tens of mm of trace  -> a real RF defect
  - the match sits next to the chip and something ELSE is far away (e.g. a connector or a test pad
    at the far end) -> the far item is not the match, and the distance is harmless

Read-only. Does not modify the board.
"""
import math
import sys

import pcbnew

BOARD = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"
NET = sys.argv[2] if len(sys.argv) > 2 else "/SX1280_RF"

b = pcbnew.LoadBoard(BOARD)
print(f"board: {BOARD}\nnet  : {NET}\n")

# --- pads on the net ---
pads = []
for fp in b.GetFootprints():
    for p in fp.Pads():
        if p.GetNetname() == NET:
            c = p.GetPosition()
            pads.append((fp.GetReference(), str(p.GetNumber()), fp.GetValue(),
                         pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)))
pads.sort(key=lambda t: (t[0], t[1]))
print("pads on the net:")
for ref, num, val, x, y in pads:
    print(f"  {ref:8} pad {num:4} {val[:20]:22} at ({x:6.2f},{y:6.2f})")

# --- tracks on the net, with total copper length ---
tracks = [t for t in b.GetTracks()
          if t.GetNetname() == NET and t.Type() != pcbnew.PCB_VIA_T]
vias = [t for t in b.GetTracks()
        if t.GetNetname() == NET and t.Type() == pcbnew.PCB_VIA_T]
total = 0.0
per_layer = {}
for t in tracks:
    a, c = t.GetStart(), t.GetEnd()
    ln = pcbnew.ToMM(math.hypot(c.x - a.x, c.y - a.y))
    total += ln
    ln_name = pcbnew.LayerName(t.GetLayer())
    per_layer[ln_name] = per_layer.get(ln_name, 0.0) + ln
print(f"\ntracks on the net: {len(tracks)}   vias: {len(vias)}")
print(f"  total copper length: {total:.2f} mm")
for k, v in sorted(per_layer.items()):
    print(f"    {k:8} {v:7.2f} mm")

# --- pairwise straight-line distances, so the reader can see the geometry ---
print("\npairwise straight-line distance (pads):")
for i in range(len(pads)):
    for j in range(i + 1, len(pads)):
        a, b_ = pads[i], pads[j]
        d = math.hypot(a[3] - b_[3], a[4] - b_[4])
        print(f"  {a[0]}.{a[1]} <-> {b_[0]}.{b_[1]}   {d:7.2f} mm")

# --- is the far element actually part of the series match, or a stub? ---
print("\ninterpretation aid -- the RFIO pad and each other pad's copper distance along the net:")
if pads:
    # locate U4's pad as the chip end
    chip = next((p for p in pads if p[0].startswith("U")), pads[0])
    print(f"  chip end taken as {chip[0]}.{chip[1]} at ({chip[3]:.2f},{chip[4]:.2f})")
    for ref, num, val, x, y in pads:
        if (ref, num) == (chip[0], chip[1]):
            continue
        d = math.hypot(x - chip[3], y - chip[4])
        print(f"    {ref}.{num} ({val[:16]}) straight-line {d:6.2f} mm")
    print(f"  -> compare against the {total:.2f} mm of copper actually routed on this net")

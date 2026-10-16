#!/usr/bin/env python3
"""Print the exact geometry of the J_W* edge-interface pads, for the JLCPCB drawing."""
import sys

import pcbnew

for ref in ("J_W1", "J_W3"):
    fp = pcbnew.LoadBoard("tracker/hardware/hub_board_v9.kicad_pcb").FindFootprintByReference(ref)
    print(f"--- {ref} ({fp.GetValue()}) ---")
    for p in sorted(fp.Pads(), key=lambda q: str(q.GetNumber())):
        c = p.GetPosition()
        s = p.GetSize()
        d = p.GetDrillSize()
        print(f"  pad {p.GetNumber():4} {p.GetNetname():16} "
              f"pad {pcbnew.ToMM(s.x):.2f}x{pcbnew.ToMM(s.y):.2f} mm  "
              f"drill {pcbnew.ToMM(d.x):.2f}  "
              f"at ({pcbnew.ToMM(c.x):6.2f},{pcbnew.ToMM(c.y):6.2f})  "
              f"layer {pcbnew.LayerName(p.GetLayer())}")

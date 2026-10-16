#!/usr/bin/env python3
"""Restore U4's net bindings that were LOST when the footprint was rebuilt, keeping the EP fix.

WHAT WENT WRONG. Renumbering the exposed pad required rebuilding U4 from the corrected library
footprint. `pcbnew.FootprintLoad` returns a footprint with pad NUMBERS and GEOMETRY but no nets, so
after re-adding it to the board all 24 perimeter pads had an empty net. The renumber gate caught this
as "24 empty-net pads" -- exactly the class of over-reach the gate existed to stop. Evaluation order
mattered: rebuilding first and net-binding second is the wrong order.

THE FIX. Copy the net assignment for every pad from the PRE-EDIT board by PAD NUMBER, and take the
exposed pad's net from the netlist (which says GND). This is a net-binding-only change:

  - pad geometry and numbering come from the corrected library footprint (the EP is now '0')
  - pad NETS come from the pre-edit board for the 24 perimeter pads
  - the EP ('0') takes GND, which is what the netlist states: GND U4 pins include '0'

It deliberately does NOT touch any pad that is genuinely unconnected in the netlist.

Usage: restore_u4_nets.py <pre_edit.kicad_pcb> <current.kicad_pcb> <out.kicad_pcb>
"""
import sys

import pcbnew

EP_OLD, EP_NEW, EP_NET = "25", "0", "GND"


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    pre_path, cur_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

    pre = pcbnew.LoadBoard(pre_path)
    cur = pcbnew.LoadBoard(cur_path)

    pre_fp = pre.FindFootprintByReference("U4")
    cur_fp = cur.FindFootprintByReference("U4")
    if pre_fp is None or cur_fp is None:
        print("U4 missing from one of the boards")
        return 1

    # netcode lookup on the CURRENT board (netcodes can differ between files)
    def code_for(name):
        for c in range(1, cur.GetNetCount()):
            n = cur.FindNet(c)
            if n and n.GetNetname() == name:
                return c
        return 0

    pre_nets = {str(p.GetNumber()): p.GetNetname() for p in pre_fp.Pads()}
    print(f"pre-edit U4 pads: {len(pre_nets)}   "
          f"empty: {sum(1 for v in pre_nets.values() if not v)}")
    print(f"  EP was '{EP_OLD}' with net {pre_nets.get(EP_OLD)!r} -> becomes '{EP_NEW}' with {EP_NET}\n")

    restored = 0
    ep_done = False
    for p in cur_fp.Pads():
        num = str(p.GetNumber())
        if num == EP_NEW:
            p.SetNet(cur.FindNet(code_for(EP_NET)))
            ep_done = True
            print(f"  EP  pad '{num}' -> {EP_NET}")
            continue
        want = pre_nets.get(num)
        if want:
            p.SetNet(cur.FindNet(code_for(want)))
            restored += 1
    print(f"\n  perimeter pads rebound: {restored}")
    print(f"  EP rebound:             {ep_done}")

    # report what is still empty, and say plainly that NC pins are expected
    still = [(str(p.GetNumber()), p.GetNetname()) for p in cur_fp.Pads() if not p.GetNetname()]
    print(f"\n  U4 pads still with no net: {len(still)} -> {[n for n, _v in still]}")

    pcbnew.SaveBoard(out_path, cur)
    print(f"\nwrote {out_path}")
    return 0 if ep_done else 1


if __name__ == "__main__":
    sys.exit(main())

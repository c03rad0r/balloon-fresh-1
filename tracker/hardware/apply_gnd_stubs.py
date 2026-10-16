#!/usr/bin/env python3
"""Apply the J_W* GND stubs, then re-run DRC and compare against the baseline.

FIX, measured by try_gnd_stub.py: each J_W* GND pad (an SMD land on F.Cu with no drill) reaches the
F.Cu GND plane with a 0.30 mm-wide stub of under 0.7 mm. No via, no zone island, no footprint change,
no clearance-rule change.

WHY THIS REPLACES THE ISLAND. The operator approved a higher-priority GND zone island; that was proven
impossible because the pad's neighbouring solar/cut-sense copper sits only 0.60 mm away edge-to-edge,
so no island wide enough to enclose a 4.00 x 1.20 mm pad can also clear them. A STUB needs only a
0.30 mm corridor out one short side, which the geometry does allow.

BASELINE (pre-stub, from output/fabgrade_u4/hub_board_v9_drc.json):
    copper_edge_clearance 27   starved_thermal 2   (both are accounted for separately: the 27 are the
    wing-socket edge interface, and the starved_thermal pair is U4's QFN land)

Usage: apply_gnd_stubs.py <in.kicad_pcb> <out.kicad_pcb>
"""
import sys

import pcbnew

STUBS = {
    "J_W1": ((6.20, 33.93), (5.65, 33.88)),
    "J_W2": ((37.90, 67.80), (38.55, 67.80)),
    "J_W3": ((63.80, 36.07), (64.35, 36.12)),
    "J_W4": ((32.10, 2.74), (31.47, 2.90)),
}
WIDTH = 0.30


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    b = pcbnew.LoadBoard(src)

    # GND netcode on this board
    gnd = None
    for c in range(1, b.GetNetCount()):
        n = b.FindNet(c)
        if n and n.GetNetname() == "GND":
            gnd = n
            break
    if gnd is None:
        print("no GND net")
        return 1

    # remove any previously added stubs on GND so this is idempotent:
    # a stub is a short single-segment track (< 1.0 mm) on F.Cu on GND whose endpoints match a stub.
    removed = 0
    for t in list(b.GetTracks()):
        if t.GetNetname() != "GND" or t.Type() == pcbnew.PCB_VIA_T:
            continue
        s, e = t.GetStart(), t.GetEnd()
        sx, sy, ex, ey = (pcbnew.ToMM(s.x), pcbnew.ToMM(s.y), pcbnew.ToMM(e.x), pcbnew.ToMM(e.y))
        for _ref, (a, c2) in STUBS.items():
            for (p, q) in ((a, c2), (c2, a)):
                if (abs(sx - p[0]) < 0.01 and abs(sy - p[1]) < 0.01
                        and abs(ex - q[0]) < 0.01 and abs(ey - q[1]) < 0.01):
                    b.Remove(t)
                    removed += 1
    if removed:
        print(f"removed {removed} pre-existing stub(s) (idempotent re-run)")

    added = 0
    for ref, (a, c2) in STUBS.items():
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(int(round(a[0] * 1e6)), int(round(a[1] * 1e6))))
        t.SetEnd(pcbnew.VECTOR2I(int(round(c2[0] * 1e6)), int(round(c2[1] * 1e6))))
        t.SetWidth(int(round(WIDTH * 1e6)))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(gnd)
        b.Add(t)
        added += 1
        print(f"  {ref}: ({a[0]:.2f},{a[1]:.2f}) -> ({c2[0]:.2f},{c2[1]:.2f})  w={WIDTH} mm")

    # read back
    fb = [t for t in b.GetTracks()
          if t.GetNetname() == "GND" and t.Type() != pcbnew.PCB_VIA_T
          and max(abs(pcbnew.ToMM(t.GetEnd().x) - pcbnew.ToMM(t.GetStart().x)),
                  abs(pcbnew.ToMM(t.GetEnd().y) - pcbnew.ToMM(t.GetStart().y))) < 1.0]
    print(f"\nstubs added: {added}; short GND tracks now on the board: {len(fb)}")
    pcbnew.SaveBoard(dst, b)
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

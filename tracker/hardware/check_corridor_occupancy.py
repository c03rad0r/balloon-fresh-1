#!/usr/bin/env python3
"""Is /W3_SOLAR_N routing THROUGH the U4/U1 radio corridor, boxing in U4's east pads?

DIAGNOSIS SO FAR (diagnose_failed_nets.py, on the routed board):
    U4.17 (/SX1280_MOSI)  1/24 escape directions, best 1.05 mm
    U4.18 (/SX1280_SCK)   0/24 escape directions -- BOXED IN
    U1.8 and U1.22 have 3-8 legal directions and up to 6 mm of travel
Blockers named at U4's east side include a TRACK on /W3_SOLAR_N -- a WING SOLAR net. A wing solar net
running through the radio's escape corridor would be a placement/routing-order problem of the kind that
cannot be fixed by re-running the router: the corridor is occupied by a net that has nothing to do with
the radio.

This script measures, from the board itself:
  1. where /W3_SOLAR_N's copper actually runs
  2. whether it passes within the U4<->U1 gap
  3. how much of the corridor it consumes

If a wing net is crossing the radio corridor, the fix is to change the ROUTING ORDER or the net's
allowed path, not to move U4 -- and that distinction decides which change to authorise.

Read-only.

Usage: check_corridor_occupancy.py <routed_board.kicad_pcb>
"""
import math
import sys

import pcbnew

CORRIDOR_SUSPECTS = ("/W3_SOLAR_N", "/W2_SOLAR_N", "/W1_SOLAR_N", "/W4_SOLAR_N",
                     "/CUT_SENSE_W1", "/CUT_SENSE_W2", "/CUT_SENSE_W3", "/CUT_SENSE_W4")


def mm(v):
    return pcbnew.ToMM(v)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        print(__doc__)
        return 2
    b = pcbnew.LoadBoard(path)
    print(f"board: {path}\n")

    # the U4/U1 corridor: between U4's top and U1's bottom, in x where they overlap
    u1 = b.FindFootprintByReference("U1").GetBoundingBox(False, False)
    u4 = b.FindFootprintByReference("U4").GetBoundingBox(False, False)
    cx0 = max(mm(u1.GetLeft()), mm(u4.GetLeft()))
    cx1 = min(mm(u1.GetRight()), mm(u4.GetRight()))
    cy0 = mm(u4.GetTop()) - 1.0
    cy1 = mm(u1.GetBottom()) + 1.0
    print(f"U1 bbox y {mm(u1.GetTop()):.2f}..{mm(u1.GetBottom()):.2f}  "
          f"x {mm(u1.GetLeft()):.2f}..{mm(u1.GetRight()):.2f}")
    print(f"U4 bbox y {mm(u4.GetTop()):.2f}..{mm(u4.GetBottom()):.2f}  "
          f"x {mm(u4.GetLeft()):.2f}..{mm(u4.GetRight()):.2f}")
    print(f"corridor tested: x {cx0:.2f}..{cx1:.2f}  y {cy0:.2f}..{cy1:.2f}\n")

    counts = {}
    samples = {}
    for t in b.GetTracks():
        net = t.GetNetname()
        a, c = t.GetStart(), t.GetEnd()
        ax, ay, bx, by = mm(a.x), mm(a.y), mm(c.x), mm(c.y)
        # does any point of this segment fall inside the corridor?
        inside = 0
        n = 24
        for i in range(n + 1):
            px = ax + (bx - ax) * i / n
            py = ay + (by - ay) * i / n
            if cx0 <= px <= cx1 and cy0 <= py <= cy1:
                inside += 1
        if inside:
            counts[net] = counts.get(net, 0) + inside
            samples.setdefault(net, []).append(
                (round(ax, 2), round(ay, 2), round(bx, 2), round(by, 2),
                 pcbnew.LayerName(t.GetLayer())))

    print("nets with copper inside the corridor (sample points, by net):")
    for net, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        tag = "   <-- WING/SOLAR NET" if net in CORRIDOR_SUSPECTS else ""
        print(f"  {net:22} {n:4d} samples{tag}")
    print()
    for net in sorted(samples):
        if net in CORRIDOR_SUSPECTS:
            print(f"  {net} segments in the corridor:")
            for s in samples[net][:6]:
                print(f"    ({s[0]},{s[1]}) -> ({s[2]},{s[3]})  {s[4]}")
    print()
    wing = [n for n in counts if n in CORRIDOR_SUSPECTS]
    if wing:
        print(f"FINDING: {len(wing)} wing/solar net(s) occupy the radio corridor: {wing}")
        print("A wing net crossing the U4/U1 escape corridor is not a router failure -- the corridor is")
        print("occupied by copper that has no business there. The fix is a net SCOPE/ORDER change or a")
        print("placement change for those nets, not another router pass.")
    else:
        print("FINDING: no wing/solar net inside the corridor. The crowding is between radio-adjacent")
        print("nets themselves, so the fix is placement or layer strategy rather than net scoping.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

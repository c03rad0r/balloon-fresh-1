"""Print the EXACT hand-routing worksheet: every net to route, its endpoints, and what blocks it.

Written because the operator is going to do this in the KiCad GUI and needs coordinates, not prose. Every
number here comes from pcbnew on the canonical board, not from a previous report.
"""

import pcbnew

BOARD = "tracker/hardware/hub_board_v10.kicad_pcb"  # v10 is the live board (was v9)
UM = 1_000_000.0  # KiCad internal units per mm


def mm(v) -> float:
    return v / UM


def main() -> int:
    b = pcbnew.LoadBoard(BOARD)
    print(f"board: {BOARD}")
    print(f"  size: {b.GetBoardEdgesBoundingBox().GetWidth()/UM:.2f} x "
          f"{b.GetBoardEdgesBoundingBox().GetHeight()/UM:.2f} mm")

    # 1. Which nets are unrouted? A net is unrouted if it has pads on 2+ distinct positions with no
    #    track connecting them. pcbnew has a proper API: GetConnectivity()->GetUnconnectedCount() but it
    #    needs a build step; instead report per-net track counts and pad counts, and flag nets with pads
    #    but no tracks.
    nets = b.GetNetsByNetcode()
    print("\n=== NETS WITH PADS BUT NO COPPER (candidates for hand-routing) ===")
    work = []
    for code, net in sorted(nets.items()):
        name = net.GetNetname()
        if not name:
            continue
        pads = [p for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetCode() == code]
        tracks = [t for t in b.GetTracks() if t.GetNetCode() == code
                  and t.Type() == pcbnew.PCB_TRACE_T]
        if len(pads) >= 2 and not tracks:
            work.append((name, pads))
            print(f"  {name}: {len(pads)} pad(s), 0 tracks")

    if not work:
        print("  (none)")

    # 2. For each, print pad refdes.pin and absolute position in mm.
    for name, pads in work:
        print(f"\n=== {name} ===")
        pts = []
        for p in pads:
            pos = p.GetPosition()
            x, y = mm(pos.x), mm(pos.y)
            pts.append((x, y))
            # p.GetParent() returns a BOARD_ITEM_CONTAINER, not the FOOTPRINT. Use GetParentFootprint().
            fp = p.GetParentFootprint()
            ref = fp.GetReference() if fp else "?"
            print(f"  {ref}.{str(p.GetNumber()):<3} "
                  f"({x:7.2f}, {y:7.2f})  net {p.GetNetname()}")
        if len(pts) == 2:
            (x1, y1), (x2, y2) = pts
            d = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
            print(f"  -> straight-line distance: {d:.2f} mm")

    # 3. Wing socket pads: which have copper attached (these break if the footprints move).
    print("\n=== J_W* WING-SOCKET PADS WITH COPPER ATTACHED ===")
    wing = {}
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if not ref.startswith("J_W"):
            continue
        for p in fp.Pads():
            if not p.GetNetname():
                continue
            wing[(ref, p.GetNumber())] = (p.GetPosition(), p.GetNetname())

    hits = 0
    for (ref, num), (pos, net) in sorted(wing.items()):
        touch = []
        for t in b.GetTracks():
            if t.Type() != pcbnew.PCB_TRACE_T:
                continue
            for pt, label in ((t.GetStart(), "start"), (t.GetEnd(), "end")):
                if abs(pt.x - pos.x) <= 1000 and abs(pt.y - pos.y) <= 1000:
                    touch.append(f"{label} of track on {t.GetNetname()}")
                    break
            if touch:
                break
        if touch:
            hits += 1
            x, y = mm(pos.x), mm(pos.y)
            print(f"  {ref}.{num:<3} ({x:7.2f}, {y:7.2f})  {net:<18} <- {touch[0]}")
    if not hits:
        print("  (none)")
    else:
        print(f"\n  {hits} pad(s) would need re-routing if the J_W* footprints move.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

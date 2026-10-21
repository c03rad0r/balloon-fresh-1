import pcbnew, math
b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
UM = 1e6
tracks = [t for t in b.GetTracks() if "TRACK" in str(type(t)) and "VIA" not in str(type(t))]
# find tracks whose BOTH endpoints touch pads of the same footprint ref (the "same chip" case)
pads = []
for fp in b.GetFootprints():
    for p in fp.Pads():
        n = p.GetNet()
        pos = p.GetPosition()
        pads.append((fp.GetReference(), p.GetNumber(), n.GetNetname() if n else "", pos.x/UM, pos.y/UM))
print("MARK === same-footprint track endpoints ===")
for t in tracks:
    n = t.GetNet(); name = n.GetNetname() if n else "?"
    s, e = t.GetStart(), t.GetEnd()
    ends = []
    for (px, py) in ((s.x/UM, s.y/UM), (e.x/UM, e.y/UM)):
        best = min(pads, key=lambda q: math.hypot(px-q[3], py-q[4]))
        d = math.hypot(px-best[3], py-best[4])
        ends.append((best[0], best[1], best[2], d))
    a, c = ends
    if a[0] == c[0]:
        print(f"MARK {name}: both ends on {a[0]} -> pad {a[1]} ({a[2]}) and pad {c[1]} ({c[2]})")
    else:
        print(f"MARK {name}: {a[0]}.{a[1]}({a[2]}) -> {c[0]}.{c[1]}({c[2]})")
print("MARK === endpoint distances (how close each end is to its nearest pad) ===")
for t in tracks:
    n = t.GetNet(); name = n.GetNetname() if n else "?"
    s, e = t.GetStart(), t.GetEnd()
    for lbl, (px, py) in (("start", (s.x/UM, s.y/UM)), ("end", (e.x/UM, e.y/UM))):
        best = min(pads, key=lambda q: math.hypot(px-q[3], py-q[4]))
        d = math.hypot(px-best[3], py-best[4])
        flag = "  <-- DEAD END (no pad within 0.2mm)" if d > 0.2 else ""
        print(f"MARK {name} {lbl} ({px:.2f},{py:.2f}) nearest {best[0]}.{best[1]} d={d:.3f}{flag}")

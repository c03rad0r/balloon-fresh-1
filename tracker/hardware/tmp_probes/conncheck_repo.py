import pcbnew
b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
tracks = [t for t in b.GetTracks() if 'TRACK' in str(type(t))]
print("MARK tracks:", len(tracks))
by_net = {}
for t in tracks:
    n = t.GetNet()
    by_net.setdefault(n.GetNetname() if n else "?", []).append(t)
for name, ts in sorted(by_net.items()):
    pads = [p for fp in b.GetFootprints() for p in fp.Pads()
            if p.GetNet() and p.GetNet().GetNetname() == name]
    ok = 0
    for p in pads:
        pos = p.GetPosition()
        for t in ts:
            x0,y0 = t.GetStart().x, t.GetStart().y
            x1,y1 = t.GetEnd().x, t.GetEnd().y
            dx,dy = x1-x0, y1-y0
            L2 = dx*dx+dy*dy
            if L2 == 0: continue
            tt = max(0.0, min(1.0, ((pos.x-x0)*dx + (pos.y-y0)*dy)/L2))
            px,py = x0+tt*dx, y0+tt*dy
            if ((pos.x-px)**2 + (pos.y-py)**2) ** 0.5 < 800000:
                ok += 1
                break
    print(f"MARK {name}: {ok}/{len(pads)} pads touched")

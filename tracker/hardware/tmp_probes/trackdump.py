import pcbnew, math
b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
UM = 1e6
tracks = [t for t in b.GetTracks() if "TRACK" in str(type(t)) and "VIA" not in str(type(t))]
pads = []
for fp in b.GetFootprints():
    for p in fp.Pads():
        n = p.GetNet()
        pos = p.GetPosition()
        pads.append((fp.GetReference(), p.GetNumber(), n.GetNetname() if n else "",
                     pos.x/UM, pos.y/UM, p.GetSize().x/UM, p.GetSize().y/UM))
print("MARK ===== TRACK DUMP =====")
for i, t in enumerate(tracks):
    n = t.GetNet()
    name = n.GetNetname() if n else "?"
    s, e = t.GetStart(), t.GetEnd()
    x0,y0,x1,y1 = s.x/UM, s.y/UM, e.x/UM, e.y/UM
    print(f"MARK [{i}] {name}: ({x0:.2f},{y0:.2f}) -> ({x1:.2f},{y1:.2f}) len={math.hypot(x1-x0,y1-y0):.2f}mm")
    for label, (px, py) in (("start", (x0,y0)), ("end", (x1,y1))):
        near = []
        for ref, num, nm, qx, qy, w, h in pads:
            d = math.hypot(px-qx, py-qy)
            if d < 1.6:
                near.append(f"{ref}.{num}[{nm or 'NC'}] d={d:.2f}")
        print(f"MARK     {label} touches: {', '.join(near) if near else 'NOTHING WITHIN 1.6mm'}")

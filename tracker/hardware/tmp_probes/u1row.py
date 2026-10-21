import pcbnew
b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
u1 = b.FindFootprintByReference("U1")
for p in sorted(u1.Pads(), key=lambda q: q.GetPosition().x):
    pos = p.GetPosition()
    if abs(pos.y/1e6 - 51.65) < 0.01:
        n = p.GetNet()
        print("MARK U1.%s at %.2f,%.2f net=%s" % (p.GetNumber(), pos.x/1e6, pos.y/1e6, n.GetNetname() if n else "NC"))

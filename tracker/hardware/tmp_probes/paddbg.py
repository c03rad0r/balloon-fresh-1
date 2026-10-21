import pcbnew
b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
for fp in b.GetFootprints():
    for p in fp.Pads():
        n = p.GetNet()
        if n and n.GetNetname() == "/CUT_SENSE_W1":
            pos = p.GetPosition()
            print("CUT_W1 pad:", fp.GetReference(), p.GetNumber(), pos.x/1e6, pos.y/1e6)
        if n and n.GetNetname() == "/W1_SOLAR_P":
            pos = p.GetPosition()
            print("W1_SOL_P pad:", fp.GetReference(), p.GetNumber(), pos.x/1e6, pos.y/1e6)

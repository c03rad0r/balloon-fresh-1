import pcbnew
b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
for t in b.GetTracks():
    if "TRACK" in str(type(t)):
        n = t.GetNet()
        print("TRACK net:", n.GetNetname() if n else None, "code:", n.GetNetCode() if n else None,
              "layer:", t.GetLayer(), "w:", t.GetWidth())

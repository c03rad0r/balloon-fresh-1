import pcbnew
b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
dead = 0
for t in list(b.GetTracks()):
    if "TRACK" in str(type(t)):
        s, e = t.GetStart(), t.GetEnd()
        if s.x == e.x and s.y == e.y:
            b.Remove(t)
            dead += 1
print("zero-length tracks removed:", dead)
pcbnew.SaveBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb", b)

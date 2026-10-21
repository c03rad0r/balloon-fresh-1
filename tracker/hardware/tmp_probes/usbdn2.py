import pcbnew
b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
print("MARK F_Cu=%d B_Cu=%d" % (pcbnew.F_Cu, pcbnew.B_Cu))
for t in b.GetTracks():
    if "TRACK" not in str(type(t)): continue
    n = t.GetNet()
    if n and n.GetNetname() == "/USB_DN":
        e = t.GetEnd()
        print("MARK USB_DN seg layer=%s end=(%.2f,%.2f) via=%s" % (t.GetLayer(), e.x/1e6, e.y/1e6, "VIA" in str(type(t))))

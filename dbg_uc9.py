import pcbnew
b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/poison_uc9.kicad_pcb")
uc = b.FindFootprintByReference("U_C")
print("MARK U_C footprint layer:", uc.GetLayer(), "F_Cu=", pcbnew.F_Cu, "B_Cu=", pcbnew.B_Cu)
for p in uc.Pads():
    if p.GetNumber() in ("9","10"):
        n = p.GetNet()
        print("MARK U_C.%s layer=%s attr=%s net=%s size=%.2fx%.2f at %.2f,%.2f" % (
            p.GetNumber(), p.GetLayer(), p.GetAttribute(), n.GetNetname() if n else "NC",
            p.GetSize().x/1e6, p.GetSize().y/1e6, p.GetPosition().x/1e6, p.GetPosition().y/1e6))
for t in b.GetTracks():
    if "TRACK" in str(type(t)):
        print("MARK track layer:", t.GetLayer(), "net:", t.GetNet().GetNetname() if t.GetNet() else None)

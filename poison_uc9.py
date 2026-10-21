import pcbnew, shutil
SRC = "/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb"
POI = "/home/c08r4d0r/worktrees/master-check/poison_uc9.kicad_pcb"
shutil.copy(SRC, POI)
b = pcbnew.LoadBoard(POI)
uc = b.FindFootprintByReference("U_C")
p9 = [p for p in uc.Pads() if p.GetNumber() == "9"][0]
pos = p9.GetPosition()
print("MARK U_C.9 at %.2f,%.2f" % (pos.x/1e6, pos.y/1e6))
net = b.FindNet("/ANT3_2G4_RX")
if net is None:
    b.Add(pcbnew.NETINFO_ITEM(b, "/ANT3_2G4_RX")); net = b.FindNet("/ANT3_2G4_RX")
t = pcbnew.PCB_TRACK(b)
t.SetNet(net); t.SetLayer(pcbnew.B_Cu); t.SetWidth(int(0.2*1e6))
t.SetStart(pcbnew.VECTOR2I(pos.x - int(3e6), pos.y))
t.SetEnd(pcbnew.VECTOR2I(pos.x + int(3e6), pos.y))
b.Add(t)
pcbnew.SaveBoard(POI, b)
print("MARK poison track written over U_C.9")

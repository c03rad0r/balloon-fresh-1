import pcbnew, tempfile, os
UM=1e6
SRC="/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb"
b=pcbnew.LoadBoard(SRC)
n0=len([t for t in b.GetTracks()])
fp=b.FindFootprintByReference("U3")
p=[x for x in fp.Pads() if x.GetNumber()=="3"][0]
print("MARK U3.3 net:", repr(p.GetNetname()), "layer", fp.GetLayerName(), "drill", p.GetDrillSize().x/UM)
c=p.GetPosition()
t=pcbnew.PCB_TRACK(b)
t.SetNetCode(0); t.SetLayer(pcbnew.B_Cu); t.SetWidth(int(0.2*UM))
t.SetStart(pcbnew.VECTOR2I(c.x-int(1.0*UM), c.y)); t.SetEnd(pcbnew.VECTOR2I(c.x+int(1.0*UM), c.y))
b.Add(t)
n1=len([x for x in b.GetTracks()])
print("MARK tracks before/after add:", n0, n1)
d=tempfile.mkdtemp(prefix="dbgpoison"); dst=os.path.join(d,"p.kicad_pcb")
pcbnew.SaveBoard(dst, b)
b2=pcbnew.LoadBoard(dst)
print("MARK reloaded tracks:", len([x for x in b2.GetTracks()]))
for x in b2.GetTracks():
    if "VIA" not in str(type(x)) and x.GetNetCode()==0:
        print("MARK netless track layer", x.GetLayer(), "start", x.GetStart().x/UM, x.GetStart().y/UM)
        break

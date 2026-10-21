import pcbnew, tempfile, os
UM=1e6
SRC="/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb"
b=pcbnew.LoadBoard(SRC)
fp=b.FindFootprintByReference("U3"); p=[x for x in fp.Pads() if x.GetNumber()=="3"][0]
c=p.GetPosition()
t=pcbnew.PCB_TRACK(b)
t.SetNetCode(0); t.SetLayer(pcbnew.B_Cu); t.SetWidth(int(0.2*UM))
t.SetStart(pcbnew.VECTOR2I(c.x-int(1.0*UM), c.y)); t.SetEnd(pcbnew.VECTOR2I(c.x+int(1.0*UM), c.y))
b.Add(t)
d=tempfile.mkdtemp(prefix="dbgpoison2"); dst=os.path.join(d,"p.kicad_pcb")
pcbnew.SaveBoard(dst, b)
b2=pcbnew.LoadBoard(dst)
print("MARK searching near", c.x/UM, c.y/UM)
for x in b2.GetTracks():
    if "TRACK" not in str(type(x)) or "VIA" in str(type(x)): continue
    if abs(x.GetStart().y-c.y) < 1000 and abs(x.GetStart().x-c.x) < 2*UM:
        n=x.GetNet()
        print("MARK found layer",x.GetLayer(),"code",x.GetNetCode(),"name",repr(n.GetNetname() if n else None),
              "start",x.GetStart().x/UM,x.GetStart().y/UM,"end",x.GetEnd().x/UM,x.GetEnd().y/UM)

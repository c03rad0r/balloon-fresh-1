import pcbnew, tempfile, os, subprocess
UM=1e6
SRC="/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb"
GATE="/home/c08r4d0r/worktrees/master-check/tracker/hardware/check_lane_vs_pad_layer.py"
b=pcbnew.LoadBoard(SRC)
gnd=b.FindNet("GND").GetNetCode()
fp=b.FindFootprintByReference("U3"); p=[x for x in fp.Pads() if x.GetNumber()=="3"][0]
c=p.GetPosition()
print("MARK target pad U3.3 net", repr(p.GetNetname()), "layers", [l for l in (0,2) if p.GetLayerSet().Contains(l)], "drill", p.GetDrillSize().x/UM)
t=pcbnew.PCB_TRACK(b); t.SetLayer(pcbnew.B_Cu); t.SetWidth(int(0.2*UM))
t.SetStart(pcbnew.VECTOR2I(c.x-UM, c.y)); t.SetEnd(pcbnew.VECTOR2I(c.x+UM, c.y))
b.Add(t)
t.SetNetCode(gnd)
print("MARK track net after set:", repr(t.GetNetname()))
d=tempfile.mkdtemp(prefix="pz"); dst=os.path.join(d,"p.kicad_pcb")
pcbnew.SaveBoard(dst,b)
b2=pcbnew.LoadBoard(dst)
for x in b2.GetTracks():
    if "TRACK" in str(type(x)) and "VIA" not in str(type(x)) and abs(x.GetStart().x-c.x)<2*UM and abs(x.GetStart().y-c.y)<100:
        print("MARK RELOADED net", repr(x.GetNetname()), "layer", x.GetLayer())
r=subprocess.run(["/home/c08r4d0r/venvs/kicad/bin/python",GATE,"--board",dst],capture_output=True,text=True,timeout=180)
print("MARK gate exit", r.returncode)
for line in (r.stdout or "").splitlines():
    if "SHORT" in line or "HARD" in line or "audited" in line: print("MARK  |", line)

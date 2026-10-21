import pcbnew, tempfile, os, subprocess
UM=1e6
SRC="/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb"
b=pcbnew.LoadBoard(SRC)
# any pad drilled but with copper on only ONE outer layer?
odd=[]
for fp in b.GetFootprints():
    for p in fp.Pads():
        ls=p.GetLayerSet(); n=sum(1 for l in (0,2) if ls.Contains(l))
        if p.GetDrillSize().x>0 and n<2: odd.append((fp.GetReference(),p.GetNumber(),n))
print("MARK drilled single-layer pads:", len(odd), odd[:6])
# P1: track between two different-net pads -> real short
fp=b.FindFootprintByReference("U3")
pa=[x for x in fp.Pads() if x.GetNumber()=="4"][0]; pb=[x for x in fp.Pads() if x.GetNumber()=="3"][0]
ca,cb=pa.GetPosition(),pb.GetPosition()
t=pcbnew.PCB_TRACK(b); t.SetLayer(pcbnew.B_Cu); t.SetWidth(int(0.2*UM))
t.SetStart(pcbnew.VECTOR2I(int(ca.x),int(ca.y))); t.SetEnd(pcbnew.VECTOR2I(int(cb.x),int(cb.y)))
b.Add(t)
d=tempfile.mkdtemp(prefix="pz5"); dst=os.path.join(d,"p.kicad_pcb"); pcbnew.SaveBoard(dst,b)
b2=pcbnew.LoadBoard(dst)
for x in b2.GetTracks():
    if "TRACK" in str(type(x)) and "VIA" not in str(type(x)) and abs(x.GetStart().y-ca.y)<2000 and abs(x.GetEnd().y-cb.y)<2000 and abs(x.GetStart().x-ca.x)<2000:
        print("MARK planted net:", repr(x.GetNetname()))
r=subprocess.run(["/home/c08r4d0r/venvs/kicad/bin/python","/home/c08r4d0r/worktrees/master-check/tracker/hardware/check_lane_vs_pad_layer.py","--board",dst],capture_output=True,text=True,timeout=180)
print("MARK P1 gate exit:", r.returncode)
for line in (r.stdout or "").splitlines():
    if "SHORT" in line or "HARD" in line: print("MARK  |", line)

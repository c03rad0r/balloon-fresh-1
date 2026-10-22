import pcbnew
UM=1e6
b=pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
# J_W2 edge segments
seg=[]
for d in b.GetDrawings():
    if d.GetLayer()==pcbnew.Edge_Cuts:
        seg.append(((d.GetStart().x/UM,d.GetStart().y/UM),(d.GetEnd().x/UM,d.GetEnd().y/UM)))
print("MARK edge segs:",len(seg))
for s in seg: print("MARK  seg (%.2f,%.2f)->(%.2f,%.2f)"%(s[0][0],s[0][1],s[1][0],s[1][1]))
for t in b.GetTracks():
    if "TRACK" in str(type(t)) and (t.GetNetname() or "")=="/E28_BUSY":
        print("MARK busy (%.2f,%.2f)->(%.2f,%.2f)"%(t.GetStart().x/UM,t.GetStart().y/UM,t.GetEnd().x/UM,t.GetEnd().y/UM))

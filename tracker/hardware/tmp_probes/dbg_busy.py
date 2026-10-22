import pcbnew
UM=1e6
b=pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
e=b.FindFootprintByReference("U_E28")
bb=e.GetBoundingBox(False,True)
print("MARK E28 courtyard x %.2f..%.2f y %.2f..%.2f" % (bb.GetX()/UM,(bb.GetX()+bb.GetWidth())/UM,bb.GetY()/UM,(bb.GetY()+bb.GetHeight())/UM))
print("MARK E28 pads:")
for p in e.Pads():
    pb=p.GetBoundingBox()
    print("MARK  pad %-3s x %.2f..%.2f y %.2f..%.2f net %s" % (p.GetNumber(),pb.GetX()/UM,(pb.GetX()+pb.GetWidth())/UM,
          pb.GetY()/UM,(pb.GetY()+pb.GetHeight())/UM, p.GetNetname()))
for t in b.GetTracks():
    if "TRACK" in str(type(t)) and (t.GetNetname() or "")=="/E28_BUSY":
        print("MARK busy track layer %d (%.2f,%.2f)->(%.2f,%.2f)" % (t.GetLayer(),
            t.GetStart().x/UM,t.GetStart().y/UM,t.GetEnd().x/UM,t.GetEnd().y/UM))

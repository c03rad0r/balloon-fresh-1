import pcbnew
UM=1e6
b=pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
a2=b.FindFootprintByReference("ANT2")
print("MARK ANT2 pos", a2.GetPosition().x/UM, a2.GetPosition().y/UM, "rot", a2.GetOrientationDegrees())
for p in a2.Pads():
    pb=p.GetBoundingBox()
    print("MARK  pad %-3s x %.2f..%.2f y %.2f..%.2f  net %r" % (p.GetNumber(),
        pb.GetX()/UM,(pb.GetX()+pb.GetWidth())/UM,pb.GetY()/UM,(pb.GetY()+pb.GetHeight())/UM, p.GetNetname()))
u2=b.FindFootprintByReference("U2")
for p in u2.Pads():
    if p.GetNumber()=="13":
        pb=p.GetBoundingBox()
        print("MARK U2.13 x %.2f..%.2f y %.2f..%.2f net %r" % (pb.GetX()/UM,(pb.GetX()+pb.GetWidth())/UM,
              pb.GetY()/UM,(pb.GetY()+pb.GetHeight())/UM, p.GetNetname()))

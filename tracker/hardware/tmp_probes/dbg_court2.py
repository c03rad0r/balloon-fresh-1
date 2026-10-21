import pcbnew
UM=1e6
b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
# which footprints DECLARE a courtyard?
print("MARK courtyard declarations:")
for fp in b.GetFootprints():
    ref=fp.GetReference()
    if ref.startswith(("H1","H2","H3","H4","HW")): continue
    n=sum(1 for g in fp.GraphicalItems() if g.GetLayer() in (pcbnew.F_CrtYd, pcbnew.B_CrtYd))
    if n: print("MARK   %-8s %d courtyard items" % (ref, n))
# the marginal U2.13 / ANT2.2 case
for ref,num in (("U2","13"),("ANT2","2")):
    fp=b.FindFootprintByReference(ref)
    for p in fp.Pads():
        if p.GetNumber()==num:
            pb=p.GetBoundingBox()
            print("MARK   %s.%s  x %.3f..%.3f  y %.3f..%.3f  (%.2f x %.2f)" % (
                ref,num,pb.GetX()/UM,(pb.GetX()+pb.GetWidth())/UM,
                pb.GetY()/UM,(pb.GetY()+pb.GetHeight())/UM, pb.GetWidth()/UM, pb.GetHeight()/UM))

import pcbnew
UM=1e6
b=pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
u1=b.FindFootprintByReference("U1")
left=[]
for p in u1.Pads():
    bb=p.GetBoundingBox()
    x0,x1=bb.GetX()/UM,(bb.GetX()+bb.GetWidth())/UM
    if x1 < 13.0:   # left column of U1
        left.append((p.GetNumber(), round(x0,2), round(x1,2), round(bb.GetY()/UM,2), round((bb.GetY()+bb.GetHeight())/UM,2), p.GetNetname()))
left.sort(key=lambda t:t[3])
print("MARK U1 LEFT-side pads (x < 13):")
for t in left: print("MARK   pad %-3s x %.2f..%.2f  y %.2f..%.2f  %s" % t)
print("MARK")
for ref in ("J_W1","H2","H3","HW1"):
    fp=b.FindFootprintByReference(ref)
    if not fp: continue
    bb=fp.GetBoundingBox(False,True)
    print("MARK %-5s courtyard x %.2f..%.2f  y %.2f..%.2f" % (ref, bb.GetX()/UM,(bb.GetX()+bb.GetWidth())/UM,
          bb.GetY()/UM,(bb.GetY()+bb.GetHeight())/UM))

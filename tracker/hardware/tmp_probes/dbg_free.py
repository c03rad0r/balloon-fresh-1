import pcbnew
UM=1e6
b=pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
bb=b.GetBoardEdgesBoundingBox()
BX0,BY0,BX1,BY1 = bb.GetX()/UM, bb.GetY()/UM, (bb.GetX()+bb.GetWidth())/UM, (bb.GetY()+bb.GetHeight())/UM
print("MARK board %.1f..%.1f  %.1f..%.1f  (%.1f x %.1f)" % (BX0,BX1,BY0,BY1,BX1-BX0,BY1-BY0))
front=[]; back=[]; holes=[]
for fp in b.GetFootprints():
    ref=fp.GetReference()
    r=fp.GetBoundingBox(False,True)
    rect=(r.GetX()/UM,r.GetY()/UM,(r.GetX()+r.GetWidth())/UM,(r.GetY()+r.GetHeight())/UM)
    if ref.startswith(("H1","H2","H3","H4","HW")) or ref.startswith("J_W"):
        holes.append((ref,rect)); continue
    (front if fp.GetLayerName()=="F.Cu" else back).append((ref,rect))
print("MARK FRONT parts (obstacles for a BACK part via cross-side):")
for r,x in front: print("MARK   %-12s x %6.2f..%6.2f  y %6.2f..%6.2f" % (r,x[0],x[2],x[1],x[3]))
print("MARK BACK parts:")
for r,x in back: print("MARK   %-12s x %6.2f..%6.2f  y %6.2f..%6.2f" % (r,x[0],x[2],x[1],x[3]))
print("MARK holes/seats:")
for r,x in holes: print("MARK   %-12s x %6.2f..%6.2f  y %6.2f..%6.2f" % (r,x[0],x[2],x[1],x[3]))

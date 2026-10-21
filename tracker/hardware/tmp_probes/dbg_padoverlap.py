import pcbnew, math
UM=1e6
b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
pads=[]
for fp in b.GetFootprints():
    ref=fp.GetReference()
    if ref.startswith(("H1","H2","H3","H4","HW")): continue
    lay = "F" if fp.GetLayerName()=="F.Cu" else "B"
    for p in fp.Pads():
        bb=p.GetBoundingBox()
        pads.append((ref, p.GetNumber(), lay,
                     bb.GetX()/UM, bb.GetY()/UM,
                     (bb.GetX()+bb.GetWidth())/UM, (bb.GetY()+bb.GetHeight())/UM))
print("MARK total pads", len(pads))
bad=[]
for i in range(len(pads)):
    for j in range(i+1,len(pads)):
        a=pads[i]; c=pads[j]
        if a[0]==c[0]: continue
        ox = min(a[5],c[5]) - max(a[3],c[3])
        oy = min(a[6],c[6]) - max(a[4],c[4])
        if ox > 0 and oy > 0:
            area = ox*oy
            bad.append((round(area,3), a[0]+"."+str(a[1])+"("+a[2]+")", c[0]+"."+str(c[1])+"("+c[2]+")",
                        round(ox,2), round(oy,2)))
bad.sort(reverse=True)
print("MARK pad-PAD physical overlaps:", len(bad))
for x in bad[:16]: print("MARK  ", x)

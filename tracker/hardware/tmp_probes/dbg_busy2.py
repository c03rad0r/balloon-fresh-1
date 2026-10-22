import pcbnew
UM=1e6
b=pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
e=b.FindFootprintByReference("U_E28")
bb=e.GetBoundingBox(False,True)
R=(bb.GetX()/UM,bb.GetY()/UM,(bb.GetX()+bb.GetWidth())/UM,(bb.GetY()+bb.GetHeight())/UM)
print("MARK courtyard x %.2f..%.2f y %.2f..%.2f" % R)
# pad rows
ys=[(p.GetBoundingBox().GetY()/UM,(p.GetBoundingBox().GetY()+p.GetBoundingBox().GetHeight())/UM) for p in e.Pads()]
print("MARK pad y-range: %.2f..%.2f" % (min(y[0] for y in ys), max(y[1] for y in ys)))
for t in b.GetTracks():
    if "TRACK" not in str(type(t)) or "VIA" in str(type(t)): continue
    if (t.GetNetname() or "")!="/E28_BUSY": continue
    x0,y0=t.GetStart().x/UM,t.GetStart().y/UM; x1,y1=t.GetEnd().x/UM,t.GetEnd().y/UM
    mx,my=(x0+x1)/2,(y0+y1)/2
    inside = R[0]<=mx<=R[2] and R[1]<=my<=R[3]
    if inside:
        print("MARK INSIDE layer %d (%.2f,%.2f)->(%.2f,%.2f) len %.2f" % (t.GetLayer(),x0,y0,x1,y1,
              ((x1-x0)**2+(y1-y0)**2)**0.5))

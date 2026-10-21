import pcbnew, math
UM=1e6
b=pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
e28=b.FindFootprintByReference("U_E28")
e28_bb=e28.GetBoundingBox(False,True)
EW,EH = e28_bb.GetWidth()/UM, e28_bb.GetHeight()/UM
e28_origin=(e28_bb.GetX()/UM, e28_bb.GetY()/UM)
print("MARK E28 courtyard %.2f x %.2f  at %.2f,%.2f" % (EW,EH,e28_origin[0],e28_origin[1]))
# E28 pad offsets relative to its bbox origin
poff=[]
for p in e28.Pads():
    pb=p.GetBoundingBox()
    poff.append((pb.GetX()/UM-e28_origin[0], pb.GetY()/UM-e28_origin[1],
                 (pb.GetX()+pb.GetWidth())/UM-e28_origin[0],
                 (pb.GetY()+pb.GetHeight())/UM-e28_origin[1], p.GetNumber()))
# other parts: courtyards + pads
others=[]; opads=[]
for fp in b.GetFootprints():
    ref=fp.GetReference()
    if ref=="U_E28": continue
    r=fp.GetBoundingBox(False,True)
    others.append((ref, fp.GetLayerName(), (r.GetX()/UM,r.GetY()/UM,(r.GetX()+r.GetWidth())/UM,(r.GetY()+r.GetHeight())/UM)))
    for p in fp.Pads():
        pb=p.GetBoundingBox()
        opads.append((ref,p.GetNumber(),(pb.GetX()/UM,pb.GetY()/UM,(pb.GetX()+pb.GetWidth())/UM,(pb.GetY()+pb.GetHeight())/UM)))
BX0,BY0,BX1,BY1 = -0.1,-0.1,72.0,80.0
def ov(a,c):
    dx=min(a[2],c[2])-max(a[0],c[0]); dy=min(a[3],c[3])-max(a[1],c[1])
    return dx*dy if (dx>0 and dy>0) else 0.0
best=[]
for rot in (0,90):
    W2,H2 = (EW,EH) if rot==0 else (EH,EW)
    x=BX0
    while x+W2<=BX1:
        y=BY0
        while y+H2<=BY1:
            rect=(x,y,x+W2,y+H2)
            padov=0; bad=None
            for (dx0,dy0,dx1,dy1,num) in poff:
                if rot==90:
                    dx0,dy0,dx1,dy1 = dy0, EW-dx1, dy1, EW-dx0
                pr=(x+dx0,y+dy0,x+dx1,y+dy1)
                for (r2,n2,r2rect) in opads:
                    a=ov(pr,r2rect)
                    if a>0: padov+=a; bad=(r2,n2); break
                if bad: break
            if bad: 
                y+=0.5; continue
            cov=0
            for (r2,lay,r2rect) in others:
                cov+=ov(rect,r2rect)
            best.append((round(cov,1), rot, round(x,1), round(y,1)))
            y+=0.5
        x+=0.5
best.sort()
print("MARK legal positions (pad-clear): %d" % len(best))
for e in best[:18]: print("MARK   overlap=%7.1f mm2 rot=%d at (%.1f, %.1f)" % e)

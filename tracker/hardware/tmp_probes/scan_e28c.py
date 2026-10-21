import pcbnew, math
UM=1e6
b=pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
e28=b.FindFootprintByReference("U_E28")
eb=e28.GetBoundingBox(False,True); EW,EH=eb.GetWidth()/UM,eb.GetHeight()/UM
eo=(eb.GetX()/UM,eb.GetY()/UM)
poff=[(p.GetBoundingBox().GetX()/UM-eo[0], p.GetBoundingBox().GetY()/UM-eo[1],
       (p.GetBoundingBox().GetX()+p.GetBoundingBox().GetWidth())/UM-eo[0],
       (p.GetBoundingBox().GetY()+p.GetBoundingBox().GetHeight())/UM-eo[1]) for p in e28.Pads()]
parts=[];pads=[];holes=[]
for fp in b.GetFootprints():
    ref=fp.GetReference()
    if ref=="U_E28": continue
    r=fp.GetBoundingBox(False,True)
    rect=(r.GetX()/UM,r.GetY()/UM,(r.GetX()+r.GetWidth())/UM,(r.GetY()+r.GetHeight())/UM)
    if ref.startswith(("H1","H2","H3","H4","HW")): holes.append((ref,rect)); continue
    parts.append((ref,rect))
    for p in fp.Pads():
        pb=p.GetBoundingBox()
        pads.append((ref,p.GetNumber(),(pb.GetX()/UM,pb.GetY()/UM,(pb.GetX()+pb.GetWidth())/UM,(pb.GetY()+pb.GetHeight())/UM)))
def ov(a,c):
    dx=min(a[2],c[2])-max(a[0],c[0]); dy=min(a[3],c[3])-max(a[1],c[1])
    return dx*dy if (dx>0 and dy>0) else 0.0
def grow(r,m): return (r[0]-m,r[1]-m,r[2]+m,r[3]+m)
u1=b.FindFootprintByReference("U1"); up=[p.GetPosition() for p in u1.Pads()]
ucx=sum(p.x for p in up)/len(up)/UM; ucy=sum(p.y for p in up)/len(up)/UM
MARGIN=1.0
res=[]
for rot in (90,270):
    W2,H2=EH,EW
    x=2.0
    while x+W2<=70.0:
        y=2.0
        while y+H2<=78.0:
            rect=(x,y,x+W2,y+H2)
            if any(ov(rect,grow(r2,MARGIN))>0 for (_,r2) in parts): y+=0.5; continue
            if any(ov(rect,grow(r2,0.6))>0 for (_,r2) in holes): y+=0.5; continue
            okp=True
            for (dx0,dy0,dx1,dy1) in poff:
                pr=(x+dy0,y+EW-dx1,x+dy1,y+EW-dx0)
                if any(ov(pr,r3)>0 for (_,_,r3) in pads): okp=False;break
            if okp:
                mx,my=x+W2/2,y+H2/2
                res.append((round(math.hypot(mx-ucx,my-ucy),1),round(min(x,y,72-(x+W2),80-(y+H2)),2),rot,round(x,1),round(y,1)))
            y+=0.5
        x+=0.5
res.sort()
print("MARK U1 centroid %.1f,%.1f   margin=%.1fmm" % (ucx,ucy,MARGIN))
print("MARK candidates: %d" % len(res))
for e in res[:14]: print("MARK   dU1=%5.1f edge=%4.2f rot=%3d bbox(%.1f, %.1f)" % e)

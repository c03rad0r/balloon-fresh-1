import pcbnew, math
UM=1e6
b=pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
e28=b.FindFootprintByReference("U_E28")
eb=e28.GetBoundingBox(False,True)
EW,EH=eb.GetWidth()/UM, eb.GetHeight()/UM
eo=(eb.GetX()/UM, eb.GetY()/UM)
poff=[]
for p in e28.Pads():
    pb=p.GetBoundingBox()
    poff.append((pb.GetX()/UM-eo[0], pb.GetY()/UM-eo[1],
                 (pb.GetX()+pb.GetWidth())/UM-eo[0], (pb.GetY()+pb.GetHeight())/UM-eo[1]))
u1=b.FindFootprintByReference("U1")
u1pads=[p.GetPosition() for p in u1.Pads()]
ucx=sum(p.x for p in u1pads)/len(u1pads)/UM; ucy=sum(p.y for p in u1pads)/len(u1pads)/UM
others=[];opads=[]
for fp in b.GetFootprints():
    ref=fp.GetReference()
    if ref=="U_E28": continue
    r=fp.GetBoundingBox(False,True)
    others.append((ref,fp.GetLayerName(),(r.GetX()/UM,r.GetY()/UM,(r.GetX()+r.GetWidth())/UM,(r.GetY()+r.GetHeight())/UM)))
    for p in fp.Pads():
        pb=p.GetBoundingBox()
        opads.append((ref,p.GetNumber(),(pb.GetX()/UM,pb.GetY()/UM,(pb.GetX()+pb.GetWidth())/UM,(pb.GetY()+pb.GetHeight())/UM)))
def ov(a,c):
    dx=min(a[2],c[2])-max(a[0],c[0]); dy=min(a[3],c[3])-max(a[1],c[1])
    return dx*dy if (dx>0 and dy>0) else 0.0
res=[]
for rot in (0,90,180,270):
    W2,H2=(EW,EH) if rot in (0,180) else (EH,EW)
    x=1.0
    while x+W2<=71.0:
        y=1.0
        while y+H2<=79.0:
            rect=(x,y,x+W2,y+H2)
            if any(ov(rect,r2)>0 for (_,_,r2) in others):
                y+=0.5; continue
            okp=True
            for (dx0,dy0,dx1,dy1) in poff:
                if rot==90: dx0,dy0,dx1,dy1 = dy0,EW-dx1,dy1,EW-dx0
                elif rot==180: dx0,dy0,dx1,dy1 = EW-dx1,EH-dy1,EW-dx0,EH-dy0
                elif rot==270: dx0,dy0,dx1,dy1 = EH-dy1,dx0,EH-dy0,dx1
                pr=(x+dx0,y+dy0,x+dx1,y+dy1)
                if any(ov(pr,r3)>0 for (_,_,r3) in opads): okp=False; break
            if okp:
                mx,my=x+W2/2,y+H2/2
                d=math.hypot(mx-ucx,my-ucy)
                edge=min(x,y,72-(x+W2),80-(y+H2))
                res.append((round(d,1),round(edge,2),rot,round(x,1),round(y,1)))
            y+=0.5
        x+=0.5
res.sort()
print("MARK U1 pad centroid %.1f,%.1f" % (ucx,ucy))
print("MARK truly-free positions: %d  (zero overlap with EVERY part, both sides)" % len(res))
print("MARK closest to U1 (distance, edge-clearance, rot, x, y):")
seen=set()
for e in res:
    k=(e[2],e[3]//3,e[4]//3)
    if k in seen: continue
    seen.add(k)
    print("MARK   d=%5.1f edge=%5.2f rot=%3d at (%.1f, %.1f)" % e)
    if len(seen)>=10: break

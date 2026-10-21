import pcbnew, math
UM=1e6
SRC="/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb"
b=pcbnew.LoadBoard(SRC)
e28=b.FindFootprintByReference("U_E28")
eb=e28.GetBoundingBox(False,True); EW,EH=eb.GetWidth()/UM,eb.GetHeight()/UM
# reference pad pattern: pad bbox relative to fp position
pats=[]
for p in e28.Pads():
    pb=p.GetBoundingBox()
    pats.append((pb.GetX()/UM, pb.GetY()/UM, (pb.GetX()+pb.GetWidth())/UM, (pb.GetY()+pb.GetHeight())/UM))
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
res=[]
for rot in (0,90,180,270):
  for x in [i*0.5 for i in range(4,142)]:
    for y in [i*0.5 for i in range(4,158)]:
        e28.SetOrientationDegrees(rot)
        e28.SetPosition(pcbnew.VECTOR2I(int(x*UM),int(y*UM)))
        bb=e28.GetBoundingBox(False,True)
        rect=(bb.GetX()/UM,bb.GetY()/UM,(bb.GetX()+bb.GetWidth())/UM,(bb.GetY()+bb.GetHeight())/UM)
        if rect[0]<1.0 or rect[1]<1.0 or rect[2]>71.0 or rect[3]>79.0: continue
        if any(ov(rect,grow(r2,0.8))>0 for (_,r2) in parts): continue
        if any(ov(rect,grow(r2,0.5))>0 for (_,r2) in holes): continue
        okp=True
        for p in e28.Pads():
            pb=p.GetBoundingBox()
            pr=(pb.GetX()/UM,pb.GetY()/UM,(pb.GetX()+pb.GetWidth())/UM,(pb.GetY()+pb.GetHeight())/UM)
            if any(ov(pr,r3)>0 for (_,_,r3) in pads): okp=False; break
        if not okp: continue
        mx,my=(rect[0]+rect[2])/2,(rect[1]+rect[3])/2
        res.append((round(math.hypot(mx-ucx,my-ucy),1), round(min(rect[0],rect[1],72-rect[2],80-rect[3]),2), rot, round(x,1), round(y,1)))
res.sort()
print("MARK AUTHORITATIVE candidates (footprint-transformed): %d" % len(res))
for e in res[:12]: print("MARK   dU1=%5.1f edge=%4.2f rot=%3d fp@(%.1f, %.1f)" % e)

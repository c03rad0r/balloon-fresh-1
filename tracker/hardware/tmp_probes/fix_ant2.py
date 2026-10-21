import pcbnew
UM=1e6
B="/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb"
b=pcbnew.LoadBoard(B)
a2=b.FindFootprintByReference("ANT2")
def tabs(fp):
    return [(p.GetNumber(), p.GetBoundingBox().GetX()/UM,(p.GetBoundingBox().GetX()+p.GetBoundingBox().GetWidth())/UM,
             p.GetBoundingBox().GetY()/UM,(p.GetBoundingBox().GetY()+p.GetBoundingBox().GetHeight())/UM) for p in fp.Pads()]
u2=b.FindFootprintByReference("U2")
u2p=[p for p in u2.Pads() if p.GetNumber()=="13"][0].GetBoundingBox()
u2r=(u2p.GetX()/UM,(u2p.GetX()+u2p.GetWidth())/UM,u2p.GetY()/UM,(u2p.GetY()+u2p.GetHeight())/UM)
print("MARK U2.13 rect", [round(x,2) for x in u2r])
# candidate moves: shift ANT2 in y (and small x) and test
for dy in (-0.3,-0.4,-0.5,-0.6,-0.8,-1.0):
    a2.SetPosition(pcbnew.VECTOR2I(int(30.7*UM), int((28.0+dy)*UM)))
    bad=[]
    for (n,x0,x1,y0,y1) in tabs(a2):
        if x0 < u2r[1] and x1 > u2r[0] and y0 < u2r[3] and y1 > u2r[2]: bad.append(n)
    # also check against every OTHER pad on the board (cross-side)
    otherbad=0
    mine=[(p.GetBoundingBox()) for p in a2.Pads()]
    for fp in b.GetFootprints():
        if fp.GetReference()=="ANT2": continue
        if fp.GetLayer()==a2.GetLayer(): continue
        for p in fp.Pads():
            pb=p.GetBoundingBox()
            for mb in mine:
                dx=min(mb.GetX()+mb.GetWidth(),pb.GetX()+pb.GetWidth())-max(mb.GetX(),pb.GetX())
                dy2=min(mb.GetY()+mb.GetHeight(),pb.GetY()+pb.GetHeight())-max(mb.GetY(),pb.GetY())
                if dx>0 and dy2>0: otherbad+=1
    print("MARK dy=%+.1f  overlaps U2.13: %s   cross-side pad overlaps: %d" % (dy, bad, otherbad))

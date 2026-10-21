import pcbnew
UM=1e6
B="/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb"
b=pcbnew.LoadBoard(B)
e28=b.FindFootprintByReference("U_E28")
oldpos=(e28.GetPosition().x/UM, e28.GetPosition().y/UM)
bb=e28.GetBoundingBox(False,True)
oldbb=(bb.GetX()/UM,bb.GetY()/UM)
print("MARK old fp pos %.2f,%.2f  bbox %.2f,%.2f" % (oldpos[0],oldpos[1],oldbb[0],oldbb[1]))
# solve fp position so bbox lands on a target, by rotation transform
def bbox_for(pos, rot):
    e28.SetPosition(pcbnew.VECTOR2I(int(pos[0]*UM), int(pos[1]*UM)))
    e28.SetOrientationDegrees(rot)
    r=e28.GetBoundingBox(False,True)
    return (r.GetX()/UM, r.GetY()/UM, r.GetWidth()/UM, r.GetHeight()/UM)
for target,rot in (((41.0,60.0),90), ((41.0,60.0),270)):
    # iterative solve
    pos=list(target)
    for _ in range(8):
        bx,by,bw,bh = bbox_for(pos, rot)
        pos[0] += target[0]-bx; pos[1] += target[1]-by
    bx,by,bw,bh = bbox_for(pos, rot)
    print("MARK rot=%d  fp pos -> (%.2f, %.2f)   bbox (%.2f,%.2f) %.2fx%.2f" % (rot,pos[0],pos[1],bx,by,bw,bh))

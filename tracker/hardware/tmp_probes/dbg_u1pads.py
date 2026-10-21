import sys
sys.path.insert(0, "/home/c08r4d0r/worktrees/master-check/tracker/hardware")
import route_v10_astar as R, pcbnew
w = R.load_world(R.BOARD)
b = pcbnew.LoadBoard(R.BOARD)
UM=1e6
for ref in ("U1","U_E28"):
    fp=b.FindFootprintByReference(ref)
    pads=sorted(fp.Pads(), key=lambda p: p.GetNumber())
    ps=[(p.GetNumber(), round(p.GetPosition().x/UM,2), round(p.GetPosition().y/UM,2),
         round(p.GetSize().x/UM,2), round(p.GetSize().y/UM,2)) for p in pads]
    print("MARK", ref, "npads", len(ps))
    for row in ps[:8]: print("MARK   ", row)
    # pitch along the row that contains pin 4
    ys = sorted(set(round(p[2],1) for p in ps))
    if ref=="U1":
        for y in ys[:6]:
            row=[p for p in ps if abs(p[2]-y)<0.2]
            if len(row)>2:
                xs=sorted(p[1] for p in row)
                d=[round(xs[i+1]-xs[i],2) for i in range(len(xs)-1)]
                print("MARK   row y=%.1f n=%d pitch=%s padw=%.2f" % (y, len(row), sorted(set(d)), row[0][3]))

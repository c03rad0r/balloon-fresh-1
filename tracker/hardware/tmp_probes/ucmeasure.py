import pcbnew, math
b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
UM = 1e6
ts = [t for t in b.GetTracks() if "TRACK" in str(type(t))]
print("MARK tracks on board NOW:", len(ts))
def seg_pt(px, py, x0, y0, x1, y1):
    dx, dy = x1-x0, y1-y0
    L2 = dx*dx+dy*dy
    if L2 == 0: return math.hypot(px-x0, py-y0)
    t = max(0.0, min(1.0, ((px-x0)*dx + (py-y0)*dy)/L2))
    return math.hypot(px-(x0+t*dx), py-(y0+t*dy))
def seg_rect(x0,y0,x1,y1,bb):
    L = math.hypot(x1-x0, y1-y0); steps = max(2, int(L/0.02)+2)
    for i in range(steps+1):
        t=i/steps; px,py = x0+t*(x1-x0), y0+t*(y1-y0)
        if bb[0]<=px<=bb[2] and bb[1]<=py<=bb[3]: return 0.0
    best=1e9
    for (ex0,ey0,ex1,ey1) in ((bb[0],bb[1],bb[2],bb[1]),(bb[2],bb[1],bb[2],bb[3]),(bb[2],bb[3],bb[0],bb[3]),(bb[0],bb[3],bb[0],bb[1])):
        for (px,py) in ((x0,y0),(x1,y1)):
            best=min(best, seg_pt(px,py,ex0,ey0,ex1,ey1))
        for (qx,qy) in ((ex0,ey0),(ex1,ey1)):
            best=min(best, seg_pt(qx,qy,x0,y0,x1,y1))
    return best
uc = b.FindFootprintByReference("U_C")
print("MARK === OLD /ANT3_2G4_RX segments (removed by PR #271) vs every U_C pad ===")
segs = [((30.80,21.86),(36.70,21.86)), ((36.70,21.86),(36.70,26.50))]
worst = []
for p in sorted(uc.Pads(), key=lambda q: int(q.GetNumber()) if q.GetNumber().isdigit() else 99):
    pos, s = p.GetPosition(), p.GetSize()
    bb = (pos.x/UM-s.x/UM/2, pos.y/UM-s.y/UM/2, pos.x/UM+s.x/UM/2, pos.y/UM+s.y/UM/2)
    best = min(seg_rect(a[0],a[1],c[0],c[1],bb) for a,c in segs)
    n = p.GetNet()
    worst.append((best, p.GetNumber(), n.GetNetname() if n else "NC"))
for d, num, nm in sorted(worst):
    flag = "  <== COPPER IN PAD" if d <= 0.1 else ("  <== TIGHT" if d < 0.5 else "")
    print(f"MARK U_C.{num:>2} {nm:<16} clear {d:+.3f}mm{flag}")
print("MARK min clearance overall: %.3f mm" % min(w[0] for w in worst))

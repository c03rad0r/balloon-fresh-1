import pcbnew, math
b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
UM = 1e6
def pt_seg(px,py,x0,y0,x1,y1):
    dx,dy = x1-x0, y1-y0
    L2 = dx*dx+dy*dy
    if L2==0: return math.hypot(px-x0,py-y0)
    t = max(0.0,min(1.0,((px-x0)*dx+(py-y0)*dy)/L2))
    return math.hypot(px-(x0+t*dx), py-(y0+t*dy))
def seg_seg(a0,a1,b0,b1):
    # sample-based, 0.05mm resolution
    L = math.hypot(a1[0]-a0[0], a1[1]-a0[1])
    n = max(2,int(L/0.05)+2)
    best=1e9
    for i in range(n+1):
        t=i/n
        px,py=a0[0]+t*(a1[0]-a0[0]), a0[1]+t*(a1[1]-a0[1])
        best=min(best, pt_seg(px,py,b0[0],b0[1],b1[0],b1[1]))
    return best
ts=[t for t in b.GetTracks() if "TRACK" in str(type(t)) and "VIA" not in str(type(t))]
tracks=[]
for t in ts:
    n=t.GetNet()
    nm = n.GetNetname() if n else "?"
    s=(t.GetStart().x/UM, t.GetStart().y/UM); e=(t.GetEnd().x/UM, t.GetEnd().y/UM)
    tracks.append((nm, s, e, t.GetLayer()))
print("MARK tracks", len(tracks))
bad=0
for i in range(len(tracks)):
    for j in range(i+1, len(tracks)):
        na,sa,ea,la = tracks[i]; nb,sb,eb,lb = tracks[j]
        if na==nb or na=="?" or nb=="?": continue
        if la!=lb: continue
        d = seg_seg(sa,ea,sb,eb) - 0.2  # minus both half-widths
        if d < 0.2 - 0.05:  # under CLEAR with tolerance
            bad+=1
            if bad<=12: print("MARK CROSS %.3fmm: %s x %s (layer %d)" % (d, na, nb, la))
print("MARK different-net under-clearances:", bad)

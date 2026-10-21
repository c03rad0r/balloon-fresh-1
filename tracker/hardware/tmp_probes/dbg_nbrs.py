import sys
sys.path.insert(0, "/home/c08r4d0r/worktrees/master-check/tracker/hardware")
import route_v10_astar as R, math
w = R.load_world(R.BOARD); P=0.1
blocked, nx, ny = R.build_grid(w, P)
for netname in ("/F33_CS_N", "/SPI2_SCK"):
    key=[k for k in w["net_pads"] if k[1]==netname][0]
    uniq={}
    for ref,num,sides,rect in w["net_pads"][key]:
        uniq.setdefault((ref,num),(sides,rect))
    keys=list(uniq.keys())
    a_sides,a_rect=uniq[keys[0]]; c_sides,c_rect=uniq[keys[1]]
    allr=[pr[5] for pr in w["pads"]]
    saved=R.unblock_own(blocked,w,P,[a_rect,c_rect],{0,1},allr)
    start=R.to_cell(w,P,(a_rect[0]+a_rect[2])/2,(a_rect[1]+a_rect[3])/2)
    goal=R.to_cell(w,P,(c_rect[0]+c_rect[2])/2,(c_rect[1]+c_rect[3])/2)
    flips=0
    for i,j in ((start[0]+1,start[1]),(start[0]-1,start[1]),(start[0],start[1]+1),(start[0],start[1]-1)):
        if 0<=i<nx and 0<=j<ny and blocked[0][j][i]:
            flips+=1
    print("MARK", netname, "start", start, "goal", goal, "own-layer neighbors blocked:", flips, "of 4")
    # scan outward from start for the nearest open cell on F
    found=[]
    for rr in range(0, 40):
        for di in range(-rr, rr+1):
            for dj in (-rr, rr):
                i,j = start[0]+di, start[1]+dj
                if 0<=i<nx and 0<=j<ny and not blocked[0][j][i]:
                    found.append((rr, (i,j))); break
            if found: break
        if found: break
    print("MARK", netname, "nearest open F cell:", found[:1])
    R.restore(blocked, saved)

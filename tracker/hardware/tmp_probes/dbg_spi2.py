import sys
sys.path.insert(0, "/home/c08r4d0r/worktrees/master-check/tracker/hardware")
import route_v10_astar as R
from collections import deque
w = R.load_world(R.BOARD); P=0.1
blocked, nx, ny = R.build_grid(w, P)
for netname in ("/SPI2_SCK", "/SPI2_MOSI", "/SPI2_MISO", "/F33_CS_N"):
    key=[k for k in w["net_pads"] if k[1]==netname][0]
    uniq={}
    for ref,num,sides,rect in w["net_pads"][key]:
        uniq.setdefault((ref,num),(sides,rect))
    ks=list(uniq.keys())
    a_rect=uniq[ks[0]][1]; c_rect=uniq[ks[1]][1]
    saved=R.unblock_own(blocked,w,P,[a_rect,c_rect],{0,1},[pr[5] for pr in w["pads"]])
    start=R.to_cell(w,P,(a_rect[0]+a_rect[2])/2,(a_rect[1]+a_rect[3])/2)
    # reachable set from start, per layer
    info={}
    for lay in (0,1):
        seen={(start[0],start[1])}
        q=deque([(start[0],start[1])])
        while q:
            i,j=q.popleft()
            for di,dj in ((1,0),(-1,0),(0,1),(0,-1)):
                ni,nj=i+di,j+dj
                if 0<=ni<nx and 0<=nj<ny and (ni,nj) not in seen and not blocked[lay][nj][ni]:
                    seen.add((ni,nj)); q.append((ni,nj))
        info[lay]=len(seen)
    R.restore(blocked, saved)
    print("MARK", netname, "start", start, "local, reachable F:", info[0], "B:", info[1])

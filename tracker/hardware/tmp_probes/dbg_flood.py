import sys
sys.path.insert(0, "/home/c08r4d0r/worktrees/master-check/tracker/hardware")
import route_v10_astar as R
from collections import deque
w = R.load_world(R.BOARD); P=0.1
blocked, nx, ny = R.build_grid(w, P)
key=[k for k in w["net_pads"] if k[1]=="/F33_CS_N"][0]
uniq={}
for ref,num,sides,rect in w["net_pads"][key]:
    uniq.setdefault((ref,num),(sides,rect))
keys=list(uniq.keys())
a_rect=uniq[keys[0]][1]; c_rect=uniq[keys[1]][1]
allr=[pr[5] for pr in w["pads"]]
saved=R.unblock_own(blocked,w,P,[a_rect,c_rect],{0,1},allr)
start=R.to_cell(w,P,(a_rect[0]+a_rect[2])/2,(a_rect[1]+a_rect[3])/2)
goal=R.to_cell(w,P,(c_rect[0]+c_rect[2])/2,(c_rect[1]+c_rect[3])/2)
# flood fill on F from start
seen={(start[0],start[1])}
q=deque([(start[0],start[1])])
while q:
    i,j=q.popleft()
    for di,dj in ((1,0),(-1,0),(0,1),(0,-1)):
        ni,nj=i+di,j+dj
        if 0<=ni<nx and 0<=nj<ny and (ni,nj) not in seen and not blocked[0][nj][ni]:
            seen.add((ni,nj)); q.append((ni,nj))
print("MARK reachable F cells from start:", len(seen), "goal reached:", (goal[0],goal[1]) in seen)
print("MARK goal cell blocked:", blocked[0][goal[1]][goal[0]])
# where is the F barrier? count open cells per row near start row
j=start[1]
row=[i for i in range(nx) if not blocked[0][j][i]]
print("MARK open cells on start row:", len(row), "first/last:", (row[0], row[-1]) if row else None)

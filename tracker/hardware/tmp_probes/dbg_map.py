import sys
sys.path.insert(0, "/home/c08r4d0r/worktrees/master-check/tracker/hardware")
import route_v10_astar as R
w = R.load_world(R.BOARD); P=0.1
blocked, nx, ny = R.build_grid(w, P)
key=[k for k in w["net_pads"] if k[1]=="/SPI2_SCK"][0]
uniq={}
for ref,num,sides,rect in w["net_pads"][key]:
    uniq.setdefault((ref,num),(sides,rect))
ks=list(uniq.keys())
a_rect=uniq[ks[0]][1]; c_rect=uniq[ks[1]][1]
print("MARK a", ks[0], [round(x,2) for x in a_rect], "c", ks[1], [round(x,2) for x in c_rect])
allp=[pr[5] for pr in w["pads"]]
saved=R.unblock_own(blocked,w,P,[a_rect,c_rect],{0,1},allp)
start=R.to_cell(w,P,(a_rect[0]+a_rect[2])/2,(a_rect[1]+a_rect[3])/2)
print("MARK start", start)
si,sj=start
# ASCII map, 46 wide x 30 tall, x to the LEFT = toward board edge
for j in range(sj-14, sj+15):
    row=""
    for i in range(si-26, si+20):
        if not (0<=i<nx and 0<=j<ny): row+="#"; continue
        if (i,j)==(si,sj): row+="S"; continue
        row += "#" if blocked[0][j][i] else "."
    print("MARK %4d %s" % (j, row))
# which pads sit within 1mm of U1.4's rect?
import math
cx,cy=(a_rect[0]+a_rect[2])/2,(a_rect[1]+a_rect[3])/2
near=[]
for pr in w["pads"]:
    r2=pr[5]
    d=math.hypot(max(r2[0]-cx,0,cx-r2[2]), max(r2[1]-cy,0,cy-r2[3]))
    if d<1.6: near.append((round(d,2), pr[0], pr[1], pr[3]))
print("MARK near pads:", sorted(near)[:14])
R.restore(blocked, saved)

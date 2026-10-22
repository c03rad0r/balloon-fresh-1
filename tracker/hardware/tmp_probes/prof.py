import sys, time, math
sys.path.insert(0,"/home/c08r4d0r/worktrees/master-check/tracker/hardware")
import route_v10_astar as R
w=R.load_world(R.BOARD); P=0.1
t0=time.time(); blocked,nx,ny=R.build_grid(w,P); print("MARK grid %.1fs  %dx%d" % (time.time()-t0,nx,ny))
# time ONE 2-pad net end to end
key=[k for k in w["net_pads"] if k[1]=="/SPI2_SCK"][0]
plist=w["net_pads"][key]
uniq={}
for ref,num,sides,rect in plist: uniq.setdefault((ref,num),(sides,rect))
keys=list(uniq.keys())
a_sides,a_rect=uniq[keys[0]]; c_sides,c_rect=uniq[keys[1]]
allr=[pr[5] for pr in w["pads"]]
t0=time.time(); saved=R.unblock_own(blocked,w,P,[a_rect,c_rect],{0,1},allr); tu=time.time()-t0
t0=time.time()
start=R.to_cell(w,P,(a_rect[0]+a_rect[2])/2,(a_rect[1]+a_rect[3])/2)
goal=R.to_cell(w,P,(c_rect[0]+c_rect[2])/2,(c_rect[1]+c_rect[3])/2)
best=None
for ls in sorted(a_sides):
    for lg in sorted(c_sides):
        p=R.astar(blocked,nx,ny,(start[0],start[1],ls),(goal[0],goal[1],lg),P,{0,1})
        if p and (best is None or len(p)<len(best)): best=p
ta=time.time()-t0
R.restore(blocked,saved)
print("MARK unblock %.2fs   astar %.2fs  path=%s" % (tu, ta, len(best) if best else None))

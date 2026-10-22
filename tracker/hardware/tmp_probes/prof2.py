import sys, time, cProfile, pstats, io
sys.path.insert(0,"/home/c08r4d0r/worktrees/master-check/tracker/hardware")
import route_v10_astar as R
w=R.load_world(R.BOARD); P=0.1
blocked,nx,ny=R.build_grid(w,P)
key=[k for k in w["net_pads"] if k[1]=="/SPI2_SCK"][0]
uniq={}
for ref,num,sides,rect in w["net_pads"][key]: uniq.setdefault((ref,num),(sides,rect))
keys=list(uniq.keys()); a_sides,a_rect=uniq[keys[0]]; c_sides,c_rect=uniq[keys[1]]
allr=[pr[5] for pr in w["pads"]]
saved=R.unblock_own(blocked,w,P,[a_rect,c_rect],{0,1},allr)
start=R.to_cell(w,P,(a_rect[0]+a_rect[2])/2,(a_rect[1]+a_rect[3])/2)
goal=R.to_cell(w,P,(c_rect[0]+c_rect[2])/2,(c_rect[1]+c_rect[3])/2)
pr=cProfile.Profile(); pr.enable()
p=R.astar(blocked,nx,ny,(start[0],start[1],0),(goal[0],goal[1],0),P,{0,1})
pr.disable()
st=pstats.Stats(pr, stream=io.StringIO()); st.sort_stats("cumulative")
buf=io.StringIO(); st.stream=buf; st.print_stats(8)
for line in buf.getvalue().splitlines():
    if "route_v10_astar" in line or "ncalls" in line: print("MARK",line.strip()[:110])
print("MARK path len", len(p) if p else None)

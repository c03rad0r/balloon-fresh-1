import sys
sys.path.insert(0,"/home/c08r4d0r/worktrees/master-check/tracker/hardware")
import route_v10_astar as R
w=R.load_world(R.BOARD); P=0.1
blocked,nx,ny=R.build_grid(w,P)
vok=R.build_via_ok(blocked,nx,ny,P)
for lay in (0,1):
    n=sum(vok[lay])
    print("MARK layer %d via-ok %d of %d (%.1f%%)" % (lay, n, nx*ny, 100.0*n/(nx*ny)))

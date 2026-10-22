import sys, math
sys.path.insert(0,"/home/c08r4d0r/worktrees/master-check/tracker/hardware")
import route_v10_astar as R
w=R.load_world(R.BOARD); P=0.1
blocked,nx,ny=R.build_grid(w,P)
print("MARK VIA_D",R.VIA_D,"CLEAR",R.CLEAR,"TRACK_W",R.TRACK_W)
for extra in (0.0, R.TRACK_W/2):
    r=int(math.ceil((R.VIA_D/2+R.CLEAR+extra)/P))+1
    ok=0
    for j in range(ny):
        for i in range(nx):
            good=True
            for dj in range(-r,r+1):
                nj=j+dj
                if nj<0 or nj>=ny: good=False;break
                b0=blocked[0][nj]; b1=blocked[1][nj]
                for di in range(-r,r+1):
                    ni=i+di
                    if ni<0 or ni>=nx or b0[ni] or b1[ni]: good=False;break
                if not good: break
            if good: ok+=1
    print("MARK r=%d (extra %.2fmm): via-ok cells = %d of %d  (%.3f%%)" % (r, extra, ok, nx*ny, 100.0*ok/(nx*ny)))

import sys
sys.path.insert(0,"/home/c08r4d0r/worktrees/master-check/tracker/hardware")
import route_v10_astar as R
w=R.load_world(R.BOARD); P=0.1
blocked,nx,ny=R.build_grid(w,P)
vok=R.build_via_ok(blocked,nx,ny,P)
# U1 pin-row band: y 32.4..52.6, x 10.0..29.6
ox,oy=w["origin"]
def cells(x0,x1,y0,y1):
    i0=int((x0-ox)/P); i1=int((x1-ox)/P); j0=int((y0-oy)/P); j1=int((y1-oy)/P)
    return i0,i1,j0,j1
for name,(x0,x1,y0,y1) in {"U1 full box":(10.0,29.6,32.4,52.6),
                           "U1 pin-row left edge":(9.0,13.0,36.0,45.0),
                           "board (all)":(0.5,71.5,0.5,79.5)}.items():
    i0,i1,j0,j1=cells(x0,x1,y0,y1)
    tot=0; okf=0; okb=0
    for j in range(j0,j1+1):
        for i in range(i0,i1+1):
            tot+=1
            if vok[0][j*nx+i]: okf+=1
            if vok[1][j*nx+i]: okb+=1
    print("MARK %-22s cells=%6d  via-ok F.Cu %5.1f%%  B.Cu %5.1f%%" % (name, tot, 100.0*okf/tot, 100.0*okb/tot))

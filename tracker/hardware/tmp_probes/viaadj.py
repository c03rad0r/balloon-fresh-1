import sys, math
sys.path.insert(0,"/home/c08r4d0r/worktrees/master-check/tracker/hardware")
import route_v10_astar as R
w=R.load_world(R.BOARD); P=0.1
blocked,nx,ny=R.build_grid(w,P)
vok=R.build_via_ok(blocked,nx,ny,P)
ox,oy=w["origin"]
nets=["/SPI2_SCK","/SPI2_MOSI","/SPI2_MISO","/F33_CS_N","/F33_RESET_N","/F33_BUSY","/F33_IRQ","/E28_CS_N","/SPI1_MOSI","/SPI1_MISO"]
print("MARK net            pad      nearest LEGAL via cell (mm from pad centre)  reachable?")
for n in nets:
    key=[k for k in w["net_pads"] if k[1]==n]
    if not key: print("MARK %-15s (not on board)"%n); continue
    for ref,num,sides,rect in w["net_pads"][key[0]]:
        if ref!="U1": continue
        cx,cy=(rect[0]+rect[2])/2,(rect[1]+rect[3])/2
        i0=int((cx-ox)/P); j0=int((cy-oy)/P)
        best=None
        for rr in range(0,25):
            for di in range(-rr,rr+1):
                for dj in (-rr,rr):
                    i,j=i0+di,j0+dj
                    if 0<=i<nx and 0<=j<ny and vok[0][j*nx+i]:
                        d=math.hypot(i-i0,j-j0)*P
                        if best is None or d<best: best=d
            if best is not None: break
        print("MARK %-15s U1.%-4s %-8s %s" % (n, num, ("%.2fmm"%best) if best is not None else "NONE", "YES" if best is not None else "NO"))
        break

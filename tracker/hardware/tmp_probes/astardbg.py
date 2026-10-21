import sys, math
sys.path.insert(0, "/home/c08r4d0r/worktrees/master-check/tracker/hardware")
import route_v10_astar as R
w = R.load_world(R.BOARD)
blocked, nx, ny = R.build_grid(w, 0.1)
print("MARK grid", nx, "x", ny)
# where are U3.10 and ANT3.1, and are their cells blocked?
plist = w["net_pads"][[k for k in w["net_pads"] if k[1]=="/ANT3_2G4_RX"][0]]
for ref, num, sides, rect in plist:
    cx, cy = (rect[0]+rect[2])/2, (rect[1]+rect[3])/2
    i, j = R.to_cell(w, 0.1, cx, cy)
    print("MARK", ref, num, "rect", [round(v,2) for v in rect], "cell", (i,j),
          "sides", sides, "blocked F/B:", blocked[0][j][i], blocked[1][j][i])
# how much of the board is blocked?
tot = sum(sum(row) for row in blocked[0]); print("MARK blocked cells F:", tot, "of", nx*ny)
tot2 = sum(sum(row) for row in blocked[1]); print("MARK blocked cells B:", tot2)

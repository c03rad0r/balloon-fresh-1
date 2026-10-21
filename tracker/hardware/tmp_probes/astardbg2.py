import sys
sys.path.insert(0, "/home/c08r4d0r/worktrees/master-check/tracker/hardware")
import route_v10_astar as R
w = R.load_world(R.BOARD)
P = 0.1
blocked, nx, ny = R.build_grid(w, P)
key = [k for k in w["net_pads"] if k[1]=="/ANT3_2G4_RX"][0]
plist = w["net_pads"][key]
uniq = {}
for ref, num, sides, rect in plist:
    uniq.setdefault((ref,num), (sides, rect))
keys = list(uniq.keys())
a_sides, a_rect = uniq[keys[0]]
c_sides, c_rect = uniq[keys[1]]
allow = sorted(a_sides & c_sides)
print("MARK allow:", allow, "a:", keys[0], "c:", keys[1])
saved = R.unblock_own(blocked, w, P, [a_rect, c_rect], set(allow))
print("MARK unblocked cells:", len(saved))
start = R.to_cell(w, P, (a_rect[0]+a_rect[2])/2, (a_rect[1]+a_rect[3])/2)
goal = R.to_cell(w, P, (c_rect[0]+c_rect[2])/2, (c_rect[1]+c_rect[3])/2)
print("MARK start", start, "goal", goal, "blocked now F/B:", blocked[0][start[1]][start[0]], blocked[1][start[1]][start[0]])
for layer in allow:
    p = R.astar(blocked, nx, ny, (start[0], start[1], layer), (goal[0], goal[1], layer), P, set(allow))
    print("MARK layer", layer, "path:", (len(p) if p else None))

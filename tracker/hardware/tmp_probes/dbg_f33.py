import sys
sys.path.insert(0, "/home/c08r4d0r/worktrees/master-check/tracker/hardware")
import route_v10_astar as R, math
w = R.load_world(R.BOARD)
P = 0.1
blocked, nx, ny = R.build_grid(w, P)
key = [k for k in w["net_pads"] if k[1]=="/F33_CS_N"][0]
plist = w["net_pads"][key]
uniq = {}
for ref, num, sides, rect in plist:
    uniq.setdefault((ref,num), (sides, rect))
print("MARK pads:", [(k, sorted(v[0]), [round(x,2) for x in v[1]]) for k,v in uniq.items()])
keys = list(uniq.keys())
a_sides, a_rect = uniq[keys[0]]
c_sides, c_rect = uniq[keys[1]]
start = R.to_cell(w, P, (a_rect[0]+a_rect[2])/2, (a_rect[1]+a_rect[3])/2)
goal  = R.to_cell(w, P, (c_rect[0]+c_rect[2])/2, (c_rect[1]+c_rect[3])/2)
print("MARK start", start, "goal", goal)
allr = [pr[5] for pr in w["pads"]]
saved = R.unblock_own(blocked, w, P, [a_rect, c_rect], {0,1}, allr)
print("MARK unblocked", len(saved))
for ls in sorted(a_sides):
    for lg in sorted(c_sides):
        p = R.astar(blocked, nx, ny, (start[0],start[1],ls), (goal[0],goal[1],lg), P, {0,1})
        print("MARK path %d->%d:" % (ls,lg), (len(p) if p else None))
R.restore(blocked, saved)
j = start[1]
print("MARK blocked F.Cu on start row:", sum(blocked[0][j]), "of", nx)
print("MARK bodies near U1:", [b for b in w["bodies"] if b[0] in ("U1","U2")])

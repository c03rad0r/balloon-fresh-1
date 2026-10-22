import sys
sys.path.insert(0,"/home/c08r4d0r/worktrees/master-check/tracker/hardware")
import route_v10_astar as R
print("MARK F=%r B=%r KEEPOUT_REFS=%r" % (R.F, R.B, getattr(R,"KEEPOUT_REFS",None)))
w=R.load_world(R.BOARD)
print("MARK bodies:", w["bodies"])
print("MARK n_pads", len(w["pads"]), "n_nets", len(w["net_pads"]))

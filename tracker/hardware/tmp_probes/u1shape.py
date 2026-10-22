import pcbnew
UM=1e6
SRC="/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb"
b=pcbnew.LoadBoard(SRC)
u1=b.FindFootprintByReference("U1")
bb=u1.GetBoundingBox(False,True)
print("MARK U1 courtyard now x %.2f..%.2f y %.2f..%.2f" % (bb.GetX()/UM,(bb.GetX()+bb.GetWidth())/UM,bb.GetY()/UM,(bb.GetY()+bb.GetHeight())/UM))
# which edge is each signal pad column on? classify by position
import collections
sig={"pad":[],"other":[]}
for p in u1.Pads():
    n=p.GetNetname() or ""
    pb=p.GetBoundingBox()
    sig["pad" if n else "other"].append((p.GetNumber(), round(pb.GetX()/UM,2), round(pb.GetY()/UM,2), n))
print("MARK U1 pad columns (x, count):")
c=collections.Counter(round(t[1]) for t in sig["pad"]+sig["other"])
print("MARK  ", sorted(c.items()))
print("MARK U1 pad rows (y, count):")
c2=collections.Counter(round(t[2]) for t in sig["pad"]+sig["other"])
print("MARK  ", sorted(c2.items()))

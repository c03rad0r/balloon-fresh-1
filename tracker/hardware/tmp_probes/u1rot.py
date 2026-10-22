import pcbnew
UM=1e6
b=pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
u1=b.FindFootprintByReference("U1")
bb=u1.GetBoundingBox(False,True)
print("MARK U1 rot90 courtyard x %.2f..%.2f y %.2f..%.2f" % (bb.GetX()/UM,(bb.GetX()+bb.GetWidth())/UM,bb.GetY()/UM,(bb.GetY()+bb.GetHeight())/UM))
import collections
c=collections.Counter(round(p.GetBoundingBox().GetY()/UM) for p in u1.Pads())
print("MARK pad rows:", sorted(c.items()))
print("MARK J_W1 seat y 35.17..44.83 -- do pad rows fall inside?")

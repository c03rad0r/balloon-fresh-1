import pcbnew
UM=1e6
b=pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
# find two B.Cu SMD pads on DIFFERENT nets that are close (same chip) to prove a real short
fp=b.FindFootprintByReference("U3")
ps=sorted([p for p in fp.Pads()], key=lambda p:p.GetPosition().y)
print("MARK U3 pads (num, net, y):")
for p in ps[:10]:
    print("MARK  ", p.GetNumber(), repr(p.GetNetname()), round(p.GetPosition().y/UM,2), "drill", p.GetDrillSize().x/UM)

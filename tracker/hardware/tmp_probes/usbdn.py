import pcbnew
b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
for ref, num in (("J_PROG","4"), ("U1","13")):
    fp = b.FindFootprintByReference(ref)
    for p in fp.Pads():
        if p.GetNumber() == num:
            bb = p.GetBoundingBox()
            print("MARK %s.%s rect %.2f,%.2f .. %.2f,%.2f net=%s" % (ref, num,
                  bb.GetX()/1e6, bb.GetY()/1e6, (bb.GetX()+bb.GetWidth())/1e6, (bb.GetY()+bb.GetHeight())/1e6,
                  p.GetNet().GetNetname() if p.GetNet() else "NC"))

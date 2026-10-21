import pcbnew
UM=1e6
b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
for ref in ("U1","U_E28"):
    fp=b.FindFootprintByReference(ref)
    bb=fp.GetBoundingBox(False,True)
    print("MARK", ref, "layer", fp.GetLayerName(), "rot", fp.GetOrientationDegrees(),
          "courtyard x %.2f..%.2f  y %.2f..%.2f" % (bb.GetX()/UM,(bb.GetX()+bb.GetWidth())/UM,
                                                     bb.GetY()/UM,(bb.GetY()+bb.GetHeight())/UM))
print("MARK --- does any gate check pad-vs-pad across sides? ---")

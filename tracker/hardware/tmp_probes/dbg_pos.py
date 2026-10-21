import pcbnew
UM=1e6
b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
for ref in ("U1","U_E28"):
    fp=b.FindFootprintByReference(ref)
    print("MARK", ref, "fp pos", round(fp.GetPosition().x/UM,2), round(fp.GetPosition().y/UM,2),
          "layer", fp.GetLayerName(), "rot", fp.GetOrientationDegrees())
    for num in ("4","5"):
        for p in fp.Pads():
            if p.GetNumber()==num:
                bb=p.GetBoundingBox()
                print("MARK   pad", num, "pos", round(p.GetPosition().x/UM,2), round(p.GetPosition().y/UM,2),
                      "bbox", round(bb.GetX()/UM,2), round(bb.GetY()/UM,2),
                      round((bb.GetX()+bb.GetWidth())/UM,2), round((bb.GetY()+bb.GetHeight())/UM,2))

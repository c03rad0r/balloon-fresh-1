import pcbnew
UM=1e6
b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
print("MARK ref layer courtyard(WxH)  padfield(WxH)  npads")
for fp in b.GetFootprints():
    ref=fp.GetReference()
    if ref.startswith(("H1","H2","H3","H4","HW")): continue
    bb=fp.GetBoundingBox(False,True)
    cw,ch=bb.GetWidth()/UM, bb.GetHeight()/UM
    pads=[p for p in fp.Pads()]
    if pads:
        xs=[p.GetBoundingBox().GetX()/UM for p in pads]
        xe=[(p.GetBoundingBox().GetX()+p.GetBoundingBox().GetWidth())/UM for p in pads]
        ys=[p.GetBoundingBox().GetY()/UM for p in pads]
        ye=[(p.GetBoundingBox().GetY()+p.GetBoundingBox().GetHeight())/UM for p in pads]
        pw,ph=max(xe)-min(xs), max(ye)-min(ys)
    else:
        pw=ph=0
    lay = "F" if fp.GetLayerName()=="F.Cu" else "B"
    flag = "  <== COURTYARD >> PADS" if (pw>0 and (cw > pw*1.6 or ch > ph*1.6)) else ""
    print("MARK %-7s %s %6.2f x %5.2f   %6.2f x %5.2f   %2d%s" % (ref, lay, cw, ch, pw, ph, len(pads), flag))

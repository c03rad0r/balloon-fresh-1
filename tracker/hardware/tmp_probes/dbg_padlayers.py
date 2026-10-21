import pcbnew
UM=1e6
b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
FL,BL = pcbnew.F_Cu, pcbnew.B_Cu
for ref in ("U1","U_E28","U2","U3","U_C","U5","ANT2","ANT3"):
    fp=b.FindFootprintByReference(ref)
    if not fp: continue
    two=[]; one=[]
    for p in fp.Pads():
        ls=p.GetLayerSet()
        n=sum(1 for l in (FL,BL) if ls.Contains(l))
        (two if n==2 else one).append(p.GetNumber())
    print("MARK %-6s layer=%-5s  two-layer pads: %d %s" % (ref, fp.GetLayerName(), len(two), sorted(two)[:12]))
    print("MARK        one-layer pads: %d" % len(one))
    # attribute: is it a THT pad (drilled) or SMD?
    if two:
        for p in fp.Pads():
            if p.GetNumber()==two[0]:
                print("MARK        sample pad %s attr=%s drill=%.2f  layerset=%s" % (
                    p.GetNumber(), p.GetAttribute(), p.GetDrillSize().x/UM, ls))

import pcbnew
b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
print("MARK ref  fp_layer  pad_layer  attr  padnum")
for ref in ("U2","U1","U3","U_C","U_E28","ANT2","ANT3","C_CAP1"):
    fp = b.FindFootprintByReference(ref)
    if fp is None:
        print("MARK", ref, "MISSING"); continue
    pl = fp.GetLayer()
    sides = {}
    for p in fp.Pads():
        ls = p.GetLayerSet()
        # which copper layers does the pad actually live on?
        on = []
        if ls.Contains(pcbnew.F_Cu): on.append("F")
        if ls.Contains(pcbnew.B_Cu): on.append("B")
        key = "+".join(on) if on else "NONE"
        sides[key] = sides.get(key, 0) + 1
    print(f"MARK {ref:6s} fp={('F' if pl==pcbnew.F_Cu else 'B')}  pads_by_layer={sides}")

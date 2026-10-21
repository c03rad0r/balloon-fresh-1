import pcbnew
b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
for ref in ("U_C", "U3"):
    fp = b.FindFootprintByReference(ref)
    print(f"MARK === {ref} ({fp.GetFPID().GetLibItemName()}) pads with nets ===")
    for p in sorted(fp.Pads(), key=lambda q: int(q.GetNumber()) if q.GetNumber().isdigit() else 99):
        n = p.GetNet()
        print(f"MARK {ref}.{p.GetNumber():>2} net={n.GetNetname() if n else 'NC'}")

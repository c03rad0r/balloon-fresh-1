import pcbnew, collections
b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
nets = collections.defaultdict(set)
for fp in b.GetFootprints():
    for p in fp.Pads():
        n = p.GetNet()
        if n and n.GetNetCode() != 0:
            nets[n.GetNetname()].add((fp.GetReference(), p.GetNumber()))
multi = {k: sorted(v) for k, v in nets.items() if len(v) > 1}
print("real multi-point nets:", len(multi))
for k in sorted(multi):
    print(f"  {k:18s} {multi[k]}")

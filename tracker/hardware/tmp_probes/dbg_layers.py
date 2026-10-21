import pcbnew, math
UM=1e6
b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
FL, BL = pcbnew.F_Cu, pcbnew.B_Cu
def ln(l):
    return {FL:"F.Cu", BL:"B.Cu"}.get(l, str(l))
tracks=[t for t in b.GetTracks() if "TRACK" in str(type(t)) and "VIA" not in str(type(t))]
vias=[t for t in b.GetTracks() if "VIA" in str(type(t))]
print("MARK tracks by layer:")
for lay in (FL,BL):
    ls=[t for t in tracks if t.GetLayer()==lay]
    print("MARK   %s: %d tracks, %.1f mm total" % (ln(lay), len(ls), sum(t.GetLength()/UM for t in ls)))
print("MARK vias: %d" % len(vias))
# pads with their layer SET
pads=[]
for fp in b.GetFootprints():
    for p in fp.Pads():
        ls=p.GetLayerSet()
        layers=tuple(l for l in (FL,BL) if ls.Contains(l))
        pads.append((fp.GetReference(), p.GetNumber(), layers, p.GetBoundingBox(), ls))
print("MARK pads by layer coverage:")
from collections import Counter
c=Counter(len(p[2]) for p in pads)
print("MARK   pads on 2 layers (THT):", c[2], " on 1 layer (SMD):", c[1])
tht=[p for p in pads if len(p[2])==2]
print("MARK   THT pad refs:", sorted(set(p[0] for p in tht))[:12])

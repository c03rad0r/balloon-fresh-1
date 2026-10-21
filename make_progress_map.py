
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mp
import pcbnew, collections

b = pcbnew.LoadBoard("/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb")
UM = 1e6
bb = b.GetBoardEdgesBoundingBox()
W, H = bb.GetWidth()/UM, bb.GetHeight()/UM
fig, ax = plt.subplots(figsize=(9, 10.2), dpi=150)
fig.patch.set_facecolor("#0d1117"); ax.set_facecolor("#0d1117")
ax.add_patch(mp.Rectangle((0,0), W, H, fill=False, ec="#58a6ff", lw=2))

# footprints: front = orange, back = cyan; pads small
for fp in b.GetFootprints():
    ref = fp.GetReference()
    fbb = fp.GetBoundingBox(False, True)
    x, y = fbb.GetX()/UM, fbb.GetY()/UM
    w, h = fbb.GetWidth()/UM, fbb.GetHeight()/UM
    if ref.startswith(("H","HW")):
        ax.add_patch(mp.Circle((x+w/2, y+h/2), 1.25, fc="none", ec="#f85149", lw=1.4))
        continue
    front = fp.GetLayer() == pcbnew.F_Cu
    col = "#d29922" if front else "#3fb950"
    ax.add_patch(mp.Rectangle((x,y), w, h, fill=True, fc=col, alpha=0.13, ec=col, lw=1.0))
    ax.text(x+w/2, y+h/2, ref, color=col, fontsize=6.5, ha="center", va="center", weight="bold")
    for p in fp.Pads():
        pp = p.GetPosition()
        ax.add_patch(mp.Circle((pp.x/UM, pp.y/UM), 0.22, fc="#8b949e", ec="none"))

# tracks
routed = collections.defaultdict(list)
for t in b.GetTracks():
    if "TRACK" not in str(type(t)): continue
    s, e = t.GetStart(), t.GetEnd()
    routed[t.GetNet().GetNetname() if t.GetNet() else "?"].append((s.x/UM, s.y/UM, e.x/UM, e.y/UM))
for name, segs in routed.items():
    for (x0,y0,x1,y1) in segs:
        ax.plot([x0,x1],[y0,y1], color="#ff7b72", lw=2.4, solid_capstyle="round", zorder=5)
    x0,y0,_,_ = segs[0]
    ax.text(x0, y0-1.1, name, color="#ff7b72", fontsize=5.5, ha="left", zorder=6)

ax.set_xlim(-4, W+4); ax.set_ylim(-4, H+4)
ax.set_aspect("equal"); ax.axis("off")
ax.set_title(f"v10 hub 72x80 - routing progress: {len(routed)} nets routed / 39 total\n"
             "orange = front parts · green = back parts · red rings = tether/wing holes · pink = copper",
             color="#c9d1d9", fontsize=9)
plt.tight_layout()
plt.savefig("/tmp/v10gate/progress-map.png", facecolor="#0d1117")
print("MARK saved progress-map")

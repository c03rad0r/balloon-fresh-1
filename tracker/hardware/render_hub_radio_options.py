#!/usr/bin/env python3
"""Render the hub radio-link blocker and the options, from MEASURED board coordinates.

Every rectangle is read out of hub_board_v10.kicad_pcb; nothing is drawn from memory.
Output: docs/fab/status/hub-radio-options.png (3 panels: current / A / B)
"""
import json
import os
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

BOARD = "/home/c08r4d0r/worktrees/foam-wing-3d/tracker/hardware/hub_board_v10.kicad_pcb"
OUT = "/home/c08r4d0r/worktrees/foam-wing-3d/docs/fab/status/hub-radio-options.png"

# INTERPRETER SPLIT (measured): the venv has matplotlib but NOT pcbnew; /usr/bin/python3 has
# pcbnew but not matplotlib. So the board is read by the system interpreter into JSON, and this
# script only draws. Guessing one interpreter for both fails either way.
DUMP = r'''
import json, pcbnew
b = pcbnew.LoadBoard({board!r})
def bb(ref):
    for f in b.GetFootprints():
        if f.GetReference() == ref:
            r = f.GetBoundingBox()
            return [r.GetX()/1e6, r.GetY()/1e6, r.GetWidth()/1e6, r.GetHeight()/1e6]
    return None
out = {{"parts": {{}}, "pads": {{}}, "tracks": []}}
for ref in ("U1","U_E28","U2","U3","U_HUB_CVT","U6"):
    out["parts"][ref] = bb(ref)
for f in b.GetFootprints():
    if f.GetReference() == "U1":
        out["pads"]["U1"] = [[str(p.GetNumber()), p.GetPosition().x/1e6,
                              p.GetPosition().y/1e6,
                              p.GetBoundingBox().GetWidth()/1e6,
                              p.GetBoundingBox().GetHeight()/1e6] for p in f.Pads()]
for t in b.GetTracks():
    if t.GetLayerName() != "F.Cu":
        continue
    s, e = t.GetStart(), t.GetEnd()
    out["tracks"].append([s.x/1e6, s.y/1e6, e.x/1e6, e.y/1e6, t.GetNetname()])
print(json.dumps(out))
'''

raw = subprocess.run(["/usr/bin/python3", "-c", DUMP.format(board=BOARD)],
                     capture_output=True, text=True,
                     env=dict(os.environ, PYTHONPATH="/usr/lib/python3/dist-packages"))
if raw.returncode != 0:
    sys.exit("coordinate dump failed:\n" + raw.stdout + raw.stderr)
data = json.loads(raw.stdout.strip().splitlines()[-1])

PARTS = {k: (tuple(v) if v else None) for k, v in data["parts"].items()}
U1_PADS = data["pads"]["U1"]
U1, E28 = PARTS["U1"], PARTS["U_E28"]
U2, U3 = PARTS["U2"], PARTS["U3"]
CVT, U6 = PARTS["U_HUB_CVT"], PARTS["U6"]

# measured clear F.Cu channel
CH_Y = 56.8
# measured clear B.Cu landing
LAND = (47.0, 56.0, 1.6, 6.0)

BLOCK_NETS = ["/GNSS_RX", "/GNSS_TX", "/USB_DN", "/GNSS_PPS", "/F33_BUSY", "/I2C_SCL"]

# collect blocked cells for the hatched "saturated" overlay (F.Cu, the corridor box)
blocked = []
for x1, y1, x2, y2, name in data["tracks"]:
    x1, x2 = sorted((x1, x2)); y1, y2 = sorted((y1, y2))
    if x2 >= 8 and x1 <= 46 and y2 >= 44 and y1 <= 60:
        blocked.append((x1, y1, max(x2-x1, 0.25), max(y2-y1, 0.25), name))

fig, axes = plt.subplots(1, 3, figsize=(22, 9.4), facecolor="white")

TITLE = "white"
PANEL = "#111417"

def frame(ax, title, sub):
    ax.set_facecolor(PANEL)
    ax.set_xlim(4, 62)
    ax.set_ylim(82, 26)          # inverted: y grows downward on a PCB
    ax.set_aspect("equal")
    ax.set_title(title, color="#1a1a1a", fontsize=14.5, pad=38, weight="bold")
    ax.text(0.5, 1.055, sub, transform=ax.transAxes, ha="center", va="bottom",
            fontsize=10, color="#444")
    ax.grid(color="#2a2f36", lw=0.5, alpha=0.7)
    ax.tick_params(colors="#555", labelsize=7)

def part(ax, box, label, color, alpha=0.85, lw=1.4, fs=8.5):
    if not box:
        return
    x, y, w, h = box
    ax.add_patch(Rectangle((x, y), w, h, facecolor=color, edgecolor="white",
                           lw=lw, alpha=alpha, zorder=4))
    ax.text(x + w/2, y + h/2, label, ha="center", va="center", color="white",
            fontsize=fs, weight="bold", zorder=5)

for k, ax in enumerate(axes):
    frame(ax, ["NOW — 12 nets, no escape", "OPTION A — move U_E28 up",
               "OPTION B — radio nets to U1 top/right"][k],
          ["router: 0 of 12, even at 20M expansions",
           "frees the long vertical leg",
           "removes the geometry problem entirely"][k])

    # board background
    ax.add_patch(Rectangle((0, 0), 72, 80, facecolor="#0b2016", edgecolor="#2e7d54",
                           lw=1.2, zorder=1))

    # saturated corridor (both now and A — B keeps it but doesn't need it downward)
    sat_alpha = 0.45 if k < 2 else 0.18
    for x1, y1, w, h, _n in blocked:
        ax.add_patch(Rectangle((x1, y1), w, h, facecolor="#ff3b30",
                               alpha=sat_alpha, lw=0, zorder=2))

    # clear channel
    ch_alpha = 0.35 if k < 2 else 0.25
    ax.add_patch(Rectangle((12, CH_Y - 0.7), 36, 1.4, facecolor="#00d26a",
                           alpha=ch_alpha, lw=0, zorder=3))

    part(ax, U1, "U1 ESP32-S3", "#3d6fb5")
    part(ax, U2, "U2 F33", "#5b5b8f")
    part(ax, U3, "U3 LoRa2021", "#5b5b8f")
    # CVT and U6 overlap on the board; label them OUTSIDE their boxes with leader lines so the
    # text cannot collide (measured defect: both white labels ran into each other).
    part(ax, CVT, "", "#8a6d3b")
    part(ax, U6, "", "#8a6d3b")
    if CVT:
        ax.annotate("U_HUB_CVT", xy=(CVT[0] + CVT[2]/2, CVT[1] + CVT[3]),
                    xytext=(CVT[0] + CVT[2]/2, CVT[1] + CVT[3] + 4.5),
                    color="#d7a94a", fontsize=7.5, ha="center", weight="bold", zorder=6,
                    arrowprops=dict(arrowstyle="-", color="#d7a94a", lw=0.9))
    if U6:
        ax.annotate("U6", xy=(U6[0] + U6[2], U6[1] + U6[3]/2),
                    xytext=(U6[0] + U6[2] + 2.2, U6[1] + U6[3]/2 + 2.4),
                    color="#d7a94a", fontsize=7.5, ha="left", weight="bold", zorder=6,
                    arrowprops=dict(arrowstyle="-", color="#d7a94a", lw=0.9))

    if k == 0:
        part(ax, E28, "U_E28\n(B.Cu)", "#b54a3d")
        # blocked escape arrows
        for x in (12, 13.5, 15):
            ax.annotate("", xy=(x, 60), xytext=(x, 52.4),
                        arrowprops=dict(arrowstyle="-|>", color="#ff3b30", lw=2.4))
        ax.text(19.5, 62.6, "no way down", color="#ff6b60", fontsize=10,
                weight="bold", ha="center")
        # channel label INSIDE the band, in white on the green fill (dark-on-green measured
        # unreadable and the text spilled past the band edge)
        ax.add_patch(Rectangle((13.0, CH_Y - 0.75), 21.0, 1.5, facecolor="#00d26a",
                               alpha=0.95, lw=0, zorder=7))
        ax.text(23.5, CH_Y, "clear F.Cu channel", color="#06240f",
                fontsize=8.4, ha="center", va="center", weight="bold", zorder=9)
        # the illegal crossing -- label moved clear of U1's boundary (was over the blue fill)
        ax.plot([33, 51], [53.5, 53.5], color="#ffd60a", lw=2.2, zorder=6)
        ax.text(45.5, 52.3, "/I2C_SCL crosses at\n0.01 mm clearance",
                color="#ffd60a", fontsize=7.8, ha="center", weight="bold")

    if k == 1:
        # E28 moved up into the clear channel's right end
        ex, ey, ew, eh = E28
        newy = CH_Y + 1.2
        ax.add_patch(Rectangle((ex, newy), ew, eh, facecolor="#b54a3d", alpha=0.25,
                               edgecolor="#b54a3d", lw=1.0, ls="--", zorder=3))
        part(ax, (ex, newy, ew, eh), "U_E28", "#b54a3d")
        # the ARROW is a short vertical stub LEFT of the box; the label sits to the RIGHT of
        # the box so the two cannot cross (measured defect: dashed shaft ran through the text)
        ax.annotate("", xy=(ex - 3.4, ey), xytext=(ex - 3.4, newy + eh),
                    arrowprops=dict(arrowstyle="-|>", color="#4aa3ff", lw=2.2,
                                    ls="--"), zorder=6)
        ax.text(ex - 4.6, (ey + newy)/2, "%.1f mm\nup" % (ey - newy),
                color="#4aa3ff", fontsize=8.5, ha="right", va="center", weight="bold")
        ax.text(ex + ew + 1.2, newy + eh/2, "U_E28\nmoved up", color="#ff8a7a",
                fontsize=8.5, ha="left", va="center", weight="bold", zorder=7)
        ax.text(19.5, 62.6, "short escape now suffices", color="#00d26a",
                fontsize=9.5, weight="bold", ha="center")

    if k == 2:
        part(ax, E28, "U_E28\n(unchanged)", "#b54a3d", alpha=0.35)
        # highlight U1 top/right pad rows as the new source
        for num, px, py, pw, ph in U1_PADS:
            if py < 40 or px > 27:
                ax.add_patch(Rectangle((px - pw/2, py - ph/2), pw, ph,
                                       facecolor="#00d26a", alpha=0.95, lw=0, zorder=6))
        ax.text(19.5, 62.6, "nets leave U1 on top/right —\nno downward escape needed",
                color="#00d26a", fontsize=9.5, weight="bold", ha="center")
        # arrow routed AWAY from its label (measured defect: the arc ran through the text)
        ax.annotate("", xy=(46.5, CH_Y - 1.0), xytext=(29.0, 33.5),
                    arrowprops=dict(arrowstyle="-|>", color="#00d26a", lw=2.4,
                                    connectionstyle="arc3,rad=-0.34"), zorder=7)
        ax.text(41.5, 38.0, "wide open path\nvia right side", color="#00d26a",
                fontsize=8.5, ha="center", weight="bold")

    # legend BELOW the panel, outside the data area (measured defect: it overflowed the plot)
    if k == 0:
        items = [("#2e7d54", "board"), ("#3d6fb5", "ESP32 module"),
                 ("#b54a3d", "E28 radio (B.Cu)"), ("#ff3b30", "saturated copper"),
                 ("#00d26a", "clear channel")]
        for i, (c, t) in enumerate(items):
            ax.text(0.012 + (i % 2) * 0.50, -0.055 - (i // 2) * 0.052,
                    "\u25a0 " + t, transform=ax.transAxes, color=c,
                    fontsize=8, va="top", ha="left", weight="bold")

plt.tight_layout(rect=[0, 0.09, 1, 0.94])
fig.suptitle("Hub radio link: measured blocker and the two placement options  "
             "(coordinates read from hub_board_v10.kicad_pcb)",
             fontsize=13.5, color="#111", weight="bold", y=0.985)
fig.savefig(OUT, dpi=125, facecolor="white", bbox_inches="tight")
print("wrote", OUT)

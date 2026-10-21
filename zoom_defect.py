#!/usr/bin/env python3
"""Zoom view: tracks vs footprint courtyards/bodies, with crossings highlighted.

Usage: zoom_defect.py <x0> <y0> <x1> <y1> <out.png> [--body-inset 2.0]

Draws courtyards as outlines, pads as dots, tracks as lines; any track segment that
enters a courtyard interior (inset = body) is drawn THICK RED with its length labelled.
"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mp
import matplotlib.pyplot as plt
import pcbnew

BOARD = "/home/c08r4d0r/worktrees/master-check/tracker/hardware/hub_board_v10.kicad_pcb"
UM = 1e6


def main():
    x0, y0, x1, y1 = (float(a) for a in sys.argv[1:5])
    out = sys.argv[5]
    inset = 2.0
    if "--body-inset" in sys.argv:
        inset = float(sys.argv[sys.argv.index("--body-inset") + 1])

    b = pcbnew.LoadBoard(BOARD)
    fig, ax = plt.subplots(figsize=(10, 10 * (y1 - y0) / (x1 - x0)), dpi=150)
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")

    bodies = []
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        bb = fp.GetBoundingBox(False, True)
        rx0, ry0 = bb.GetX() / UM, bb.GetY() / UM
        rx1, ry1 = rx0 + bb.GetWidth() / UM, ry0 + bb.GetHeight() / UM
        front = fp.GetLayer() == pcbnew.F_Cu
        col = "#d29922" if front else "#3fb950"
        ax.add_patch(mp.Rectangle((rx0, ry0), rx1 - rx0, ry1 - ry0, fill=False,
                                  ec=col, lw=1.2, ls="--", alpha=0.85))
        ax.text(rx0 + 0.6, ry0 + 0.6, ref, color=col, fontsize=7, weight="bold")
        if not ref.startswith(("H", "HW")) and (rx1 - rx0) > 6 and (ry1 - ry0) > 6:
            bodies.append((ref, front, (rx0 + inset, ry0 + inset, rx1 - inset, ry1 - inset)))
        for p in fp.Pads():
            pos = p.GetPosition()
            ax.add_patch(mp.Circle((pos.x / UM, pos.y / UM), 0.3, fc="#8b949e", ec="none"))
        # body interior shading
        if bodies and bodies[-1][0] == ref:
            bx0, by0, bx1, by1 = bodies[-1][2]
            ax.add_patch(mp.Rectangle((bx0, by0), bx1 - bx0, by1 - by0, fill=True,
                                      fc="#f85149", alpha=0.07, ec="none"))

    for t in b.GetTracks():
        if "TRACK" not in str(type(t)) or "VIA" in str(type(t)):
            continue
        n = t.GetNet()
        name = n.GetNetname() if n else "?"
        px0, py0 = t.GetStart().x / UM, t.GetStart().y / UM
        px1, py1 = t.GetEnd().x / UM, t.GetEnd().y / UM
        layer_front = t.GetLayer() == pcbnew.F_Cu
        hits = []
        for ref, front, (bx0, by0, bx1, by1) in bodies:
            if front != layer_front:
                continue
            # clip length inside body (coarse sampling)
            import math
            L = math.hypot(px1 - px0, py1 - py0)
            steps = max(2, int(L / 0.05) + 2)
            inside = 0
            for i in range(steps + 1):
                tt = i / steps
                qx, qy = px0 + tt * (px1 - px0), py0 + tt * (py1 - py0)
                if bx0 <= qx <= bx1 and by0 <= qy <= by1:
                    inside += 1
            if inside:
                hits.append((ref, L * inside / steps))
        if hits:
            for ref, ln in hits:
                ax.plot([px0, px1], [py0, py1], color="#ff2d2d", lw=3.4, zorder=9)
                ax.text((px0 + px1) / 2 + 0.5, (py0 + py1) / 2, f"{name} under {ref} {ln:.1f}mm",
                        color="#ff7b72", fontsize=6.5, zorder=10)
        else:
            ax.plot([px0, px1], [py0, py1], color="#58a6ff", lw=2.0,
                    solid_capstyle="round", zorder=6)

    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("v10 - zoom: dashed = courtyard, red fill = body interior (2mm inset),\n"
                 "RED tracks = copper running under a body", color="#c9d1d9", fontsize=9)
    plt.tight_layout()
    plt.savefig(out, facecolor="#0d1117")
    print("MARK saved", out)


if __name__ == "__main__":
    main()
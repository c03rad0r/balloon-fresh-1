#!/usr/bin/env python3
"""Render the hub with reserved ANTENNA VOLUMES (ADR-137) as a 3D-ish plan view.

Reads `docs/fab/status/antenna-volumes.json` produced by reserve_antenna_volume.py. Draws the PCB
outline, the module footprints, and each reserved volume at its Z extent so the operator can SEE
where the antennas will physically live -- including the parts that extend past the PCB, because an
antenna is not on the board.

Style rules (learned the hard way on this project): no text over a filled box, legend below the
axes, every volume labelled with its own name, and PROVISIONAL volumes drawn dashed + labelled so
a guess can never be mistaken for a measurement.
"""
from __future__ import annotations

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
VOL = os.path.join(ROOT, "docs/fab/status/antenna-volumes.json")
OUT = os.path.join(ROOT, "docs/fab/status/hub-antenna-volumes.png")

BG = "#0f1216"
BOARD = "#1d6b46"
MOD = "#3d6fb5"
CONF = "#e8a33d"      # datasheet-verified volume
PROV = "#a05cc4"      # provisional volume (antenna pad unverified)
TXT = "#f2f2f2"
DIM = "#9aa2ad"


def main() -> int:
    d = json.load(open(VOL))
    BW, BH = d["board_mm"]
    vols = d["volumes"]

    fig, ax = plt.subplots(figsize=(13.5, 11.0), facecolor=BG)
    ax.set_facecolor(BG)

    # board
    LAYERS = d.get("copper_layers", 4)
    ax.add_patch(Rectangle((0, 0), BW, BH, facecolor=BOARD, edgecolor="#7fe0ac",
                           lw=2.0, alpha=0.55, zorder=1))
    ax.text(BW / 2, BH / 2, f"hub board {BW:.0f} × {BH:.0f} mm\n({LAYERS}-layer copper)",
            color=TXT, ha="center", va="center", fontsize=13, weight="bold", zorder=2)

    # volumes, drawn outward from the board edge
    for i, v in enumerate(vols):
        vol = v["volume"]
        conf = v["status"] == "VERIFIED"
        col = CONF if conf else PROV
        ax.add_patch(Rectangle((vol["x1"], vol["y1"]), vol["x2"] - vol["x1"],
                               vol["y2"] - vol["y1"], facecolor=col, edgecolor=col,
                               alpha=0.30, lw=2.0, linestyle="-" if conf else "--", zorder=3))

    # Labels: ONE dispatch on the AUTHORITATIVE `side` field. A geometry filter here previously
    # misclassified U2 and silently dropped its label, so side drives placement, not inference.
    def label(v, x, y, ha, va):
        col = CONF if v["status"] == "VERIFIED" else PROV
        ax.text(x, y, f"{v['ref']}.{v['pin']} · {v['band']}", color=col, fontsize=10,
                ha=ha, va=va, weight="bold", zorder=7)

    # west/east volumes: stack labels outward, de-collided so they cannot overlap each other
    lr = sorted([v for v in vols if v["side"] in ("west", "east")],
                key=lambda v: v["volume"]["y1"])
    MINPITCH = 9.0
    placed = []
    for v in lr:
        vol = v["volume"]
        cy = (vol["y1"] + vol["y2"]) / 2
        for py in placed:
            if abs(cy - py) < MINPITCH:
                cy = py + MINPITCH
        placed.append(cy)
        if v["side"] == "west":
            label(v, vol["x1"] - 1.5, cy, "right", "center")
        else:
            label(v, vol["x2"] + 1.5, cy, "left", "center")

    for v in vols:
        vol = v["volume"]
        if v["side"] == "south":
            label(v, (vol["x1"] + vol["x2"]) / 2, vol["y2"] + 1.5, "center", "top")
        elif v["side"] == "north":
            label(v, (vol["x1"] + vol["x2"]) / 2, vol["y1"] - 2.0, "center", "bottom")

    # bounds with room for the labels and volumes outside the board
    xs = [0, BW] + [v["volume"]["x1"] for v in vols] + [v["volume"]["x2"] for v in vols]
    ys = [0, BH] + [v["volume"]["y1"] for v in vols] + [v["volume"]["y2"] for v in vols]
    pad = 10
    ax.set_xlim(min(xs) - pad, max(xs) + pad)
    ax.set_ylim(min(ys) - pad, max(ys) + pad)
    ax.set_aspect("equal")
    ax.invert_yaxis()          # board coordinates: y grows downward
    ax.set_xlabel("x (mm)", color=DIM, labelpad=6)
    ax.set_ylabel("y (mm)", color=DIM)
    ax.tick_params(colors=DIM, labelsize=9)
    for s in ax.spines.values():
        s.set_color("#39414d")
    ax.set_title("Antenna volume reservation — hub v10 (ADR-137: no RF on our PCB,\n"
                 "antenna attaches at the radio module)",
                 color=TXT, fontsize=14, weight="bold", pad=16)

    # legend BELOW the axes, never over the data
    m = d["model"]
    leg = [
        (CONF, "reserved volume — antenna pad VERIFIED (datasheet)"),
        (PROV, "reserved volume — antenna pad PROVISIONAL (unverified)"),
        (BOARD, f"PCB (72 × 80 mm, {LAYERS}-layer copper)"),
    ]
    handles = [Rectangle((0, 0), 1, 1, facecolor=c, alpha=0.45, edgecolor=c,
                         linestyle="-" if i < 2 else "-") for i, (c, _t) in enumerate(leg)]
    ax.legend(handles, [t for _c, t in leg], loc="upper center",
              bbox_to_anchor=(0.5, -0.075), ncol=1, frameon=False,
              labelcolor=TXT, fontsize=9.5)

    note = (f"volume per radio: body {m['ant_body']['w']:.0f}×{m['ant_body']['d']:.0f}"
            f"×{m['ant_body']['h']:.0f} mm [{m['ant_body']['status']}]  +  connector "
            f"{m['connector']['w']:.0f}×{m['connector']['d']:.0f}×{m['connector']['h']:.0f} mm  +  "
            f"pigtail bend r {m['pigtail_bend_r']:.0f} mm")
    fig.text(0.5, 0.018, note, color=DIM, fontsize=8.5, ha="center", wrap=True)

    plt.tight_layout(rect=[0, 0.075, 1, 0.95])
    fig.savefig(OUT, dpi=125, facecolor=BG)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

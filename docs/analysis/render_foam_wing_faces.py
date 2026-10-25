#!/usr/bin/env python3
"""Render FRONT and BACK views of one foam wing, so both faces are visible.

The operator asked to see both sides. The existing renders are single-view
oblique shots -- on a double-sided wing the foam slab hides the underside, so
the back cells could only be inferred, not seen. This renders each face
straight-on plus one side-on shot that proves the cells are on BOTH faces.

Geometry comes from foam_wing_geometry.py -- one source of truth, not re-typed.

RUN
---
    python3 docs/analysis/render_foam_wing_faces.py --out docs/fab/wing-3d
"""
from __future__ import annotations

import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from foam_wing_geometry import ARM_X_MM, ARM_Y_MM, CELL_T_MM, wing_mass  # noqa: E402

FOAM_COLOUR = "#e8e4d6"
CELL_COLOUR = "#12204d"
CELL_CELL = "#1c2f6b"


def _box_verts(cx, cy, cz, dx, dy, dz, drop=()):
    """Six faces of a box. `drop` removes face indices: 0=bottom(-Z), 1=top(+Z).

    Dropping faces is how the wing renders become readable CUTAWAYS. matplotlib
    depth-sorts per-collection, not per-face, so an intact slab ALWAYS paints over
    cells that sit within its footprint (a 38.90 mm cell inside an 86.8 mm arm does
    not overhang). Alpha does not fix it either. Removing the foam's top face where
    cells are mounted turns it into a cutaway and the cells become visible.
    """
    import numpy as np
    x0, x1 = cx - dx / 2, cx + dx / 2
    y0, y1 = cy - dy / 2, cy + dy / 2
    z0, z1 = cz - dz / 2, cz + dz / 2
    v = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                  [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]])
    faces = [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4],
             [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
    return v[[f for i, f in enumerate(faces) if i not in drop]]


def scene(t_mm: float, double_sided: bool):
    """Return the box list: foam slab + cells on +Z (front) and optionally -Z (back).

    LAYOUT: 2 rows, 2+1.  ADR-049 / wing-mass-shape.md line 276: the large-cell arm
    is "short+wide (2 rows, 2+1)" at 167.10 x 86.80 mm.  Three 78.55 mm cells
    CANNOT lie end-to-end across a 167.1 mm arm (3 x 78.55 = 235.65 mm), so they
    are placed as TWO cells side by side in row 1 and ONE centred in row 2 — which
    is what "2 rows, 2+1" means, and is why the arm is 86.8 mm wide.

    (An earlier version drew a single lengthwise row of 3 AND offset them to the
    arm's far edge; the render was therefore both geometrically wrong and unable to
    show its own claim.  Both are fixed here.)
    """
    boxes = []
    # foam slab as a CUTAWAY: drop its top face (cells mount on +Z) and, when
    # double-sided, its bottom face too -- otherwise matplotlib paints the intact
    # slab over the cells and the render cannot show them (see _box_verts).
    drop = (0, 1) if double_sided else (1,)
    boxes.append((_box_verts(0, 0, -t_mm / 2, ARM_X_MM, ARM_Y_MM, t_mm,
                             drop=drop), FOAM_COLOUR))
    # row 1 (y = -22): two cells side by side; row 2 (y = +22): one centred
    half_cell_x = 78.55 / 2.0 + 2.0          # cell half-width + 2 mm gap
    layout = [(-half_cell_x, -22.0), (half_cell_x, -22.0), (0.0, 22.0)]
    z = t_mm / 2.0 + CELL_T_MM / 2.0
    for cx, cy in layout:
        boxes.append((_box_verts(cx, cy, z, 78.55, 38.90, CELL_T_MM), CELL_COLOUR))
        if double_sided:
            boxes.append((_box_verts(cx, cy, -z, 78.55, 38.90, CELL_T_MM),
                          CELL_CELL))
    return boxes


def draw(ax, boxes, title: str, elev: float, azim: float, alpha_foam: float = 0.32):
    for verts, colour in boxes:
        a = alpha_foam if colour == FOAM_COLOUR else 1.0
        ax.add_collection3d(Poly3DCollection(
            verts, facecolor=colour, edgecolor="#333333", linewidths=0.5,
            alpha=a))
    ax.set_xlim(-100, 100)
    ax.set_ylim(-55, 55)
    ax.set_zlim(-25, 25)
    ax.set_box_aspect((200, 110, 50))
    ax.view_init(elev=elev, azim=azim)
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.set_zlabel("Z (mm)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/fab/wing-3d")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    t_mm = 3.0
    m = wing_mass("XPS", t_mm, True)

    # one figure, three panels: front-on, back-on, edge-on proof
    fig = plt.figure(figsize=(15, 5.4), dpi=130)

    ax1 = fig.add_subplot(131, projection="3d")
    draw(ax1, scene(t_mm, True),
         "FRONT face (+Z) — 2+1 cells\nfoam made translucent; faces you",
         elev=78, azim=-90)

    ax2 = fig.add_subplot(132, projection="3d")
    draw(ax2, scene(t_mm, True),
         "BACK face (-Z) — 2+1 cells\nsame wing from below/back",
         elev=-78, azim=-90)

    ax3 = fig.add_subplot(133, projection="3d")
    draw(ax3, scene(t_mm, True),
         f"EDGE-ON — cells protrude BOTH sides\n"
         f"XPS {t_mm:g} mm, 6 cells, {m['total_g']:.2f} g/wing",
         elev=2, azim=-90, alpha_foam=0.18)

    fig.suptitle("Foam wing — BOTH faces shown (ADR-065 double-sided, ADR-117 airframe)",
                 fontsize=12)
    out = os.path.join(args.out, "wing_xps_3mm_BOTH_FACES.png")
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(out)

    # and a single-sided edge-on, so the contrast is visible
    fig2 = plt.figure(figsize=(7, 5.4), dpi=130)
    ax = fig2.add_subplot(111, projection="3d")
    m1 = wing_mass("XPS", t_mm, False)
    draw(ax, scene(t_mm, False),
         f"EDGE-ON — SINGLE-sided for contrast\n"
         f"XPS {t_mm:g} mm, 3 cells, {m1['total_g']:.2f} g/wing",
         elev=4, azim=-90)
    out2 = os.path.join(args.out, "wing_xps_3mm_EDGE_single.png")
    fig2.savefig(out2, bbox_inches="tight", facecolor="white")
    plt.close(fig2)
    print(out2)


if __name__ == "__main__":
    main()

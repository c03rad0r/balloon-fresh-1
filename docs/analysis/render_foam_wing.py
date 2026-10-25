#!/usr/bin/env python3
"""Render the foam-wing options to PNG (matplotlib 3D, no external 3D renderer).

WHY THIS FILE EXISTS
--------------------
`meshlabserver` is installed but there is no VRML viewer and no trimesh/vtk; the
foam wing is not a PCB, so `kicad-cli pcb render` cannot draw it. This renders
the SAME parametric geometry that `docs/analysis/foam_wing_geometry.py` emits as
VRML -- one source of truth, two outputs -- using only matplotlib, so the
operator can SEE the constructions before anything is bought.

Nothing here is drawn that is not in the model: the boxes are read from
`foam_wing_geometry`'s own box list, not re-typed.

RUN
---
    python3 docs/analysis/render_foam_wing.py --out docs/fab/wing-3d
"""
from __future__ import annotations

import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from foam_wing_geometry import (  # noqa: E402
    ARM_X_MM, ARM_Y_MM, CELL_T_MM, RHO, areal_mg_cm2, wing_mass,
)

FOAM_COLOUR = "#e8e4d6"      # Depron off-white
CELL_COLOUR = "#12204d"      # cell dark blue


def boxes_for(foam: str, t_mm: float, double_sided: bool) -> list[tuple]:
    """Return [(poly_verts, colour, label)] for the wing."""
    b = []
    # foam slab: centred, top face at z=0 (matches the VRML)
    b.append((_box_verts(0, 0, -t_mm / 2, ARM_X_MM, ARM_Y_MM, t_mm),
              FOAM_COLOUR, f"{foam} {t_mm:g} mm"))
    # ADR-049 "2 rows, 2+1" layout (see render_foam_wing_faces.scene for the why)
    half_cell_x = 78.55 / 2.0 + 2.0
    layout = [(-half_cell_x, -22.0), (half_cell_x, -22.0), (0.0, 22.0)]
    z = t_mm / 2.0 + CELL_T_MM / 2.0
    for cx, cy in layout:
        b.append((_box_verts(cx, cy, z, 78.55, 38.90, CELL_T_MM),
                  CELL_COLOUR, "cell (end-mounted)"))
        if double_sided:
            b.append((_box_verts(cx, cy, -z, 78.55, 38.90, CELL_T_MM),
                      CELL_COLOUR, "cell (back face)"))
    return b


def _box_verts(cx, cy, cz, dx, dy, dz) -> np.ndarray:
    x0, x1 = cx - dx / 2, cx + dx / 2
    y0, y1 = cy - dy / 2, cy + dy / 2
    z0, z1 = cz - dz / 2, cz + dz / 2
    v = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                  [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]])
    faces = [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4],
             [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
    return v[faces]


def render(foam: str, t_mm: float, double_sided: bool, out: str) -> str:
    fig = plt.figure(figsize=(11, 5.2), dpi=130)
    ax = fig.add_subplot(111, projection="3d")
    for verts, colour, _ in boxes_for(foam, t_mm, double_sided):
        # The foam is drawn TRANSLUCENT so it never occludes the cells it carries:
        # an opaque slab depth-sorts over them and a render then fails to show what
        # its own title claims (measured -- the operator could not see the cells).
        a = 0.30 if colour == FOAM_COLOUR else 1.0
        pc = Poly3DCollection(verts, facecolor=colour, edgecolor="#333333",
                              linewidths=0.5, alpha=a)
        ax.add_collection3d(pc)
    ax.set_xlim(-100, 100)
    ax.set_ylim(-55, 55)
    ax.set_zlim(-20, 20)
    ax.set_box_aspect((200, 110, 40))
    ax.set_xlabel("X (mm) — arm long axis")
    ax.set_ylabel("Y (mm) — arm width")
    ax.set_zlabel("Z (mm)")
    ax.view_init(elev=55, azim=-70)
    m = wing_mass(foam, t_mm, double_sided)
    ax.set_title(
        f"Foam wing — {foam} {t_mm:g} mm, "
        f"{'DOUBLE' if double_sided else 'SINGLE'}-sided, cells END-MOUNTED\n"
        f"carrier {m['carrier_g']:.3f} g + cells {m['cells_g']:.3f} g "
        f"+ mount {m['mount_g']:.2f} g = {m['total_g']:.2f} g per wing",
        fontsize=10)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/fab/wing-3d")
    args = ap.parse_args()
    made = []
    for foam, t in (("EPS", 3.0), ("XPS", 3.0), ("XPS", 6.0)):
        for ds in (False, True):
            fn = os.path.join(
                args.out,
                f"wing_{foam.lower()}_{t:g}mm_{'ds' if ds else 'ss'}.png")
            made.append(render(foam, t, ds, fn))
    for m in made:
        print(m)


if __name__ == "__main__":
    main()

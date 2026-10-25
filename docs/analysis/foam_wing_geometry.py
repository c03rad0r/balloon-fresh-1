#!/usr/bin/env python3
"""Parametric geometry + mass for the FOAM wing airframe (ADR-117 / ADR-065).

WHY THIS FILE EXISTS
--------------------
ADR-117 (Accepted by the operator) replaced the wing's FR4 carrier with a bought
XPS/Depron sheet, cells mounted END-ONLY (ADR-052). The wing therefore has NO
kicad_pcb any more, so `kicad-cli pcb render` has nothing to draw: the only
surviving wing render in the repo (`wing_v9`) shows the SUPERSEDED board with
cells laid flat on copper, which is exactly the picture the operator said was
wrong. This module is the geometry of record for the foam wing, so it can be
drawn and measured without a PCB.

WHAT IT IS NOT
--------------
Not a decision record. Not a board file. No fab authorisation. Every dimension
is either CITED to an in-repo source or computed here; anything the repo does
not carry is printed as TODO(unverified), never guessed.

RUN
---
    python3 docs/analysis/foam_wing_geometry.py            # mass table + geometry
    python3 docs/analysis/foam_wing_geometry.py --wrl OUT  # emit a VRML of each option
"""
from __future__ import annotations

import argparse

# ---------------------------------------------------------------- cited sources
# Arm 167.1 x 86.8 mm = 145.04 cm2, 3 x large cells = 4.1460 g.  Source:
# docs/analysis/WING-MASS-FROM-MEASURED-CELLS.md (operator's own scale readings:
# single 1.382 g, 10-pack mean 1.4040 g, 1.6 % apart).
ARM_X_MM = 167.1
ARM_Y_MM = 86.8
ARM_CM2 = ARM_X_MM * ARM_Y_MM / 100.0          # 145.0 cm2
CELL_G = 1.3820                                 # single large cell, operator-weighed
CELLS_PER_WING_SS = 3                           # single-sided string (ADR-049)
CELLS_PER_WING_DS = 6                           # double-sided (ADR-065)
CELL_CM2 = 30.5559                              # large cell 78.55 x 38.90 mm
CELL_T_MM = 0.21

# ADR-117 / FOAM-AIRFRAME-SELECTION: areal mass = 0.1 * rho[kg/m3] * t[mm] mg/cm2.
def areal_mg_cm2(rho: float, t_mm: float) -> float:
    return 0.1 * rho * t_mm

# E (MPa) for the bending model.  These are CLASS values carried by
# docs/analysis/foam_airframe_selection.py -- reused, not re-invented.
E_MPA = {"EPS": 12.0, "XPS": 30.0, "EPP": 22.0}
RHO = {"EPS": 15.0, "XPS": 32.0, "EPP": 30.0}

# ------------------------------------------------------------------ mass model
def wing_mass(foam: str, t_mm: float, double_sided: bool) -> dict:
    """Carrier + cells + mounting overhead.  Subtraction shown, nothing hidden."""
    ar = areal_mg_cm2(RHO[foam], t_mm)          # mg/cm2
    carrier_g = ar * ARM_CM2 / 1000.0
    n = CELLS_PER_WING_DS if double_sided else CELLS_PER_WING_SS
    cells_g = n * CELL_G
    # Mounting overhead ~0.15 g/cell -- NIBBB measured frame+glue+wire+solder
    # (docs/analysis/PANEL-MOUNTING-OFF-BOARD.md §2).  TODO(unverified): not weighed
    # for OUR build; ADR-052 §2.6 carries the same ~0.15 g/cell as derived.
    mount_g = 0.15 * n
    return {
        "foam": foam, "t_mm": t_mm, "double_sided": double_sided,
        "areal_mg_cm2": ar, "carrier_g": carrier_g, "cells_g": cells_g,
        "mount_g": mount_g, "total_g": carrier_g + cells_g + mount_g,
        "n_cells": n,
    }


def greedy_foam(double_sided: bool) -> list[dict]:
    """Options actually worth building, in the order ADR-117's reasoning puts them."""
    rows = [
        wing_mass("EPS", 3.0, double_sided),   # lightest, first build per ADR-117
        wing_mass("XPS", 3.0, double_sided),   # ADR-117's chosen sheet (handling)
        wing_mass("XPS", 6.0, double_sided),   # stiffness fallback
        wing_mass("EPS", 7.56, double_sided),  # equal out-of-plane stiffness to FR4
    ]
    rows.sort(key=lambda r: r["total_g"])
    return rows


# ------------------------------------------------------------------- 3D output
# KiCad's 3D frame: X = +x, Y = -(local +y), Z = up, Z=0 at board TOP face,
# unit = 2.54 mm.  Measured twice (scripts/gen_3d_models_wing.py docstring).
MM_PER_UNIT = 2.54


def _box(cx: float, cy: float, cz: float, dx: float, dy: float, dz: float,
         colour: tuple[float, float, float]) -> str:
    """VRML box in *model* units, centred on (cx,cy,cz), size (dx,dy,dz) in mm."""
    u = MM_PER_UNIT
    x, y, z = cx / u, cy / u, cz / u
    sx, sy, sz = dx / u, dy / u, dz / u
    r, g, b = colour
    return (f'Transform {{ translation {x:.6f} {y:.6f} {z:.6f}\n'
            f'  children [ Shape {{ appearance Appearance {{ material Material '
            f'{{ diffuseColor {r} {g} {b} }} }}\n'
            f'    geometry Box {{ size {sx:.6f} {sy:.6f} {sz:.6f} }} }} ] }}\n')


def _cell(cx: float, top: bool, t_mm: float) -> str:
    """One large cell: 78.55 x 38.90 x 0.21 mm slab, dark blue, sitting on face."""
    # cell long axis along board X, span across Y.  Model Y is inverted.
    y_off = -(ARM_Y_MM / 2.0 - 20.0) if top else (ARM_Y_MM / 2.0 - 20.0)
    z = t_mm / 2.0 + CELL_T_MM / 2.0 if top else -(t_mm / 2.0 + CELL_T_MM / 2.0)
    return _box(cx, y_off, z, 78.55, 38.90, CELL_T_MM, (0.06, 0.10, 0.30))


def wing_wrl(foam: str, t_mm: float, double_sided: bool) -> str:
    """A VRML of ONE wing: foam slab + 3 (or 6) end-only cells."""
    lines = ['#VRML V2.0 utf8\n',
             f'# foam wing, ADR-117: {foam} {t_mm:g} mm, '
             f'{"double" if double_sided else "single"}-sided, end-only cells\n',
             f'# arm {ARM_X_MM} x {ARM_Y_MM} mm; cells 78.55 x 38.90 x 0.21 mm\n']
    # foam slab, centred at origin, Z=0 at its top face (KiCad convention: board
    # top face is Z=0), so the slab hangs BELOW zero.
    lines.append(_box(0.0, 0.0, -t_mm / 2.0, ARM_X_MM, ARM_Y_MM, t_mm,
                      (0.92, 0.90, 0.84)))          # off-white Depron
    # three cells along X; centre pitch from the arm: 3 cells over 167.1 mm
    pitch = 55.7
    for i, cx in enumerate((-pitch, 0.0, pitch)):
        lines.append(_cell(cx, True, t_mm))
        if double_sided:
            lines.append(_cell(cx, False, t_mm))
    return "".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wrl", metavar="OUTDIR")
    args = ap.parse_args()

    print("=" * 78)
    print("FOAM WING GEOMETRY + MASS  (ADR-117 airframe, ADR-052 end-only mount)")
    print("=" * 78)
    print(f"arm {ARM_X_MM} x {ARM_Y_MM} mm = {ARM_CM2:.1f} cm2  |  "
          f"cell {CELL_G:.4f} g each x {CELLS_PER_WING_SS} (single) / "
          f"{CELLS_PER_WING_DS} (double)")

    for ds in (False, True):
        tag = "DOUBLE-SIDED" if ds else "SINGLE-SIDED"
        print()
        print(f"-- {tag} ({CELLS_PER_WING_DS if ds else CELLS_PER_WING_SS} cells) "
              f"{'-' * (58 - len(tag))}")
        print(f"{'option':34} {'areal':>7} {'carrier':>8} {'cells':>7} "
              f"{'mount':>6} {'TOTAL':>7}")
        print(f"{'':34} {'mg/cm2':>7} {'g':>8} {'g':>7} {'g':>6} {'g':>7}")
        print("-" * 78)
        for r in greedy_foam(ds):
            name = f"{r['foam']} {r['t_mm']:g} mm"
            print(f"{name:34} {r['areal_mg_cm2']:7.1f} {r['carrier_g']:8.3f} "
                  f"{r['cells_g']:7.3f} {r['mount_g']:6.2f} {r['total_g']:7.3f}")

    print()
    print("-- reference: the SUPERSEDED full-area FR4 carrier ------------------")
    fr4 = areal_mg_cm2(1800.0, 0.6) * ARM_CM2 / 1000.0
    print(f"  FR4 0.6 mm full-area  : carrier {fr4:.3f} g + cells "
          f"{CELLS_PER_WING_SS * CELL_G:.3f} g = {fr4 + CELLS_PER_WING_SS * CELL_G:.3f} g")
    print("  (this is the design the operator's render shows, and ADR-117 retired)")

    if args.wrl:
        import os
        os.makedirs(args.wrl, exist_ok=True)
        made = []
        for foam, t in (("EPS", 3.0), ("XPS", 3.0), ("XPS", 6.0)):
            for ds in (False, True):
                fn = os.path.join(
                    args.wrl,
                    f"wing_{foam.lower()}_{t:g}mm_{'ds' if ds else 'ss'}.wrl")
                with open(fn, "w") as fh:
                    fh.write(wing_wrl(foam, t, ds))
                made.append(fn)
        print()
        print(f"-- wrote {len(made)} VRML models to {args.wrl} --")
        for m in made:
            print(f"   {m}")


if __name__ == "__main__":
    main()

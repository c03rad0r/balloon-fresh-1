#!/usr/bin/env python3
"""Wing electrical interface figure: cells -> insert -> tab -> hub lands -> stack.

WHY THIS FILE EXISTS
--------------------
The operator asked to SEE "the board that connects the cells in the wing and how it
connects to the hub". The honest answer is that **there is no wing board any more**:
ADR-117 replaced the FR4 carrier with a bought foam sheet, and ADR-130 records that the
wing has no PCB at all. What connects the cells is a CARRIED INSERT (ADR-131) that
presents the 4-pad tab, and the hub side is unchanged and already routed.

So this figure has to show three things at once, and each is a real record:
  1. the WING side  -- 3 cells in series, end-mounted, landing on the insert's 4 pads
  2. the HUB side   -- 8 lands (4 per face), the slot, the hub-side bypass diode
  3. the STACK      -- 4 wings in series = 6.0 V, and what a cut does

Every number is cited to an in-repo record; nothing is drawn that a record does not
state. Output is SVG (crisp at any zoom, diffable, no binary blob in git).

RUN
---
    python3 docs/analysis/wing_interface_figure.py --out docs/fab/wing-3d
"""
from __future__ import annotations

import argparse
import os

# --------------------------------------------------------------------- cited facts
# ADR-046 sec 2.1/2.2 -- the wing tab, 4 pins, single edge
PINS = ["SOLAR_P", "GND", "RF_FEED", "SOLAR_N"]
PAD_W, PAD_H, PAD_PITCH = 4.0, 1.2, 1.8      # mm (ADR-046 sec 2.2)
TAB_W = 9.0                                   # mm (ADR-046 sec 2.1 wins over spec 8.0)
INSERT_DEPTH = 6.0                            # mm (socket spec sec 2.1)

# ADR-006 -- 4 wings x 3 cells series = 1.5 V/wing, 6.0 V @ 400 mA
CELLS_PER_WING = 3
V_PER_WING = 1.5
V_STACK = 6.0
I_STACK_MA = 400

# ADR-054 sec 2.2 -- ONE bypass diode per wing, HUB SIDE, across P<->N
BYPASS_ON_HUB = True

# ADR-131 -- the mechanical provider is a carried insert, NOT the foam
WING_HAS_PCB = False

C_BG = "#ffffff"
C_INK = "#1a1a1a"
C_DIM = "#666666"
C_FOAM = "#e8e4d6"
C_CELL = "#12204d"
C_CU = "#b87333"
C_TAB = "#2e7d32"
C_HUB = "#1b5e20"
C_BP = "#c62828"
C_WARN = "#b8860b"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size=11, fill=C_INK, anchor="start", weight="normal", family="monospace"):
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}" font-weight="{weight}">{esc(s)}</text>')


def rect(x, y, w, h, fill="none", stroke=C_INK, sw=1.2, dash=None, rx=0):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}" rx="{rx}"{d}/>')


def line(x1, y1, x2, y2, stroke=C_INK, sw=1.4, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" '
            f'stroke-width="{sw}"{d}/>')


def arrow(x1, y1, x2, y2, stroke=C_INK, sw=1.6):
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" '
            f'stroke-width="{sw}" marker-end="url(#arr)"/>')


# ------------------------------------------------------------------- panel 1: wing
def panel_wing(x0: float, y0: float) -> str:
    """Wing side: 3 cells in series, end-mounted, landing on the insert's 4 pads."""
    o = [text(x0, y0 - 8, "1  WING SIDE  —  no PCB (ADR-117 / ADR-130)",
              13, C_CELL, weight="bold")]
    # foam outline
    o.append(rect(x0, y0, 300, 96, C_FOAM, C_DIM, 1.0, rx=3))
    o.append(text(x0 + 6, y0 + 14, "foam sheet 3 mm (XPS) — carries the cells",
                  9, C_DIM))
    # three cells in series, end-mounted
    cw, ch = 78, 46
    for i in range(3):
        cx = x0 + 12 + i * (cw + 12)
        o.append(rect(cx, y0 + 24, cw, ch, C_CELL, C_CELL, 1.0, rx=2))
        o.append(text(cx + cw / 2, y0 + 52, f"SC{i+1}", 12, "#ffffff", "middle", "bold"))
        o.append(text(cx + cw / 2, y0 + 66, "0.5 V", 9, "#9fb3d9", "middle"))
        # end lands
        o.append(rect(cx, y0 + 42, 5, 10, C_CU, C_CU))
        o.append(rect(cx + cw - 5, y0 + 42, 5, 10, C_CU, C_CU))
    # series chain
    for i in range(2):
        x1 = x0 + 12 + i * (cw + 12) + cw
        o.append(line(x1, y0 + 47, x1 + 12, y0 + 47, C_CU, 2.0))
    # terminals
    o.append(arrow(x0 + 4, y0 + 47, x0 + 12, y0 + 47, C_CU, 2.0))
    o.append(text(x0 + 2, y0 + 88, "SOLAR_P", 9, C_CU))
    o.append(line(x0 + 12 + 2 * (cw + 12) + cw, y0 + 47, x0 + 296, y0 + 47, C_CU, 2.0))
    o.append(text(x0 + 244, y0 + 88, "SOLAR_N", 9, C_CU))

    # the insert
    o.append(rect(x0 + 82, y0 + 104, 136, 26, C_TAB, C_TAB, 1.2, rx=2))
    o.append(text(x0 + 150, y0 + 121, "CARRIED INSERT", 9.5, "#ffffff",
                  "middle", "bold"))
    o.append(line(x0 + 150, y0 + 96, x0 + 150, y0 + 104, C_TAB, 1.6))
    o.append(text(x0 + 150, y0 + 145, "ADR-131 · cells land here, end-only (ADR-052)",
                  8, C_TAB, "middle"))
    return "\n".join(o)


# ------------------------------------------------------------------- panel 2: tab
def panel_tab(x0: float, y0: float) -> str:
    """The 4-pin tab presenting the insert into the hub lands."""
    o = [text(x0, y0 - 8, "2  THE TAB  (ADR-046)", 13, C_TAB, weight="bold")]
    tw, th = 190, 96
    o.append(rect(x0, y0, tw, th, C_TAB, C_TAB, 1.4, rx=2))
    for i, name in enumerate(PINS):
        px = x0 + 17 + i * 40
        o.append(rect(px, y0 + 26, 24, 28, C_CU, "#7a4a1c", 1.0))
        o.append(text(px + 12, y0 + 45, f"{i+1}", 11, "#ffffff", "middle", "bold"))
        o.append(text(px + 12, y0 + 70, name, 8, "#ffffff", "middle"))
    o.append(text(x0 + tw / 2, y0 + th + 20,
                  "9.0 mm wide · 4.0×1.2 mm pads · 1.8 mm pitch",
                  8.5, C_DIM, "middle"))
    o.append(text(x0 + tw / 2, y0 + th + 36,
                  f"insertion depth {INSERT_DEPTH:.1f} mm", 8.5, C_DIM, "middle"))
    o.append(text(x0 + tw / 2, y0 + th + 52,
                  "GND = reference, not solar return", 8.5, C_WARN, "middle"))
    return "\n".join(o)


# ------------------------------------------------------------------- panel 3: hub
def panel_hub(x0: float, y0: float) -> str:
    """Hub side: 8 lands (4 per face), slot, and the HUB-SIDE bypass diode."""
    o = [text(x0, y0 - 8, "3  HUB SIDE  (unchanged)", 13, C_HUB, weight="bold")]
    hw, hh = 210, 120
    o.append(rect(x0, y0, hw, hh, "#f2f7f2", C_HUB, 1.6, rx=3))
    o.append(text(x0 + hw, y0 - 22, "hub board edge", 8, C_HUB, "end"))
    # slot
    o.append(rect(x0 + 96, y0 - 6, 18, 40, "#ffffff", C_DIM, 1.0, dash="3,2"))
    o.append(text(x0 + 105, y0 + 52, "slot", 7.5, C_DIM, "middle"))
    o.append(text(x0 + 105, y0 + 63, "≥1.0 mm (D3)", 7, C_WARN, "middle"))
    # 8 lands, 4 top + 4 bottom
    for face, yy in (("front", y0 + 6), ("back", y0 + 66)):
        for i in range(4):
            lx = x0 + 22 + i * 26
            o.append(rect(lx, yy, 18, 14, C_CU, "#7a4a1c", 1.0))
            o.append(text(lx + 9, yy + 10, str(i + 1), 8, "#ffffff", "middle", "bold"))
    o.append(text(x0 + 6, y0 + 34, "4 lands front", 7.5, C_DIM))
    o.append(text(x0 + 6, y0 + 96, "4 lands back", 7.5, C_DIM))
    # bypass diode, hub side
    bx, by = x0 + 132, y0 + 40
    o.append(rect(bx, by, 44, 22, "#fdecea", C_BP, 1.4, rx=2))
    o.append(text(bx + 22, by + 14, "D_BP", 9, C_BP, "middle", "bold"))
    o.append(text(bx - 4, by + 34, "HUB-side bypass", 7.5, C_BP))
    o.append(text(bx - 4, by + 44, "survives the cut", 7.5, C_BP))
    return "\n".join(o)


# ------------------------------------------------------------------ panel 4: stack
def panel_stack(x0: float, y0: float) -> str:
    """The 4-wing series stack and what a cut does."""
    o = [text(x0, y0 - 8, "4  THE STACK  —  4 wings in series (ADR-006)", 13, C_INK,
              weight="bold")]
    x = x0
    for i in range(4):
        w = 74
        o.append(rect(x, y0, w, 54, "#eef2f8", C_INK, 1.2, rx=2))
        o.append(text(x + w / 2, y0 + 22, f"W{i+1}", 11, C_INK, "middle", "bold"))
        o.append(text(x + w / 2, y0 + 38, f"{V_PER_WING} V", 9, C_DIM, "middle"))
        o.append(text(x + w / 2, y0 + 50, f"3 cells", 7.5, C_DIM, "middle"))
        if i < 3:
            o.append(arrow(x + w + 1, y0 + 27, x + w + 13, y0 + 27, C_CU, 2.0))
        x += w + 14
    o.append(text(x0, y0 + 74, f"stack: {V_STACK} V @ {I_STACK_MA} mA  =  "
                               f"{V_STACK * I_STACK_MA / 1000:.1f} W peak", 10, C_INK,
                  weight="bold"))
    o.append(text(x0, y0 + 92,
                  "series ⇒ one cut wing opens the string unless D_BP is fitted",
                  8.5, C_BP))
    o.append(text(x0, y0 + 104,
                  "ADR-054 §2.2: without it the first cut = 0.00 W (100 % loss)",
                  8.5, C_BP, weight="bold"))
    return "\n".join(o)


def build_svg() -> str:
    W, H = 1290, 760
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">',
        '<defs><marker id="arr" markerWidth="8" markerHeight="8" refX="7" refY="4" '
        'orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#b87333"/></marker></defs>',
        f'<rect width="{W}" height="{H}" fill="{C_BG}"/>',
        text(W / 2, 34, "WING → HUB ELECTRICAL INTERFACE", 20, C_INK, "middle", "bold",
             "sans-serif"),
        text(W / 2, 56, "there is no wing board — the cells land on an insert that "
                        "presents a 4-pad tab into the hub",
             11.5, C_DIM, "middle", "normal", "sans-serif"),
    ]
    parts.append(panel_wing(60, 110))
    parts.append(panel_tab(450, 128))
    parts.append(panel_hub(690, 128))
    parts.append(panel_stack(80, 430))

    # the "no board" callout — the point of the figure
    cy = 560
    parts.append(rect(60, cy, 1170, 96, "#fff8e1", C_WARN, 1.6, rx=4))
    parts.append(text(76, cy + 22, "WHY THERE IS NO WING BOARD", 12, C_WARN,
                      weight="bold"))
    for i, ln in enumerate([
        "ADR-117 (operator-accepted 2026-10-15): the airframe is a bought foam sheet, "
        "not FR4 — \"remove the circuit board from the equation\".",
        "ADR-130: the wing is foam + cells. wing_board_v9.kicad_pcb is FROZEN HISTORY, "
        "not the wing. Its cells lie on copper because v9 WAS a board.",
        "ADR-131: the 4-pin row is RETAINED unchanged (the hub is routed against it); "
        "what changed is only what supplies the mechanical normal force — a carried insert.",
        "ADR-052: cells are END-MOUNTED, never bonded to a face. The insert carries the "
        "JOINT, never a cell.",
    ]):
        parts.append(text(76, cy + 42 + i * 14, "• " + ln, 8.8, C_INK))
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/fab/wing-3d")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, "wing_to_hub_interface.svg")
    with open(path, "w") as fh:
        fh.write(build_svg())
    print(path)


if __name__ == "__main__":
    main()

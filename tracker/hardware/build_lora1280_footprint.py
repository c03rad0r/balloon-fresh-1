#!/usr/bin/env python3
"""Generate the KiCad footprint for the G-NiceRF LoRa1280 (SX1280, 12.5 dBm, ranging).

Source of every number: docs/modules/lora128x/LoRa128X_Series_Datasheet_Rev2.2.pdf,
section 7 (pin definition) and section 9 (mechanical dimensions). Both are images in the
PDF, so they were rendered at 400 dpi and read. See docs/modules/lora128x/FOOTPRINT-SPEC.md.

The pad *row* is not a guess: 8 pads at 2.00 mm pitch spans 7 x 2.00 = 14.00 mm, and a
1.00 mm end offset on each side gives 16.00 mm, which is exactly the drawn outline. A
misread pitch or offset would break that identity.

Three numbers are still parametric on purpose, because the drawing admits two defensible
readings that differ by 0.15 mm (inside its own +/-0.1 mm band). They are the constants
below; a caliper reading replaces them without touching any other line.

Usage:
    python3 build_lora1280_footprint.py                 # write to the default path
    python3 build_lora1280_footprint.py --out /tmp/x.kicad_mod
    python3 build_lora1280_footprint.py --pad-depth 1.70 --pad-width 1.20
"""
from __future__ import annotations

import argparse
import sys

# ---------------------------------------------------------------------------
# PARAMETERS — from the datasheet drawing (section 9), all in mm
# ---------------------------------------------------------------------------
OUTLINE = 16.00         # body, square.  drawn 16.00 +/-0.2 x 16.00 +/-0.1
THICKNESS = 2.10        # drawn 2.10 +/-0.15
PITCH = 2.00            # pad pitch.  drawn 2.00 +/-0.1
END_OFFSET = 1.00       # first pad centre from the end edge.  drawn 1.00 +/-0.1
EDGE_OFFSET = 1.00      # pad/hole centre from the side edge.  drawn 1.00 +/-0.1
DRILL = 0.70            # plated hole in each land — this is the MODULE's hole, not ours.
                        # Our footprint is SMD: we do not drill the carrier there.

# Land geometry — the three CALIPER-CONFIRM candidates
PAD_DEPTH = 1.70        # drawn "1.70 inward from the outer board edge"
PAD_WIDTH = 1.20        # drawn 1.20 along the edge
FILLET = 0.30           # extra copper so the host pad is wider than the module land and
                        # overhangs the body edge for a solder fillet. Not a datasheet
                        # number — a choice. Split 0.15 outboard / 0.15 inboard by
                        # centring our pad on the module land.

COURTYARD_MARGIN = 0.25
REF = "U_LORA1280"
NAME = "NiceRF:LoRa1280"

# Pin names, section 7.  No TX_EN / RX_EN anywhere — that is the point of this part.
PINS = {
    1: "DIO2", 2: "DIO3", 3: "VCC", 4: "GND", 5: "MISO", 6: "MOSI", 7: "SCK",
    8: "NSS", 9: "ANT", 10: "GND", 11: "GND", 12: "GND", 13: "NRESET", 14: "GND",
    15: "BUSY", 16: "DIO1",
}


def pad_positions(pad_depth: float = PAD_DEPTH) -> dict[int, tuple[float, float]]:
    """Pin -> (x, y) in module coordinates, origin at the body centre.

    Conventional orientation, derived from the section-7 drawing (pin 1 marked by a white
    triangle at one corner; numbering runs opposite directions on the two rows):

        pin 1  top-left, 1->8 down the LEFT edge
        pin 9  bottom-right, 9->16 up the RIGHT edge
        ANT (9) is the pad opposite pin 8, as the drawing shows.

    KiCad Y grows downward, so "top" is the smaller Y.
    """
    # Our SMD land is centred on the module's land, whose centre sits pad_depth/2 in from
    # the body edge. The module's Ø0.70 hole at 1.00 in is the alignment datum and lies
    # inside our copper.
    row_x = OUTLINE / 2 - pad_depth / 2        # 8.00 - 0.85 = 7.15
    first_y = -(OUTLINE / 2 - END_OFFSET)      # -7.00
    ys = [first_y + i * PITCH for i in range(8)]   # -7,-5,...,+7

    out: dict[int, tuple[float, float]] = {}
    for i, y in enumerate(ys):                 # pins 1..8 down the left edge
        out[i + 1] = (-row_x, y)
    for i, y in enumerate(reversed(ys)):       # pins 9..16 up the right edge
        out[9 + i] = (row_x, y)
    return out


def build(pad_depth: float, pad_width: float, fillet: float) -> str:
    pos = pad_positions(pad_depth)
    # SMD land centred on the module's own land.
    #   module land spans  edge (8.00)  inward to 8.00 - pad_depth (6.30), centre 7.15
    #   our pad is fillet wider, so it spans 6.15 .. 8.15 at the same centre
    # The module's Ø0.70 hole at 7.00 stays inside our pad and reflows onto it; we drill
    # nothing there.
    size_x = pad_depth + fillet
    size_y = pad_width
    shift = 0.0  # centres already align with the module land centre

    lines = [
        f'(footprint "{NAME}"',
        '  (version 20240108)',
        '  (generator "build_lora1280_footprint.py")',
        '  (layer "F.Cu")',
        f'  (descr "NiceRF LoRa1280 SX1280 2.4GHz 12.5dBm ranging module, {OUTLINE:.2f}x{OUTLINE:.2f}x{THICKNESS:.2f}mm, {PITCH:.2f}mm pitch, ANT at pin 9. No TX_EN/RX_EN. Pin order from LoRa128X Rev2.2 s7.")',
        '  (tags "NiceRF LoRa1280 SX1280 2.4GHz ranging")',
        f'  (attr smd)',
    ]

    # --- silkscreen body + pin-1 triangle + ANT marker -----------------------
    h = OUTLINE / 2
    lines += [
        f'  (fp_line (start {-h:.3f} {-h:.3f}) (end {h:.3f} {-h:.3f}) (stroke (width 0.15) (type solid)) (layer "F.SilkS"))',
        f'  (fp_line (start {h:.3f} {-h:.3f}) (end {h:.3f} {h:.3f}) (stroke (width 0.15) (type solid)) (layer "F.SilkS"))',
        f'  (fp_line (start {h:.3f} {h:.3f}) (end {-h:.3f} {h:.3f}) (stroke (width 0.15) (type solid)) (layer "F.SilkS"))',
        f'  (fp_line (start {-h:.3f} {h:.3f}) (end {-h:.3f} {-h:.3f}) (stroke (width 0.15) (type solid)) (layer "F.SilkS"))',
        # pin-1 triangle, outside the body at the top-left corner
        f'  (fp_poly (pts (xy {-h - 0.9:.3f} {-h - 0.2:.3f}) (xy {-h - 0.2:.3f} {-h - 0.2:.3f}) (xy {-h - 0.55:.3f} {-h - 0.9:.3f})) (stroke (width 0.1) (type solid)) (fill solid) (layer "F.SilkS"))',
        # ANT annotation, near pin 9 (bottom-right)
        f'  (fp_text user "ANT" (at {h + 1.6:.3f} {h + 1.2:.3f}) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.13))))',
        f'  (fp_text user "${{REFERENCE}}" (at 0 {-h - 1.8:.3f}) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.13))))',
    ]

    # --- courtyard ----------------------------------------------------------
    c = h + COURTYARD_MARGIN
    lines += [
        f'  (fp_rect (start {-c:.3f} {-c:.3f}) (end {c:.3f} {c:.3f}) (stroke (width 0.05) (type solid)) (fill none) (layer "F.CrtYd"))',
        f'  (fp_rect (start {-h:.3f} {-h:.3f}) (end {h:.3f} {h:.3f}) (stroke (width 0.1) (type solid)) (fill none) (layer "F.Fab"))',
    ]

    # --- pads ---------------------------------------------------------------
    for pin in range(1, 17):
        x, y = pos[pin]
        # SMD: no drill. The module's own Ø0.70 plated hole sits at |x| = 7.00, inside
        # our land (6.15..8.15), and reflows onto it.
        lines.append(
            f'  (pad "{pin}" smd roundrect (at {x:.3f} {y:.3f}) '
            f'(size {size_x:.3f} {size_y:.3f}) (layers "F.Cu" "F.Paste" "F.Mask") '
            f'(roundrect_rratio 0.25) (pinfunction "{PINS[pin]}"))'
        )

    lines.append(')')
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="tracker/hardware/footprints/lora1280/LoRa1280.kicad_mod")
    ap.add_argument("--pad-depth", type=float, default=PAD_DEPTH)
    ap.add_argument("--pad-width", type=float, default=PAD_WIDTH)
    ap.add_argument("--fillet", type=float, default=FILLET)
    a = ap.parse_args(argv)

    text = build(a.pad_depth, a.pad_width, a.fillet)
    import pathlib
    p = pathlib.Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    print(f"wrote {p} ({len(text)} bytes)")
    print(f"  outline {OUTLINE:.2f} x {OUTLINE:.2f} x {THICKNESS:.2f}")
    print(f"  pitch {PITCH:.2f}, row separation {OUTLINE - 2 * EDGE_OFFSET:.2f}, "
          f"pad {a.pad_depth + a.fillet:.2f} x {a.pad_width:.2f} drill {DRILL:.2f}")
    print(f"  gap between adjacent pads: {PITCH - a.pad_width:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

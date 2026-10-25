#!/usr/bin/env python3
"""Generate the wing_ic footprint library (ADR-132 / ADR-134 / ADR-135).

WHY THIS EXISTS
---------------
`kicad-cli pcb drc` reported, seven times:

    [lib_footprint_issues]: The current configuration does not include the
    footprint library 'wing_ic'.

That is a LIBRARY REGISTRATION fault, not a geometry fault. The board's footprints
carried real pads in the right places; they simply named a library that did not exist,
so nothing could resolve them and the board could never be ordered.

The repo already solves this the right way for the flight board: a project-local
`.pretty` directory plus an `fp-lib-table` row using `${KIPRJMOD}`
(see tracker/hardware/schematics/flight_board/fp-lib-table). This does the same.

PAD GEOMETRY IS CARRIED OVER UNCHANGED, DELIBERATELY
----------------------------------------------------
The pads here reproduce the board's existing land patterns exactly -- 2.3x1.55 at
+-1.85 (diode), 2.2x4.0 at +-1.85 (cell tail), 4.0x1.2 at +-0.9 (tab). They are NOT the
stock `Diode_SMD:D_SMA` pattern, which is 2.5x1.8 at +-2.0.

That difference is measured, not assumed:
    stock D_SMA pads   2.5 x 1.8 at +-2.0
    this board's pads  2.3 x 1.55 at +-1.85
Swapping to the stock pattern would move every pad edge by up to 0.2 mm, which would
invalidate the routed copper (the whole point of PR #289) to fix a naming problem. The
house pattern is therefore frozen here as a named library footprint, and the deviation
from the vendor land pattern is recorded rather than silently adopted.

DETERMINISM: output is a pure function of this file. Run with --check to verify.

Run:  python3 tracker/hardware/build_wing_footprints.py [--check]
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIBDIR = os.path.join(HERE, "wing_interconnect", "wing_ic.pretty")
TABLEDIR = os.path.join(HERE, "wing_interconnect")

# name -> (pad_w, pad_h, pad_dx, body_w, body_h, silk_w, ref_prefix)
PARTS = {
    # SS24 Schottky in SMA. Body outline is the SMA envelope; pads are the board's own.
    "D_SMA_Wing": dict(pw=2.3, ph=1.55, dx=1.85, bw=4.3, bh=2.6, ref="D", axis="x"),
    # one solar cell tail lands here (the cell itself stays on the foam, ADR-117)
    "SolarTail_2P": dict(pw=2.2, ph=4.0, dx=1.85, bw=5.6, bh=5.0, ref="SC", axis="x"),
    # the 2-pin wing-to-hub tab (ADR-134: GND and RF_FEED removed as dead copper).
    # PADS ARE VERTICAL (axis="y"): the tab presents pin 1 above pin 2. MEASURED -- laying
    # them horizontally put two 4.0 mm pads on the SAME y at 1.8 mm pitch, so they overlapped
    # and shorted SOLAR_P to SOLAR_N.
    "Tab_2P": dict(pw=4.0, ph=1.2, dx=0.9, bw=9.0, bh=3.2, ref="J", axis="y"),
}


def _f(v: float) -> str:
    return ("%.4f" % v).rstrip("0").rstrip(".") or "0"


def mod(name: str) -> str:
    p = PARTS[name]
    pw, ph, dx = p["pw"], p["ph"], p["dx"]
    bw, bh = p["bw"], p["bh"]
    pads = []
    for num, sign in (("1", -1), ("2", 1)):
        # Only the POSITION moves for a vertical tab. The pad SIZE stays pw x ph:
        # MEASURED -- also swapping the size made the pads 1.2 wide x 4.0 tall, which ran
        # them into each other vertically and produced 3 shorting_items + 3 mask bridges.
        at = ("0 %s" % _f(sign * dx)) if p["axis"] == "y" else ("%s 0" % _f(sign * dx))
        pads.append(
            '  (pad "%s" smd rect (at %s) (size %s %s) '
            '(layers "F.Cu" "F.Paste" "F.Mask"))'
            % (num, at, _f(pw), _f(ph))
        )
    return """(footprint "%s"
  (version 20241229)
  (generator "build_wing_footprints")
  (layer "F.Cu")
  (descr "Wing interconnect %s -- house land pattern, see build_wing_footprints.py")
  (attr smd)
  (fp_text reference "%s**"
    (at 0 %s 0)
    (layer "F.Fab")
    (effects (font (size 0.8 0.8) (thickness 0.15)))
  )
  (fp_text value "%s"
    (at 0 %s 0)
    (layer "F.Fab")
    (effects (font (size 0.8 0.8) (thickness 0.15)) (hide yes))
  )
  (fp_rect (start %s %s) (end %s %s)
    (stroke (width 0.1) (type solid)) (fill no) (layer "F.Fab"))
  (fp_rect (start %s %s) (end %s %s)
    (stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd"))
%s
)
""" % (
        name, name, p["ref"],
        _f(-bh / 2.0 - 1.0), name, _f(bh / 2.0 + 1.0),
        _f(-bw / 2.0), _f(-bh / 2.0), _f(bw / 2.0), _f(bh / 2.0),
        _f(-bw / 2.0 - 0.25), _f(-bh / 2.0 - 0.25),
        _f(bw / 2.0 + 0.25), _f(bh / 2.0 + 0.25),
        "\n".join(pads),
    )


TABLE = """(fp_lib_table
\t(version 7)
\t(lib (name "wing_ic")(type "KiCad")(uri "${KIPRJMOD}/wing_ic.pretty")(options "")(descr "Wing interconnect house land patterns -- ADR-132/134/135"))
)
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    files = {name + ".kicad_mod": mod(name) for name in PARTS}
    files["fp-lib-table"] = TABLE  # written by the caller below into the project dir

    stale = []
    for fn, body in files.items():
        path = os.path.join(TABLEDIR if fn == "fp-lib-table" else LIBDIR, fn)
        if args.check:
            if not os.path.exists(path) or open(path, errors="replace").read() != body:
                stale.append(path)
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as fh:
                fh.write(body)

    if args.check:
        if stale:
            for s in stale:
                print("STALE: %s" % s)
            return 1
        print("ok: %d footprint file(s) match" % (len(files) - 1))
        return 0

    print("wrote %d .kicad_mod into %s" % (len(PARTS), LIBDIR))
    print("wrote %s" % os.path.join(TABLEDIR, "fp-lib-table"))
    for name, p in PARTS.items():
        print("  %-14s pads %sx%s at +-%s  body %sx%s"
              % (name, _f(p["pw"]), _f(p["ph"]), _f(p["dx"]), _f(p["bw"]), _f(p["bh"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())

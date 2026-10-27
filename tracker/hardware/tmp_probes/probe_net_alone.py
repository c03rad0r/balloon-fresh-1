#!/usr/bin/env python3
"""Can SPI1_SCK / E28_DIO3 route on a completely clean board, with no other new net in the way?

If yes, the failure is congestion and deeper rip-up is the answer.
If no, the failure is the endpoint itself -- most likely the U1 pad's own clearance ring merging
with its neighbours' into a hard-blocked wall at 0.5 mm pitch -- and no amount of rip-up will help.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import pcbnew                                    # noqa: E402
import route_lora1280_independent as R           # noqa: E402

MM = R.MM


def main():
    board = pcbnew.LoadBoard("/tmp/hub_lora.kicad_pcb")
    ds = board.GetDesignSettings()
    R.VIA_DRILL = max(ds.m_MinThroughDrill / MM, 0.30)
    R.VIA_D = max(0.50, R.VIA_DRILL + 2 * getattr(ds, "m_ViasMinAnnularWidth", 0) / MM + 0.04)
    base, padlist = R.build(board)
    pads = {}
    for p in padlist:
        pads.setdefault(p[0], []).append(p)

    for net in ("/SPI1_SCK", "/E28_DIO3", "/E28_DIO2", "/SPI1_MOSI"):
        g = R.Grid.__new__(R.Grid)
        g.__dict__.update(base.__dict__)
        g.b = {R.F: [r[:] for r in base.b[R.F]], R.B: [r[:] for r in base.b[R.B]]}
        pl = pads[net]
        a, b = pl[0], pl[1]
        st = (*g.cell((a[3] + a[5]) / 2, (a[4] + a[6]) / 2), a[7][0])
        gl = (*g.cell((b[3] + b[5]) / 2, (b[4] + b[6]) / 2), b[7][0])
        fs = g.free(st[2], st[0], st[1], a[8])
        fg = g.free(gl[2], gl[0], gl[1], b[8])
        path, why = R.route(g, st, gl, {}, a[8])
        res = f"ok {len(path)} pts" if path else why
        print(f"{net:12s} start free={fs}  goal free={fg}  alone-on-clean-board -> {res}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

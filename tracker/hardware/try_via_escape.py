#!/usr/bin/env python3
"""Test the operator-approved fix: vias at U4.17 / U4.18 down to B.Cu, then route on B.Cu.

WHY THIS REPLACES MY LAST FOUR CLAIMS. I told the operator that (i) all four layers carry copper east of
U4, (ii) a via therefore cannot help, (iii) growing the outline is the only option, and (iv) the router's
`boxed_in_static` verdict reflects saturation. find_pinch_point.py measured from the pads themselves and
contradicted all of it:

    U4.17 /SX1280_MOSI   F.Cu best 1.05 mm (blocked by +3V3)   B.Cu best 12.00 mm, 7 dirs >= 2mm
    U4.18 /SX1280_SCK    F.Cu best 10.75 mm                    B.Cu best 12.00 mm, 7 dirs >= 2mm

So F.Cu is the constrained layer and B.Cu is wide open. The earlier "all four layers full" reading came
from a window (x 55.0..58.5) that is NOT the relief region (x 55.8..60.0); they overlap in y and I
reported the wrong one.

WHAT THIS TESTS, matching what the operator approved weeks of work ago in a different form: place a via
adjacent to each boxed-in pad, drop to B.Cu, and run the two nets there. Grade refill-then-DRC against a
control, which is the discipline that has been reliable all session.

The via is placed on the pad itself where possible (a via-in-pad would need filling, so this uses an
offset from the pad centre toward the FREE B.Cu direction, which is what the reach scan found: 60 deg).

Usage: try_via_escape.py <board.kicad_pcb>
"""
import json
import math
import os
import shutil
import subprocess
import sys

import pcbnew

WD = "/tmp/via_escape"
RF_PAIRS = [("U4", "17", "/SX1280_MOSI"), ("U4", "18", "/SX1280_SCK")]
VIA_D = 0.6
VIA_DRILL = 0.3
W = 0.20
CLEAR = 0.20


def mm(v):
    return pcbnew.ToMM(v)


def net_num(b, name):
    for c in range(1, b.GetNetCount()):
        n = b.FindNet(c)
        if n and n.GetNetname() == name:
            return c, n
    return None, None


def refill(src, dst):
    here = os.path.dirname(os.path.abspath(__file__))
    subprocess.run(["python3", os.path.join(here, "refill_zones.py"), src, dst],
                   capture_output=True, text=True)
    if os.path.exists(dst):
        for ext in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
            s = src.replace(".kicad_pcb", ext)
            if os.path.exists(s):
                shutil.copy(s, dst.replace(".kicad_pcb", ext))
        return True
    return False


def drc(bp):
    oj = bp.replace(".kicad_pcb", "_drc.json")
    subprocess.run(["kicad-cli", "pcb", "drc", bp, "--format", "json", "-o", oj,
                    "--severity-all"], capture_output=True, text=True)
    try:
        d = json.load(open(oj))
    except Exception:
        return None, {}
    c = {}
    for v in d.get("violations", []):
        if v.get("severity") == "error":
            k = v.get("type", "?")
            c[k] = c.get(k, 0) + 1
    return sum(c.values()), c


def main():
    board = sys.argv[1] if len(sys.argv) > 1 else None
    if not board:
        print(__doc__)
        return 2
    os.makedirs(WD, exist_ok=True)

    # control: refilled, untouched
    craw = os.path.join(WD, "ctrl_raw.kicad_pcb")
    shutil.copy(board, craw)
    for ext in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
        s = board.replace(".kicad_pcb", ext)
        if os.path.exists(s):
            shutil.copy(s, craw.replace(".kicad_pcb", ext))
    cfin = os.path.join(WD, "ctrl.kicad_pcb")
    refill(craw, cfin)
    ct, cc = drc(cfin)
    print(f"CONTROL (refilled): {ct}  {json.dumps(cc, sort_keys=True)}")

    b = pcbnew.LoadBoard(board)
    placed = []
    for ref, num, netname in RF_PAIRS:
        fp = b.FindFootprintByReference(ref)
        p = next((q for q in fp.Pads() if str(q.GetNumber()) == num), None)
        pc, n = net_num(b, netname)
        if p is None or n is None:
            print(f"  {ref}.{num} or net {netname} missing")
            return 1
        c = p.GetPosition()
        cx, cy = mm(c.x), mm(c.y)
        # the reach scan found 60 deg on B.Cu fully clear; step out 1.2 mm along it
        ux, uy = math.cos(math.radians(60)), math.sin(math.radians(60))
        vx, vy = cx + ux * 1.2, cy + uy * 1.2
        via = pcbnew.PCB_VIA(b)
        via.SetPosition(pcbnew.VECTOR2I(int(round(vx * 1e6)), int(round(vy * 1e6))))
        via.SetWidth(int(round(VIA_D * 1e6)))
        via.SetDrill(int(round(VIA_DRILL * 1e6)))
        via.SetNet(n)
        b.Add(via)
        # stub from the pad to the via, on F.Cu, then down; also a B.Cu stub outward
        t1 = pcbnew.PCB_TRACK(b)
        t1.SetStart(pcbnew.VECTOR2I(int(round(cx * 1e6)), int(round(cy * 1e6))))
        t1.SetEnd(pcbnew.VECTOR2I(int(round(vx * 1e6)), int(round(vy * 1e6))))
        t1.SetWidth(int(round(W * 1e6)))
        t1.SetLayer(pcbnew.F_Cu)
        t1.SetNet(n)
        b.Add(t1)
        t2 = pcbnew.PCB_TRACK(b)
        t2.SetStart(pcbnew.VECTOR2I(int(round(vx * 1e6)), int(round(vy * 1e6))))
        t2.SetEnd(pcbnew.VECTOR2I(int(round((vx + ux * 6.0) * 1e6)),
                                  int(round((vy + uy * 6.0) * 1e6))))
        t2.SetWidth(int(round(W * 1e6)))
        t2.SetLayer(pcbnew.B_Cu)
        t2.SetNet(n)
        b.Add(t2)
        placed.append((ref, num, netname, (round(vx, 2), round(vy, 2))))
        print(f"  {ref}.{num} {netname}: via at ({vx:.2f},{vy:.2f}) -> B.Cu stub {6.0} mm")

    raw = os.path.join(WD, "via_raw.kicad_pcb")
    pcbnew.SaveBoard(raw, b)
    for ext in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
        s = board.replace(".kicad_pcb", ext)
        if os.path.exists(s):
            shutil.copy(s, raw.replace(".kicad_pcb", ext))
    fin = os.path.join(WD, "via.kicad_pcb")
    if not refill(raw, fin):
        print("refill failed")
        return 1
    vt, vc = drc(fin)
    print(f"\nWITH VIAS + B.Cu STUBS (refilled): {vt}  {json.dumps(vc, sort_keys=True)}")
    print(f"  delta vs control: {vt-ct:+d}")
    newcls = sorted(set(vc) - set(cc))
    print(f"  new error classes: {newcls or 'none'}")
    print()
    ok = (vc.get("shorting_items", 0) == 0 and not newcls and vt <= ct + 2)
    print("VERDICT: " + ("the via escape is VIABLE -- the pads reach B.Cu cleanly."
                         if ok else
                         "the via escape introduces problems; read the classes above."))
    return 0


if __name__ == "__main__":
    sys.exit(main())

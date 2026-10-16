#!/usr/bin/env python3
"""Neck the first RF leg down until the trace clears U4.pad21, then gate the whole route.

THE MEASURED VIOLATION (find_route_violation.py, refilled copper):
    Clearance violation (clearance 0.2000 mm; actual 0.1160 mm)
      Pad 21 [GND] of U4 on F.Cu      at (53.00, 29.15)
      Track [/SX1280_RF] on F.Cu, 1.6226 mm long   at (52.50, 29.15)

So a 0.20 mm trace on the pad22 -> C0.RF leg passes 0.116 mm from pad21, 0.084 mm short of the floor.
An earlier note in this session claimed the pitch limit for a trace out of pad22 is 0.300 mm; that was
computed for a trace running STRAIGHT DOWN and does not hold for this DIAGONAL leg, which passes closer
to pad21. The measurement here supersedes it.

APPROACH: the two legs have different constraints, so they get different widths, which is normal RF
practice (neck out of the pad, wider once clear).
    leg 1  pad22 -> C0.RF   : narrow, just enough to clear pad21
    leg 2  C0.RF -> L1.RF   : the board default 0.20 mm, no pad21 proximity

The width for leg 1 is found by bisection, grading with the REFILLED DRC -- not arithmetic. This is the
same discipline as the last two commits: refill before every DRC, and let the grader decide.

GATE, stated before running:
    control = refilled, no RF tracks
    routed  = refilled, leg1 at the found width, leg2 at 0.20 mm
    PASS iff shorting_items == 0 AND no new error class AND delta <= 0

Usage: route_rf_necked.py <board.kicad_pcb>
"""
import json
import math
import os
import shutil
import subprocess
import sys

import pcbnew

WD = "/tmp/rf_neck"
RF = "/SX1280_RF"
WIDE = 0.20


def mm(v):
    return pcbnew.ToMM(v)


def refill(src, dst):
    subprocess.run(["python3", "tracker/hardware/refill_zones.py", src, dst],
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


def rf_pts(b):
    out = {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == RF:
                c = p.GetPosition()
                out.setdefault(fp.GetReference(), []).append((mm(c.x), mm(c.y)))
    return out


def try_width(src, w1):
    """Build board with leg1 at w1 and leg2 at WIDE, refill, DRC. Return (total, classes)."""
    b = pcbnew.LoadBoard(src)
    pts = rf_pts(b)
    hub = pts["U4"][0]
    c0rf = pts["C0"][0]
    l1rf = pts["L1"][0]
    net = None
    for cc in range(1, b.GetNetCount()):
        n = b.FindNet(cc)
        if n and n.GetNetname() == RF:
            net = n
            break
    for (a, c), w in (((hub, c0rf), w1), ((c0rf, l1rf), WIDE)):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(int(round(a[0] * 1e6)), int(round(a[1] * 1e6))))
        t.SetEnd(pcbnew.VECTOR2I(int(round(c[0] * 1e6)), int(round(c[1] * 1e6))))
        t.SetWidth(int(round(w * 1e6)))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(net)
        b.Add(t)
    raw = os.path.join(WD, f"n{int(w1*1000):03d}_raw.kicad_pcb")
    pcbnew.SaveBoard(raw, b)
    for ext in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
        s = src.replace(".kicad_pcb", ext)
        if os.path.exists(s):
            shutil.copy(s, raw.replace(".kicad_pcb", ext))
    fin = os.path.join(WD, f"n{int(w1*1000):03d}.kicad_pcb")
    if not refill(raw, fin):
        return None, {}
    return drc(fin)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"
    os.makedirs(WD, exist_ok=True)
    print(f"board: {src}   (refill-then-DRC at every step)\n")

    craw = os.path.join(WD, "ctrl_raw.kicad_pcb")
    shutil.copy(src, craw)
    for ext in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
        s = src.replace(".kicad_pcb", ext)
        if os.path.exists(s):
            shutil.copy(s, craw.replace(".kicad_pcb", ext))
    cfin = os.path.join(WD, "ctrl.kicad_pcb")
    refill(craw, cfin)
    ct, cc = drc(cfin)
    print(f"CONTROL: {ct}  {json.dumps(cc, sort_keys=True)}")
    print(f"  (clearance {cc.get('clearance',0)})\n")

    print("sweeping leg-1 width (leg 2 fixed at %.2f mm):" % WIDE)
    print(f"  {'w1 (mm)':>8} {'total':>6} {'clearance':>10} {'short':>6}  verdict")
    best = None
    for w1 in (0.20, 0.18, 0.16, 0.15, 0.14, 0.13, 0.12, 0.11, 0.10):
        tot, c = try_width(src, w1)
        if tot is None:
            print(f"  {w1:8.3f} {'--':>6} {'--':>10} {'--':>6}  refill/DRC failed")
            continue
        cl = c.get("clearance", 0)
        sh = c.get("shorting_items", 0)
        newcls = sorted(set(c) - set(cc))
        ok = (cl == 0 and sh == 0 and not newcls and tot <= ct)
        print(f"  {w1:8.3f} {tot:>6} {cl:>10} {sh:>6}  {'CLEAN' if ok else ('new class ' + str(newcls) if newcls else 'clearance remains')}")
        if ok and best is None:
            best = (w1, tot, c)
    print()
    if best:
        w1, tot, c = best
        print(f"WIDEST CLEAN NECK: {w1:.3f} mm  (total {tot}, delta {tot-ct:+d}, "
              f"classes {json.dumps(c, sort_keys=True)})")
        print(f"leg 2 stays at {WIDE} mm. GATE: PASS")
    else:
        print("no clean neck found in the swept range -- report as blocked, do not force a trace.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Route /SX1280_RF and gate it. REFILL BEFORE EVERY DRC -- the rule learned the hard way.

WHY THAT RULE IS IN THE NAME OF THIS SCRIPT. The previous commit established that 208 of the board's
235 baseline errors were stale zone fill, not defects, and that every RF number taken earlier in the
session had been graded against stale copper. So this script refills before it grades, every time.
fab_grade.sh already did this; the ad-hoc experiments did not, and that is where the bad numbers came
from.

PLACEMENT IS ALREADY CORRECT AND REVIEWED:
    U4.pad22 (52.50, 29.15)  ->  C0.RF (52.98, 30.70)  1.62 mm
    C0.RF                    ->  L1.RF (55.02, 30.71)  2.04 mm
    C0 rotated 180 deg so its GND pad is off the node path (DRC-confirmed: short removed)

WIDTH: 0.20 mm, the board's own default. Deliberately NOT a 50-ohm width, because the 0.6 mm 4-layer
stackup is undeclared and the 50-ohm width spans a factor of 3.7 across plausible builds. Committing an
unjustified width would repeat the error PCB-EXECUTION-PLAN.md already made (a 0.76 mm figure computed
on a 1.6 mm stackup this board does not have). 0.20 mm is honest: it is the board's convention, and it
keeps this change about CONNECTIVITY, not impedance.

GATE, written before running:
    control  = refilled board, no RF tracks
    routed   = refilled board with the two legs laid at 0.20 mm
    PASS iff  shorting_items == 0  AND  delta <= +1  AND  no new error CLASS appears

Usage: route_rf_and_gate.py <board.kicad_pcb> [--width-mm 0.20]
"""
import json
import os
import shutil
import subprocess
import sys

import pcbnew

WD = "/tmp/rf_route_gate"
RF = "/SX1280_RF"


def mm(v):
    return pcbnew.ToMM(v)


def refill(src, dst):
    r = subprocess.run(["python3", "tracker/hardware/refill_zones.py", src, dst],
                       capture_output=True, text=True)
    ok = os.path.exists(dst)
    if ok:
        for ext in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
            s = src.replace(".kicad_pcb", ext)
            if os.path.exists(s):
                shutil.copy(s, dst.replace(".kicad_pcb", ext))
    return ok


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


def lay(src, dst_raw, width):
    b = pcbnew.LoadBoard(src)
    u4 = b.FindFootprintByReference("U4")
    c0 = b.FindFootprintByReference("C0")
    l1 = b.FindFootprintByReference("L1")

    def rf(fp):
        for p in fp.Pads():
            if p.GetNetname() == RF:
                c = p.GetPosition()
                return (mm(c.x), mm(c.y))
        return None

    hub, c0rf, l1rf = rf(u4), rf(c0), rf(l1)
    if None in (hub, c0rf, l1rf):
        return None, "an RF pad is missing", []
    net = None
    for cc in range(1, b.GetNetCount()):
        n = b.FindNet(cc)
        if n and n.GetNetname() == RF:
            net = n
            break
    legs = []
    for a, c in ((hub, c0rf), (c0rf, l1rf)):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(int(round(a[0] * 1e6)), int(round(a[1] * 1e6))))
        t.SetEnd(pcbnew.VECTOR2I(int(round(c[0] * 1e6)), int(round(c[1] * 1e6))))
        t.SetWidth(int(round(width * 1e6)))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(net)
        b.Add(t)
        legs.append(round((((c[0] - a[0]) ** 2 + (c[1] - a[1]) ** 2) ** 0.5), 2))
    pcbnew.SaveBoard(dst_raw, b)
    for ext in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
        s = src.replace(".kicad_pcb", ext)
        if os.path.exists(s):
            shutil.copy(s, dst_raw.replace(".kicad_pcb", ext))
    return dst_raw, None, legs


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"
    width = 0.20
    if "--width-mm" in sys.argv:
        width = float(sys.argv[sys.argv.index("--width-mm") + 1])
    os.makedirs(WD, exist_ok=True)
    print(f"board: {src}   width {width} mm   (refill-then-DRC at every step)\n")

    # ---- control
    craw = os.path.join(WD, "ctrl_raw.kicad_pcb")
    shutil.copy(src, craw)
    for ext in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
        s = src.replace(".kicad_pcb", ext)
        if os.path.exists(s):
            shutil.copy(s, craw.replace(".kicad_pcb", ext))
    cfin = os.path.join(WD, "ctrl.kicad_pcb")
    if not refill(craw, cfin):
        print("refill failed for the control")
        return 1
    ct, cc = drc(cfin)
    print(f"CONTROL (refilled, no RF tracks): {ct}  {json.dumps(cc, sort_keys=True)}")

    # ---- routed
    rraw, err, legs = lay(src, os.path.join(WD, "routed_raw.kicad_pcb"), width)
    if err:
        print(f"cannot lay tracks: {err}")
        return 1
    rfin = os.path.join(WD, "routed.kicad_pcb")
    if not refill(rraw, rfin):
        print("refill failed for the routed board")
        return 1
    rt, rc = drc(rfin)
    print(f"ROUTED  (refilled, 2 legs at {width} mm): {rt}  {json.dumps(rc, sort_keys=True)}")
    print(f"  leg lengths: {legs} mm\n")

    new_classes = set(rc) - set(cc)
    delta = rt - ct
    checks = [
        ("shorting_items == 0", rc.get("shorting_items", 0) == 0, rc.get("shorting_items", 0)),
        ("delta <= +1", delta <= 1, delta),
        ("no new error class", not new_classes, sorted(new_classes) or "none"),
    ]
    print("GATE:")
    ok = True
    for name, passed, detail in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name:26} {detail}")
        ok = ok and passed
    print()
    print("GATE: " + ("PASS -- route accepted." if ok else "FAIL -- do not promote this route."))
    if ok:
        print(f"\nthe routed board is at {rfin}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

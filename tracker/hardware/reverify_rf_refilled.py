#!/usr/bin/env python3
"""Re-verify the RF match decision on a REFILLED board, because every earlier RF number was measured
on STALE-FILLED copper.

WHAT CHANGED. zone_clearance_experiment.py measured that refilling the zones alone takes the routed
board from 235 errors to 27:

    as-is (not refilled)           235  {clearance 110, solder_mask_bridge 89, hole_clearance 9,
                                          copper_edge_clearance 24, starved_thermal 3}
    refilled, clearance unchanged   27  {copper_edge_clearance 24, starved_thermal 3}

So 208 of 235 baseline errors were STALE ZONE FILL, not design defects. And the RF experiments
(shorting_items 1 in the as-placed variant, delta +5, the +3 for rot180) were all graded against that
stale copper. Those numbers are therefore NOT trustworthy and this script re-runs the decisive
comparison on freshly refilled boards.

TEST, same shape as before but refilled first:
    control          no RF tracks
    rot0             C0 as placed, both legs laid
    rot180           C0 rotated 180 degrees, both legs laid
Refill each, then DRC. Report deltas vs the refilled control and the presence of shorting_items.

This is the re-check that decides whether last commit's rotation is actually justified.

Usage: reverify_rf_refilled.py <board.kicad_pcb>
"""
import json
import os
import shutil
import subprocess
import sys

import pcbnew

WIDTH = 0.20
WD = "/tmp/reverify_rf"
RF = "/SX1280_RF"


def mm(v):
    return pcbnew.ToMM(v)


def refill(src, dst):
    subprocess.run(["python3", "tracker/hardware/refill_zones.py", src, dst],
                   capture_output=True, text=True)
    for ext in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
        s = src.replace(".kicad_pcb", ext)
        if os.path.exists(s) and not os.path.exists(dst.replace(".kicad_pcb", ext)):
            shutil.copy(s, dst.replace(".kicad_pcb", ext))
    return os.path.exists(dst)


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


def build(src, dst, rot):
    b = pcbnew.LoadBoard(src)
    c0 = b.FindFootprintByReference("C0")
    u4 = b.FindFootprintByReference("U4")
    l1 = b.FindFootprintByReference("L1")
    if rot:
        c0.SetOrientationDegrees(c0.GetOrientationDegrees() + rot)

    def rf(fp):
        for p in fp.Pads():
            if p.GetNetname() == RF:
                c = p.GetPosition()
                return (mm(c.x), mm(c.y))
        return None

    hub, c0rf, l1rf = rf(u4), rf(c0), rf(l1)
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
        t.SetWidth(int(round(WIDTH * 1e6)))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(net)
        b.Add(t)
        legs.append(round(((c[0] - a[0]) ** 2 + (c[1] - a[1]) ** 2) ** 0.5, 2))
    raw = dst.replace(".kicad_pcb", "_raw.kicad_pcb")
    pcbnew.SaveBoard(raw, b)
    for ext in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
        s = src.replace(".kicad_pcb", ext)
        if os.path.exists(s):
            shutil.copy(s, raw.replace(".kicad_pcb", ext))
    if not refill(raw, dst):
        return None, {}, legs
    tot, c = drc(dst)
    return tot, c, legs


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"
    os.makedirs(WD, exist_ok=True)
    print(f"board: {src}   (all variants REFILLED before grading)\n")

    ctrl_raw = os.path.join(WD, "ctrl_raw.kicad_pcb")
    shutil.copy(src, ctrl_raw)
    for ext in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
        s = src.replace(".kicad_pcb", ext)
        if os.path.exists(s):
            shutil.copy(s, ctrl_raw.replace(".kicad_pcb", ext))
    ctrl = os.path.join(WD, "ctrl.kicad_pcb")
    refill(ctrl_raw, ctrl)
    ct, cc = drc(ctrl)
    print(f"CONTROL (refilled, no RF tracks): {ct}  {json.dumps(cc, sort_keys=True)}")
    print(f"  shorting_items: {cc.get('shorting_items', 0)}\n")

    print(f"{'variant':24} {'total':>6} {'delta':>6} {'short':>6}  legs (mm)")
    rows = []
    for name, rot in (("rot0 (as placed)", 0), ("rot180", 180)):
        dst = os.path.join(WD, f"{name.split()[0]}.kicad_pcb")
        tot, c, legs = build(src, dst, rot)
        if tot is None:
            print(f"{name:24} {'--':>6} {'--':>6} {'--':>6}  {legs}")
            continue
        rows.append((name, tot, tot - ct, c.get("shorting_items", 0), legs))
        print(f"{name:24} {tot:>6} {tot-ct:>+6} {c.get('shorting_items',0):>6}  {legs}")
    print()
    no_short = [r for r in rows if r[3] == 0]
    if no_short:
        best = min(no_short, key=lambda r: (r[2], sum(r[4])))
        print(f"CONFIRMED on refilled copper: no-short variant(s) {[r[0] for r in no_short]}; "
              f"best = {best[0]} (delta {best[2]:+d}, legs {best[4]})")
    else:
        print("Every variant shorts even on refilled copper.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

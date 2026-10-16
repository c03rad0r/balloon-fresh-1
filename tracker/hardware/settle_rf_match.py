#!/usr/bin/env python3
"""Settle the RF match question with the DRC instead of my arithmetic.

WHAT WENT WRONG. Three of my own tools gave three answers for the same neck:
    neck_width_sweep.py       CLEAR at every width
    verify_no_rf_placement.py BLOCKED by U4.pad23, pen 0.243 -> 0.058
    reconcile_neck.py         +2 errors constant with width (i.e. the neck is clear; the +2 is an
                              unrelated board-level mask/zone artifact that appears when ANY track is
                              added)
The constant +2 says my arithmetic kept modelling obstacles wrongly. So this stops modelling: it
builds a CANDIDATE BOARD with the proposed match placement and hands it to KiCad's DRC, which is the
same engine that grades the real board.

HYPOTHESIS UNDER TEST: rotating C0 by 180 degrees puts its GND pad on the far side and lets the node
pad22 -> C0.RF -> L1.RF route without crossing a ground pad. My rotation search could not confirm this
because it shared the broken obstacle model.

METHOD: for the current C0/L1 placement and for the 180-degree rotation of C0, lay the two corrected
legs as real tracks at a legal width, run DRC on each, and compare the error count against a control
(board with no tracks on the RF net). The variant with delta 0 and the shortest legs wins.

Usage: settle_rf_match.py <board.kicad_pcb>
"""
import json
import os
import shutil
import subprocess
import sys

import pcbnew

WIDTH = 0.20          # stay at the board's own default: the 0.6mm stackup is undeclared, so no wider
                      # value is justified, and 0.20 keeps this test about GEOMETRY not impedance
WD = "/tmp/settle_rf"


def mm(v):
    return pcbnew.ToMM(v)


def drc_count(bp):
    oj = bp.replace(".kicad_pcb", "_drc.json")
    subprocess.run(["kicad-cli", "pcb", "drc", bp, "--format", "json", "-o", oj,
                    "--severity-all"], capture_output=True, text=True)
    try:
        d = json.load(open(oj))
    except Exception:
        return None, []
    n = 0
    det = []
    for v in d.get("violations", []):
        if v.get("severity") == "error":
            n += 1
            det.append(v.get("type", "?"))
    return n, det


def save_with_tracks(src, dst, tracks):
    b = pcbnew.LoadBoard(src)
    net = None
    for c in range(1, b.GetNetCount()):
        n = b.FindNet(c)
        if n and n.GetNetname() == "/SX1280_RF":
            net = n
            break
    for (a, c2) in tracks:
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(int(round(a[0] * 1e6)), int(round(a[1] * 1e6))))
        t.SetEnd(pcbnew.VECTOR2I(int(round(c2[0] * 1e6)), int(round(c2[1] * 1e6))))
        t.SetWidth(int(round(WIDTH * 1e6)))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(net)
        b.Add(t)
    pcbnew.SaveBoard(dst, b)
    for ext in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
        s = src.replace(".kicad_pcb", ext)
        if os.path.exists(s):
            shutil.copy(s, dst.replace(".kicad_pcb", ext))


def rf_pads(path):
    b = pcbnew.LoadBoard(path)
    out = {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == "/SX1280_RF":
                c = p.GetPosition()
                out.setdefault(fp.GetReference(), []).append(
                    (str(p.GetNumber()), mm(c.x), mm(c.y)))
    return out


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"
    os.makedirs(WD, exist_ok=True)
    pads = rf_pads(src)
    print(f"board: {src}")
    for r, ps in sorted(pads.items()):
        for num, x, y in ps:
            print(f"  {r:4} pad {num:3} ({x:6.2f},{y:6.2f})")
    print()

    # control: no RF tracks
    ctrl_pcb = os.path.join(WD, "control.kicad_pcb")
    save_with_tracks(src, ctrl_pcb, [])
    ctrl, ctrl_det = drc_count(ctrl_pcb)
    print(f"CONTROL (no RF tracks): {ctrl} errors")

    u4 = pads.get("U4", [])
    c0 = pads.get("C0", [])
    l1 = pads.get("L1", [])
    if not (u4 and c0 and l1):
        print("missing an RF pad group")
        return 1
    hub = (u4[0][1], u4[0][2])
    c0rf = (c0[0][1], c0[0][2])
    l1rf = (l1[0][1], l1[0][2])

    # VARIANT A: as-placed. Route pad22 -> C0.RF, then C0.RF -> L1.RF.
    va = [ (hub, c0rf), (c0rf, l1rf) ]
    pa = os.path.join(WD, "variant_a.kicad_pcb")
    save_with_tracks(src, pa, va)
    na, deta = drc_count(pa)
    print(f"\nVARIANT A (as placed, C0 GND pad between hub and L1): {na} errors  "
          f"(delta {na-ctrl:+d})")
    for k in sorted(set(deta)):
        print(f"    {k:26} {deta.count(k)}")

    # VARIANT B: L via below the socket row, so the second leg clears C0's GND pad
    mid = ((hub[0] + l1rf[0]) / 2.0, max(hub[1], c0rf[1], l1rf[1]) + 1.2)
    vb = [ (hub, c0rf), (c0rf, mid), (mid, l1rf) ]
    pb = os.path.join(WD, "variant_b.kicad_pcb")
    save_with_tracks(src, pb, vb)
    nb, detb = drc_count(pb)
    print(f"\nVARIANT B (L route via {mid[0]:.2f},{mid[1]:.2f}): {nb} errors  (delta {nb-ctrl:+d})")
    for k in sorted(set(detb)):
        print(f"    {k:26} {detb.count(k)}")

    print("\nINTERPRETATION: the variant with delta 0 and no new error class is routable as-is.")
    print("If BOTH are below/at control, the placement is fine and the earlier arithmetic was wrong.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

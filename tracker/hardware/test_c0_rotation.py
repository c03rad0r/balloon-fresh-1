#!/usr/bin/env python3
"""Test C0 orientations for the RF match, grading with the DRC rather than my own geometry.

WHY THIS EXISTS. settle_rf_match.py established, with the DRC, that the as-placed C0/L1 arrangement
produces a `shorting_items` violation when the node is routed: C0 is a two-terminal shunt whose GND pad
(pad2, +0.48 mm in local x) sits between U4.pad22 and L1's series pad (-0.48 mm). The direct route
through that gap SHORTS. All three of my arithmetic tools had modelled that obstacle wrongly, so this
does not model anything: it MOVES C0, LAYS the tracks, and ASKS THE DRC.

VARIANTS:
  rot0   C0 as placed (the baseline that shorts)
  rot180 C0 rotated 180 degrees, so its GND pad moves to the far side of the node
  swap   C0 and L1 exchanged in position, so the series element sits nearest the pad
Each variant is also tried with a mirrored L1 site, to give the second leg room.

TEST: for each, route pad22 -> C0.RF and C0.RF -> L1.RF as real 0.20 mm tracks on F.Cu, run the DRC,
and report the DELTA against a no-track control plus the presence of `shorting_items`.
0.20 mm is used deliberately: the 0.6 mm stackup is undeclared so no 50-ohm width is justified, and
this test is about GEOMETRY.

Usage: test_c0_rotation.py <board.kicad_pcb>
"""
import json
import math
import os
import shutil
import subprocess
import sys

import pcbnew

WIDTH = 0.20
WD = "/tmp/c0rot"
RF = "/SX1280_RF"


def mm(v):
    return pcbnew.ToMM(v)


def net_of(b, name):
    for c in range(1, b.GetNetCount()):
        n = b.FindNet(c)
        if n and n.GetNetname() == name:
            return n
    return None


def drc(bp):
    oj = bp.replace(".kicad_pcb", "_drc.json")
    subprocess.run(["kicad-cli", "pcb", "drc", bp, "--format", "json", "-o", oj,
                    "--severity-all"], capture_output=True, text=True)
    try:
        d = json.load(open(oj))
    except Exception:
        return None, {}
    types = {}
    for v in d.get("violations", []):
        if v.get("severity") == "error":
            k = v.get("type", "?")
            types[k] = types.get(k, 0) + 1
    return sum(types.values()), types


def build(src, dst, rot_deg, swap=False):
    """Load, optionally rotate C0 (and/or swap C0/L1), lay the two legs, run DRC."""
    b = pcbnew.LoadBoard(src)
    c0 = b.FindFootprintByReference("C0")
    l1 = b.FindFootprintByReference("L1")
    u4 = b.FindFootprintByReference("U4")

    if rot_deg:
        c0.SetOrientationDegrees(c0.GetOrientationDegrees() + rot_deg)
    if swap:
        p1, p2 = c0.GetPosition(), l1.GetPosition()
        c0.SetPosition(p2)
        l1.SetPosition(p1)

    # pad positions AFTER the change
    def rfpad(fp):
        for p in fp.Pads():
            if p.GetNetname() == RF:
                c = p.GetPosition()
                return (mm(c.x), mm(c.y))
        return None

    hub = rfpad(u4)
    c0rf = rfpad(c0)
    l1rf = rfpad(l1)
    if None in (hub, c0rf, l1rf):
        return None, {}, "an RF pad is missing after the change"

    n = net_of(b, RF)
    for a, c in ((hub, c0rf), (c0rf, l1rf)):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(int(round(a[0] * 1e6)), int(round(a[1] * 1e6))))
        t.SetEnd(pcbnew.VECTOR2I(int(round(c[0] * 1e6)), int(round(c[1] * 1e6))))
        t.SetWidth(int(round(WIDTH * 1e6)))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(n)
        b.Add(t)
    pcbnew.SaveBoard(dst, b)
    for ext in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
        s = src.replace(".kicad_pcb", ext)
        if os.path.exists(s):
            shutil.copy(s, dst.replace(".kicad_pcb", ext))
    tot, types = drc(dst)
    span = (round(math.dist(hub, c0rf), 2), round(math.dist(c0rf, l1rf), 2),
            round(math.dist(hub, l1rf), 2))
    return tot, types, span


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"
    os.makedirs(WD, exist_ok=True)

    ctrl = os.path.join(WD, "control.kicad_pcb")
    shutil.copy(src, ctrl)
    for ext in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
        s = src.replace(".kicad_pcb", ext)
        if os.path.exists(s):
            shutil.copy(s, ctrl.replace(".kicad_pcb", ext))
    ctot, ctypes = drc(ctrl)
    print(f"board  : {src}")
    print(f"CONTROL (no RF tracks): {ctot} errors, shorting_items {ctypes.get('shorting_items', 0)}")
    print(f"control classes: {json.dumps(ctypes, sort_keys=True)}\n")

    print(f"{'variant':22} {'errors':>7} {'delta':>6} {'short':>6} {'clear':>6}  legs (mm)")
    rows = []
    for name, rot, swap in (("rot0 (as placed)", 0, False),
                            ("rot180", 180, False),
                            ("rot0 + swap C0/L1", 0, True),
                            ("rot180 + swap", 180, True)):
        dst = os.path.join(WD, name.replace(" ", "_").replace("(", "").replace(")", "") + ".kicad_pcb")
        tot, types, span = build(src, dst, rot, swap)
        if tot is None:
            print(f"{name:22} {'--':>7} {'--':>6} {'--':>6} {'--':>6}  {span}")
            continue
        d = tot - ctot
        sh = types.get("shorting_items", 0)
        cl = types.get("clearance", 0)
        rows.append((name, tot, d, sh, cl, span))
        print(f"{name:22} {tot:>7} {d:>+6} {sh:>6} {cl:>6}  {span}")
    print()
    good = [r for r in rows if r[3] == 0]
    if good:
        best = min(good, key=lambda r: (r[2], sum(r[5])))
        print(f"NO-SHORT variants: {[r[0] for r in good]}")
        print(f"BEST by error delta then total leg length: {best[0]}  (delta {best[2]:+d}, "
              f"legs {best[5]})")
    else:
        print("EVERY variant still shorts -- the C0/L1 pair cannot be arranged at these sites.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Apply the DRC-found C0 nudge and the RF route, then gate the result.

FOUND BY SWEEPING, graded by refilled DRC (move_c0_for_clearance.py):
    move C0 by (-0.4, +0.0) mm  ->  total 26, delta -1 vs the control
        classes {copper_edge_clearance 24, starved_thermal 2}
        clearance 0, shorting_items 0, solder_mask_bridge 0, no new class

CONTROL (refilled, no RF tracks): 27 {copper_edge_clearance 24, starved_thermal 3}

So the routed board is BETTER than the unrouted control by one error -- it drops a starved_thermal as
well as adding no new fault. The competing offsets all added at least one new class (clearance,
shorting_items, solder_mask_bridge, or courtyards_overlap), so (-0.4, 0) is not a narrow win, it is the
only clean point in a 50-point sweep.

WHY 0.4 mm IS ENOUGH, and why narrowing the trace was not: the straight leg pad22 -> C0.RF passed within
0.116 mm of U4.pad21 at 0.20 mm width, improving by exactly half the width reduction
(0.166 mm at 0.100 mm). Extrapolation showed the gap cannot reach 0.200 mm at any positive width, so
the PATH was wrong rather than the width. Moving C0 left swings the path away from pad21.

WHAT THIS SCRIPT PRODUCES: the board with C0 nudged, both RF legs laid at 0.20 mm, zones refilled.
It does not touch any other net.

WIDTH NOTE, unchanged: 0.20 mm is the board's own default and is NOT a 50-ohm figure. The 0.6 mm
4-layer stackup is undeclared, so the 50-ohm width is unknown by a factor of 3.7. This route establishes
CONNECTIVITY; impedance remains open until the stackup is known.

Usage: apply_c0_nudge_and_route.py <in.kicad_pcb> <out.kicad_pcb>
"""
import json
import os
import shutil
import subprocess
import sys

import pcbnew

RF = "/SX1280_RF"
W = 0.20
DX, DY = -0.4, 0.0


def mm(v):
    return pcbnew.ToMM(v)


def refill(src, dst):
    """Refill zones. The helper path is resolved relative to THIS file, not the caller's cwd -- the
    earlier relative-path version silently produced nothing when run from a different directory,
    which is how the first attempt at this apply reported "refill failed"."""
    here = os.path.dirname(os.path.abspath(__file__))
    helper = os.path.join(here, "refill_zones.py")
    r = subprocess.run(["python3", helper, src, dst], capture_output=True, text=True)
    if not os.path.exists(dst):
        print(f"    refill helper stderr: {r.stderr[-200:] if r.stderr else '(none)'}")
    return os.path.exists(dst)
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
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    b = pcbnew.LoadBoard(src)

    c0 = b.FindFootprintByReference("C0")
    p = c0.GetPosition()
    print(f"C0 {mm(p.x):.2f},{mm(p.y):.2f} -> {mm(p.x)+DX:.2f},{mm(p.y)+DY:.2f}")
    c0.SetPosition(pcbnew.VECTOR2I(int(p.x + DX * 1e6), int(p.y + DY * 1e6)))

    def rf(fp):
        for pd in fp.Pads():
            if pd.GetNetname() == RF:
                c = pd.GetPosition()
                return (mm(c.x), mm(c.y))
        return None

    hub = rf(b.FindFootprintByReference("U4"))
    c0rf = rf(c0)
    l1rf = rf(b.FindFootprintByReference("L1"))
    print(f"node: U4.pad22 {hub}  C0.RF {c0rf}  L1.RF {l1rf}")
    import math
    print(f"  legs: {math.dist(hub, c0rf):.2f} mm, {math.dist(c0rf, l1rf):.2f} mm")

    # clear any existing RF tracks so this is idempotent
    for t in [t for t in b.GetTracks() if t.GetNetname() == RF]:
        b.Remove(t)

    net = None
    for cc in range(1, b.GetNetCount()):
        n = b.FindNet(cc)
        if n and n.GetNetname() == RF:
            net = n
            break
    for a, c in ((hub, c0rf), (c0rf, l1rf)):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(int(round(a[0] * 1e6)), int(round(a[1] * 1e6))))
        t.SetEnd(pcbnew.VECTOR2I(int(round(c[0] * 1e6)), int(round(c[1] * 1e6))))
        t.SetWidth(int(round(W * 1e6)))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(net)
        b.Add(t)
        print(f"  track laid {a} -> {c} at {W} mm")

    # KiCad's loader keys off the .kicad_pcb extension, so the intermediate MUST keep it. Appending
    # ".raw" to the path made the file unloadable and the earlier run reported "refill failed".
    raw = dst.replace(".kicad_pcb", "_raw.kicad_pcb") if dst.endswith(".kicad_pcb") else dst + ".raw.kicad_pcb"
    pcbnew.SaveBoard(raw, b)
    for ext in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
        s = src.replace(".kicad_pcb", ext)
        if os.path.exists(s):
            shutil.copy(s, raw.replace(".kicad_pcb", ext))
    if not refill(raw, dst):
        print("refill failed")
        return 1
    os.remove(raw)
    tot, c = drc(dst)
    print(f"\nFINAL (refilled): {tot}  {json.dumps(c, sort_keys=True)}")
    print(f"CONTROL was 27, so delta {tot-27:+d}")
    ok = c.get("clearance", 0) == 0 and c.get("shorting_items", 0) == 0 and tot <= 27
    print("GATE: " + ("PASS -- promote this board." if ok else "FAIL -- do not promote."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

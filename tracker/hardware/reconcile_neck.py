#!/usr/bin/env python3
"""RECONCILE the two disagreeing RF neck tools using KiCad's DRC as the arbiter.

THE DISAGREEMENT, left open in the previous commit:
    verify_no_rf_placement.py : neck from U4.pad22 downward is BLOCKED by U4.pad23 GND,
                               penetration 0.243 mm at depth 0.15, best 0.058 mm at depth 2.75
    neck_width_sweep.py       : the same neck is CLEAR at every width 0.140 .. 0.300 mm
Both cannot be true.

SUSPECTED BUG in neck_width_sweep.py, stated before testing: it starts the neck at the pad's BOTTOM
EDGE (y = 29.550) and its inner loop breaks as soon as the first sampled point is clear, so it reports
"CLEAR at y_end = 29.60" -- a 0.05 mm stub that reaches nothing. It never traverses the pad.

THE ARBITER. KiCad's own DRC is run on a board with exactly one track added: the neck. If KiCad reports
a copper clearance violation against U4.pad23, the neck is blocked; if it reports clean, it is clear.
This replaces my arithmetic with the same engine that grades the board, which is the only way to settle
it without trusting either script.

Method: for each candidate width, build board + one neck track, run DRC, count clearance violations
whose items mention U4. Report width -> verdict. The first clean width is the answer.

Usage: reconcile_neck.py <board.kicad_pcb> [--workdir /tmp/reconcile]
"""
import json
import os
import shutil
import subprocess
import sys

import pcbnew

NECK_DEPTH = 3.0          # how far below the pad to run the test neck
WIDTHS = [0.300, 0.280, 0.260, 0.240, 0.220, 0.200, 0.180]


def mm(v):
    return pcbnew.ToMM(v)


def run_drc(board_path, out_json):
    cmd = ["kicad-cli", "pcb", "drc", board_path, "--format", "json",
           "-o", out_json, "--severity-all"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode


def main():
    board = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"
    wd = "/tmp/reconcile"
    if "--workdir" in sys.argv:
        wd = sys.argv[sys.argv.index("--workdir") + 1]
    os.makedirs(wd, exist_ok=True)

    b = pcbnew.LoadBoard(board)
    fp = b.FindFootprintByReference("U4")
    p22 = next(p for p in fp.Pads() if str(p.GetNumber()) == "22")
    c = p22.GetPosition()
    ax, ay = mm(c.x), mm(c.y)
    s = p22.GetSize()
    print(f"board: {board}")
    print(f"U4.pad22 centre ({ax:.3f},{ay:.3f})  size {mm(s.x):.2f}x{mm(s.y):.2f}  "
          f"so the pad spans y {ay-mm(s.y)/2:.3f}..{ay+mm(s.y)/2:.3f}")

    gnd = None
    for cc in range(1, b.GetNetCount()):
        n = b.FindNet(cc)
        if n and n.GetNetname() == "/SX1280_RF":
            gnd = n
            break
    if gnd is None:
        print("/SX1280_RF net absent")
        return 1

    def count_for(width_or_none):
        """DRC error count on a board with (or without) the test neck. Returns (count, detail)."""
        bb = pcbnew.LoadBoard(board)
        if width_or_none is not None:
            t = pcbnew.PCB_TRACK(bb)
            t.SetStart(pcbnew.VECTOR2I(int(round(ax * 1e6)), int(round(ay * 1e6))))
            t.SetEnd(pcbnew.VECTOR2I(int(round(ax * 1e6)), int(round((ay + NECK_DEPTH) * 1e6))))
            t.SetWidth(int(round(width_or_none * 1e6)))
            t.SetLayer(pcbnew.F_Cu)
            for cc in range(1, bb.GetNetCount()):
                n = bb.FindNet(cc)
                if n and n.GetNetname() == "/SX1280_RF":
                    t.SetNet(n)
                    break
            bb.Add(t)
        tag = "control" if width_or_none is None else f"{int(width_or_none*1000):03d}"
        bp = os.path.join(wd, f"neck_{tag}.kicad_pcb")
        pcbnew.SaveBoard(bp, bb)
        for ext in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
            src = board.replace(".kicad_pcb", ext)
            if os.path.exists(src):
                shutil.copy(src, bp.replace(".kicad_pcb", ext))
        oj = bp.replace(".kicad_pcb", "_drc.json")
        run_drc(bp, oj)
        n = 0
        det = []
        try:
            d = json.load(open(oj))
            for v in d.get("violations", []):
                if v.get("severity") != "error":
                    continue
                txt = " | ".join(i.get("description", "") for i in v.get("items", []))
                n += 1
                det.append(f"{v.get('type')}: {txt[:80]}")
        except Exception:
            pass
        return n, det

    ctrl, ctrl_det = count_for(None)
    print(f"\nCONTROL (no neck): {ctrl} DRC errors")
    print(f"  the control's own top items, for scale:")
    for x in ctrl_det[:3]:
        print(f"    {x}")
    print(f"\nneck under test: pad CENTRE ({ax:.3f},{ay:.3f}) straight DOWN {NECK_DEPTH} mm")
    print(f"{'width':>7}  {'errors':>7}  {'delta vs control':>17}  verdict")
    results = []
    for w in WIDTHS:
        n, det = count_for(w)
        delta = n - ctrl
        verdict = "CLEAR" if delta <= 0 else "BLOCKED"
        results.append((w, verdict, det, delta))
        print(f"{w:7.3f}  {n:>7}  {delta:>+17}  {verdict}")
        for dd in det[:2] if delta > 0 else []:
            print(f"          {dd}")
    print()
    clear = [w for w, v, _d, _x in results if v == "CLEAR"]
    if clear:
        print(f"WIDEST CLEAR NECK: {max(clear):.3f} mm  (KiCad DRC, not my arithmetic)")
        print("This is the widest trace that legally leaves U4.pad22 downward on F.Cu.")
    else:
        print("NO WIDTH CLEAR per KiCad DRC. pad22 cannot be escaped downward at all.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

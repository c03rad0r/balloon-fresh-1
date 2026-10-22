#!/usr/bin/env python3
"""POISON TEST for check_lane_crossing.py -- prove it can FAIL.

WHY (2026-10-22): the operator asked whether two same-layer lanes crossing was a short, and
whether any test caught it. The first version of check_lane_crossing.py reported **165 crossings
and 2948 via-near hits** on a board that kicad-cli DRC reports with ZERO clearance violations.
That disagreement was the tell. Both causes were bugs in MY geometry:

  B42a  the collinear branch of the segment-intersection test used the wrong containment
        predicate, and because most tracks here are axis-aligned the orientation determinant is
        exactly 0.0 for many pairs -- so the broken branch fired constantly and invented
        crossings between nets millimetres apart. Verified by measuring a named pair:
        /ANT1_433_TX at x 13.35..14.95 vs /ANT4_GNSS_L1 starting at x=19.25.
  B42b  PCB_VIA::GetWidth() called with NO layer argument is undefined (KiCad asserts on it) and
        returned garbage, producing 2948 bogus VIA-NEAR hits.

A gate that once reported 165 false defects MUST have a test proving it can still report a REAL
one. This plants a genuine same-layer crossing between two different nets and requires exit 1.

Run: python3 tests/poison_lane_crossing.py
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HW = os.path.join(REPO, "tracker", "hardware")
BOARD = os.path.join(HW, "hub_board_v10.kicad_pcb")
PY = sys.executable


def run_gate(board):
    r = subprocess.run([PY, os.path.join(HW, "check_lane_crossing.py"), "--board", board],
                       capture_output=True, text=True, timeout=600)
    return r.returncode, (r.stdout or "")


def main():
    if not os.path.exists(BOARD):
        print("SKIP: no v10 board")
        return 0
    try:
        import pcbnew
    except Exception:
        print("SKIP: pcbnew unavailable")
        return 0

    rc_clean, out_clean = run_gate(BOARD)
    print(f"clean board: rc={rc_clean}")
    print("   " + [l for l in out_clean.splitlines() if l.startswith("CROSSINGS")][-1])
    if rc_clean != 0:
        print("FAIL: the real board is reported as having crossings -- investigate before trusting")
        return 1

    # plant a real same-layer crossing between two different nets
    with tempfile.TemporaryDirectory() as td:
        poisoned = os.path.join(td, "poisoned.kicad_pcb")
        b = pcbnew.LoadBoard(BOARD)
        nets = {}
        for fp in b.GetFootprints():
            for p in fp.Pads():
                n = p.GetNetname() or ""
                if n and n not in nets:
                    r = p.GetBoundingBox()
                    nets[n] = (r.GetX() / 1e6, r.GetY() / 1e6,
                               (r.GetX() + r.GetWidth()) / 1e6,
                               (r.GetY() + r.GetHeight()) / 1e6)
        # two nets whose pads are far apart; draw two crossing tracks between them on F.Cu
        pick = [n for n in sorted(nets) if n.startswith("/")][:2]
        if len(pick) < 2:
            print("SKIP: not enough named nets to plant a crossing")
            return 0
        n1, n2 = pick
        c1 = ((nets[n1][0] + nets[n1][2]) / 2, (nets[n1][1] + nets[n1][3]) / 2)
        c2 = ((nets[n2][0] + nets[n2][2]) / 2, (nets[n2][1] + nets[n2][3]) / 2)
        made = 0
        for net, (a, c) in ((n1, (c1, c2)), (n2, (c2, c1))):
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(pcbnew.VECTOR2I(int(a[0] * 1e6), int(a[1] * 1e6)))
            t.SetEnd(pcbnew.VECTOR2I(int(c[0] * 1e6), int(c[1] * 1e6)))
            t.SetWidth(int(0.2 * 1e6))
            t.SetLayer(pcbnew.F_Cu)
            t.SetNetCode(0)
            b.Add(t)
            made += 1
        b.Save(poisoned)
        print(f"planted {made} crossing track(s) on F.Cu between {n1} and {n2}")

        rc_bad, out_bad = run_gate(poisoned)
        line = [l for l in out_bad.splitlines() if l.startswith("CROSSINGS")]
        print(f"poisoned board: rc={rc_bad}   {line[-1] if line else '(no summary)'}")
        for l in out_bad.splitlines():
            if "CROSSING" in l:
                print("   " + l.strip()[:150])
                break

        ok = (rc_bad != 0)
        print(f"poison test: {'PASS' if ok else 'FAIL'} -- the gate "
              f"{'detected' if ok else 'MISSED'} a planted same-layer crossing")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

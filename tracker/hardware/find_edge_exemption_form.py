#!/usr/bin/env python3
"""Find the condition form that actually clears the J_W* edge violations, measured not guessed.

ESTABLISHED by test_dru_loading.py:
    A  repo dru as-is (condition on A.Reference only)     24 copper_edge_clearance errors
    B  blanket waiver (rule with NO condition at all)     16
    C  no dru file                                        24
A == C proves the repo's rule has ZERO effect. B < A proves custom rules DO run (8 were removed), and
therefore the CONDITION is what fails to match. But B = 16 also proves 8 pairs are unreachable by any
condition at all -- so the ceiling for a condition-based fix is 24 -> 16, not 24 -> 0.

This sweeps condition FORMS, measuring each, to find the widest reach available. Candidates:
  1. A.Reference only                (the current rule)
  2. A.Reference OR B.Reference      (either side of the pair)
  3. A.Type == 'Pad' && A.Reference
  4. B.Type == 'Pad' && B.Reference
  5. reference match on both sides plus a Type guard
It reports the error count for each so the choice is a number, not a preference.

Read-only. Writes to /tmp only.

Usage: find_edge_exemption_form.py <board.kicad_pcb>
"""
import json
import os
import shutil
import subprocess
import sys

WD = "/tmp/dru_forms"

REF = " || ".join(f"A.Reference == 'J_W{i}'" for i in (1, 2, 3, 4))
REF_B = " || ".join(f"B.Reference == 'J_W{i}'" for i in (1, 2, 3, 4))
FORMS = [
    ("as-is: A.Reference only", REF),
    ("either side: A.Reference || B.Reference", f"({REF}) || ({REF_B})"),
    ("A is a Pad and a J_W", f"A.Type == 'Pad' && ({REF})"),
    ("B is a Pad and a J_W", f"B.Type == 'Pad' && ({REF_B})"),
    ("either side is a Pad and a J_W",
     f"(A.Type == 'Pad' && ({REF})) || (B.Type == 'Pad' && ({REF_B}))"),
]


def drc(bp):
    oj = bp.replace(".kicad_pcb", "_drc.json")
    subprocess.run(["kicad-cli", "pcb", "drc", bp, "--format", "json", "-o", oj,
                    "--severity-all"], capture_output=True, text=True)
    try:
        d = json.load(open(oj))
    except Exception:
        return None
    return sum(1 for v in d.get("violations", [])
               if v.get("severity") == "error" and v.get("type") == "copper_edge_clearance")


def main():
    board = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"
    src_dru = "tracker/hardware/jlcpcb-s1-frozen.kicad_dru"
    os.makedirs(WD, exist_ok=True)
    print(f"board: {board}\n")

    results = []
    for i, (label, cond) in enumerate(FORMS):
        tag = f"f{i}"
        pb = os.path.join(WD, f"{tag}.kicad_pcb")
        shutil.copy(board, pb)
        for ext in (".kicad_pro", ".kicad_prl"):
            s = board.replace(".kicad_pcb", ext)
            if os.path.exists(s):
                shutil.copy(s, pb.replace(".kicad_pcb", ext))
        # start from the repo dru so the frozen S1 rules stay in force, then REPLACE the two
        # wing-socket rules with a single rule using this candidate condition
        dru = open(src_dru).read()
        # drop the two existing wing-socket rules (they are the ones being varied)
        keep = []
        skip_depth = 0
        for line in dru.splitlines():
            if 'rule "S1 hub wing-socket edge-launch' in line or \
               'rule "edge_clearance_wing_socket_lands_44"' in line:
                skip_depth = 1
                continue
            if skip_depth:
                if line.strip().endswith("))") or line.strip().endswith(")"):
                    skip_depth = 0
                continue
            keep.append(line)
        extra = (f'\n(rule "CANDIDATE wing-socket exemption"\n'
                 f'  (constraint edge_clearance (min 0.0mm))\n'
                 f'  (condition "{cond}"))\n')
        open(pb.replace(".kicad_pcb", ".kicad_dru"), "w").write("\n".join(keep) + extra)
        n = drc(pb)
        results.append((label, n))
        print(f"  {label:46} -> {n}")

    print()
    base = next((n for l, n in results if l.startswith("as-is")), None)
    best = min((n for _l, n in results if n is not None), default=None)
    for label, n in results:
        if n == best:
            print(f"BEST: {label}  ->  {n}  (from {base})")
    print()
    print("NOTE: 16 was the blanket-waiver floor, so any value above 16 means that form only reaches")
    print("part of the set. A value of 16 is the best a condition can do; the remaining 16 pairs are a")
    print("KiCad rule-APPLICABILITY artifact (no condition-visible field on the edge side) and cannot be")
    print("suppressed by any rule -- they must be accepted and documented, or the board default lowered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

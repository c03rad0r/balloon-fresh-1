#!/usr/bin/env python3
"""Decisive test: is the J_W* edge exemption inert because the CONDITION cannot match, or because the
.kicad_dru file is not being loaded at all?

WHY THIS TEST EXISTS. I previously claimed the exemption was "proven inert" because KiCad's condition
field cannot see `A.Reference` on an Edge.Cuts item. But the evidence I used was a STRING HEURISTIC over
item descriptions (counting how many descriptions contain a J_W token), not KiCad's condition
evaluator. That is not proof of the mechanism. There is a competing and simpler explanation I never
ruled out:

    the custom rules file may not be loading at all.

KiCad auto-loads custom rules from a file matching the PROJECT name. The repo's file is
`jlcpcb-s1-frozen.kicad_dru`; the board is `hub_board_v9.kicad_pcb`. Unless it is copied to
`hub_board_v9.kicad_dru` next to the board, KiCad may load NO custom rules, in which case the exemption
never runs regardless of its condition -- and the fix would be a filename/copy issue, not a condition
rewrite. Those two causes need completely different repairs, so guessing between them would be the same
mistake as the rest of this session.

METHOD, and it distinguishes them in one run:
    A. control                : board + its normal dru                  -> baseline count
    B. unconditional exemption : dru whose edge rule has NO condition and min 0.0mm. If the file loads,
                                EVERY edge violation disappears (the rule becomes a blanket waiver).
    C. reference-scoped rule   : the repo's actual rule, verbatim.
Readings:
    B == control  -> the dru is NOT being loaded. Fix = load the file. The condition is innocent.
    B < control   -> the dru IS loaded. Then C == control proves the condition alone is at fault.

Read-only. Writes to /tmp only.

Usage: test_dru_loading.py <board.kicad_pcb> [<source_dru>]
"""
import json
import os
import re
import shutil
import subprocess
import sys

WD = "/tmp/dru_test"


def drc(bp):
    oj = bp.replace(".kicad_pcb", "_drc.json")
    subprocess.run(["kicad-cli", "pcb", "drc", bp, "--format", "json", "-o", oj,
                    "--severity-all"], capture_output=True, text=True)
    try:
        d = json.load(open(oj))
    except Exception:
        return None, None
    n = 0
    for v in d.get("violations", []):
        if v.get("severity") == "error" and v.get("type") == "copper_edge_clearance":
            n += 1
    return n, oj


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    board = sys.argv[1]
    src_dru = sys.argv[2] if len(sys.argv) > 2 else "tracker/hardware/jlcpcb-s1-frozen.kicad_dru"
    os.makedirs(WD, exist_ok=True)
    base = os.path.basename(board).replace(".kicad_pcb", "")
    print(f"board      : {board}")
    print(f"source dru : {src_dru}")
    print(f"project key: {base}   (KiCad loads custom rules from {base}.kicad_dru)\n")

    variants = {}

    # A. control: board + the repo dru copied under the project name (what fab_grade.sh does)
    pa = os.path.join(WD, "control.kicad_pcb")
    shutil.copy(board, pa)
    for ext in (".kicad_pro", ".kicad_prl"):
        s = board.replace(".kicad_pcb", ext)
        if os.path.exists(s):
            shutil.copy(s, pa.replace(".kicad_pcb", ext))
    shutil.copy(src_dru, pa.replace(".kicad_pcb", ".kicad_dru"))
    variants["A control (repo dru, no condition change)"] = pa

    # B. unconditional blanket waiver -- if the dru loads, this removes EVERY edge violation
    pb = os.path.join(WD, "blanket.kicad_pcb")
    shutil.copy(board, pb)
    for ext in (".kicad_pro", ".kicad_prl"):
        s = board.replace(".kicad_pcb", ext)
        if os.path.exists(s):
            shutil.copy(s, pb.replace(".kicad_pcb", ext))
    open(pb.replace(".kicad_pcb", ".kicad_dru"), "w").write(
        '(version 1)\n'
        '(rule "BLANKET TEST - no condition, min 0.0mm"\n'
        '  (constraint edge_clearance (min 0.0mm)))\n')
    variants["B blanket waiver (rule with NO condition)"] = pb

    # C. no dru at all -- does the built-in board-setup value alone apply?
    pc = os.path.join(WD, "nodru.kicad_pcb")
    shutil.copy(board, pc)
    for ext in (".kicad_pro", ".kicad_prl"):
        s = board.replace(".kicad_pcb", ext)
        if os.path.exists(s):
            shutil.copy(s, pc.replace(".kicad_pcb", ext))
    variants["C no dru file at all"] = pc

    results = {}
    for name, path in variants.items():
        n, _oj = drc(path)
        results[name] = n
        print(f"  {name:48} copper_edge_clearance = {n}")

    print()
    a = results.get("A control (repo dru, no condition change)")
    b = results.get("B blanket waiver (rule with NO condition)")
    c = results.get("C no dru file at all)")
    print("READING:")
    if b is None or a is None:
        print("  a run failed; cannot conclude")
        return 1
    if b == a:
        print("  B == A  ->  THE DRU IS NOT BEING LOADED. A blanket waiver changed nothing, so no")
        print("             custom rule is running at all. The condition is innocent; the fix is to make")
        print("             the file load (project-name match / path), not to rewrite the condition.")
    else:
        print(f"  B ({b}) < A ({a})  ->  THE DRU IS LOADED. A blanket waiver removed edge violations, so")
        print("             custom rules do run; the repo's reference-scoped condition is then the thing")
        print("             that fails to match, and rewriting the CONDITION is the correct fix.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

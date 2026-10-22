#!/usr/bin/env python3
"""pre-commit: board gates. Blocks a commit that touches PCB connectivity with a failing gate.

WHY THIS EXISTS (operator, 2026-10-22): "Please include it in your git hooks and run it before
showing me the images in future so that you catch and fix such errors before showing me your
progress." Eight custom gates reported all-zero while kicad-cli DRC found 48 violations on the
same board, and the board had no schematic at all. A convention is worth nothing the day someone
forgets; this is the forcing function.

WHEN IT RUNS: only when the staged set touches a board, schematic, footprint, or the
connectivity registry. Other commits pay nothing.

WHAT IT RUNS:
  check_drc.py                kicad-cli pcb drc, classified. clearance/shorting_items are hard.
  check_schematic_parity.py   schematic <-> board parity both ways + ERC (ADR-128)

REFUSAL SEMANTICS: if kicad-cli is missing these gates cannot run. They then REFUSE (non-zero)
rather than pass -- a gate that cannot run must never look green. Set
BOARD_GATES_ALLOW_MISSING_KICAD=1 only to bypass on a machine that genuinely has no KiCad.
"""
import os
import re
import subprocess
import sys

REPO = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                      capture_output=True, text=True).stdout.strip()
if not REPO:
    sys.exit(0)

# which files in this commit matter?
staged = subprocess.run(["git", "diff", "--cached", "--name-only"],
                        capture_output=True, text=True).stdout.split()
TRIGGERS = (".kicad_pcb", ".kicad_sch", ".kicad_mod", "v10_pinmap.reg", "OPEN-ITEMS.md")
touching = [f for f in staged if f.endswith(TRIGGERS) or any(t in f for t in TRIGGERS[3:])]
if not touching:
    sys.exit(0)

print(f"board-gates: {len(touching)} staged file(s) touch PCB connectivity")
for f in touching[:6]:
    print(f"  - {f}")

HW = os.path.join(REPO, "tracker", "hardware")
BOARD = os.path.join(HW, "hub_board_v10.kicad_pcb")

if not os.path.exists(BOARD):
    print("board-gates: no v10 board in this commit -- skipped")
    sys.exit(0)

import shutil
if not shutil.which("kicad-cli"):
    if os.environ.get("BOARD_GATES_ALLOW_MISSING_KICAD") == "1":
        print("board-gates: kicad-cli missing, bypassed by BOARD_GATES_ALLOW_MISSING_KICAD=1")
        sys.exit(0)
    print("board-gates: REFUSED -- kicad-cli not found, so the DRC/parity gates cannot run.")
    print("             A gate that cannot run must not look green. Install kicad-cli, or set")
    print("             BOARD_GATES_ALLOW_MISSING_KICAD=1 to bypass deliberately.")
    sys.exit(1)

# pick the interpreter that can import pcbnew (the KiCad venv), else fall back to python3
PY = None
for cand in (os.path.expanduser("~/venvs/kicad/bin/python"), sys.executable, "python3"):
    if not cand:
        continue
    r = subprocess.run([cand, "-c", "import pcbnew"], capture_output=True)
    if r.returncode == 0:
        PY = cand
        break
if PY is None:
    print("board-gates: REFUSED -- no interpreter with pcbnew found (needed to read the board)")
    sys.exit(1)

GATES = [
    ("check_drc.py", []),
    ("check_schematic_parity.py", []),
]

failed = []
for script, extra in GATES:
    path = os.path.join(HW, script)
    if not os.path.exists(path):
        failed.append(f"{script}: MISSING (gate expected but absent)")
        print(f"board-gates: FAIL {script} -- expected gate not found")
        continue
    r = subprocess.run([PY, path, *extra], capture_output=True, text=True, timeout=900)
    tail = [l for l in (r.stdout or "").strip().splitlines() if l.strip()][-3:]
    if r.returncode == 0:
        print(f"board-gates: PASS {script}")
    else:
        print(f"board-gates: FAIL {script} (rc={r.returncode})")
        for l in tail:
            print(f"    {l[:160]}")
        failed.append(script)

if failed:
    print(f"board-gates: {len(failed)} gate(s) failed: {', '.join(failed)}")
    print("board-gates: fix the defect, or commit with --no-verify ONLY if you have stated why.")
    sys.exit(1)
print("board-gates: all gates pass")
sys.exit(0)

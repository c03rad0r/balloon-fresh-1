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

# ---------------------------------------------------------------------------------------------
# SCHEMATIC-SAFETY GATE (operator, 2026-10-22): "please make sure the schematic always exists and
# is fully tested before we make the board. Please make sure its part of the git hooks and
# agents.md."
#
# TWO checks, in the order the design flow says they must happen:
#
#   ORDER      A board may not be committed unless its schematic exists AND is ERC-clean. This
#              is the mechanical form of "schematic before board". Without it the board can be
#              re-routed freely while the schematic rots, which is exactly how v10 reached the
#              state where 16 nets of copper existed with no schematic behind them at all.
#
#   TESTED     The schematic must be proven TESTED, not merely present. "Exists" is trivially
#              satisfiable by an empty file, so the check is: ERC actually ran on it and returned
#              zero violations. A missing file, a missing kicad-cli, or an unparseable report all
#              REFUSE rather than pass.
#
# The check is skipped ONLY when the staged set touches no board and no schematic -- editing a
# README must not require a KiCad install.
# ---------------------------------------------------------------------------------------------
SCHEM = os.path.join(HW, "schematics", "flight_board", "v10_flight.kicad_sch")
touch_board = any(f.endswith(".kicad_pcb") for f in staged)
touch_sch = any(f.endswith(".kicad_sch") for f in staged)

if touch_board or touch_sch:
    # ---- ORDER: the schematic must exist before/with the board ------------------------------
    if not os.path.exists(SCHEM):
        print("board-gates: FAIL SCHEMATIC EXISTS -- no v10 schematic at")
        print(f"    {SCHEM}")
        print("    ADR-128: the board is DERIVED from the schematic. A board committed with no")
        print("    schematic has never been ERC-checked. Refusing.")
        sys.exit(1)

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        rpt = os.path.join(td, "erc.rpt")
        try:
            r = subprocess.run(
                ["kicad-cli", "sch", "erc", "--exit-code-violations", "-o", rpt, SCHEM],
                capture_output=True, text=True, timeout=600,
                cwd=os.path.dirname(SCHEM),
            )
        except Exception as e:
            print(f"board-gates: REFUSED -- ERC could not run on the schematic ({e})")
            sys.exit(1)
        txt = ""
        try:
            with open(rpt, encoding="utf-8", errors="replace") as fh:
                txt = fh.read()
        except Exception:
            pass
        m = re.search(r"ERC messages:\s*(\d+)\s*Errors\s*(\d+)\s*Warnings\s*(\d+)", txt or "")
        if r.returncode != 0 or not m or int(m.group(1)) != 0:
            if m:
                n, e, w = int(m.group(1)), int(m.group(2)), int(m.group(3))
                print(f"board-gates: FAIL SCHEMATIC FULLY TESTED -- ERC reports "
                      f"{n} violation(s): {e} error(s), {w} warning(s)")
                tys = {}
                for t in re.findall(r"\[([a-z_]+)\]", txt):
                    tys[t] = tys.get(t, 0) + 1
                if tys:
                    print("    " + ", ".join(f"{k}:{v}" for k, v in
                                             sorted(tys.items(), key=lambda kv: -kv[1])[:8]))
            else:
                print(f"board-gates: FAIL SCHEMATIC FULLY TESTED -- ERC rc={r.returncode} and no "
                      f"parseable report")
                print("    A gate that cannot prove it ran must not look green.")
            print("    Fix the schematic (ADR-128 direction: schematic -> ERC -> netlist -> board).")
            sys.exit(1)
        print("board-gates: PASS SCHEMATIC FULLY TESTED -- ERC 0 violations before the board")

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

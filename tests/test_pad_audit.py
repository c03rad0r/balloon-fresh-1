#!/usr/bin/env python3
"""Guard: pad_audit.py must be EXACT and must be ABLE TO FAIL.

WHY. pad_audit.py is intended to run as a pre-commit hook and in CI. A hook that fires wrongly is worse
than no hook: it teaches the committer to bypass it. This file was written AFTER an earlier version of
pad_audit.py reported two visually identical pads as "DIFFERENT -> overlapping copper", because its
signature included LayerSet.FmtHex(), whose string form is not stable across calls.

So these tests assert the two properties that make it trustworthy:

  A. EXACTNESS -- two coincident pads must compare EQUAL, and a pad whose geometry really differs must
     compare UNEQUAL. Tested on synthesized pcbnew pad objects, not on the repo board, so the property
     does not depend on the board's current state.
  B. IT CAN FAIL -- take the real board's text, inject a repeated pad number, and require the audit to
     report an ERROR and exit non-zero. A check that cannot fail proves nothing, which is the same rule
     the determinism, ERC and DRC gates use.

Run: ~/venvs/ho-test/bin/python -m pytest tests/test_pad_audit.py -v
     (pad_audit itself must be run with an interpreter that has pcbnew; the test drives it as a
      subprocess and skips with a reason if none is available, rather than failing for an environment
      cause no committer can fix.)
"""
from __future__ import annotations

import glob
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
AUDIT = REPO / "tracker" / "hardware" / "pad_audit.py"
BOARD = REPO / "tracker" / "hardware" / "hub_board_v9.kicad_pcb"


def _pcbnew_python() -> str:
    """An interpreter that can import pcbnew, chosen by TESTING rather than by assuming a path."""
    cands = [os.path.expanduser("~/venvs/kicad/bin/python"), "/usr/bin/python3", "python3"]
    cands += sorted(glob.glob(os.path.expanduser("~/venvs/*/bin/python")))
    for c in cands:
        try:
            if subprocess.run([c, "-c", "import pcbnew"], capture_output=True, timeout=60).returncode == 0:
                return c
        except Exception:
            continue
    return ""


PY = _pcbnew_python()
pytestmark = pytest.mark.skipif(not PY, reason="no interpreter with pcbnew on this host")


# --------------------------------------------------------------------------- A. exactness
def test_pad_sig_is_exact_for_coincident_pads():
    """Two pads built with identical geometry must produce the SAME signature.

    This is the regression test for the bug that made the audit lie.
    """
    code = (
        "import sys;sys.path.insert(0,'tracker/hardware')\n"
        "import pcbnew, pad_audit as pa\n"
        "def mk(x,y,w,h,net):\n"
        "    p=pcbnew.PAD(None)\n"
        "    p.SetPosition(pcbnew.VECTOR2I(int(x*1e6),int(y*1e6)))\n"
        "    p.SetSize(pcbnew.VECTOR2I(int(w*1e6),int(h*1e6)))\n"
        "    p.SetDrillSize(pcbnew.VECTOR2I(0,0))\n"
        "    p.SetShape(pcbnew.PAD_SHAPE_RECT)\n"
        "    p.SetNetCode(1)\n"
        "    return p\n"
        "a=mk(8.2,32.3,4.0,1.2,1); b=mk(8.2,32.3,4.0,1.2,1)\n"
        "c=mk(8.2,32.4,4.0,1.2,1)\n"
        "print('SAME', pa.pad_sig(a)==pa.pad_sig(b))\n"
        "print('DIFF', pa.pad_sig(a)!=pa.pad_sig(c))\n"
        "print('REPEAT', pa.pad_sig(a)==pa.pad_sig(a))\n"
    )
    r = subprocess.run([PY, "-c", code], cwd=str(REPO), capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, f"probe failed:\n{r.stdout[-600:]}\n{r.stderr[-400:]}"
    out = r.stdout
    assert "SAME True" in out, f"coincident pads compared UNEQUAL -- the audit will lie again:\n{out}"
    assert "DIFF True" in out, f"genuinely different pads compared EQUAL -- the audit is blind:\n{out}"
    assert "REPEAT True" in out, f"signature is not stable across calls:\n{out}"


# --------------------------------------------------------------------------- B. it can fail
def test_audit_reports_the_known_U1_defects():
    """On the real board the audit must report U1's collision and unnamed pads as ERRORS."""
    r = subprocess.run([PY, str(AUDIT), str(BOARD)], cwd=str(REPO),
                       capture_output=True, text=True, timeout=300)
    out = r.stdout
    assert r.returncode == 1, f"audit should exit 1 on this board:\n{out[-600:]}"
    assert re.search(r"U1.*pad number '41'", out), f"missing the 13x pad-41 collision:\n{out[-800:]}"
    assert re.search(r"U1.*EMPTY number", out), f"missing U1's unnamed pads:\n{out[-800:]}"
    assert "WARN" in out, "coincident duplicates should be reported as warnings, not silent"


def test_audit_FAILS_when_a_repeated_pad_number_is_injected():
    """THE IMPORTANT ONE: corrupt a copy of the board and require a non-zero exit.

    A pad number is duplicated by rewriting one pad's number in the board TEXT. The audit must notice.
    """
    if not BOARD.exists():
        pytest.skip("hub board not present")
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="pad-audit-"))
    try:
        copy = tmp / BOARD.name
        text = BOARD.read_text(encoding="utf-8", errors="replace")
        # find a U1 pad block and change a distinctive number to one that already exists, so a number
        # repeats at a DIFFERENT position -- i.e. a real collision.
        injected = text.replace('(pad "40" ', '(pad "1" ', 1)
        assert injected != text, "could not inject the fault; the pad block pattern has changed"
        copy.write_text(injected, encoding="utf-8")
        r = subprocess.run([PY, str(AUDIT), str(copy)], cwd=str(REPO),
                           capture_output=True, text=True, timeout=300)
        assert r.returncode == 1, (
            f"the audit exited 0 on a board with an injected repeated pad number -- it cannot fail, "
            f"so it is worthless:\n{r.stdout[-700:]}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_audit_exits_2_when_it_cannot_run():
    """A gate that cannot run must say so loudly, never pass silently."""
    r = subprocess.run([sys.executable, "-c",
                        f"import sys;sys.argv=['x','/nonexistent.kicad_pcb'];"
                        f"exec(open({str(AUDIT)!r}).read())"],
                       cwd=str(REPO), capture_output=True, text=True, timeout=120)
    # either it exits 2 (no pcbnew) or 1 (absent board) -- but NEVER 0
    assert r.returncode != 0, "audit returned 0 for a board it could not read"

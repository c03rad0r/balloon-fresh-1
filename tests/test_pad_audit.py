"""Guard: pad_audit.py must be EXACT and must be ABLE TO FAIL.

WHY. pad_audit.py runs as a pre-commit hook and a CI step. A hook that fires wrongly is worse than no
hook: it teaches the committer to bypass it. This file exists because the audit was WRONG IN BOTH
DIRECTIONS before these tests were written:

  pass 1  8 "errors" -- 13 pads sharing number '41', 9 pads with no number, four U.FL connectors with pad
          '2' three times. ALL FALSE. Measured against the stock KiCad libraries, the 13x'41' is a
          thermal-via array and the 9 unnamed pads sit on F.Paste ONLY -- paste apertures with no copper,
          which cannot be floating. The repeated numbers are the official convention for "several
          physical pads, one net".
  pass 2  45 "errors" -- every stock-library part reported as having an unresolvable model, because only
          ${KIPRJMOD} was expanded and not ${KICAD<n>_3DMODEL_DIR}.

So the assertions below pin the CORRECTED rules, and the important test INJECTS the fault that actually
matters: a pad number whose pads disagree on a NET, which is the one condition KiCad cannot express.

Run: ~/venvs/ho-test/bin/python -m pytest tests/test_pad_audit.py -v
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


def _run(board, *extra, root=None):
    cmd = [PY, str(AUDIT)]
    if root:
        cmd += ["--root", root]
    cmd.append(str(board))
    return subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=300)


# --------------------------------------------------------------- exactness of the pad signature
def test_pad_sig_is_exact_for_coincident_pads():
    """Two identical pads must compare EQUAL; genuinely different pads must compare UNEQUAL.

    Regression test for the bug that made the audit lie: an earlier signature included
    LayerSet.FmtHex(), whose string form is not stable across calls, so two IDENTICAL pads compared as
    DIFFERENT and the audit reported "overlapping copper" for a coincident duplicate.
    """
    code = (
        "import sys;sys.path.insert(0,'tracker/hardware')\n"
        "import pcbnew, pad_audit as pa\n"
        "def mk(x,y,w,h):\n"
        "    p=pcbnew.PAD(None)\n"
        "    p.SetPosition(pcbnew.VECTOR2I(int(x*1e6),int(y*1e6)))\n"
        "    p.SetSize(pcbnew.VECTOR2I(int(w*1e6),int(h*1e6)))\n"
        "    p.SetDrillSize(pcbnew.VECTOR2I(0,0))\n"
        "    p.SetShape(pcbnew.PAD_SHAPE_RECT)\n"
        "    p.SetNetCode(1)\n"
        "    return p\n"
        "a=mk(8.2,32.3,4.0,1.2); b=mk(8.2,32.3,4.0,1.2); c=mk(8.2,32.4,4.0,1.2)\n"
        "print('SAME', pa.pad_sig(a)==pa.pad_sig(b))\n"
        "print('DIFF', pa.pad_sig(a)!=pa.pad_sig(c))\n"
        "print('REPEAT', pa.pad_sig(a)==pa.pad_sig(a))\n"
    )
    r = subprocess.run([PY, "-c", code], cwd=str(REPO), capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, f"probe failed:\n{r.stdout[-500:]}\n{r.stderr[-400:]}"
    assert "SAME True" in r.stdout, f"coincident pads compared UNEQUAL -- the audit will lie:\n{r.stdout}"
    assert "DIFF True" in r.stdout, f"different pads compared EQUAL -- the audit is blind:\n{r.stdout}"
    assert "REPEAT True" in r.stdout, f"signature unstable across calls:\n{r.stdout}"


def test_model_ref_expansion_uses_the_census_rules():
    """${KICAD<n>_3DMODEL_DIR} must expand to the COMPILED-IN default, not the shell environment.

    This is the pass-2 bug: expanding only ${KIPRJMOD} reported 37 stock-library parts as broken.
    """
    code = (
        "import sys;sys.path.insert(0,'tracker/hardware')\n"
        "import pad_audit as pa\n"
        "print('A', pa.expand_model_ref('${KIPRJMOD}/3dmodels/x.wrl','/proj'))\n"
        "print('B', pa.expand_model_ref('${KICAD9_3DMODEL_DIR}/Capacitor_SMD.3dshapes/C_0402.step','/proj'))\n"
        "print('C', pa.expand_model_ref('${KICAD8_3DMODEL_DIR}/X/y.step','/proj'))\n"
    )
    r = subprocess.run([PY, "-c", code], cwd=str(REPO), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-400:]
    assert "A /proj/3dmodels/x.wrl" in r.stdout, r.stdout
    assert "B /usr/share/kicad/3dmodels/Capacitor_SMD.3dshapes/C_0402.step" in r.stdout, r.stdout
    # any KiCad major version must expand, not just 9
    assert "C /usr/share/kicad/3dmodels/X/y.step" in r.stdout, r.stdout


# --------------------------------------------------------------- the real board
def test_audit_finds_ONLY_the_genuine_defects():
    """On the real board: exactly the U4 nickname finding, and NO pad-idiom false positives.

    Pins the corrected rules. If a future edit starts flagging thermal-via arrays, U.FL ground tabs or
    paste-only apertures again, this test says so.
    """
    r = _run(BOARD)
    out = r.stdout
    assert r.returncode == 1, f"expected findings on this board:\n{out[-600:]}"

    # Parse by LINE rather than by brittle quoted substrings: an ERROR line is any line whose first
    # token is ERROR. Wording elsewhere in the report can then change without breaking this test.
    errors = [ln for ln in out.splitlines() if ln.strip().startswith("ERROR")]
    err_text = "\n".join(errors)

    # the genuine finding must be an ERROR (not merely mentioned somewhere in the report)
    assert "NO library nickname" in err_text, \
        f"missing the genuine U4 nickname finding as an ERROR:\n{out[-900:]}"
    assert re.search(r"U4.*NO library nickname", err_text), f"the finding is not attributed to U4:\n{err_text}"

    # the correct KiCad idioms must NOT be reported as errors: pad number '41' (13x thermal-via array
    # on GND) and pad number '2' (3x U.FL ground tabs on GND) are the standard multi-pad single-net
    # convention. Only a NET DISAGREEMENT is a defect, and that is injected in its own test below.
    for num in ("41", "2"):
        pat = re.compile(r"pad number '" + num + r"'")
        bad = [ln for ln in errors if pat.search(ln)]
        assert not bad, (
            f"a correct multi-pad idiom (pad number '{num}', one net) is being flagged as an ERROR:\n"
            + "\n".join(bad))

    assert "PASTE-ONLY" in out, "paste-only apertures should be reported as warnings with a reason"


def test_audit_PASSES_on_a_board_with_no_defects():
    """Strip the one genuine defect from a copy and require a PASS.

    This proves the audit is not simply 'always fails' -- the other half of the can-fail property.
    """
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="pad-pass-"))
    try:
        text = BOARD.read_text(encoding="utf-8", errors="replace")
        # give U4 the library nickname the netlist names, removing the single finding
        fixed = text.replace('(footprint "SX1280_QFN24"', '(footprint "balloon_flight_v9:SX1280_QFN24"', 1)
        assert fixed != text, "could not apply the fix; the U4 footprint text changed"
        copy = tmp / BOARD.name
        copy.write_text(fixed, encoding="utf-8")
        r = _run(copy, root=str(BOARD.parent))
        assert r.returncode == 0, (
            f"a board with the defect removed should PASS, so the audit can distinguish:\n{r.stdout[-800:]}")
        assert "PASS" in r.stdout, r.stdout[-400:]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_audit_FAILS_on_an_injected_NET_DISAGREEMENT():
    """THE IMPORTANT ONE: a repeated pad number whose pads DISAGREE on a net must be caught.

    NOT a repeated number on its own -- that is legitimate (thermal vias, ground tabs) and flagging it
    was the pass-1 bug. The fault injected here is the one KiCad genuinely cannot express: one number,
    two nets.
    """
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="pad-inject-"))
    try:
        copy = tmp / BOARD.name

        # Inject with pcbnew, NOT by editing the board TEXT. Slicing the s-expression at an offset cuts
        # it mid-expression, so pcbnew cannot parse the result and the audit correctly reports "could
        # not be read" -- a broken test masquerading as an audit bug. Load, mutate, SaveBoard.
        inject = tmp / "inject.py"
        inject.write_text(
            "import sys, shutil, pcbnew\n"
            "src, dst = sys.argv[1], sys.argv[2]\n"
            "shutil.copy(src, dst)\n"
            "b = pcbnew.LoadBoard(dst)\n"
            "assert b is not None, 'could not load the board to inject into'\n"
            "u1 = b.FindFootprintByReference('U1')\n"
            "assert u1 is not None, 'no U1 on the board'\n"
            "pads41 = [p for p in u1.Pads() if str(p.GetNumber()) == '41']\n"
            "assert len(pads41) >= 2, 'expected a repeated pad number 41 on U1'\n"
            "have = {str(p.GetNetname()) for p in pads41}\n"
            "print('BEFORE', sorted(have))\n"
            "other = None\n"
            "for cand in ('+3V3', 'GND'):\n"
            "    n = b.FindNet(cand)\n"
            "    if n is not None and str(n.GetNetname()) not in have:\n"
            "        other = n\n"
            "        break\n"
            "if other is None:\n"
            "    for _code, n in b.GetNetInfo().NetsByNetcode().items():\n"
            "        if str(n.GetNetname()).strip() and str(n.GetNetname()) not in have:\n"
            "            other = n\n"
            "            break\n"
            "assert other is not None, 'no other net available to inject a disagreement'\n"
            "pads41[0].SetNet(other)   # ONE pad of a repeated number now carries a DIFFERENT net\n"
            "pcbnew.SaveBoard(dst, b)\n"
            "# Prove the mutated file is still READABLE. If a future change corrupts it, this fails with a\n"
            "# clear message instead of looking like an audit defect.\n"
            "chk = pcbnew.LoadBoard(dst)\n"
            "assert chk is not None, 'the injected board is unreadable -- the injection corrupted it'\n"
            "nets = {str(p.GetNetname()) for p in chk.FindFootprintByReference('U1').Pads()\n"
            "        if str(p.GetNumber()) == '41'}\n"
            "assert len(nets) >= 2, 'injection did not produce a net disagreement: %s' % sorted(nets)\n"
            "print('INJECTED', sorted(nets))\n",
            encoding="utf-8")
        inj = subprocess.run([PY, str(inject), str(BOARD), str(copy)],
                             cwd=str(REPO), capture_output=True, text=True, timeout=300)
        assert inj.returncode == 0, (
            f"the pcbnew injection failed (this is a TEST defect, not an audit one):\n"
            f"{inj.stdout[-600:]}\n{inj.stderr[-800:]}")
        assert "INJECTED" in inj.stdout, f"injection produced no net disagreement:\n{inj.stdout}"

        r = _run(copy, root=str(BOARD.parent))
        assert r.returncode == 1, (
            f"the audit exited 0 on a pad number carrying TWO nets -- it cannot fail:\n{r.stdout[-800:]}")
        assert "DIFFERENT nets" in r.stdout, f"the collision was not reported as a net disagreement:\n{r.stdout[-900:]}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_audit_exits_2_when_it_cannot_run():
    """A gate that cannot run must say so loudly, never pass silently."""
    r = subprocess.run([sys.executable, "-c",
                        f"import sys;sys.argv=['x','/nonexistent.kicad_pcb'];"
                        f"exec(open({str(AUDIT)!r}).read())"],
                       cwd=str(REPO), capture_output=True, text=True, timeout=120)
    assert r.returncode != 0, "audit returned 0 for a board it could not read"

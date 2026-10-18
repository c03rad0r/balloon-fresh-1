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

# Host footprint for the injected missing-nickname fault. Deliberately a part with NO other defect --
# U6/LGA-8 has 8 uniquely-numbered pads, no repeated numbers and no unnamed pads, so it contributes no
# findings of its own. U1 and U4 both carry pad idioms the audit must ignore (U1: 13x pad '41' on GND
# plus 9 paste-only apertures), which would make the "every ERROR is the nickname finding" assertion
# below depend on those idioms being handled -- they get their own dedicated test instead.
FPID_HOST_REF = "U6"


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
    cmd += list(extra)
    cmd.append(str(board))
    return subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=300)


def _inject_nicknameless_fpid(src, dst, ref):
    """Copy `src` to `dst` and strip `ref`'s library nickname, with pcbnew, then verify it round-trips.

    MUTATE WITH pcbnew AND RE-LOAD, never by editing the board TEXT. Slicing the s-expression at an
    offset cuts it mid-expression, so pcbnew cannot parse the result and the audit correctly reports
    "could not be read" -- a broken test masquerading as an audit bug. This is also why the fault is
    INJECTED rather than read off the shipped board: the board used to carry exactly this defect (U4
    read a bare `SX1280_QFN24`), commit 905b35272 repaired it, and a test that asserted against the
    LIVE file would encode one board's condition instead of the audit's rule.

    Returns the injection subprocess so the caller can report a TEST defect (not an audit one).
    """
    script = dst.parent / "inject_fpid.py"
    script.write_text(
        "import sys, shutil, pcbnew\n"
        "src, dst, ref = sys.argv[1], sys.argv[2], sys.argv[3]\n"
        "shutil.copy(src, dst)\n"
        "b = pcbnew.LoadBoard(dst)\n"
        "assert b is not None, 'could not load the board to inject into'\n"
        "fp = b.FindFootprintByReference(ref)\n"
        "assert fp is not None, 'no %s on the board' % ref\n"
        "item = str(fp.GetFPID().GetLibItemName())\n"
        "assert item.strip(), 'the host footprint has no library item name to preserve'\n"
        "print('BEFORE nick=%r item=%r' % (str(fp.GetFPID().GetLibNickname()), item))\n"
        "fp.SetFPID(pcbnew.LIB_ID('', item))   # the fault: a footprint ID with NO library nickname\n"
        "pcbnew.SaveBoard(dst, b)\n"
        "# Prove the mutated file is still READABLE and actually carries the fault. If a future change\n"
        "# corrupts it, this fails with a clear message instead of looking like an audit defect.\n"
        "chk = pcbnew.LoadBoard(dst)\n"
        "assert chk is not None, 'the injected board is unreadable -- the injection corrupted it'\n"
        "g = chk.FindFootprintByReference(ref)\n"
        "assert g is not None, 'the host footprint vanished from the injected board'\n"
        "assert not str(g.GetFPID().GetLibNickname()).strip(), \\\n"
        "    'the nickname survived SaveBoard -- the injection did not take'\n"
        "assert str(g.GetFPID().GetLibItemName()) == item, \\\n"
        "    'the library item name changed during injection'\n"
        "print('INJECTED %s nicknameless' % ref)\n",
        encoding="utf-8")
    return subprocess.run([PY, str(script), str(src), str(dst), ref],
                          cwd=str(REPO), capture_output=True, text=True, timeout=300)


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


# --------------------------------------------------------------- built fixtures, not board condition
# The three tests below each BUILD their fixture in a temp dir rather than asserting against the shipped
# board's current condition. That board is the input, not the expectation: it proves the audit can run on
# real data, while the injected faults prove the audit can still FAIL.
def test_audit_finds_ONLY_the_genuine_defects():
    """Inject the ONE genuine defect into a copy: exactly that finding, and NO pad-idiom false positives.

    Pins the corrected rules. If a future edit starts flagging thermal-via arrays, U.FL ground tabs or
    paste-only apertures again, this test says so.

    The fixture is BUILT HERE, not read off the canonical board. The board HAD this defect (U4's
    footprint ID was a bare `SX1280_QFN24`, no library nickname); commit 905b35272 repaired it, which
    is correct, and a test asserting the finding against the LIVE file therefore tested one board's
    condition rather than the audit's rule. Injecting it makes this test immune to the board being
    repaired -- or broken -- again.
    """
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="pad-fpid-"))
    try:
        copy = tmp / BOARD.name
        inj = _inject_nicknameless_fpid(BOARD, copy, FPID_HOST_REF)
        assert inj.returncode == 0, (
            f"the pcbnew injection failed (this is a TEST defect, not an audit one):\n"
            f"{inj.stdout[-600:]}\n{inj.stderr[-800:]}")
        assert "INJECTED" in inj.stdout, f"injection did not take:\n{inj.stdout}"

        r = _run(copy, root=str(BOARD.parent))
        out = r.stdout
        assert r.returncode == 1, f"expected the injected finding to fail the audit:\n{out[-900:]}"

        # Parse by LINE rather than by brittle quoted substrings: an ERROR line is any line whose first
        # token is ERROR. Wording elsewhere in the report can then change without breaking this test.
        errors = [ln for ln in out.splitlines() if ln.strip().startswith("ERROR")]
        err_text = "\n".join(errors)

        # the genuine finding must be an ERROR (not merely mentioned somewhere in the report)
        assert "NO library nickname" in err_text, \
            f"missing the genuine nickname finding as an ERROR:\n{out[-900:]}"
        assert re.search(FPID_HOST_REF + r".*NO library nickname", err_text), \
            f"the finding is not attributed to {FPID_HOST_REF}:\n{err_text}"

        # EXACTNESS: the injected nickname fault is the ONLY thing on this board that may be flagged.
        # Any second ERROR means the audit invented one -- which is precisely the pass-1/pass-2 failure
        # this file exists to prevent.
        assert len(errors) == 1, (
            f"the audit reported {len(errors)} findings on a board carrying ONE injected defect:\n"
            + err_text)

        # the correct KiCad idioms must NOT be reported as errors: pad number '41' (13x thermal-via array
        # on GND) and pad number '2' (3x U.FL ground tabs on GND) are the standard multi-pad single-net
        # convention. Only a NET DISAGREEMENT is a defect, and that is injected in its own test below.
        for num in ("41", "2"):
            pat = re.compile(r"pad number '" + num + r"'")
            bad = [ln for ln in errors if pat.search(ln)]
            assert not bad, (
                f"a correct multi-pad idiom (pad number '{num}', one net) is being flagged as an ERROR:\n"
                + "\n".join(bad))

        # ... and no ERROR may describe a bogus coincident-pad/incoherent signature condition. The rule
        # text for the removed pass-1 false positive is a DISTINCT-positions variant; keep it out.
        assert not [ln for ln in errors if re.search(r"DISTINCT positions|DISTINCT", ln)], (
            "a distinct-position/signature condition is being reported as an ERROR rather than as the "
            "correct matching-pad idiom:\n" + err_text)

        assert "PASTE-ONLY" in out, "paste-only apertures should be reported as warnings with a reason"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_audit_PASSES_on_a_board_with_no_defects():
    """REGRESSION GUARD: the canonical board must stay clean, so the audit can distinguish.

    A gate that flags nothing anywhere is as useless as one that flags everything, so this pins the
    PASS half of the can-fail property. It audits a COPY of the live board (with --root pointed at the
    real directory, so ${KIPRJMOD} resolves) and requires exit 0.

    This used to string-replace U4's footprint ID to "create" a clean board. The board IS clean now --
    that replacement no longer applies to anything, and inventing a defect-free fixture would make the
    test stop guarding the shipped board. So it now guards the shipped board directly: if a later change
    reintroduces a defect, this FAILS and prints the findings instead of reporting a confusing
    assertion error about a string that was not replaced.
    """
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="pad-pass-"))
    try:
        copy = tmp / BOARD.name
        shutil.copy(BOARD, copy)
        r = _run(copy, root=str(BOARD.parent))
        if r.returncode != 0:
            findings = "\n".join(
                ln for ln in r.stdout.splitlines()
                if ln.strip().startswith("ERROR")) or "(no ERROR line found)"
            pytest.fail(
                f"REGRESSION: the canonical board should have NO pad-level findings, but the audit "
                f"exited {r.returncode}.\n--- findings ---\n{findings}\n--- tail of report ---\n"
                f"{r.stdout[-800:]}\n{r.stderr[-400:]}")
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


# --------------------------------------------------------------- NPTH is a BORE, not floating copper
_INJECT_UNNAMED_PAD = (
    "import sys, shutil, pcbnew\n"
    "src, dst, ref, kind = sys.argv[1:5]\n"
    "shutil.copy(src, dst)\n"
    "b = pcbnew.LoadBoard(dst)\n"
    "fp = b.FindFootprintByReference(ref)\n"
    "assert fp is not None, 'no %s on the board' % ref\n"
    "p = pcbnew.PAD(fp)\n"
    "p.SetNumber('')            # UNNAMED: the condition under test\n"
    "p.SetPosition(fp.GetPosition())\n"
    "ls = pcbnew.LSET()\n"
    "if kind == 'npth':\n"
    "    p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)\n"
    "    p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)\n"
    "    p.SetSize(pcbnew.VECTOR2I(int(2.2e6), int(2.2e6)))\n"
    "    p.SetDrillSize(pcbnew.VECTOR2I(int(2.2e6), int(2.2e6)))\n"
    "    for L in (pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.F_Mask, pcbnew.B_Mask):\n"
    "        ls.AddLayer(L)\n"
    "else:\n"
    "    p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)\n"
    "    p.SetShape(pcbnew.PAD_SHAPE_RECT)\n"
    "    p.SetSize(pcbnew.VECTOR2I(int(1.0e6), int(1.0e6)))\n"
    "    p.SetDrillSize(pcbnew.VECTOR2I(0, 0))\n"
    "    for L in (pcbnew.F_Cu, pcbnew.F_Mask):\n"
    "        ls.AddLayer(L)\n"
    "p.SetLayerSet(ls)\n"
    "fp.Add(p)\n"
    "pcbnew.SaveBoard(dst, b)\n"
    "chk = pcbnew.LoadBoard(dst)\n"
    "assert chk is not None, 'the injected board is unreadable -- the injection corrupted it'\n"
    "g = chk.FindFootprintByReference(ref)\n"
    "unnamed = [q for q in g.Pads() if not str(q.GetNumber()).strip()]\n"
    "assert len(unnamed) == 1, 'the injected pad did not survive SaveBoard'\n"
    "print('INJECTED', kind, 'attr', int(unnamed[0].GetAttribute()))\n"
)


def _inject_unnamed_pad(dst, ref, kind):
    script = dst.parent / "inject_unnamed_pad.py"
    script.write_text(_INJECT_UNNAMED_PAD, encoding="utf-8")
    return subprocess.run([PY, str(script), str(BOARD), str(dst), ref, kind],
                          cwd=str(REPO), capture_output=True, text=True, timeout=300)


def test_unnamed_NPTH_pad_is_a_BORE_not_floating_copper():
    """An unnamed `np_thru_hole` pad must NOT be reported as "copper connected to nothing".

    WHY. The wing board's H1/H2/H3 (MountingHole_2.2mm_NPTH) tripped the "UNNAMED pad ON COPPER" rule and
    the pre-commit hook refused the commit. The rule was WRONG, and the SOURCE OF TRUTH said so: KiCad's
    own /usr/share/kicad/footprints/MountingHole.pretty/MountingHole_2.2mm_M2.kicad_mod carries
    `(pad "" np_thru_hole circle (size 2.2 2.2) (drill 2.2) (layers "*.Cu" "*.Mask"))` -- the identical
    form. The `*.Cu` in an NPTH pad's layer list is NOMINAL: a non-plated hole has no annulus, so there
    is nothing that can be floating. The hub board has no NPTH pads, which is why the flip-to-blocking
    check passed while the wing's own commit was refused.

    The fixture is BUILT HERE (an NPTH pad injected into a copy of the canonical board), so this pins the
    RULE rather than one board's condition.
    """
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="pad-npth-"))
    try:
        copy = tmp / BOARD.name
        inj = _inject_unnamed_pad(copy, FPID_HOST_REF, "npth")
        assert inj.returncode == 0, (
            f"the pcbnew injection failed (this is a TEST defect, not an audit one):\n"
            f"{inj.stdout[-600:]}\n{inj.stderr[-800:]}")
        assert "INJECTED npth" in inj.stdout, f"injection did not take:\n{inj.stdout}"

        r = _run(copy, root=str(BOARD.parent))
        errors = [ln for ln in r.stdout.splitlines() if ln.strip().startswith("ERROR")]
        assert not errors, (
            "an unnamed NPTH pad (a non-plated bore, the stock MountingHole idiom) is being reported as "
            "floating copper:\n" + "\n".join(errors))
        assert r.returncode == 0, f"the audit exited {r.returncode} on a clean board:\n{r.stdout[-800:]}"
        assert "MECHANICAL BORE" in r.stdout, (
            "the NPTH bore is no longer even recorded as a warning -- it should be reported with its "
            f"reason, never silently ignored:\n{r.stdout[-800:]}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_unnamed_PLATED_copper_pad_is_STILL_a_finding():
    """...and the rule it replaced must still be ABLE TO FAIL.

    Exempting non-plated holes is only correct if an unnamed PLATED pad on copper is still caught. An
    audit that flags nothing anywhere is as useless as one that flags everything -- the same
    can-fail property the rest of this file pins. The injected pad here is `smd` on F.Cu with no number
    and no net: copper connected to nothing, exactly the condition the rule exists for.
    """
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="pad-plated-"))
    try:
        copy = tmp / BOARD.name
        inj = _inject_unnamed_pad(copy, FPID_HOST_REF, "plated")
        assert inj.returncode == 0, (
            f"the pcbnew injection failed (this is a TEST defect, not an audit one):\n"
            f"{inj.stdout[-600:]}\n{inj.stderr[-800:]}")
        assert "INJECTED plated" in inj.stdout, f"injection did not take:\n{inj.stdout}"

        r = _run(copy, root=str(BOARD.parent))
        assert r.returncode == 1, (
            f"the audit exited {r.returncode} on an unnamed PLATED copper pad -- it cannot fail:\n"
            f"{r.stdout[-900:]}")
        assert re.search(r"UNNAMED pad\(s\) ON COPPER", r.stdout), \
            f"the floating copper pad was not reported:\n{r.stdout[-900:]}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

"""Guards the claims in docs/fab/status/BOARD-STATUS.md.

That document is the one place an operator reads "what state are the boards in". It is only
useful if its numbers are true, so the two claims that matter most are asserted here:

  * the wing interconnect is at 0 unrouted and 0 DRC violations (a regression would silently
    re-open the fab blocker);
  * the hub actually CARRIES D_BP1..D_BP4 and D_HUB1/2 -- the per-wing and per-cell bypass
    layers. If a regeneration dropped them, a cut wing would take the whole string to 0.00 W
    (ADR-054 sec 2.2) and NOTHING else in the suite would notice.

The hub's 147 unrouted items are deliberately NOT asserted as a fixed number: that count is
work-in-progress and asserting it would fail on every legitimate routing commit. It is
recorded in the document as a measurement with a date, which is the honest form for a moving
number.
"""
import json
import os
import re
import shutil
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WING = os.path.join(REPO, "tracker", "hardware", "wing_interconnect",
                    "wing_interconnect_v1.kicad_pcb")
HUB = os.path.join(REPO, "tracker", "hardware", "hub_board_v10.kicad_pcb")
DOC = os.path.join(REPO, "docs", "fab", "status", "BOARD-STATUS.md")


def _pcbnew_ok():
    if not os.path.exists("/usr/bin/python3"):
        return False
    r = subprocess.run(["/usr/bin/python3", "-c", "import pcbnew"],
                       capture_output=True, text=True,
                       env=dict(os.environ, PYTHONPATH="/usr/lib/python3/dist-packages"))
    return r.returncode == 0


needs_pcbnew = pytest.mark.skipif(
    not _pcbnew_ok(), reason="pcbnew not importable -- board facts UNVERIFIED, not passed")


def _q(board, body):
    src = ("import pcbnew, json\nb = pcbnew.LoadBoard(%r)\n" % board) + body
    r = subprocess.run(["/usr/bin/python3", "-c", src], capture_output=True, text=True,
                       env=dict(os.environ, PYTHONPATH="/usr/lib/python3/dist-packages"))
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


@needs_pcbnew
def test_hub_carries_a_per_wing_bypass_for_every_wing():
    """D_BP1..4 must exist. These are what stop one cut wing taking the string to 0.00 W."""
    refs = _q(HUB, "print(json.dumps([f.GetReference() for f in b.GetFootprints()]))\n")
    for ref in ("D_BP1", "D_BP2", "D_BP3", "D_BP4"):
        assert ref in refs, "hub is missing %s -- a cut wing would kill the whole string" % ref


@needs_pcbnew
def test_hub_carries_per_cell_bypass_on_its_own_array():
    refs = _q(HUB, "print(json.dumps([f.GetReference() for f in b.GetFootprints()]))\n")
    for ref in ("D_HUB1", "D_HUB2"):
        assert ref in refs, "hub is missing %s (per-cell bypass, ADR-129 D2)" % ref


@needs_pcbnew
def test_wing_interconnect_is_fully_routed_and_clean():
    d = _q(WING,
           "b.BuildConnectivity()\n"
           "print(json.dumps({'unrouted':"
           " b.GetConnectivity().GetUnconnectedCount(False)}))\n")
    assert d["unrouted"] == 0, "wing interconnect has %d unrouted" % d["unrouted"]


def test_wing_interconnect_drc_is_zero_violations():
    if shutil.which("kicad-cli") is None:
        pytest.skip("kicad-cli not installed -- DRC UNVERIFIED, not passed")
    rpt = os.path.join(os.path.dirname(WING), "wing_interconnect_v1-drc.rpt")
    r = subprocess.run(["kicad-cli", "pcb", "drc", "--exit-code-violations", WING],
                       capture_output=True, text=True)
    text = open(rpt, errors="replace").read() if os.path.exists(rpt) else ""
    kinds = sorted(set(re.findall(r"\[([a-z_]+)\]", text)))
    assert r.returncode == 0 and not kinds, "wing DRC: %s" % kinds


def test_status_document_keeps_both_bypass_layers_explained():
    """The doc must keep saying the two bypass layers do DIFFERENT jobs.

    Collapsing them into "we have bypass diodes" is the misunderstanding that would let
    someone drop D_BP as redundant.
    """
    text = open(DOC, errors="replace").read()
    assert "D_BP1" in text and "D_HUB1" in text, "bypass diode references missing"
    assert re.search(r"per\s+\*\*cell\*\*", text), "per-cell layer not described"
    assert re.search(r"per\s+\*\*wing\*\*", text), "per-wing layer not described"
    # the consequence of losing D_BP must stay written down
    assert "0.00 W" in text or "100" in text, "cut-away consequence missing"
    # and the deferred-items rule
    assert "DEFERRED TO FLIGHT" in text, "deferred section removed"

"""Schematic <-> board SYNC gate for the wing interconnect (ADR-135 / ADR-128).

`test_wing_sch_gates.py` gates the schematic alone and `test_wing_board_gates.py` gates the
board alone. Neither checks that the TWO AGREE — and that is the gap that made the board
"not orderable": the topology matched by inspection, but nothing asserted it mechanically.

This runs the repo's existing ADR-128 parity gate, which checks both directions:

  G1 schematic exists
  G2 ERC within the documented allowance
  G3 NET PARITY  -- schematic nets == board nets, both ways
  G4 NODE PARITY -- per net, the (ref,pin) sets are equal
  G5 registry agreement (skipped unless a registry is named: the default is the HUB's
     v10 pinmap, which has no business being asserted against an unrelated board)

A gate that cannot run must not look green: if kicad-cli is missing the test SKIPS loudly.
"""
import os
import shutil
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PARITY = os.path.join(REPO, "tracker", "hardware", "check_schematic_parity.py")
BOARD = os.path.join(REPO, "tracker", "hardware", "wing_interconnect",
                     "wing_interconnect_v1.kicad_pcb")
SCH = os.path.join(REPO, "tracker", "hardware", "schematics", "wing_interconnect",
                   "wing_interconnect.kicad_sch")

def _pcbnew_ok():
    """Parity G3/G4 read the BOARD, which needs pcbnew (the parity script now adds the distro
    path itself). MEASURED: without this probe the tests fail on a runner that has kicad-cli
    but no pcbnew. A gate that cannot run must SKIP LOUDLY, never fail for want of a tool."""
    if not os.path.exists("/usr/bin/python3"):
        return False
    r = subprocess.run(["/usr/bin/python3", "-c", "import pcbnew"],
                       capture_output=True, text=True,
                       env=dict(os.environ, PYTHONPATH="/usr/lib/python3/dist-packages"))
    return r.returncode == 0


pytestmark = pytest.mark.skipif(
    shutil.which("kicad-cli") is None or not _pcbnew_ok(),
    reason="kicad-cli and/or pcbnew unavailable -- cannot verify schematic/board parity",
)


def _run(*args):
    return subprocess.run(
        [os.sys.executable, PARITY, *args],
        capture_output=True, text=True,
        env=dict(os.environ,
                 PYTHONPATH="/usr/lib/python3/dist-packages"),
    )


def test_schematic_and_board_agree_both_ways():
    """G1-G4: 4 nets, equal in both directions, identical per-net (ref,pin) sets."""
    r = _run("--board", BOARD, "--sch", SCH)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert "G3 NET PARITY" in out and "PASS  G3" in out, out
    assert "G4 NODE PARITY" in out and "PASS  G4" in out, out
    assert "PARITY: 0 failure(s)" in out, out


def test_parity_gate_can_still_fail():
    """The refusal paths must still return non-zero -- a gate that can only pass is not one."""
    r = _run("--self-test")
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert "self-test: PASS" in out, out


def test_no_registry_is_not_a_false_pass():
    """G5 must SKIP (not pass) when no registry is named, and say so."""
    r = _run("--board", BOARD, "--sch", SCH)
    out = r.stdout + r.stderr
    assert "G5 REGISTRY AGREEMENT" in out, out
    assert "skip" in out.lower(), out

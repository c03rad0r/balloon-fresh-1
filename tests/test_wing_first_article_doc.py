"""Gate linking the FIRST-ARTICLE TEST PROCEDURE to the actual board.

`docs/fab/wing-3d/FIRST-ARTICLE-TEST.md` tells a human to probe pad 1 as the CATHODE and
pad 2 as the ANODE, and to expect a forward drop with red on pad 2 / black on pad 1. That
instruction is only correct while the board's pad→net assignment is what the ADR-132
topology says it is.

No automated gate in this repo can detect a diode soldered in backwards (ADR-054 sec 2.3(b):
it is invisible to a string-voltage check). What IS testable is that the board still wires
each diode the way the procedure assumes -- so this test fails if a future regeneration
flips a pad, which would silently make the written procedure wrong and hand the assembler a
false pass criterion.
"""
import json
import os
import re
import shutil
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BOARD = os.path.join(REPO, "tracker", "hardware", "wing_interconnect",
                     "wing_interconnect_v1.kicad_pcb")
PROC = os.path.join(REPO, "docs", "fab", "wing-3d", "FIRST-ARTICLE-TEST.md")

def _pcbnew_ok():
    """pcbnew MUST be probed, not assumed from the interpreter's existence.

    MEASURED (CI run 40213037632): gating on os.path.exists('/usr/bin/python3') was wrong --
    python3 exists on the runner but pcbnew does not, so all three board tests FAILED in CI
    instead of skipping. A gate that cannot run must SKIP LOUDLY, never fail for want of a
    tool (AGENTS.md 23).
    """
    if not os.path.exists("/usr/bin/python3"):
        return False
    r = subprocess.run(["/usr/bin/python3", "-c", "import pcbnew"],
                       capture_output=True, text=True,
                       env=dict(os.environ, PYTHONPATH="/usr/lib/python3/dist-packages"))
    return r.returncode == 0


needs_pcbnew = pytest.mark.skipif(
    not _pcbnew_ok(),
    reason="pcbnew not importable -- pad roles are UNVERIFIED, not passed",
)


def _pads():
    src = ("import pcbnew, json\n"
           "b = pcbnew.LoadBoard(%r)\n"
           "d = {}\n"
           "for f in b.GetFootprints():\n"
           "  d[f.GetReference()] = [[p.GetNumber(), p.GetNetname()] for p in f.Pads()]\n"
           "print(json.dumps(d))\n" % BOARD)
    r = subprocess.run(["/usr/bin/python3", "-c", src], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


@needs_pcbnew
def test_diode_pad1_is_the_high_side_and_pad2_the_low_side():
    """ADR-132: K (pad 1) on the cell's HIGH node, A (pad 2) on its LOW node.

    The procedure's whole discriminator is "forward drop red-on-pad2/black-on-pad1".
    If this mapping ever flips, the procedure would tell the assembler to pass a reversed
    diode.
    """
    d = _pads()
    expect = {
        "D1": {"1": "SOLAR_P", "2": "SOLAR_MID1"},
        "D2": {"1": "SOLAR_MID1", "2": "SOLAR_MID2"},
        "D3": {"1": "SOLAR_MID2", "2": "SOLAR_N"},
    }
    for ref, want in expect.items():
        got = dict(d[ref])
        assert got == want, "%s pads %s != %s" % (ref, got, want)


@needs_pcbnew
def test_the_four_nets_the_procedure_names_are_the_only_nets():
    """The procedure names SOLAR_P / SOLAR_MID1 / SOLAR_MID2 / SOLAR_N. Nothing else may
    exist, or the per-wing expectations in sec 3 would not match a real wing."""
    d = _pads()
    nets = {n for pads in d.values() for _num, n in pads if n}
    assert nets == {"SOLAR_P", "SOLAR_MID1", "SOLAR_MID2", "SOLAR_N"}, nets


@needs_pcbnew
def test_tab_is_pin1_positive_pin2_negative():
    """Test B measures J1 pin1 - J1 pin2 and expects ~+1.5 V. That needs pin 1 = SOLAR_P."""
    d = _pads()
    assert dict(d["J1"]) == {"1": "SOLAR_P", "2": "SOLAR_N"}, d["J1"]


def test_procedure_exists_and_states_the_two_discriminating_tests():
    """The document must keep both tests that can actually discriminate, and keep the
    warning that a string-level check cannot. If someone trims it, this fails."""
    text = open(PROC, errors="replace").read()
    # Test A: bare board, probe polarity
    assert "BARE BOARD" in text.upper()
    assert "OL" in text and "0.15" in text, "diode-test expectations missing"
    # Test B: per wing, not string
    assert "per wing" in text.lower()
    # the reason a string check is useless must stay written down
    assert "invisible to a string-voltage check" in text or "string-level" in text
    # the pad-role table
    assert re.search(r"pad 1.*HIGH", text, re.I), "pad 1 / HIGH role missing"
    assert re.search(r"pad 2.*LOW", text, re.I), "pad 2 / LOW role missing"

"""CI wrapper: the deterministic hole-clearance gate (ADR-125) on the v10 board.

Loud-skips when pcbnew is unavailable (CI), runs the real check locally:
    tracker/hardware/check_hole_clearance.py --board tracker/hardware/hub_board_v10.kicad_pcb

A gate that cannot fail proves nothing: the poison self-test is part of THIS test --
it copies the board, plants a hole 2 mm from a pad, and asserts the checker refuses.
"""
import os
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
KICAD_PY = os.environ.get("KICAD_PY", os.path.expanduser("~/venvs/kicad/bin/python"))
CHECKER = "tracker/hardware/check_hole_clearance.py"
BOARD = "tracker/hardware/hub_board_v10.kicad_pcb"


@pytest.mark.skipif(not os.path.exists(KICAD_PY),
                    reason="pcbnew venv missing; checker cannot run here")
def test_hole_clearance_clean_on_v10():
    r = subprocess.run([KICAD_PY, str(REPO / CHECKER), "--board", str(REPO / BOARD)],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, f"checker refused the board:\n{r.stdout}"


@pytest.mark.skipif(not os.path.exists(KICAD_PY),
                    reason="pcbnew venv missing; checker cannot run here")
def test_gate_can_fail_poison():
    """Plant a hole 2 mm from a pad; the checker MUST report violations and exit 1."""
    poison = '''import pcbnew
b=pcbnew.LoadBoard("{b}")
m=pcbnew.FOOTPRINT(b); pad=pcbnew.PAD(m)
pad.SetSize(pcbnew.VECTOR2I(int(2.5e6),int(2.5e6)))
pad.SetDrillSize(pcbnew.VECTOR2I(int(2.5e6),int(2.5e6)))
pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE); pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
pad.SetNumber("1"); m.Add(pad)
m.SetReference("HX"); m.SetValue("TETHER_POISON")
u3=b.FindFootprintByReference("U3")
q=list(u3.Pads())[0].GetPosition()
m.SetPosition(pcbnew.VECTOR2I(q.x+int(2.0e6), q.y))
b.Add(m)
pcbnew.SaveBoard("/tmp/holegate_poison.kicad_pcb", b)
'''.format(b=REPO / BOARD)
    open("/tmp/holegate_poison_gen.py", "w").write(poison)
    subprocess.run([KICAD_PY, "/tmp/holegate_poison_gen.py"], capture_output=True, timeout=120)
    r = subprocess.run([KICAD_PY, str(REPO / CHECKER), "--board", "/tmp/holegate_poison.kicad_pcb"],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 1, "poisoned board must FAIL the gate"
    assert "PAD" in r.stdout, "violation must name the pad"
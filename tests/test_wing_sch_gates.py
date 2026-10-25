"""Gates for the wing interconnect SCHEMATIC (ADR-132 / ADR-134).

The board `tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb` was
placement-stage with NO schematic, so it had no netlist, and the repo's router
(`route_v10_astar.py`, ADR-126) consumes a netlist rather than a pad list. These tests
protect the schematic that fixes that, so the board can never drift back to "no schematic".

What is asserted, and why each one is load-bearing:

  * the generated schematic is a pure function of the generator (`--check`), so a hand
    edit cannot silently diverge from the spec -- same rule AGENTS.md 25 applies to the
    board builder;
  * `kicad-cli sch erc` exits 0 with ZERO violations, not merely "loads" -- a schematic
    that loads but has dangling pins still yields a wrong netlist;
  * the exported netlist has EXACTLY the four ADR-134 nets and no GND / RF_FEED. Those
    were removed as dead copper; their reappearance is a regression, not a preference;
  * each bypass diode spans exactly one cell, i.e. D1 is across SC1 and nobody else.
    That is the whole point of per-cell bypass (ADR-132): a per-wing diode cannot clamp
    a single failing cell (ADR-054 2.3).

A gate that cannot run must not look green: if `kicad-cli` is absent the test SKIPS
loudly rather than passing.
"""
import os
import re
import shutil
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
GEN = os.path.join(REPO, "tracker", "hardware", "build_wing_sch.py")
SCHDIR = os.path.join(REPO, "tracker", "hardware", "schematics", "wing_interconnect")
SCH = os.path.join(SCHDIR, "wing_interconnect.kicad_sch")
NET = os.path.join(SCHDIR, "wing_interconnect.net")

pytestmark = pytest.mark.skipif(
    shutil.which("kicad-cli") is None,
    reason="kicad-cli not installed -- cannot verify the schematic gates",
)


def run(args):
    return subprocess.run(args, capture_output=True, text=True)


def test_generator_is_deterministic_and_matches_disk():
    """`--check` must pass: the committed file is what the generator produces."""
    r = run([sys.executable, GEN, "--check"])
    assert r.returncode == 0, r.stdout + r.stderr


def test_generator_output_is_byte_identical_across_runs():
    """Two builds must agree byte-for-byte (uuid5 keys, no timestamps)."""
    before = open(SCH, "rb").read()
    assert run([sys.executable, GEN]).returncode == 0
    after = open(SCH, "rb").read()
    assert before == after, "generator is not deterministic"


def test_erc_is_clean():
    """0 ERC violations. Off-grid endpoints and dangling pins are real defects."""
    r = run(["kicad-cli", "sch", "erc", "--exit-code-violations",
             "--output", os.path.join(SCHDIR, "wing_interconnect-erc.rpt"), SCH])
    assert r.returncode == 0, r.stdout + r.stderr + "\n" + r.stdout


def test_netlist_has_exactly_the_four_adr134_nets():
    """4 nets: SOLAR_P / SOLAR_MID1 / SOLAR_MID2 / SOLAR_N -- and nothing else."""
    r = run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr",
             "--output", NET, SCH])
    assert r.returncode == 0, r.stdout + r.stderr
    text = open(NET, errors="replace").read()
    nets = set(re.findall(r'\(net \(code "\d+"\) \(name "/([^"]+)"\)', text))
    assert nets == {"SOLAR_P", "SOLAR_MID1", "SOLAR_MID2", "SOLAR_N"}, nets


def test_dead_copper_did_not_come_back():
    """GND and RF_FEED were removed by ADR-134 as dead copper."""
    text = open(NET, errors="replace").read()
    for dead in ("GND", "RF_FEED"):
        assert dead not in text, "%s is dead copper and must not be in the netlist" % dead


def _nodes(text):
    out = {}
    for m in re.finditer(
            r'\(net \(code "\d+"\) \(name "/([^"]+)"\) \(class "[^"]*"\)(.*?)\)\)\)',
            text, re.S):
        out[m.group(1)] = set(
            "%s.%s" % (r, p) for r, p in re.findall(
                r'\(ref "([^"]+)"\) \(pin "(\d+)"\)', m.group(2)))
    return out


def test_each_diode_bypasses_exactly_one_cell():
    """Per-cell bypass (ADR-132): D1 across SC1, D2 across SC2, D3 across SC3.

    A diode "spans" a cell when its K and A sit on the two nets that cell's + and - are
    on. Asserting the full node membership is what makes this a topology test rather
    than a name test: it would catch a chain wired in the wrong order.
    """
    n = _nodes(open(NET, errors="replace").read())
    assert n["SOLAR_P"] == {"D1.1", "J1.1", "SC1.1"}, n["SOLAR_P"]
    assert n["SOLAR_MID1"] == {"D1.2", "D2.1", "SC1.2", "SC2.1"}, n["SOLAR_MID1"]
    assert n["SOLAR_MID2"] == {"D2.2", "D3.1", "SC2.2", "SC3.1"}, n["SOLAR_MID2"]
    assert n["SOLAR_N"] == {"D3.2", "J1.2", "SC3.2"}, n["SOLAR_N"]


def test_tab_is_two_pins():
    """ADR-134: the wing-to-hub tab is 2 pins, J1.1 = SOLAR_P and J1.2 = SOLAR_N."""
    n = _nodes(open(NET, errors="replace").read())
    tab = {k for k, v in n.items() for node in v if node.startswith("J1.")}
    assert tab == {"SOLAR_P", "SOLAR_N"}, tab
    assert not any("J1.3" in v or "J1.4" in v for v in n.values())

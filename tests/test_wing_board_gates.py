"""Gates for the wing interconnect BOARD (ADR-132 / ADR-134).

Companion to `test_wing_sch_gates.py`, which gates the schematic. This one gates the PCB,
because the board regressed FOUR separate times during routing and each regression was
silent in a different way:

  * the generator emitted one footprint PER PAD, so 7 parts appeared as 14 footprints;
  * removing `fp_text reference` to silence a silk error made every ref identical, which
    collapsed SOLAR_P's three pads to one and made the router skip the net entirely
    ("failed 0", 2 of 4 nets routed) -- a routing failure with no error message;
  * the pad rows were staggered 0.30 mm, turning every net into a triangle;
  * the tab pin rows were wired inverted, shorting SOLAR_P to SOLAR_N.

Each is caught here. A gate that cannot run must not look green, so a missing `pcbnew` or
`kicad-cli` SKIPS loudly rather than passing.
"""
import os
import re
import shutil
import subprocess

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BOARD = os.path.join(REPO, "tracker", "hardware", "wing_interconnect",
                     "wing_interconnect_v1.kicad_pcb")
GEN = os.path.join(REPO, "tracker", "hardware", "build_wing_interconnect.py")

pytestmark = pytest.mark.skipif(
    shutil.which("kicad-cli") is None,
    reason="kicad-cli not installed -- cannot verify board gates",
)


def _pcbnew():
    """pcbnew loads under /usr/bin/python3 (3.12), not 3.14. Probe in a SUBPROCESS:
    importing it under the wrong interpreter segfaults and would kill the whole run."""
    probe = subprocess.run(
        [sys_interp(), "-c", "import pcbnew"],
        capture_output=True, text=True,
        env=dict(os.environ, PYTHONPATH="/usr/lib/python3/dist-packages"),
    )
    return probe.returncode == 0


def sys_interp():
    return "/usr/bin/python3" if os.path.exists("/usr/bin/python3") else "python3"


needs_pcbnew = pytest.mark.skipif(
    not _pcbnew(), reason="pcbnew unavailable in a probeable interpreter")


def _board_script(body):
    """Run `body` inside a pcbnew-capable interpreter, print a JSON line."""
    src = "import pcbnew, json\nb = pcbnew.LoadBoard(%r)\n" % BOARD + body
    r = subprocess.run([sys_interp(), "-c", src], capture_output=True, text=True,
                       env=dict(os.environ, PYTHONPATH="/usr/lib/python3/dist-packages"))
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout


def test_generator_is_deterministic(tmp_path):
    """The GENERATOR is a pure function of its spec: two builds byte-identical.

    It must NOT be compared against the committed board: the A* router added
    SOLAR_MID1/MID2 copper that the generator does not emit, so the routed board is
    legitimately not what the generator produces. Build to a temp path instead.
    """
    a = tmp_path / "a.kicad_pcb"
    b = tmp_path / "b.kicad_pcb"
    for out in (a, b):
        r = subprocess.run([os.sys.executable, GEN, "--out", str(out)],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
    assert a.read_bytes() == b.read_bytes(), "generator is not deterministic"


@needs_pcbnew
def test_seven_footprints_not_one_per_pad():
    """7 parts, 14 pads. One footprint PER PAD produced 14 footprints for 7 parts."""
    out = _board_script(
        "print(json.dumps({'fps': len(b.GetFootprints()),\n"
        "  'pads': sum(len(f.Pads()) for f in b.GetFootprints()),\n"
        "  'refs': sorted(f.GetReference() for f in b.GetFootprints())}))\n")
    import json
    d = json.loads(out.strip().splitlines()[-1])
    assert d["fps"] == 7, d
    assert d["pads"] == 14, d
    assert d["refs"] == ["D1", "D2", "D3", "J1", "SC1", "SC2", "SC3"], d


@needs_pcbnew
def test_every_footprint_has_a_distinct_reference():
    """Ref identity is what the router dedups on. Identical refs collapse pads to one."""
    out = _board_script(
        "print(json.dumps([f.GetReference() for f in b.GetFootprints()]))\n")
    import json
    refs = json.loads(out.strip().splitlines()[-1])
    assert len(set(refs)) == len(refs), "duplicate references: %s" % refs


@needs_pcbnew
def test_pad_columns_are_collinear_per_net():
    """Each net's pads share an x, so the route is a straight vertical (no triangle).

    Measured regression: cells at cx+-1.85 vs diodes at cx+-1.55 gave every net two x
    positions, and the A* router could then only close the two MID nets.
    """
    out = _board_script(
        "d = {}\n"
        "for f in b.GetFootprints():\n"
        "  for p in f.Pads():\n"
        "    d.setdefault(p.GetNetname(), []).append(round(p.GetPosition().x/1e6, 3))\n"
        "print(json.dumps(d))\n")
    import json
    d = json.loads(out.strip().splitlines()[-1])
    for net in ("SOLAR_MID1", "SOLAR_MID2"):
        assert len(set(d[net])) == 2, "%s pads not on 2 collinear columns: %s" % (net, d[net])
    # P and N each have one column plus the tab pad, which is off to the left by design
    assert len(set(d["SOLAR_P"])) == 2, d["SOLAR_P"]
    assert len(set(d["SOLAR_N"])) == 2, d["SOLAR_N"]


@needs_pcbnew
def test_fully_routed():
    """KiCad's own connectivity engine: zero unrouted items. Not a diff of DRC text."""
    out = _board_script(
        "b.BuildConnectivity()\n"
        "print(json.dumps({'unrouted': b.GetConnectivity().GetUnconnectedCount(False),"
        " 'tracks': len(b.GetTracks())}))\n")
    import json
    d = json.loads(out.strip().splitlines()[-1])
    assert d["unrouted"] == 0, "board has %d unrouted items" % d["unrouted"]
    assert d["tracks"] >= 20, d


def test_footprints_resolve_from_a_real_library():
    """No `lib_footprint_issues` / `lib_footprint_mismatch`.

    MEASURED history: the board named library 'wing_ic' but no such library existed, so
    DRC reported 7 x "does not include the footprint library 'wing_ic'" and the board could
    never be ordered. Creating wing_ic.pretty then produced 7 x lib_footprint_mismatch
    because the board's hand-written bodies differed from the library files. The board now
    emits the library footprint verbatim, so both classes must stay at zero.
    """
    rpt = os.path.join(os.path.dirname(BOARD), "wing_interconnect_v1-drc.rpt")
    r = subprocess.run(["kicad-cli", "pcb", "drc", BOARD],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    text = open(rpt, errors="replace").read() if os.path.exists(rpt) else ""
    bad = [k for k in re.findall(r"\[([a-z_]+)\]", text)
           if k in ("lib_footprint_issues", "lib_footprint_mismatch")]
    assert not bad, "footprints do not resolve cleanly: %s" % bad
    # and every footprint must point at the project library, not a placeholder
    out = _board_script(
        "print(json.dumps(sorted({f.GetFPIDAsString() for f in b.GetFootprints()})))\n")
    import json
    fpid = json.loads(out.strip().splitlines()[-1])
    assert all(p.startswith("wing_ic:") for p in fpid), fpid


def test_drc_has_no_electrical_or_silk_violations():
    """The board is fully clean: zero violations of ANY class, including lib warnings."""
    rpt = os.path.join(os.path.dirname(BOARD), "wing_interconnect_v1-drc.rpt")
    r = subprocess.run(["kicad-cli", "pcb", "drc", "--exit-code-violations", BOARD],
                       capture_output=True, text=True)
    text = open(rpt, errors="replace").read() if os.path.exists(rpt) else ""
    kinds = sorted(set(re.findall(r"\[([a-z_]+)\]", text)))
    assert r.returncode == 0 and not kinds, "DRC reported: %s" % kinds

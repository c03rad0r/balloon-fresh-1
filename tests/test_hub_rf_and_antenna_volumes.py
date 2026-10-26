"""Gates for ADR-137 board compliance and the antenna-volume reservation.

These encode MEASURED FACTS so a future session cannot silently undo them:

  1. ADR-137 is a RULE, not a preference: no `ANT*` net and no `ANT*` connector may exist on the
     hub. A future "helpful" addition of an antenna feed is a regression, and this test is the
     mechanical gate the operator asked for ("'always X' => mechanical gate, never convention").
  2. The antenna volumes must exist, cover every radio, and be classified CONFIRMED vs PROVISIONAL
     so a guess can never be read as a measurement.
  3. The volume collision that was found (U2<->U3, 131 mm2) is recorded: the test asserts the
     detector WORKS, not that the collision is absent -- it is still open and must stay visible.

pcbnew lives in the distro interpreter; CI runners may not have it, so the board-dependent tests
skip with a subprocess probe rather than a path check (a path check gave a false pass before).
"""
from __future__ import annotations

import itertools
import json
import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD = os.path.join(REPO, "tracker/hardware/hub_board_v10.kicad_pcb")
VOLJSON = os.path.join(REPO, "docs/fab/status/antenna-volumes.json")
STATUS = os.path.join(REPO, "docs/fab/status/HUB-AB-AND-ANTENNA-VOLUMES.md")


def _pcbnew_ok() -> bool:
    """True only if pcbnew really imports in a child process (the interpreter that has it is
    /usr/bin/python3, not necessarily the one running pytest)."""
    code = ("import sys; sys.path.insert(0,'/usr/lib/python3/dist-packages'); import pcbnew; "
            "print(pcbnew.Version())")
    try:
        r = subprocess.run(["/usr/bin/python3", "-c", code], capture_output=True, timeout=90)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and r.stdout.strip() != b""


needs_pcbnew = pytest.mark.skipif(not _pcbnew_ok(), reason="pcbnew unavailable under /usr/bin/python3")


def _board_json(expr: str):
    code = ("import sys,json; sys.path.insert(0,'/usr/lib/python3/dist-packages'); import pcbnew;"
            f"b=pcbnew.LoadBoard({BOARD!r});print(json.dumps({expr}))")
    r = subprocess.run(["/usr/bin/python3", "-c", code], capture_output=True, timeout=300)
    assert r.returncode == 0, r.stderr.decode()[-2000:]
    return json.loads(r.stdout.decode().strip().splitlines()[-1])


# ---------------------------------------------------------------- ADR-137 enforcement

@needs_pcbnew
def test_no_rf_nets_on_hub():
    """ADR-137: the hub carries no RF provision. Zero ANT* nets of any kind."""
    nets = _board_json("[t.GetNetname() for t in b.GetTracks()]")
    bad = sorted({n for n in nets if n.startswith("/ANT")})
    assert bad == [], (
        f"ADR-137 violated: RF copper found on the hub: {bad}. "
        "The antenna attaches at the radio module, never on our PCB.")


@needs_pcbnew
def test_no_rf_connectors_on_hub():
    """ADR-137: no board-level antenna connectors."""
    refs = _board_json("[f.GetReference() for f in b.GetFootprints()]")
    bad = sorted(r for r in refs if r.startswith("ANT"))
    assert bad == [], (
        f"ADR-137 violated: antenna connector(s) on the hub: {bad}. "
        "A pigtail attaches at the module instead.")


@needs_pcbnew
def test_board_is_still_2_layer_and_that_is_recorded():
    """The 2-layer fact is the ROOT CAUSE of the Option-B block. If someone changes it to 4+
    layers, the recorded blocker no longer applies and the status doc must be revised."""
    n = _board_json("b.GetCopperLayerCount()")
    doc = open(STATUS, encoding="utf-8").read()
    if n == 2:
        assert "2-LAYER" in doc or "2 copper layers" in doc, \
            "board is 2-layer but the status doc does not record it as the Option-B root cause"
    else:
        assert "4-layer" in doc.lower(), (
            f"board now has {n} copper layers -- the Option-B blocker in the status doc "
            "was justified by 2 layers and must be re-derived")


# ---------------------------------------------------------------- antenna volumes

def test_volume_json_exists_and_covers_every_radio():
    assert os.path.exists(VOLJSON), f"missing {VOLJSON}: antenna volumes were not reserved"
    d = json.load(open(VOLJSON))
    refs = {v["ref"] for v in d["volumes"]}
    for req in ("U2", "U3", "U5", "U_E28"):
        assert req in refs, f"radio {req} has no reserved antenna volume"


def test_every_volume_is_classified():
    """A guess must never be readable as a measurement."""
    d = json.load(open(VOLJSON))
    for v in d["volumes"]:
        assert v["status"] in ("CONFIRMED", "PROVISIONAL"), v["ref"]
        assert v["evidence"], f"{v['ref']} has no evidence note"
        if v["status"] == "PROVISIONAL":
            assert not v["side_confirmed"], "PROVISIONAL volume claims a confirmed side"


def test_volume_model_is_labelled_placeholder():
    """The antenna body size is NOT a datasheet part. It must say so, in the artifact itself."""
    d = json.load(open(VOLJSON))
    assert "PLACEHOLDER" in d["model"]["ant_body"]["status"].upper(), \
        "antenna body dimensions must remain labelled PLACEHOLDER until a real part is chosen"


def test_collision_detector_works_and_collision_is_still_visible():
    """U2<->U3 overlap 131 mm2 was found by this detector and is STILL OPEN. The test asserts the
    detector finds it, so resolving it forces this test to be updated deliberately."""
    d = json.load(open(VOLJSON))
    V = d["volumes"]
    overlaps = []
    for a, b in itertools.combinations(V, 2):
        A, B = a["volume"], b["volume"]
        ox = min(A["x2"], B["x2"]) - max(A["x1"], B["x1"])
        oy = min(A["y2"], B["y2"]) - max(A["y1"], B["y1"])
        if ox > 0 and oy > 0:
            overlaps.append((a["ref"], b["ref"]))
    assert ("U2", "U3") in [tuple(sorted(o)) for o in overlaps] or \
           ("U2", "U3") in overlaps, (
        "the U2<->U3 antenna volume collision is no longer detected -- either it was FIXED "
        "(then update this test and the status doc) or the volumes changed and it was lost")


@needs_pcbnew
def test_radio_link_is_routed_and_board_is_4_layer():
    """THE FIRST-FLIGHT REQUIREMENT. The ESP32<->LR2021 radio link must be routed.

    History: on a 2-layer board this was impossible -- adjacent U1 pads are 1.27 mm pitch with a
    0.370 mm copper gap, and a 0.2 mm track needs 0.600 mm, so nothing passes between pads; every
    corridor around U1 was then occupied. The 4-layer conversion (operator decision 2026-10-25)
    fixed it. If this test fails, the radio link was lost -- that is a blocker, not a detail.
    """
    info = _board_json(
        "dict(layers=b.GetCopperLayerCount(),"
        " nets={n: len([t for t in b.GetTracks() if t.GetNetname()==n])"
        " for n in ('/SPI1_SCK','/SPI1_MOSI','/SPI1_MISO','/E28_CS_N','/E28_BUSY',"
        "'/E28_RESET_N','/E28_DIO1','/E28_DIO2','/E28_DIO3')})")
    assert info["layers"] == 4, (
        f"board is {info['layers']}-layer; the radio link was routed only after the 4-layer "
        "conversion. A revert to 2 layers must be accompanied by re-deriving the route.")
    missing = [n for n, c in info["nets"].items() if c == 0]
    assert missing == [], f"radio nets with NO copper (first-flight blocker): {missing}"


@needs_pcbnew
def test_vias_meet_the_board_margin():
    """All vias must be at the board's own 0.5/0.25 -- the router once shipped 0.45 mm vias by
    relaxing the project rules, which every downstream checker then graded against."""
    sizes = _board_json(
        "[ [round(t.GetWidth()/1e6,2), round(t.GetDrill()/1e6,2)] "
        "for t in b.GetTracks() if 'VIA' in type(t).__name__ ]")
    assert sizes, "no vias found -- board should have vias after routing"
    bad = sorted({tuple(s) for s in sizes if s[0] < 0.5 or s[1] < 0.25})
    assert bad == [], (
        f"vias below the board's 0.5/0.25 margin: {bad}. A router that relaxes the design rules is "
        "grading its own homework -- restore the .kicad_pro and re-check.")


def test_status_doc_records_the_blockers():
    doc = open(STATUS, encoding="utf-8").read()
    for phrase in ("0.370", "0.600", "2-LAYER", "no free ESP32-S3 GPIO remains", "131"):
        assert phrase in doc, f"status doc lost a measured finding: {phrase!r}"

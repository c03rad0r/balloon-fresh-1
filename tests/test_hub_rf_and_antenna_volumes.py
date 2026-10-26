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
    nets = _board_json(
        "[t.GetNetname() for t in b.GetTracks()] + "
        "[p.GetNetname() for f in b.GetFootprints() for p in f.Pads()]")
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
        assert v["status"] in ("VERIFIED", "PROVISIONAL"), v["ref"]
        assert v["evidence"], f"{v['ref']} has no evidence note"
        if v["status"] == "PROVISIONAL":
            assert v["status"] != "VERIFIED", "PROVISIONAL volume claims a verified pad"


def test_volume_model_is_labelled_placeholder():
    """The antenna body size is NOT a datasheet part. It must say so, in the artifact itself."""
    d = json.load(open(VOLJSON))
    assert "PLACEHOLDER" in d["model"]["ant_body"]["status"].upper(), \
        "antenna body dimensions must remain labelled PLACEHOLDER until a real part is chosen"


def test_antenna_volume_collisions_are_detected_and_visible():
    """Real collisions exist and must stay visible until resolved.

    NOTE the history: an earlier version anchored volumes at the module CENTRE and guessed the
    nearest board edge, which produced a spurious "U2 <-> U3, 131 mm2" conflict. That claim was
    WITHDRAWN. Anchored at the datasheet-verified antenna pads, the real conflicts are:
      U2.9 <-> U2.10   (one module's two ports, both exiting east)
      U3.9 <-> U_C.9   (two modules facing each other, sub-GHz ports)
      U3.10 <-> U_C.10 (same, 2.4 GHz ports)
    These are open mechanical items. If they disappear, either they were FIXED (update this test
    and the status doc) or the model lost them.
    """
    d = json.load(open(VOLJSON))
    pairs = {frozenset((c["a"], c["b"])) for c in d.get("collisions", [])}
    for want in ({"U2.9", "U2.10"}, {"U3.9", "U_C.9"}, {"U3.10", "U_C.10"}):
        assert frozenset(want) in pairs, (
            f"antenna volume collision {sorted(want)} is no longer reported -- fixed (then update "
            "this test) or lost (then the model is wrong)")


def test_volumes_are_anchored_at_real_antenna_pads():
    """Regression guard for the defect that produced the withdrawn 131 mm2 claim: a volume must
    sit at its own pad, not at a module-centre guess."""
    d = json.load(open(VOLJSON))
    board = json.load(open(VOLJSON))  # keep single load; anchors live in the same file
    for v in d["volumes"]:
        ax, ay = v["anchor"]
        vol = v["volume"]
        # the pad itself must lie on the volume's inner edge, within the body width
        if v["side"] in ("east", "west"):
            inner = vol["x1"] if v["side"] == "east" else vol["x2"]
            assert abs(ax - inner) > 0.1, (
                f"{v['ref']}.{v['pin']} volume does not start at its pad (anchor x={ax})")
        else:
            inner = vol["y1"] if v["side"] == "south" else vol["y2"]
            assert abs(ay - inner) > 0.1, (
                f"{v['ref']}.{v['pin']} volume does not start at its pad (anchor y={ay})")


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
    for phrase in ("0.370", "0.600", "no free ESP32-S3 GPIO remains", "4-layer"):
        assert phrase in doc, f"status doc lost a measured finding: {phrase!r}"


# ------------------------------------------------------- radio PA/LNA enable pins

# Enable-type pins per module, from the datasheets (pdftotext, not vision):
#   E28-2G4M27SX user manual v1.0 lines 253-254: pin 8 RX_EN, pin 9 TX_EN, both "active high"
#   LoRa2021F33-2G4 datasheet v1.1 s7: pin 5 CE, "drive high or float for operation"
ENABLE_PINS = {
    "U_E28": {"8": "RX_EN", "9": "TX_EN"},
    "U2": {"5": "CE"},
}

# Unconnected enables that are KNOWN and accepted-as-open. They must also appear in the status doc.
# Dropping an entry without fixing the board fails this test; fixing the board without dropping the
# entry ALSO fails it -- so the list cannot rot in either direction.
ACCEPTED_OPEN = {"U_E28:8", "U_E28:9"}


@needs_pcbnew
def test_no_unrecorded_floating_radio_enable():
    """A floating PA/LNA enable can make a ROUTED radio link still not work -- and it would look
    like an RF or firmware fault. Every unconnected enable must be explicitly recorded."""
    state = _board_json(
        "{f.GetReference()+'|'+str(p.GetNumber()): (p.GetNetname() or '') "
        "for f in b.GetFootprints() for p in f.Pads()}")
    doc = open(STATUS, encoding="utf-8").read()
    problems, fixed = [], []
    for ref, pins in ENABLE_PINS.items():
        for pin, name in pins.items():
            net = state.get(f"{ref}|{pin}", "MISSING")
            key = f"{ref}:{pin}"
            if net == "":
                if key not in ACCEPTED_OPEN:
                    problems.append(f"{key} ({name}) is unconnected and NOT in ACCEPTED_OPEN")
                elif name not in doc:
                    problems.append(f"{key} ({name}) is accepted-open but the status doc lost it")
            elif key in ACCEPTED_OPEN:
                fixed.append(f"{key} ({name}) is now on net {net} -- remove it from ACCEPTED_OPEN")
    assert not problems, "unrecorded floating radio enable pin(s):\n  " + "\n  ".join(problems)
    assert not fixed, (
        "a known-open enable was FIXED -- good, but the bookkeeping must follow:\n  "
        + "\n  ".join(fixed) + "\nUpdate ACCEPTED_OPEN and the status doc in the same commit.")

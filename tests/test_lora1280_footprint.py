"""Gates for the LoRa1280 footprint (ADR-139).

These assert the numbers that were read off the vendor drawing, so a later edit cannot
silently change the land pattern. Several are self-checking against the outline, which is
the dimension the drawing itself is most likely to have got right.

pcbnew lives in the distro python, not the venv, and importing it in-process can segfault
under the wrong interpreter — so every pcbnew use is behind a subprocess probe.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO / "tracker/hardware/build_lora1280_footprint.py"
FPDIR = REPO / "tracker/hardware/footprints/lora1280"

PITCH = 2.00
PAD_WIDTH = 1.20          # along the edge
PAD_DEPTH = 1.70          # drawn land depth
FILLET = 0.30
OUTLINE = 16.00
COURTYARD = 16.00 + 2 * 0.25


def _pcbnew_ok() -> bool:
    try:
        r = subprocess.run(
            [sys.executable, "-c", "import pcbnew; print(pcbnew.Version())"],
            capture_output=True, text=True, timeout=60,
        )
        return r.returncode == 0
    except Exception:
        return False


needs_pcbnew = pytest.mark.skipif(not _pcbnew_ok(), reason="pcbnew not importable in this interpreter")


def _dump() -> dict:
    """Load the committed footprint through pcbnew and report its geometry as JSON."""
    code = f"""
import json, pcbnew
fp = pcbnew.FootprintLoad({str(FPDIR)!r}, "LoRa1280")
if fp is None:
    raise SystemExit("LOAD FAILED")
out = {{"pads": {{}}, "courtyard": None}}
for p in fp.Pads():
    out["pads"][int(p.GetNumber())] = {{
        "x": p.GetPosition().x / 1e6,
        "y": p.GetPosition().y / 1e6,
        "sx": p.GetSize().x / 1e6,
        "sy": p.GetSize().y / 1e6,
        "attr": int(p.GetAttribute()),
        "name": p.GetPinFunction() or "",
    }}
for d in fp.GraphicalItems():
    if d.GetLayerName() == "F.Courtyard":
        bb = d.GetBoundingBox()
        out["courtyard"] = [bb.GetWidth() / 1e6, bb.GetHeight() / 1e6]
print(json.dumps(out))
"""
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"pcbnew load failed: {r.stderr[-800:]}"
    d = json.loads(r.stdout.strip().splitlines()[-1])
    # JSON object keys are strings; the rest of the file indexes pins by int.
    d["pads"] = {int(k): v for k, v in d["pads"].items()}
    return d


def test_generator_is_deterministic(tmp_path):
    """Same input, byte-identical output — otherwise the committed file is not reproducible."""
    a, b = tmp_path / "a.kicad_mod", tmp_path / "b.kicad_mod"
    for out in (a, b):
        r = subprocess.run([sys.executable, str(SCRIPT), "--out", str(out)],
                           capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stderr
    assert a.read_bytes() == b.read_bytes()


def test_generator_matches_committed_file(tmp_path):
    """The committed footprint is exactly what the generator produces."""
    out = tmp_path / "x.kicad_mod"
    r = subprocess.run([sys.executable, str(SCRIPT), "--out", str(out)],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    committed = (FPDIR / "LoRa1280.kicad_mod").read_text()
    assert out.read_text() == committed, (
        "committed footprint differs from generator output — regenerate it"
    )


@needs_pcbnew
def test_sixteen_smd_pads():
    d = _dump()
    assert len(d["pads"]) == 16
    # attribute 1 == SMD. The 0.70mm holes in the drawing are the MODULE's; we do not drill.
    assert {p["attr"] for p in d["pads"].values()} == {1}, "pads must all be SMD"


@needs_pcbnew
def test_pitch_is_2mm_across_every_gap():
    d = _dump()
    ys = sorted(d["pads"][i]["y"] for i in range(1, 9))
    gaps = [round(ys[i + 1] - ys[i], 3) for i in range(len(ys) - 1)]
    assert set(gaps) == {PITCH}, f"pitch gaps {gaps} != {PITCH}"


@needs_pcbnew
def test_pad_row_span_plus_end_offsets_equals_outline():
    """The self-check: 7 pitches + 2 end offsets must equal the drawn 16.00 mm outline.

    A misread pitch or end offset breaks this identity, which is why the pad row is
    trusted even though the drawing is a scan.
    """
    d = _dump()
    ys = sorted(d["pads"][i]["y"] for i in range(1, 9))
    span = ys[-1] - ys[0]
    end_offset = (OUTLINE - span) / 2
    assert round(span, 3) == round(7 * PITCH, 3) == 14.0
    assert round(end_offset, 3) == 1.0
    assert round(span + 2 * end_offset, 3) == OUTLINE


@needs_pcbnew
def test_pad_size_matches_drawing_plus_fillet():
    d = _dump()
    for p in d["pads"].values():
        assert round(p["sy"], 3) == PAD_WIDTH           # along the edge, as drawn
        assert round(p["sx"], 3) == PAD_DEPTH + FILLET  # land depth + fillet allowance


@needs_pcbnew
def test_inter_pad_gap_is_solderable():
    """0.80 mm between adjacent pads — the headline reason this part hand-solders well."""
    d = _dump()
    assert round(PITCH - PAD_WIDTH, 3) == 0.80


@needs_pcbnew
def test_pin1_top_left_and_ant_bottom_right():
    """Orientation from the section-7 drawing: pin 1 marked by a white triangle at a
    corner; 1->8 down one edge, 9->16 up the other; ANT(9) opposite pin 8."""
    d = _dump()
    p1, p8 = d["pads"][1], d["pads"][8]
    p9, p16 = d["pads"][9], d["pads"][16]
    assert p1["x"] < 0 and p1["y"] < p8["y"], "pin 1 must be at the top of the left edge"
    assert p16["x"] > 0 and p16["y"] < p9["y"], "pin 16 must be at the top of the right edge"
    assert p9["name"] == "ANT", "pin 9 is the antenna pad"
    assert p9["y"] > p16["y"], "ANT sits at the bottom-right, opposite pin 8"


@needs_pcbnew
def test_no_enable_pins():
    """The whole point of this part: there is no PA/LNA enable to get wrong.

    ADR-138's Q2/Q4/Q5 exist because the E28 has TX_EN/RX_EN. This footprint must never
    grow one.
    """
    d = _dump()
    names = {p["name"].upper() for p in d["pads"].values()}
    assert "TX_EN" not in names and "RX_EN" not in names
    assert names == {
        "DIO2", "DIO3", "VCC", "GND", "MISO", "MOSI", "SCK", "NSS",
        "ANT", "DIO1", "NRESET", "BUSY",
    }


@needs_pcbnew
def test_courtyard_covers_body():
    """Courtyard is body + 0.25 mm/side. pcbnew's bounding box measures the OUTER edge of
    the stroke, so the measured span is nominal + stroke width (0.05)."""
    STROKE = 0.05
    d = _dump()
    w, h = d["courtyard"]
    assert round(w, 2) == round(COURTYARD + STROKE, 2)
    assert round(h, 2) == round(COURTYARD + STROKE, 2)

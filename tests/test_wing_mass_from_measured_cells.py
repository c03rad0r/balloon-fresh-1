"""Tests for the wing mass derived from the operator's measured cells.

The load-bearing claims:

1. The CELL term is exact arithmetic on the operator's readings (not estimates).
2. The CARRIER term is only BOUNDED -- the script must never present it as
   measured, because no carrier was ever on the scale.
3. Foam is far lighter per unit area than the FR4 the repo rejected, and also
   lighter than the spine+ribs the repo recommends.
4. The per-wing cell totals match the values quoted in
   docs/analysis/WING-MASS-FROM-MEASURED-CELLS.md.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

MODEL = Path(__file__).resolve().parent.parent / "docs/analysis/wing_mass_from_measured_cells.py"


@pytest.fixture(scope="module")
def m() -> ModuleType:
    spec = importlib.util.spec_from_file_location("wing_mass_from_measured_cells", MODEL)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- 1. the cell term is the operator's measurement, not an estimate ---------
def test_cell_constants_are_the_operator_readings(m: ModuleType) -> None:
    assert m.M_LARGE_SINGLE_G == pytest.approx(1.382)
    assert m.M_SMALL_SINGLE_G == pytest.approx(0.440)
    assert m.M_LARGE_PACK_G == pytest.approx(1.4040, abs=1e-4)
    assert m.M_SMALL_PACK_G == pytest.approx(0.4462, abs=1e-4)


def test_per_wing_cell_masses_match_the_document(m: ModuleType) -> None:
    """The exact figures quoted in WING-MASS-FROM-MEASURED-CELLS.md s1."""
    pw_large, arr_large = m.cells_only_g(m.M_LARGE_SINGLE_G, m.CELLS_PER_WING_LARGE)
    pw_small, arr_small = m.cells_only_g(m.M_SMALL_SINGLE_G, m.CELLS_PER_WING_SMALL)
    assert pw_large == pytest.approx(4.1460, abs=1e-4)
    assert arr_large == pytest.approx(16.5840, abs=1e-4)
    assert pw_small == pytest.approx(3.9600, abs=1e-4)
    assert arr_small == pytest.approx(15.8400, abs=1e-4)


def test_small_would_be_lighter_but_needs_three_times_the_joints(m: ModuleType) -> None:
    """ADR-049 prefers large cells; the reason is joints, not mass."""
    pw_large, _ = m.cells_only_g(m.M_LARGE_SINGLE_G, m.CELLS_PER_WING_LARGE)
    pw_small, _ = m.cells_only_g(m.M_SMALL_SINGLE_G, m.CELLS_PER_WING_SMALL)
    assert pw_large > pw_small, "small cells are (slightly) lighter per wing"
    assert pw_large / pw_small < 1.10, "but the difference is under 10 %, i.e. negligible"
    assert m.CELLS_PER_WING_SMALL == 3 * m.CELLS_PER_WING_LARGE, "3x the joints"


def test_measured_cells_are_lighter_than_the_repo_estimate(m: ModuleType) -> None:
    """The repo's 0.5006 g estimate over-counted; the measured value is lower."""
    assert m.M_SMALL_SINGLE_G < m.REPO_EST_CELL_SMALL_G
    drop = 1 - m.M_SMALL_SINGLE_G / m.REPO_EST_CELL_SMALL_G
    assert drop == pytest.approx(0.121, abs=0.005), f"expected ~12.1 %, got {drop*100:.1f} %"


# --- 2. the carrier is BOUNDED, and the script must say so -------------------
def test_foam_areal_mass_arithmetic(m: ModuleType) -> None:
    """kg/m3 x mm -> mg/cm2. 15 kg/m3 at 3 mm = 4.5 mg/cm2."""
    assert m.foam_areal_mg_cm2(15.0, 3.0) == pytest.approx(4.5, abs=1e-6)
    assert m.foam_areal_mg_cm2(15.0, 2.0) == pytest.approx(3.0, abs=1e-6)
    assert m.foam_areal_mg_cm2(32.0, 6.0) == pytest.approx(19.2, abs=1e-6)
    # linear in both arguments
    assert m.foam_areal_mg_cm2(30.0, 4.0) == pytest.approx(2 * m.foam_areal_mg_cm2(15.0, 4.0))


def test_cited_areal_masses_are_the_repo_values(m: ModuleType) -> None:
    assert m.FR4_AREAL_MG_CM2 == pytest.approx(127.6)
    assert m.SI_AREAL_MG_CM2 == pytest.approx(48.9)
    # the repo's own verdict: FR4 is 2.61x heavier per area than the silicon
    assert m.FR4_AREAL_MG_CM2 / m.SI_AREAL_MG_CM2 == pytest.approx(2.61, abs=0.01)


def test_foam_is_dramatically_lighter_than_fr4(m: ModuleType) -> None:
    """The inversion that makes the operator's plan work."""
    eps3 = m.foam_areal_mg_cm2(15.0, 3.0)
    assert m.FR4_AREAL_MG_CM2 / eps3 > 25.0, "foam must be >25x lighter per area than 0.6 mm FR4"
    # and lighter than the silicon it carries -- the carrier stops dominating
    assert eps3 < m.SI_AREAL_MG_CM2, "3 mm EPS must be lighter per area than the cell itself"


def test_full_area_foam_beats_the_spine_and_ribs_carrier(m: ModuleType) -> None:
    """The result that ADR-049 never costed: foam < spine+ribs, over more area."""
    arm_cm2 = m.ARM_MM[0] * m.ARM_MM[1] / 100.0
    foam_g = arm_cm2 * m.foam_areal_mg_cm2(15.0, 3.0) / 1000.0
    assert foam_g == pytest.approx(0.653, abs=0.002)
    # the repo's recommended spine+ribs carrier is 1.620 g, and that covers only
    # the 30.69 cm2 cell court -- foam beats it outright while spanning the whole arm
    assert foam_g < m.REPO_SPINE_RIBS_SMALL_G
    assert foam_g < 1.620


def test_script_states_the_carrier_is_not_measured(
    m: ModuleType, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Presenting a bounded number as measured is the defect this guards."""
    monkeypatch.setattr("sys.argv", ["prog"])
    rc = m.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "NOT derivable" in out, "the carrier must be labelled not-derivable"
    assert "bounded" in out.lower(), "the carrier must be described as bounded"
    assert "TODO(unverified)" in out, "the residual unknowns must be listed"


def test_script_quotes_the_repo_rejected_fr4_as_reference(
    m: ModuleType, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.argv", ["prog"])
    m.main()
    out = capsys.readouterr().out
    assert "127.6" in out, "the cited FR4 areal mass must appear"
    assert "48.9" in out, "the cited silicon areal mass must appear"


def test_foam_argument_selects_the_backing(
    m: ModuleType, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """--foam 15 3 must report the operator's actual plate."""
    monkeypatch.setattr("sys.argv", ["prog", "--foam", "15", "3"])
    rc = m.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "4.50" in out or "4.5" in out, "EPS 3 mm areal mass"
    assert "4.799" in out or "4.798" in out, "EPS 3 mm + large cells wing total"

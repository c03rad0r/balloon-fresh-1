"""Tests for the foam airframe selection model.

The load-bearing claims this pins:

1. Areal mass is `0.1 * rho * t` mg/cm2 -- the rule the whole doc uses.
2. STIFFNESS IS CUBIC IN THICKNESS, mass only linear -- so the SOFTEST foam can
   win at equal out-of-plane stiffness. That is the counter-intuitive result the
   recommendation rests on, and it is exactly what an intuitive "buy the stiff
   foam" reading would get wrong.
3. The wing is a VERTICAL BLADE, so in-plane and out-of-plane deflections differ
   by orders of magnitude, and gravity is NOT the binding constraint. An earlier
   version of the model only computed out-of-plane and made foam look hopeless.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SRC = Path(__file__).resolve().parents[1] / "docs" / "analysis" / "foam_airframe_selection.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("foam_sel", SRC)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["foam_sel"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def m() -> ModuleType:
    return _load()


# --- 1. the areal-mass rule ---------------------------------------------------
def test_areal_mass_rule(m: ModuleType) -> None:
    # 15 kg/m3 at 3 mm -> 4.5 mg/cm2
    assert m.areal_mg_cm2(15.0, 3.0) == pytest.approx(4.5, abs=1e-9)
    # 32 kg/m3 at 6 mm -> 19.2 mg/cm2
    assert m.areal_mg_cm2(32.0, 6.0) == pytest.approx(19.2, abs=1e-9)
    # linear in thickness
    assert m.areal_mg_cm2(15.0, 6.0) == pytest.approx(2 * m.areal_mg_cm2(15.0, 3.0))


def test_wing_area_and_carrier(m: ModuleType) -> None:
    assert m.wing_area_cm2() == pytest.approx(145.0, abs=0.1)   # 16.71 x 8.68
    # EPS 3 mm carrier
    assert m.carrier_g(15.0, 3.0) == pytest.approx(0.653, abs=0.002)
    # wing = carrier + 3 measured cells
    assert m.wing_g(15.0, 3.0) == pytest.approx(0.653 + 4.146, abs=0.003)


# --- 2. the cubic-stiffness consequence (the counter-intuitive result) --------
def test_thickness_scales_with_inverse_cube_root_of_modulus(m: ModuleType) -> None:
    """Halving E requires only 2^(1/3) = 1.26x the thickness."""
    t = m.thickness_for_out_of_plane_EI(E_MPa=100.0, ref_E_MPa=200.0, ref_t_mm=1.0)
    assert t == pytest.approx(2 ** (1 / 3), abs=1e-6)


def test_softest_foam_wins_on_mass_at_equal_stiffness(m: ModuleType) -> None:
    """EPS (softest) needs the most thickness but the LEAST areal mass.

    This is the finding the recommendation rests on. If a change makes a stiffer
    foam win this comparison, the recommendation is wrong and must be re-derived.
    """
    a_eps = m.areal_mg_cm2(15.0, m.thickness_for_out_of_plane_EI(10.0, 20000.0, 0.6))
    a_xps = m.areal_mg_cm2(32.0, m.thickness_for_out_of_plane_EI(30.0, 20000.0, 0.6))
    assert a_eps < a_xps, "the softest foam should win on areal mass at equal EI"


def test_requiring_stiffness_costs_less_than_half_of_fr4(m: ModuleType) -> None:
    t = m.thickness_for_out_of_plane_EI(10.0, 20000.0, 0.6)
    assert m.areal_mg_cm2(15.0, t) < m.areal_mg_cm2(1800.0, 0.6) / 5.0


# --- 3. the two axes, and that orientation is the answer ---------------------
def test_in_plane_is_far_stiffer_than_out_of_plane(m: ModuleType) -> None:
    lo = m.defl_in_plane(10.0, 3.0, 40.0)
    hi = m.defl_out_of_plane(10.0, 3.0, 40.0)
    assert hi / lo > 100.0, "the weak axis must dominate by orders of magnitude"


def test_gravity_is_not_the_binding_constraint(m: ModuleType) -> None:
    """In-plane at 40 g is sub-millimetre for 3 mm EPS -- i.e. fine."""
    assert m.defl_in_plane(10.0, 3.0, 40.0) < 1.0


def test_out_of_plane_is_the_real_risk(m: ModuleType) -> None:
    """3 mm EPS is unusable out-of-plane -- the honest failure, not hidden."""
    assert m.defl_out_of_plane(10.0, 3.0, 40.0) > 100.0


def test_6mm_xps_beats_the_current_fr4_on_both_mass_and_stiffness(m: ModuleType) -> None:
    assert m.carrier_g(32.0, 6.0) < m.carrier_g(1800.0, 0.6) / 4.0
    assert m.defl_out_of_plane(30.0, 6.0, 10.0) < m.defl_out_of_plane(20000.0, 0.6, 10.0)


# --- 4. the release-force coupling ------------------------------------------
def test_release_force_follows_wing_mass(m: ModuleType) -> None:
    g0, shock, margin = 9.80665, 10.0, 1.5
    w = m.wing_g(15.0, 3.0)
    force_mN = w / 1000.0 * shock * g0 * margin * 1000.0
    assert force_mN == pytest.approx(706, abs=3)


def test_heavier_wing_needs_more_holding_force(m: ModuleType) -> None:
    light = m.wing_g(15.0, 3.0)
    heavy = m.wing_g(32.0, 6.0)
    assert heavy > light

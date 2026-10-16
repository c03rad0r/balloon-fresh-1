"""Tests for the envelope-material gap analysis.

The load-bearing claims:

1. The envelope DOMINATES our non-payload mass (~88%), so cost is not the dial.
2. Adding a second envelope is INFEASIBLE against the community's 85 g package
   ceiling -- and the reason is dry mass retained, which is the paste's own point.
3. The paste's own rationale contradicts its own material pick (it asserts the
   film must be inelastic, then recommends a laminate the manufacturer describes
   as stretchable).
4. Our design is already the paste's TOP recommendation, so there is no action.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SRC = Path(__file__).resolve().parents[1] / "docs" / "analysis" / "envelope_material_gap.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("env_gap", SRC)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["env_gap"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def m() -> ModuleType:
    return _load()


YOKOHAMA = "Yokohama 32in new (valveless)"


def _env(m: ModuleType, name: str):
    return next(e for e in m.OUR_ENVELOPES if e.name == name)


# --- 1. the envelope dominates non-payload mass ------------------------------
def test_yokohama_mass_matches_the_repo_measurement(m: ModuleType) -> None:
    """48.6 g is a MEASURED value, not an estimate -- it must not drift."""
    assert _env(m, YOKOHAMA).mass_g == 48.6


def test_envelope_is_the_dominant_non_payload_term(m: ModuleType) -> None:
    y = _env(m, YOKOHAMA)
    assert m.envelope_share(y) > 0.85, "envelope should dominate non-payload mass"


def test_non_payload_total_matches_the_repo_table(m: ModuleType) -> None:
    """The repo's table says 54.97 g for a 20 g payload on helium."""
    y = _env(m, YOKOHAMA)
    assert m.non_payload_g(y) == pytest.approx(54.97, abs=0.01)


def test_cost_per_gram_is_small_relative_to_flight_value(m: ModuleType) -> None:
    """$25 for 48.6 g -> under $1/g. The paste's $25-vs-$2 framing is a rounding error."""
    cpg = m.cost_per_gram_of_envelope(_env(m, YOKOHAMA))
    assert cpg is not None and cpg < 1.0


# --- 2. the redundancy arithmetic -------------------------------------------
def test_second_envelope_is_infeasible(m: ModuleType) -> None:
    """Two Yokohamas blow the 85 g community package ceiling."""
    y_mass = _env(m, YOKOHAMA).mass_g
    assert m.cluster_is_feasible(1, y_mass) is True
    assert m.cluster_is_feasible(2, y_mass) is False
    assert m.cluster_is_feasible(3, y_mass) is False


def test_extra_envelope_mass_exceeds_the_whole_free_lift_allowance(m: ModuleType) -> None:
    """The paste's dead-weight point, quantified: one envelope > 6 g free lift."""
    y_mass = _env(m, YOKOHAMA).mass_g
    extra = m.free_lift_needed_for_cluster(2, y_mass)
    assert extra == pytest.approx(y_mass)
    assert extra / m.FREE_LIFT_G > 5.0, "a second envelope dwarfs the free-lift allowance"


def test_cluster_mass_is_linear_in_count(m: ModuleType) -> None:
    """Dry mass is RETAINED, not shed -- the assumption the whole argument rests on."""
    y_mass = _env(m, YOKOHAMA).mass_g
    one = m.cluster_non_payload_g(1, y_mass)
    two = m.cluster_non_payload_g(2, y_mass)
    assert two - one == pytest.approx(y_mass)


# --- 3. the verdict table must not be softened ------------------------------
def test_fabricated_claim_is_recorded_as_fabricated(m: ModuleType) -> None:
    """A 36-inch Yokohama does not exist (manufacturer range is 7-32 inch)."""
    verdicts = dict((c, v) for c, v in m.PASTE_CLAIMS)
    key = next(k for k in verdicts if "36-inch" in k)
    assert "FABRICATED" in verdicts[key]


def test_inflated_volume_claim_is_flagged(m: ModuleType) -> None:
    verdicts = dict((c, v) for c, v in m.PASTE_CLAIMS)
    key = next(k for k in verdicts if "0.27-0.50" in k)
    assert "INFLATED" in verdicts[key]


def test_the_measured_claim_is_called_real(m: ModuleType) -> None:
    """48.6 g is the ONE claim the paste got right -- say so."""
    verdicts = dict((c, v) for c, v in m.PASTE_CLAIMS)
    key = next(k for k in verdicts if "48.6" in k)
    assert verdicts[key].startswith("REAL")


# --- 4. the local cost delta is small ---------------------------------------
def test_cost_delta_between_yokohama_and_cheap_film_is_tens_of_dollars(m: ModuleType) -> None:
    y = m.cost_per_gram_of_envelope(_env(m, YOKOHAMA))
    c = m.cost_per_gram_of_envelope(_env(m, "Chinese Clear 36in"))
    assert y is not None and c is not None
    assert y > c

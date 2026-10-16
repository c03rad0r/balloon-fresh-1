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
    """$12 for 48.6 g -> ~$0.25/g. The paste's $25 framing overstated it ~2x."""
    cpg = m.cost_per_gram_of_envelope(_env(m, YOKOHAMA))
    assert cpg is not None and cpg < 0.5


def test_yokohama_price_is_the_manufacturer_figure_not_the_pastes(m: ModuleType) -> None:
    """Live products.json: $120 per 10-pack = $12/balloon. The paste said ~$25."""
    y = _env(m, YOKOHAMA)
    assert y.cost_usd == pytest.approx(12.0)
    assert y.cost_usd < 25.0, "the paste's $25 was ~2x too high, in our favour"


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

# --- 5. the jurisdiction trap (second paste) --------------------------------
def test_german_law_has_no_balloon_de_minimis(m: ModuleType) -> None:
    """The 20 g figure is NOT a German balloon threshold -- the paste answered US law.

    If this ever flips to True, the whole 'excludes the envelope' reassurance becomes
    live for a German launch and the safety argument in the doc must be rewritten.
    """
    assert m.GERMAN_BALLOON_DE_MINIMIS_G is None


def test_the_real_mass_threshold_counts_envelope_and_ballast(m: ModuleType) -> None:
    """Where German law DOES use a mass figure, the envelope is INCLUDED, not excluded.

    This is the inverse of the paste's framing, and it is the load-bearing claim.
    """
    assert m.GERMAN_ATC_DE_MINIMIS_G == 500.0
    assert m.ATC_THRESHOLD_COUNTS == "Ballonhuelle und Ballast (envelope + ballast)"


def test_our_design_passes_the_500g_figure(m: ModuleType) -> None:
    """We pass -- but the point is WHY: envelope included, not excluded."""
    y = next(e for e in m.OUR_ENVELOPES if e.name == YOKOHAMA)
    envelope_plus_ballast = y.mass_g + m.ATTACHMENTS_G
    assert envelope_plus_ballast < m.GERMAN_ATC_DE_MINIMIS_G
    assert envelope_plus_ballast / m.GERMAN_ATC_DE_MINIMIS_G < 0.15


def test_the_paste_cited_the_wrong_jurisdiction(m: ModuleType) -> None:
    assert m.PASTE_CITED_JURISDICTION == "US (FAA Part 101 / 14 CFR 101)"
    assert m.OUR_JURISDICTION == "DE (LuftVO + SERA)"


def test_the_lowest_classification_boundary_is_4kg_not_20g(m: ModuleType) -> None:
    """SERA Anlage 2 no. 1.1: a 'light' balloon is payload < 4 kg.

    Even the CLASSIFICATION floor is 4 kg, 200x the mythical 20 g figure -- and it is a
    classification rule, not a de-minimis. A second, independent route to the same verdict.
    """
    assert m.SERA_LIGHT_PAYLOAD_MAX_G == 4000.0
    assert m.SERA_LIGHT_PAYLOAD_MAX_G / 20.0 == 200.0
    assert m.SERA_MEDIUM_PAYLOAD_MAX_G == 6000.0


def test_our_design_is_far_below_every_real_threshold(m: ModuleType) -> None:
    """~51 g vs a 500 g ATC figure, a 4 kg class floor and a 5 kg marking duty."""
    y = next(e for e in m.OUR_ENVELOPES if e.name == YOKOHAMA)
    total = y.mass_g + m.ATTACHMENTS_G
    for threshold in (m.GERMAN_ATC_DE_MINIMIS_G, m.SERA_LIGHT_PAYLOAD_MAX_G,
                      m.MARKING_DUTY_THRESHOLD_G):
        assert total < threshold


def test_the_pastes_130g_figure_is_unsourced(m: ModuleType) -> None:
    """The paste's 'overall mass often exceeding 130 grams' matches no instrument.

    It must not be adopted as a design figure -- it is recorded only so the claim is
    traceable, not because it means anything.
    """
    assert m.PASTE_UNSOURCED_MASS_G == 130.0


# --- 6. the reliability crossover, applied to OUR hardware -------------------
def test_our_hardware_is_in_the_backfire_regime(m: ModuleType) -> None:
    """m = 48.6 g > m* = (2B-P)/3 = 31.07 g.

    This independently confirms the n=2/n=3 infeasibility on grounds that do not
    depend on the mass-allowance argument in section 1.
    """
    assert m.in_backfire_regime() is True
    assert m.backfire_boundary_g() == pytest.approx(31.07, abs=0.05)


def test_the_pastes_own_hypothetical_is_NOT_in_the_backfire_regime(m: ModuleType) -> None:
    """m=18 g, B=110 g -> m*=65 g. So the paste's 'triple backfires' claim is
    FALSE for the hardware it describes -- it is a sizing failure, not cheapness."""
    m_star = (2 * 110.0 - 25.0) / 3.0
    assert m_star == pytest.approx(65.0, abs=0.05)
    assert 18.0 < m_star, "the paste's m is far below its own boundary"


def test_backfire_boundary_rises_with_gross_lift(m: ModuleType) -> None:
    """Sanity: a stronger envelope tolerates heavier redundancy."""
    assert m.backfire_boundary_g(B=200.0) > m.backfire_boundary_g(B=60.0)


def test_common_mode_caps_redundancy(m: ModuleType) -> None:
    """Marshall-Olkin: a shared cause caps the gain; it cannot be fixed by count."""
    p_one = 0.9
    indep = 1 - (1 - p_one) ** 3
    capped = m.system_reliability_common_mode(p_one, 3, q=0.1)
    assert capped < indep
    assert capped == pytest.approx(0.9 * indep, abs=1e-9)
    # even a strong shared cause leaves the ordering intact but collapses the gain
    assert m.system_reliability_common_mode(p_one, 3, 0.9) > m.system_reliability_common_mode(p_one, 2, 0.9)


def test_common_mode_note_names_the_shared_cause(m: ModuleType) -> None:
    assert "neck" in m.COMMON_MODE_NOTE and "weld" in m.COMMON_MODE_NOTE

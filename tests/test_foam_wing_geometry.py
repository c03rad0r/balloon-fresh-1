#!/usr/bin/env python3
"""Tests for the foam-wing mass/geometry model (ADR-117 / ADR-130).

These lock the arithmetic the analysis docs quote, so a doc and the model cannot
drift apart.  Each expected value is the model's own printed output, recomputed
here independently from the cited inputs.

Run: python3 -m pytest tests/test_foam_wing_geometry.py -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "docs", "analysis"))

from foam_wing_geometry import (  # noqa: E402
    ARM_CM2, ARM_X_MM, ARM_Y_MM, CELL_G, areal_mg_cm2, wing_mass, wing_wrl,
    greedy_foam,
)


def test_arm_area_is_the_cited_145_cm2():
    # 167.1 x 86.8 mm = 145.04 cm2  (WING-MASS-FROM-MEASURED-CELLS.md)
    assert ARM_CM2 == pytest.approx(145.0, abs=0.1)


def test_areal_mass_formula():
    # 0.1 * rho * t : EPS 15 kg/m3 @ 3 mm = 4.5 mg/cm2  (FOAM-AIRFRAME-SELECTION)
    assert areal_mg_cm2(15.0, 3.0) == pytest.approx(4.5)
    assert areal_mg_cm2(32.0, 3.0) == pytest.approx(9.6)
    assert areal_mg_cm2(1800.0, 0.6) == pytest.approx(108.0)


def test_eps_3mm_single_sided_matches_the_doc():
    m = wing_mass("EPS", 3.0, False)
    assert m["carrier_g"] == pytest.approx(0.653, abs=0.001)
    assert m["cells_g"] == pytest.approx(4.146, abs=0.001)
    assert m["total_g"] == pytest.approx(5.249, abs=0.002)


def test_double_sided_doubles_only_the_cells_not_the_carrier():
    ss = wing_mass("EPS", 3.0, False)
    ds = wing_mass("EPS", 3.0, True)
    # carrier is a property of the sheet, identical for single and double
    assert ds["carrier_g"] == pytest.approx(ss["carrier_g"])
    assert ds["cells_g"] == pytest.approx(2 * ss["cells_g"])
    assert ds["n_cells"] == 6


def test_eps_carrier_is_lighter_than_retired_fr4_by_an_order_of_magnitude():
    eps = wing_mass("EPS", 3.0, False)["carrier_g"]
    fr4 = areal_mg_cm2(1800.0, 0.6) * ARM_CM2 / 1000.0
    assert fr4 / eps > 20.0          # 15.665 / 0.653 = 24x


def test_thicker_is_heavier_but_still_far_below_fr4():
    t3 = wing_mass("XPS", 3.0, False)["carrier_g"]
    t6 = wing_mass("XPS", 6.0, False)["carrier_g"]
    assert t6 > t3
    assert t6 < areal_mg_cm2(1800.0, 0.6) * ARM_CM2 / 1000.0


def test_option_table_is_ordered_lightest_first():
    rows = greedy_foam(False)
    totals = [r["total_g"] for r in rows]
    assert totals == sorted(totals)
    assert rows[0]["foam"] == "EPS" and rows[0]["t_mm"] == 3.0


def test_wrl_emits_the_right_cell_count():
    ss = wing_wrl("EPS", 3.0, False)
    ds = wing_wrl("EPS", 3.0, True)
    # 1 foam slab + 3 cells (ss) ; 1 foam slab + 6 cells (ds)
    assert ss.count("geometry Box") == 1 + 3
    assert ds.count("geometry Box") == 1 + 6
    assert ss.startswith("#VRML V2.0 utf8")


def test_wrl_uses_kicad_model_units():
    # foam slab dz = 3 mm / 2.54 = 1.181102 model units
    assert "1.181102" in wing_wrl("EPS", 3.0, False)


def test_three_large_cells_cannot_lie_in_one_row_across_the_arm():
    """Guard the layout error this module once made.

    ADR-049 / wing-mass-shape.md line 276 put the large-cell arm at 167.10 x 86.80
    mm as "short+wide (2 rows, 2+1)".  Three 78.55 mm cells end-to-end need
    235.65 mm and DO NOT FIT, so a single lengthwise row of 3 is geometrically
    impossible and must never be drawn again.
    """
    assert 3 * 78.55 > ARM_X_MM
    # the 2+1 layout DOES fit: 2 cells + gap across X, and 2 rows across Y
    # (compare the layout's REAL extents, with a tolerance: 2*38.9 + 9.0 lands on
    #  86.80000000000001 in float and would fail a bare <= against 86.8)
    row_x = 2 * 78.55 + 2.0
    two_rows_y = 2 * 38.90 + 9.0
    assert row_x <= ARM_X_MM
    assert two_rows_y <= ARM_Y_MM + 1e-9

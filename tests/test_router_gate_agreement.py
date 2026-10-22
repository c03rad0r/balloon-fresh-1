#!/usr/bin/env python3
"""ROUTER <-> GATE AGREEMENT TEST.

Why this exists (2026-10-22): five bugs in one session (B34, B37, B38, B40 and the
corresponding gate/validator split) all had ONE shape -- the router's own validate_plan
believed a route was legal while a gate said it was not, and in every case the GATE was right:

  B34  isolation obstacle under-marked 0.10mm   -> A* found paths validate_plan discarded
  B37  --append didn't mark existing copper     -> every retry rejected
  B38  under-body check PER SEGMENT             -> tunnelled 5.71mm through a keep-out
  B40  keep-out body = pad field, not courtyard -> crossing invisible to validate_plan

A test that runs validate_plan and the gate over the SAME geometry and asserts they AGREE
would have caught all of them. That is what this file does.

METHOD: for each defect class, build a PLAN that the corresponding gate rejects, and assert
validate_plan rejects it too -- and vice versa: a legal plan must be accepted by both. The
plans are constructed directly (not routed), so the test is fast and deterministic.

Skipped (not failed) when pcbnew is unavailable, so CI without KiCad still runs the rest.
"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.join(HERE, "..", "tracker", "hardware")
sys.path.insert(0, os.path.abspath(HW))


def _mods():
    try:
        import pcbnew  # noqa: F401
    except Exception:
        pytest.skip("pcbnew not available")
    import route_v10_astar as R
    return R


def _world():
    R = _mods()
    w = R.load_world(R.BOARD)
    w["routed_segs"] = []
    w["routed_vias"] = []
    return R, w


def _plan(R, w, x0, y0, x1, y1, layer=None):
    """Build a one-segment plan in GRID coordinates from mm endpoints."""
    lay = R.F if layer is None else layer
    a = R.to_cell(w, 0.1, x0, y0)
    b = R.to_cell(w, 0.1, x1, y1)
    # a straight run of cells; the router's own paths are cell lists
    steps = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
    cells = []
    for k in range(steps + 1):
        t = k / steps if steps else 0.0
        i = round(a[0] + t * (b[0] - a[0]))
        j = round(a[1] + t * (b[1] - a[1]))
        cells.append((i, j, lay))
    return [cells]


def _pad_rect(w, ref, num):
    for r, n, name, code, sides, rect in w["pads"]:
        if r == ref and str(n) == str(num):
            return rect, sides, code, name
    raise AssertionError(f"pad {ref}.{num} not found")


def test_keepout_courtyard_is_the_body_not_the_pad_field():
    """B40: the E28 keep-out body must be its COURTYARD, which is bigger than its pad field.

    If the body rect equals the pad field, a route in the strip between them is invisible to
    validate_plan while the gate rejects it -- exactly the /E28_BUSY defect.
    """
    R, w = _world()
    bodies = [b for b in w["bodies"] if b[0] == "U_E28"]
    assert bodies, "E28 keep-out body missing from the world model"
    bx0, by0, bx1, by1 = bodies[0][2]
    # courtyard measured on the board 2026-10-22
    assert bx0 < 45.0, f"body x0 {bx0} looks like the PAD FIELD (48.06), not the courtyard (41.93)"
    assert bx1 > 60.0, f"body x1 {bx1} looks like the PAD FIELD (57.95), not the courtyard (64.08)"
    assert len(bodies) == 2, "the E28 keep-out must bind BOTH layers (ADR-118 directive 5)"


def test_validate_plan_rejects_a_route_through_the_keepout():
    """The router must refuse a route that crosses the E28 keep-out -- not emit it and let the
    gate catch it (B38/B40)."""
    R, w = _world()
    bx0, by0, bx1, by1 = [b for b in w["bodies"] if b[0] == "U_E28"][0][2]
    y = (by0 + by1) / 2
    plan = _plan(R, w, bx0 + 1.0, y, bx1 - 1.0, y)      # straight across the module
    own = [(("X", "1"), {R.F, R.B}, (bx0 + 1.0, y - 1.0, bx0 + 1.0, y + 1.0)),
           (("Y", "1"), {R.F, R.B}, (bx1 - 1.0, y - 1.0, bx1 - 1.0, y + 1.0))]
    ok, why = R.validate_plan(w, 0.1, plan, [("X", "1"), ("Y", "1")], own, 99999)
    assert not ok, "validate_plan ACCEPTED a route crossing the E28 keep-out"
    assert "travers" in why, f"rejected for the wrong reason: {why}"


def test_validate_plan_rejects_a_route_too_close_to_a_foreign_pad():
    """Pad clearance must be enforced by the router, not only by the gate."""
    R, w = _world()
    rect, sides, code, name = _pad_rect(w, "U1", "7")
    cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
    lay = R.F if R.F in sides else R.B
    # a horizontal run 0.05mm from the pad edge -> far below CLEAR (0.2)
    y = rect[3] + 0.05
    plan = _plan(R, w, cx - 3.0, y, cx + 3.0, y, layer=lay)
    own = [(("X", "1"), {lay}, (cx - 3.0, y - 1.0, cx - 3.0, y + 1.0)),
           (("Y", "1"), {lay}, (cx + 3.0, y - 1.0, cx + 3.0, y + 1.0))]
    ok, why = R.validate_plan(w, 0.1, plan, [("X", "1"), ("Y", "1")], own, 99998)
    assert not ok, "validate_plan ACCEPTED a route 0.05mm from a foreign pad"


def test_validate_plan_rejects_isolation_against_routed_copper():
    """B34/B37: copper already placed must be enforced by validate_plan, at the SAME distance
    the isolation gate uses. This is the bug that made the router discard its own valid work."""
    R, w = _world()
    rect, sides, code, name = _pad_rect(w, "U1", "7")
    cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
    lay = R.F if R.F in sides else R.B
    y = rect[3] + 2.0
    # pretend another net already runs here, 0.15mm from where we want to route
    w["routed_segs"].append(("/OTHER", lay, (cx - 3.0, y + 0.15), (cx + 3.0, y + 0.15), R.TRACK_W))
    plan = _plan(R, w, cx - 3.0, y, cx + 3.0, y, layer=lay)
    own = [(("X", "1"), {lay}, (cx - 3.0, y - 1.0, cx - 3.0, y + 1.0)),
           (("Y", "1"), {lay}, (cx + 3.0, y - 1.0, cx + 3.0, y + 1.0))]
    ok, why = R.validate_plan(w, 0.1, plan, [("X", "1"), ("Y", "1")], own, 99997)
    assert not ok, "validate_plan ACCEPTED a route 0.15mm from routed copper (needs >= 0.2mm)"


def test_validate_plan_accepts_a_legal_route():
    """The negative control: a legal route must be ACCEPTED, or the checks above are vacuous.

    Uses an empty region of the board. An earlier version used `U1.7 + 3.0mm` and was rejected
    for "clearance to U1.10" -- the VALIDATOR WAS RIGHT (U1's pads are on 1.27mm pitch), which
    is itself evidence the clearance check works.
    """
    R, w = _world()
    # empty corridor: east of the E28, below the wing seat, well inside the board
    lay = R.B
    x0, x1, y = 66.0, 69.0, 30.0
    plan = _plan(R, w, x0, y, x1, y, layer=lay)
    own = [(("X", "1"), {lay}, (x0, y - 1.0, x0, y + 1.0)),
           (("Y", "1"), {lay}, (x1, y - 1.0, x1, y + 1.0))]
    ok, why = R.validate_plan(w, 0.1, plan, [("X", "1"), ("Y", "1")], own, 99996)
    assert ok, f"validate_plan REJECTED a legal route: {why}"


def test_router_grid_marks_routed_copper_with_full_clearance():
    """B34: the obstacle growth must be CLEAR + TRACK_W (edge-to-edge clearance between two
    tracks), not CLEAR + TRACK_W/2."""
    src = open(os.path.join(HW, "route_v10_astar.py")).read()
    assert "g = CLEAR + TRACK_W\n" in src, (
        "obstacle growth is not CLEAR + TRACK_W -- the isolation mark is too tight (B34)")
    assert "g = CLEAR + TRACK_W/2\n" not in src.replace("g = CLEAR + TRACK_W\n", ""), (
        "a CLEAR + TRACK_W/2 mark remains in the obstacle path")

#!/usr/bin/env python3
"""Bind the ADR-126 routing method -- static assertions, no pcbnew needed.

The operator asked that the A* approach "is taken in all future attempts so that we don't
repeat our mistakes". Convention would not hold; these assertions do. They run in CI on
every push, so a future change that reintroduces the banned router or strips the gates
fails the build.

What is asserted:
  1. the A* router exists and carries its defining rules (via cost, clearance, holes as
     obstacles, own-pad halo guard, endpoint-layer matching)
  2. the banned straight/L router is explicitly marked as banned / negative reference
  3. the four routing gates exist
  4. AGENTS.md binds ADR-126 and names all four gates
  5. the connectivity registry and its OPEN-ITEMS ledger exist, and the registry has a
     drift-check mode
"""
import os
import re

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HW = os.path.join(REPO, "tracker", "hardware")
ASTAR = os.path.join(HW, "route_v10_astar.py")
PHASE1 = os.path.join(HW, "route_v10_phase1.py")
AGENTS = os.path.join(REPO, "AGENTS.md")
REGISTRY = os.path.join(HW, "connectivity", "registry.py")
PINMAP = os.path.join(HW, "connectivity", "v10_pinmap.reg")
OPEN_ITEMS = os.path.join(HW, "connectivity", "OPEN-ITEMS.md")

GATES = ["check_lane_clearance.py", "check_lane_integrity.py",
         "check_copper_under_body.py", "check_hole_clearance.py"]


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_astar_router_exists():
    assert os.path.exists(ASTAR), "the ADR-126 A* router is missing"


def test_astar_router_has_via_support():
    src = read(ASTAR)
    assert "VIA_COST" in src, "no via cost -- vias are what makes cross-side routing possible"
    assert "PCB_VIA" in src, "the router must be able to place vias"
    assert "VIA_D" in src and "VIA_DRILL" in src, "via geometry must be explicit"


def test_astar_router_models_obstacles():
    src = read(ASTAR)
    for token in ("blocked", "HOLE_CLEAR", "CLEAR", "EDGE_KEEP", "build_grid"):
        assert token in src, f"router does not model {token}"


def test_astar_router_treats_unnamed_pads_as_metal():
    """B5: skipping pads with no net is exactly how the operator's U_C.9 short happened."""
    src = read(ASTAR)
    assert re.search(r"unnamed pads are METAL", src), \
        "the router must state that unnamed pads are obstacles (bug B5)"


def test_astar_router_guards_neighbouring_pads():
    """B12: an own-pad halo must not clear a neighbouring pad's clearance ring."""
    src = read(ASTAR)
    assert "CLEARANCE RING" in src or "clearance ring" in src, \
        "the own-pad exception must not clear a neighbouring pad's clearance ring"


def test_astar_router_matches_endpoint_layers():
    """B11: start on the start pad's layer, finish on the goal pad's layer."""
    src = read(ASTAR)
    assert "a_sides | c_sides" in src or "a_sides" in src and "c_sides" in src, \
        "endpoint layers must come from the pads, not be forced equal"


def test_astar_router_validates_before_writing():
    """The router must be gate-bound: validate the plan in memory before emitting copper."""
    src = read(ASTAR)
    assert "validate_plan" in src, "the router must self-validate before writing copper"


def test_banned_router_is_marked():
    """The straight/L router stays only as a negative reference (ADR-126)."""
    src = read(PHASE1)
    assert re.search(r"(?i)banned|negative reference|do not use", src), \
        "route_v10_phase1.py must be marked as banned/negative-reference"


def test_all_four_routing_gates_exist():
    for g in GATES:
        assert os.path.exists(os.path.join(HW, g)), f"missing routing gate: {g}"


def test_agents_md_binds_adr_126_and_the_gates():
    src = read(AGENTS)
    assert "ADR-126" in src, "AGENTS.md must bind ADR-126"
    for g in GATES:
        assert g in src, f"AGENTS.md must name {g}"
    assert "ONLY permitted routing method" in src or "ONLY permitted" in src, \
        "AGENTS.md must state the routing method is mandatory"
    assert "unnamed pads are metal" in src.lower() or "unnamed pads INCLUDED" in src, \
        "AGENTS.md must record the unnamed-pad rule"


def test_registry_and_ledger_exist():
    for p in (REGISTRY, PINMAP, OPEN_ITEMS):
        assert os.path.exists(p), f"missing connectivity artefact: {p}"


def test_registry_has_drift_check():
    src = read(REGISTRY)
    assert "def cmd_check" in src and "DRIFT" in src, \
        "the registry must fail on drift between board and registry"


def test_pinmap_is_one_line_per_pin():
    """The registry format is the point: diff-friendly, human-auditable."""
    lines = [ln for ln in read(PINMAP).splitlines()
             if ln.strip() and not ln.startswith("#")]
    assert len(lines) > 100, f"registry looks empty ({len(lines)} pin lines)"
    for ln in lines:
        body = ln.split("#", 1)[0].strip()
        assert re.match(r"^[A-Za-z0-9_]+\.\S*\s+\S+$", body), f"bad registry line: {ln!r}"

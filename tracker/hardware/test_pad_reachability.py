#!/usr/bin/env python3
"""Regression for the pad-escape gate (2026-10-18 defect, fixed 2026-10-19).

Pins the three defects from the case study
(manager skill: firmware/kicad-board-audit-rules/references/pad-escape-verdict-contradiction.md):

  D1 mm-vs-nm: the old gate compared millimetres to `need * UM`, so EVERY
     obstacle was tagged BLOCKING. The fixed ring is millimetres throughout.
  D2 wrong threshold: a pad escapes from its EDGE, so the ring is
     half-diagonal + clearance (0.8746 + 0.200 = 1.0746 mm for the 1.5x0.9
     pads), not the trace-centreline threshold (w/2 + clearance = 0.300 mm).
     At the correct ring, the old "CLEAR (0.970 mm)" is INSIDE the ring.
  D3 wrong layer: the old gate collected obstacles from B.Cu for four
     F.Cu-only SMD pads. The fixed gate measures the pad's own LayerSet.

Expected measurement on hub_board_v9 (all self-checks pass):
  U1.8   ring 1.0746  F.Cu escapes 3.54 mm   escapable (stub via present)
  U1.22  ring 1.0746  F.Cu escapes 3.54 mm   escapable (stub via present)
  U4.17  ring 0.6272  F.Cu stalls 1.41 mm    escapable only via layer change
  U4.18  ring 0.6272  F.Cu stalls 0.78 mm    NOT ESCAPABLE (clearance binds)

Run under the KiCad python:
  ~/venvs/kicad/bin/python tracker/hardware/test_pad_reachability.py
It is also pytest-collectable where pcbnew is importable; elsewhere it skips.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

try:
    import pcbnew  # noqa: F401
except Exception:  # pragma: no cover - non-KiCad interpreter
    pcbnew = None

import pad_reachability as pr

BOARD = HERE / "hub_board_v9.kicad_pcb"
PADS = ["U1.8", "U1.22", "U4.17", "U4.18"]
RING = {"U1.8": 1.0746, "U1.22": 1.0746, "U4.17": 0.6272, "U4.18": 0.6272}
ESCAPES_FCU = {"U1.8": True, "U1.22": True, "U4.17": False, "U4.18": False}
ESCAPABLE = {"U1.8": {"F_CU", "VIA", "STUB_VIA"},
             "U1.22": {"F_CU", "VIA", "STUB_VIA"},
             "U4.17": {"VIA"},
             "U4.18": {"BLOCKED"}}


def _require_kicad():
    if pcbnew is None:
        try:
            import pytest
            pytest.skip("pcbnew not importable — run under ~/venvs/kicad/bin/python")
        except ImportError:
            raise SystemExit("run under ~/venvs/kicad/bin/python (pcbnew missing)")


def measure_all() -> dict:
    _require_kicad()
    board = pcbnew.LoadBoard(str(BOARD))
    rules = pr.Rules(board)
    out = {}
    for token in PADS:
        ref, num = pr._parse_pad(token)
        out[token] = pr.measure(board, rules, ref, num)
    return out


def test_ring_is_edge_based_after_fix():
    """D1/D2: millimetres, and the pad ring, not the trace centreline."""
    res = measure_all()
    board = pcbnew.LoadBoard(str(BOARD))
    rules = pr.Rules(board)
    for ref, r in res.items():
        assert abs(r["ring_r"] - RING[ref]) < 1e-3, (ref, r["ring_r"])
        assert r["ring_r"] > rules.trace_edge_to_copper, (
            f"{ref}: ring {r['ring_r']} must exceed the trace-centreline "
            f"threshold {rules.trace_edge_to_copper}")


def test_smd_pads_are_measured_on_their_own_layers():
    """D3: F.Cu-only pads; B.Cu is not reachable without a via."""
    res = measure_all()
    for ref, r in res.items():
        assert "F.Cu" in r["layers"], (ref, r["layers"])
        assert "B.Cu" not in r["layers"], (ref, r["layers"])


def test_expected_verdicts_and_self_checks():
    res = measure_all()
    for ref, r in res.items():
        assert r["reach"]["escaped"] is ESCAPES_FCU[ref], (ref, r["reach"])
        assert r["verdict"]["kind"] in ESCAPABLE[ref], (ref, r["verdict"])
        assert r["problems"] == [], (ref, r["problems"])


def test_no_obstacle_is_tagged_by_a_nm_threshold():
    """The old gate's `d < need * UM` tagged everything. Distances are mm."""
    res = measure_all()
    for ref, r in res.items():
        for d, kind, _label in r["ring"]:
            assert abs(d) < 10.0, (ref, kind, d)  # mm-scale, not nm-scale


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("PASS all pad-reachability regressions")

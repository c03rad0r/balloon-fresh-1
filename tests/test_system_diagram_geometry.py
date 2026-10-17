#!/usr/bin/env python3
"""Guard: the system diagram's relay geometry is MEASURED, not eyeballed.

WHY A TEST. The r3 visual review (docs/fab/reviews/system-diagram-r3.md) found three geometry defects
in docs/boards/system-diagram.png and nobody acted on them, because the finding existed only as prose.
Nothing failed. A review whose findings cannot fail a build is a review that will be ignored -- this
is the third time that has happened in this repo (board gallery, U1.41, this diagram), so the findings
are now assertions.

WHAT THIS ASSERTS
  1. the geometry gate passes on the COMMITTED svg (so the artefact cannot drift out of tolerance);
  2. the gate FAILS on a deliberately broken svg -- a check that cannot fail proves nothing. Each of
     r3's three measured findings is reproduced synthetically and must be caught:
       (a) A's arrow endpoint moved off the node -> a gap,
       (b) the flight-segment line shortened so its tip stops short,
       (c) the node's label moved onto the ring,
       (d) an oversized arrowhead (the markerUnits trap that made the head cover the whole node);
  3. the committed svg and png are what the generator produces (via the generator's own --check).

Run:  python3 -m pytest tests/test_system_diagram_geometry.py -v
      python3 tests/test_system_diagram_geometry.py        # self-contained, no pytest needed
"""
from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
SVG = REPO / "docs" / "boards" / "system-diagram.svg"
GEN = REPO / "tracker" / "hardware" / "make_system_diagram.py"
CHECKER = REPO / "scripts" / "check_system_diagram_geometry.py"
PY = sys.executable


def run_checker(svg_path: pathlib.Path) -> tuple:
    r = subprocess.run([PY, str(CHECKER), "--svg", str(svg_path), "--no-png"],
                       capture_output=True, text=True, timeout=300)
    return r.returncode, r.stdout + r.stderr


def _write_variant(tmp: pathlib.Path, name: str, mutate) -> pathlib.Path:
    text = SVG.read_text(encoding="utf-8")
    out = mutate(text)
    assert out != text, f"mutation {name!r} changed nothing -- the test would pass vacuously"
    p = tmp / f"{name}.svg"
    p.write_text(out, encoding="utf-8")
    return p


def _move_a_arrow_off_the_node(text: str) -> str:
    """Reproduce r3 finding 1: A's arrow stops short of / beside the node."""
    # A's link is the red path whose last point lands on the node's top; shorten it upwards.
    def repl(m):
        return m.group(1) + f"{float(m.group(2)) - 14:.2f}"
    # the link's final L is written as "L <x> <y>" with the x equal to the node's cx
    return re.sub(r'(marker-end="url\(#ar\)"[^>]*)|(L (\d+\.\d\d) (2\d\d\.\d\d)")',
                  lambda m: m.group(0), text) if False else _shorten_a_link(text)


def _shorten_a_link(text: str) -> str:
    """Move every red arrow endpoint 14 units BACK along its last segment, so both links miss.

    Counted from the SVG, not asserted: the drawing has TWO red link arrows (A->node, node->B). The
    third connector is a grey reference leader between two drawings of the same hardware and carries
    no arrowhead, so pulling it back would not create the gap this test is about.
    """
    def repl(m):
        x, y = float(m.group(1)), float(m.group(2))
        return f'L {x:.2f} {y - 14:.2f}" stroke="#b00020" stroke-width="3"'
    out, n = re.subn(r'L ([\d.]+) ([\d.]+)" stroke="#b00020" stroke-width="3"', repl, text)
    assert n == 2, f"expected 2 red arrow endpoints, rewrote {n}"
    return out


def _shrink_the_node(text: str) -> str:
    """Reproduce r3 finding 3 and 4: a node small enough that the label crowds it and the head covers it."""
    out = re.sub(r'r="34\.0"', 'r="18.0"', text, count=1)
    assert out != text
    return out


def _move_label_onto_the_ring(text: str) -> str:
    """Reproduce r3 finding 3 directly: put the node label back inside the circle.

    The failure mode is found by its TEXT, not by a hardcoded coordinate, so moving the label in the
    generator cannot make this test pass vacuously.
    """
    m = re.search(r'<text x="([\d.]+)" y="([\d.]+)"([^>]*)>BALLOON</text>', text)
    assert m, "did not find the BALLOON label to move"
    out = (text[:m.start()]
           + f'<text x="940.0" y="335.0"{m.group(3)}>BALLOON</text>'
           + text[m.end():])
    assert out != text
    return out


def _oversize_the_arrowhead(text: str) -> str:
    """Reproduce the markerUnits trap: let the marker scale with the stroke width again."""
    out = re.sub(r' markerUnits="userSpaceOnUse"', "", text, count=1)
    assert out != text
    return out


CASES = [
    ("a_link_short_of_the_node", _shorten_a_link, "does NOT land"),
    ("node_too_small_for_label_and_head", _shrink_the_node, None),
    ("label_on_the_ring", _move_label_onto_the_ring, "ring"),
    ("arrowhead_scales_with_stroke", _oversize_the_arrowhead, "arrowhead"),
]


def main() -> int:
    failures = []

    # 1. the committed artefact must pass
    rc, out = run_checker(SVG)
    print(f"[1] committed svg: exit {rc}")
    if rc != 0:
        failures.append(f"committed svg fails the geometry gate:\n{out}")

    # 2. every synthetic defect must be caught
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        for name, mutate, needle in CASES:
            p = _write_variant(tmp, name, mutate)
            rc, out = run_checker(p)
            ok = rc != 0 and (needle is None or needle.lower() in out.lower())
            print(f"[2] {name}: exit {rc} caught={ok}")
            if not ok:
                failures.append(f"mutation {name!r} was NOT caught (exit {rc}, needle {needle!r}):\n{out}")

    # 3. the committed artefacts must be what the generator produces
    r = subprocess.run([PY, str(GEN), "--check"], cwd=str(REPO), capture_output=True, text=True,
                       timeout=600)
    print(f"[3] generator --check: exit {r.returncode}")
    if r.returncode != 0:
        failures.append(f"committed artefacts are stale:\n{r.stdout[-800:]}")

    print()
    if failures:
        print("SELFTEST: FAIL")
        for f in failures:
            print("  - " + f.replace("\n", "\n    "))
        return 1
    print("SELFTEST: PASS -- the gate passes on the artefact and fails on every synthetic defect")
    return 0


def test_geometry_gate():
    """pytest entry point. Asserts the same three properties as the script."""
    assert main() == 0, "system-diagram geometry gate failed (see stdout above)"


if __name__ == "__main__":
    sys.exit(main())

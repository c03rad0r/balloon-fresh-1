#!/usr/bin/env python3
"""Guard: every image/plot generator must be DETERMINISTIC and CHECKABLE.

WHY A TEST RATHER THAN A CONVENTION. A convention that a generator "should" support --check is worth
nothing the day someone adds a generator without it. The repo already has this pattern for the 3D models
(scripts/gen_3d_models_hub.py and gen_3d_models_wing.py both have --check) and it has NOT been applied
to the image generators, which is how a stale committed PNG can sit in the tree unreported.

WHAT THIS ASSERTS, per generator:
  1. it accepts --check and exits 0 on a freshly-written tree
  2. it accepts --check and exits NON-ZERO when an artefact is deliberately corrupted
     (a check that cannot fail is a check that proves nothing -- the same rule the ERC and DRC gates use)
  3. running it twice produces byte-identical output (determinism, tested directly)
  4. it emits no absolute host path into the artefact

Property 2 is the one that matters most: it is what makes the difference between "the generator has a
--check flag" and "the generator's --check flag works".

Run: python3 -m pytest tests/test_generators_deterministic.py -v
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]

# The image/plot generators and the artefacts each owns. Kept explicit so a NEW generator has to be
# added here deliberately rather than being silently uncovered.
GENERATORS = [
    ("tracker/hardware/make_board_gallery.py", ["docs/boards/GALLERY.md"]),
    ("tracker/hardware/make_system_diagram.py", ["docs/boards/system-diagram.svg",
                                                 "docs/boards/system-diagram.png"]),
    ("tracker/hardware/make_edge_section.py", ["docs/fab/jlc-query/edge-launch-cross-section.svg",
                                               "docs/fab/jlc-query/edge-launch-cross-section.png"]),
]

def _find_pcbnew_python() -> str:
    """An interpreter that can import pcbnew, chosen by TESTING rather than by assuming.

    MEASURED 2026-10-16: the pytest interpreter (~/venvs/ho-test) has pytest but NOT pcbnew, while
    ~/venvs/kicad has pcbnew but not pytest. So a generator's success depended on WHICH python invoked
    it -- environment non-determinism, which is what this file exists to catch. Candidates are tried in a
    fixed order and the first that can actually import pcbnew wins; if none can, the tests skip with a
    reason instead of failing for an environmental cause no committer can fix.
    """
    import glob
    cands = [os.path.expanduser("~/venvs/kicad/bin/python"), "/usr/bin/python3", "python3"]
    cands += sorted(glob.glob(os.path.expanduser("~/venvs/*/bin/python")))
    for c in cands:
        try:
            r = subprocess.run([c, "-c", "import pcbnew"], capture_output=True, timeout=60)
            if r.returncode == 0:
                return c
        except Exception:
            continue
    return ""


PY = _find_pcbnew_python()
pytestmark = pytest.mark.skipif(not PY, reason="no interpreter with pcbnew on this host")


def _run(gen: str, *args, cwd=REPO):
    return subprocess.run([PY, str(REPO / gen), *args], cwd=str(cwd),
                          capture_output=True, text=True, timeout=600)


@pytest.mark.parametrize("gen,artefacts", GENERATORS, ids=[g[0].split("/")[-1] for g in GENERATORS])
def test_generator_has_a_check_mode_that_passes_when_current(gen, artefacts):
    """--check must exit 0 on a tree the generator has just written."""
    r = _run(gen)
    assert r.returncode == 0, f"generator failed to run:\n{r.stdout[-800:]}\n{r.stderr[-400:]}"
    c = _run(gen, "--check")
    assert c.returncode == 0, (
        f"{gen} --check is non-zero immediately after a successful write, so it cannot be trusted:\n"
        f"{c.stdout[-800:]}")


@pytest.mark.parametrize("gen,artefacts", GENERATORS, ids=[g[0].split("/")[-1] for g in GENERATORS])
def test_check_mode_FAILS_when_an_artefact_is_corrupted(gen, artefacts):
    """THE IMPORTANT ONE. A --check that cannot fail proves nothing.

    Corrupt one owned artefact, run --check, require non-zero, then restore. This is the same
    can-this-check-fail discipline the ERC and DRC gates use.
    """
    target = REPO / artefacts[0]
    if not target.exists():
        pytest.skip(f"{artefacts[0]} not present")

    backup = target.read_bytes()
    try:
        # append bytes: the file still exists and parses, but is no longer what the generator produces
        target.write_bytes(backup + b"\n<!-- corruption injected by the determinism test -->\n")
        c = _run(gen, "--check")
        assert c.returncode != 0, (
            f"{gen} --check returned 0 on a CORRUPTED {artefacts[0]} -- the check cannot fail and is "
            f"therefore worthless:\n{c.stdout[-600:]}")
    finally:
        target.write_bytes(backup)
    # and it must go back to passing once restored
    c2 = _run(gen, "--check")
    assert c2.returncode == 0, f"{gen} --check did not recover after restore:\n{c2.stdout[-600:]}"


@pytest.mark.parametrize("gen,artefacts", GENERATORS, ids=[g[0].split("/")[-1] for g in GENERATORS])
def test_generator_is_byte_deterministic(gen, artefacts):
    """Two runs, byte-identical artefacts. Non-determinism (a timestamp, a set iteration order, a random
    id) would make --check flap and make the artefact unreviewable."""
    before = {}
    for rel in artefacts:
        p = REPO / rel
        if p.exists():
            before[rel] = p.read_bytes()
    r = _run(gen)
    assert r.returncode == 0, f"generator failed:\n{r.stdout[-600:]}"
    for rel, prev in before.items():
        now = (REPO / rel).read_bytes()
        assert now == prev, (
            f"{gen} produced a DIFFERENT {rel} on a second run with unchanged inputs -- "
            f"the generator is not deterministic")


def test_artefacts_carry_no_absolute_host_path():
    """An artefact with /home/<user>/... baked in is not reproducible elsewhere and leaks the layout."""
    offenders = []
    for rel in ("docs/boards/GALLERY.md", "docs/boards/system-diagram.svg",
                "docs/fab/jlc-query/edge-launch-cross-section.svg"):
        p = REPO / rel
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for needle in ("/home/c08r4d0r", "/home/", "/Users/"):
            if needle in text:
                offenders.append(f"{rel} contains {needle!r}")
    assert not offenders, "artefacts embed absolute host paths:\n  " + "\n  ".join(offenders)


def test_the_shared_helper_is_self_testing():
    """scripts/artefact.py proves its own two properties, so a broken helper is caught here."""
    r = subprocess.run([PY, str(REPO / "scripts" / "artefact.py"), "--selftest"],
                       cwd=str(REPO), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"artefact.py --selftest failed:\n{r.stdout[-800:]}"
    assert "SELFTEST: PASS" in r.stdout

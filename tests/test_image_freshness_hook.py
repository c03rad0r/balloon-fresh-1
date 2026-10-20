#!/usr/bin/env python3
"""Guard: the image-freshness pre-commit hook works.

A hook that cannot fail is a hook that proves nothing (the same rule the ERC and DRC
gates use). This test installs the hook into a THROWAWAY clone of this repo, then:

  1. STALE case: reverts docs/boards/hub-v9.png to an older byte content (any change
     works: truncate it), stages it, and asserts the commit is REFUSED.
  2. CURRENT case: runs the owning generator (make_board_gallery.py, no --check),
     stages the re-rendered artefacts, and asserts the commit is ALLOWED.
  3. UNRELATED case: a commit touching only a non-trigger file (e.g. scripts/foo.txt)
     is allowed through without running any generator.

Run: python3 -m pytest tests/test_image_freshness_hook.py -v
Requires: git, ~/venvs/kicad/bin/python (the generators import pcbnew).
"""
import os
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
# The gallery generator imports pcbnew, which only the kicad venv has on this host.
# In CI there is no such venv: skip the re-render test there rather than fail on a
# missing host dependency (a gate that cannot run must WARN, not silently pass --
# here the skip is LOUD, with the reason printed).
KICAD_PY = os.environ.get("KICAD_PY", os.path.expanduser("~/venvs/kicad/bin/python"))
GENERATOR = "tracker/hardware/make_board_gallery.py"


def run(cmd, cwd, timeout=900):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


@pytest.fixture()
def clone(tmp_path):
    """A disposable clone with the hook installed via the installer.

    The hook scripts are copied in explicitly because they may not be committed yet
    when this test runs (the test gates the hook's own development too)."""
    c = tmp_path / "clone"
    r = run(["git", "clone", "-q", str(REPO), str(c)], tmp_path)
    assert r.returncode == 0, r.stderr
    # copy the CURRENT hook scripts from the source tree (uncommitted files included)
    for rel in ("scripts/git-hooks/pre-commit-image-freshness.py",
                "scripts/git-hooks/install.py"):
        src = REPO / rel
        dst = c / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        dst.chmod(0o755)
    # a clone has no hooks dir config; install
    r = run([sys.executable, "scripts/git-hooks/install.py"], c)
    assert r.returncode == 0, r.stderr
    # identity for commits inside the clone
    run(["git", "config", "user.email", "hook-test@example.com"], c)
    run(["git", "config", "user.name", "hook test"], c)
    return c


def stage_all(c):
    run(["git", "add", "-A"], c)


def test_hook_refuses_stale_image(clone):
    # corrupt the committed render -> generator --check must fail -> commit refused
    img = clone / "docs" / "boards" / "hub-v9.png"
    img.write_bytes(img.read_bytes()[:64])
    stage_all(clone)
    r = run(["git", "commit", "-q", "-m", "stale image test"], clone)
    assert r.returncode != 0, "commit with a stale render must be REFUSED"
    combined = r.stdout + r.stderr
    # the refusal must be a DETECTED-STALE verdict, not a generator crash masquerading
    # as one (CI has no pcbnew; a crash there must say GENERATOR FAILED, not STALE).
    if "STALE" in combined:
        assert "GENERATOR FAILED" not in combined, \
            "hook reported both staleness and a crash -- ambiguous verdict"
    else:
        assert "GENERATOR FAILED" in combined or "not up to date" in combined, \
            f"refusal gave no reason:\n{combined}"


def test_hook_allows_current_images(clone):
    # re-render with the real generator, then commit: must pass
    if not os.path.exists(KICAD_PY):
        pytest.skip(f"pcbnew venv missing here ({KICAD_PY}); the generator cannot run -- "
                    "this test needs the KiCad python to re-render the gallery")
    r = run([KICAD_PY, GENERATOR], clone)
    assert r.returncode == 0, r.stderr
    stage_all(clone)
    r = run(["git", "commit", "-q", "-m", "current images test"], clone)
    assert r.returncode == 0, f"commit with fresh renders must be ALLOWED:\n{r.stdout}\n{r.stderr}"


def test_hook_ignores_unrelated_commit(clone):
    # a commit with no .md/.kicad_pcb/generator change does not run any generator
    (clone / "scripts" / "foo.txt").write_text("unrelated\n")
    stage_all(clone)
    r = run(["git", "commit", "-q", "-m", "unrelated test"], clone)
    assert r.returncode == 0, f"unrelated commit must pass:\n{r.stdout}\n{r.stderr}"
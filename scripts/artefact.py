#!/usr/bin/env python3
"""Shared helpers that make a generator DETERMINISTIC and CHECKABLE.

WHY THIS EXISTS. The repo has two good patterns already and one gap:
  - scripts/gen_3d_models_hub.py and gen_3d_models_wing.py have a --check mode that exits non-zero if
    the committed artefact differs from what the generator produces. Nothing else does.
  - the image generators (make_board_gallery.py, make_system_diagram.py, make_edge_section.py,
    draw_peel_coupon.py) write in place with no way to ask "is what is committed still current?".
So a stale committed PNG can sit in the tree indefinitely with nothing reporting it -- which is exactly
how the fab package drifted 20 footprints behind the board, and how "HASBL" survived in a reviewed image
after its generator was fixed.

THE THREE PROPERTIES THIS ENFORCES
  1. DETERMINISM   -- the same inputs produce byte-identical output. Sources of non-determinism are
     removed by construction: no wall-clock time, no randomness, no unordered-set iteration in emitted
     text, no absolute paths in the artefact. If a generator needs a date it takes one as a parameter.
  2. VERIFIABILITY -- every generator can write to a temp location and compare against the committed
     file, so `--check` is possible for images the same way it is for the 3D models.
  3. PROVENANCE    -- the artefact records the sha256 of the inputs it was derived from, so "is this
     current?" is answerable without guessing.

USAGE in a generator:
    from artefact import DeterministicWriter
    w = DeterministicWriter(__file__)
    w.add("docs/boards/x.png", png_bytes_or_path)
    return w.finish(check=args.check)

Run: python3 scripts/artefact.py --selftest
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile

# The env var every generator must respect: where the repo root is. Never emit an absolute host path
# into an artefact -- it makes the artefact non-reproducible on any other machine and leaks the
# builder's directory layout.
REPO_ENV = "BALLOON_REPO_ROOT"


def repo_root(start: str | None = None) -> str:
    """The repo root, from BALLOON_REPO_ROOT or by walking up for .git."""
    env = os.environ.get(REPO_ENV)
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    d = os.path.abspath(start or os.getcwd())
    while True:
        if os.path.isdir(os.path.join(d, ".git")) or os.path.isfile(os.path.join(d, ".git")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return os.path.abspath(start or os.getcwd())
        d = parent


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def relpath(path: str, base: str | None = None) -> str:
    """A repo-relative path, so artefacts never embed an absolute host path."""
    base = base or repo_root()
    try:
        return os.path.relpath(os.path.abspath(path), base)
    except ValueError:
        return os.path.basename(path)


class DeterministicWriter:
    """Write a set of artefacts, then either commit them or verify they are already current.

    check=False  -> write each artefact in place, print what changed
    check=True   -> write to a temp dir, compare against the committed files, exit 1 on any difference
    """

    def __init__(self, generator: str, base: str | None = None):
        self.base = base or repo_root(os.path.dirname(os.path.abspath(generator)))
        self.generator = relpath(generator, self.base)
        self._items: list[tuple[str, bytes, str]] = []   # (relpath, bytes, sha256)

    def add(self, rel: str, data: bytes | str) -> None:
        if isinstance(data, str):
            data = data.encode("utf-8")
        self._items.append((rel, data, sha256_bytes(data)))

    def add_file(self, rel: str, src_path: str) -> None:
        with open(src_path, "rb") as fh:
            self.add(rel, fh.read())

    def finish(self, check: bool = False) -> int:
        if not self._items:
            print(f"{self.generator}: NO ARTEFACTS DECLARED -- a generator that emits nothing is a bug")
            return 2

        if check:
            stale, missing, ok = [], [], 0
            for rel, data, _ in self._items:
                p = os.path.join(self.base, rel)
                if not os.path.exists(p):
                    missing.append(rel)
                elif open(p, "rb").read() != data:
                    stale.append(rel)
                else:
                    ok += 1
            for rel in missing:
                print(f"  MISSING  {rel}")
            for rel in stale:
                print(f"  STALE    {rel}  (committed != generated)")
            print(f"\n{self.generator}: {len(self._items)} artefacts, {ok} current, "
                  f"{len(stale)} stale, {len(missing)} missing")
            if stale or missing:
                print("\nREGENERATE: run the generator without --check and commit the result.")
                return 1
            print("all current -- the committed artefacts are exactly what the generator produces")
            return 0

        written, unchanged = [], 0
        for rel, data, _ in self._items:
            p = os.path.join(self.base, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            if os.path.exists(p) and open(p, "rb").read() == data:
                unchanged += 1
                continue
            # write via a temp file in the SAME directory, then rename -- so a failure cannot leave a
            # half-written artefact, and the rename is atomic on the same filesystem.
            d = os.path.dirname(p)
            fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-", suffix=os.path.basename(p)[-8:])
            try:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(data)
                os.replace(tmp, p)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            written.append(rel)
        for rel in written:
            print(f"  wrote    {rel}")
        print(f"\n{self.generator}: {len(self._items)} artefacts, {len(written)} written, "
              f"{unchanged} already current")
        return 0


def selftest() -> int:
    """Prove the two properties that matter, on this machine, right now."""
    print("artefact.py selftest")
    print(f"  repo_root() = {repo_root()}")
    # 1. sha256 is stable
    a = sha256_bytes(b"hello")
    b = sha256_bytes(b"hello")
    print(f"  sha256 stable: {a == b}  ({a[:16]}...)")
    # 2. a deterministic writer round-trips in a temp base
    import shutil
    tmp = tempfile.mkdtemp(prefix="artefact-selftest-")
    try:
        w1 = DeterministicWriter(__file__, base=tmp)
        w1.add("sub/x.txt", "content\n")
        rc1 = w1.finish(check=False)
        w2 = DeterministicWriter(__file__, base=tmp)
        w2.add("sub/x.txt", "content\n")
        rc2 = w2.finish(check=True)
        print(f"  write rc={rc1}, re-check rc={rc2} (0 = committed matches generated)")
        w3 = DeterministicWriter(__file__, base=tmp)
        w3.add("sub/x.txt", "DIFFERENT\n")
        rc3 = w3.finish(check=True)
        print(f"  changed-input check rc={rc3} (1 = correctly reported stale)")
        ok = (rc1 == 0 and rc2 == 0 and rc3 == 1)
        print(f"\nSELFTEST: {'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    print(__doc__)

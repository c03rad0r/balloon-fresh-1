#!/usr/bin/env python3
"""pre-commit hook: block a commit whose markdown-linked images are stale.

WHY THIS HOOK EXISTS (measured 2026-10-20): the gallery check reported
    STALE docs/boards/hub-v9.png  (committed != generated)
    STALE docs/boards/GALLERY.md  (committed != generated)
after PRs #245/#247 changed the board but nobody re-rendered the docs images.
The repo HAS generators with --check (make_board_gallery.py, make_system_diagram.py,
make_edge_section.py) and a determinism test, but nothing FORCES a commit that touches
a board or its docs to re-render. A convention is worth nothing the day someone forgets;
this hook is the forcing function.

WHAT IT DOES
  For every *.kicad_pcb, generator script, or docs/*.md file in the commit, find the
markdown files that link images, resolve each link against the repo root, and:
    1. if the target image does not exist            -> REJECT (broken link)
    2. if a generator owns the image (GENERATORS map) -> run `--check`; if it fails, REJECT
    3. images not owned by any generator are allowed through (manual artefacts) -- we do
       not block commits on images we cannot verify, we only verify what we can.

WHY pre-commit AND NOT CI-ONLY: CI catches staleness a push later; the hook stops the
stale artefact entering history at all. CI keeps the same check for pushes that bypass
hooks (--no-verify is forbidden by repo policy, but the gate must not depend on trust).

EXIT: 0 = images current, 1 = stale/broken (message tells the exact fix command).
"""
import os
import re
import subprocess
import sys

REPO = os.path.abspath(os.environ.get("GIT_HOOK_REPO", "."))
# The image generators and the artefacts each owns. This is the same registry the
# determinism test (tests/test_generators_deterministic.py) enforces -- keep them in sync.
GENERATORS = {
    "docs/boards/hub-v9.png": "tracker/hardware/make_board_gallery.py",
    "docs/boards/wing-v9.png": "tracker/hardware/make_board_gallery.py",
    "docs/boards/base-station.png": "tracker/hardware/make_board_gallery.py",
    "docs/boards/GALLERY.md": "tracker/hardware/make_board_gallery.py",
    "docs/boards/system-diagram.svg": "tracker/hardware/make_system_diagram.py",
    "docs/boards/system-diagram.png": "tracker/hardware/make_system_diagram.py",
    "docs/fab/jlc-query/edge-launch-cross-section.svg": "tracker/hardware/make_edge_section.py",
    "docs/fab/jlc-query/u413-open-ground.png": "tracker/hardware/regen_fab_package.py",
}

LINK_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")

# A commit that touches any of these must have current images (board changed => renders stale).
# NOTE (2026-10-20, caught by the hook test): the trigger must fire on BOARD and GENERATOR
# changes even when NO .md is staged -- a board edit makes committed renders stale.
TRIGGER_RE = re.compile(
    r"\.(kicad_pcb|kicad_sch|net|md)$"
    r"|docs/boards/.*\.(png|svg)$"
    r"|docs/fab/jlc-query/.*\.(png|svg)$"
    r"|make_board_gallery\.py$"
    r"|make_system_diagram\.py$"
    r"|make_edge_section\.py$"
    r"|regen_fab_package\.py$"
    r"|build_hub_board_v9\.py$"
    r"|apply_sck_mosi_fix\.py$"
)


def staged_files():
    out = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=REPO,
                         capture_output=True, text=True)
    return [l.strip() for l in out.stdout.splitlines() if l.strip()]


def owned_rel_targets(md_file):
    """Owned artefact paths (repo-relative) linked by one markdown file."""
    p = os.path.join(REPO, md_file)
    out = []
    try:
        text = open(p, encoding="utf-8").read()
    except OSError:
        return out
    for m in LINK_RE.finditer(text):
        t = m.group(1).split("#")[0]
        if re.match(r"^[a-z]+://", t):
            continue
        out.append(os.path.normpath(os.path.join(os.path.dirname(md_file), t)))
    return out


def markdown_links(files):
    """(md_path, image_path) pairs for every markdown file linked to a changed artefact.

    If the commit stages .md files, those are checked. If it stages a board/generator
    (which makes RENDERS stale) but no .md, every .md that links an OWNED image is
    checked -- that is the staleness the hook exists to catch."""
    pairs = []
    md_files = [f for f in files if f.endswith(".md")]
    boardish = [f for f in files if TRIGGER_RE.search(f) and not f.endswith(".md")]
    if not md_files and boardish:
        owned_norm = {os.path.normpath(o) for o in GENERATORS}
        for root, _dirs, names in os.walk(os.path.join(REPO, "docs")):
            for n in names:
                if not n.endswith(".md"):
                    continue
                f = os.path.relpath(os.path.join(root, n), REPO)
                if any(t in owned_norm for t in owned_rel_targets(f)):
                    md_files.append(f)
    for f in md_files:
        p = os.path.join(REPO, f)
        if not os.path.exists(p):
            continue
        try:
            text = open(p, encoding="utf-8").read()
        except OSError:
            continue
        for m in LINK_RE.finditer(text):
            target = m.group(1).split("#")[0]
            if re.match(r"^[a-z]+://", target):    # remote URLs are out of scope
                continue
            pairs.append((f, target))
    return pairs


def main():
    files = staged_files()
    if not any(TRIGGER_RE.search(f) for f in files):
        return 0        # nothing image-relevant in this commit

    problems = []
    checked = set()
    for md, img in markdown_links(files):
        # resolve relative to the markdown file's directory
        base = os.path.dirname(os.path.join(REPO, md))
        full = os.path.normpath(os.path.join(base, img))
        rel = os.path.relpath(full, REPO)
        if not os.path.exists(full):
            problems.append(f"BROKEN LINK: {md} -> {img} (file does not exist)")
            continue
        gen = GENERATORS.get(rel)
        if gen is None:
            continue    # not machine-verified: allowed (manual artefact)
        if gen in checked:
            continue
        checked.add(gen)
        # generators that import pcbnew need the KiCad python; system python3 lacks it
        # (measured 2026-10-21: commit refused with GENERATOR FAILED -- ModuleNotFoundError).
        # Prefer $KICAD_PY, then ~/venvs/kicad/bin/python, then sys.executable.
        py = os.environ.get("KICAD_PY")
        if not py:
            cand = os.path.expanduser("~/venvs/kicad/bin/python")
            py = cand if os.path.exists(cand) else sys.executable
        r = subprocess.run([py, gen, "--check"], cwd=REPO,
                           capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            out = r.stdout + r.stderr
            stale = [l for l in out.splitlines() if "STALE" in l or "MISSING" in l]
            if stale:
                # the generator RAN and reported staleness
                detail = "\n    ".join(stale[:6])
                problems.append(f"STALE IMAGE: {rel} owned by {gen}\n    {detail}")
            else:
                # the generator CRASHED (e.g. no pcbnew in this python). Refusing anyway
                # is fail-safe, but the message must not claim staleness it did not detect.
                err = [l for l in out.splitlines() if l.strip()][-2:]
                problems.append(f"GENERATOR FAILED (cannot verify {rel}): {gen}\n    "
                                + "\n    ".join(err))

    if problems:
        print("pre-commit: markdown-linked images are not up to date\n")
        for p in problems:
            print(f"  {p}")
        print("\nFIX: run the owning generator WITHOUT --check and commit the result:")
        for gen in sorted(checked):
            print(f"    {gen}")
        print("\n(Do not use --no-verify. Re-render, then commit.)")
        return 1
    print(f"pre-commit: image freshness OK ({len(checked)} generator(s) verified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
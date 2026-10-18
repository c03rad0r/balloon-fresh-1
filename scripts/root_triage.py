"""Measure inbound references for every loose file at the repo ROOT, before moving anything.

WHY THIS EXISTS. The docs/ reorganisation was assumed expensive ("moving 277 files breaks cross-references")
and measured cheap: only ~18 of 277 loose docs had any inbound link. The same discipline applies to the repo
root, which the docs/ pass never covered -- my earlier cleanup card was scoped to docs/, which is why the
root still shows 21 loose .md, 21 loose data files and 3 loose .py.

=== WHY `git grep`, NOT A PYTHON LOOP ===

The first two versions read every tracked file in Python to count mentions. Measured: 180+ seconds and it
still had not finished. `git grep` does the same job in 0.12 s because it searches the index in one pass.
Choose the tool that is built for the job before optimising the loop.

=== WHY THE MATCHING IS STRICTER THAN IT LOOKS ===

A naive basename search LIES. Measured on the first version:

    REPORT.md                -> "inbound 51 from 34 files"
    INTEGRATION-ASSESSMENT.md -> "inbound 57 from 22 files"

Those look like files that must not move. They are not: the names are GENERIC and exist in many
directories, so most hits point at a DIFFERENT file with the same basename (firmware/lib/meshtastic's own
REPORT.md; a per-branch INTEGRATION-ASSESSMENT.md). Counting those as inbound to the ROOT file is the
"detector that cries wolf on correct text" failure this repo has already been bitten by.

So: if ANOTHER file shares the basename, only a PATH-QUALIFIED mention counts. If no other file shares it,
a bare mention can only mean the root file and counts normally. Generated indexes (graphify-out/cache) are
excluded because a stat index lists every path and inflates every count.

The numbers are therefore a LOWER BOUND on real inbound links -- the safe direction for a move, because
they under-state risk rather than manufacturing it.

Exit code: always 0. This is a measurement, not a gate.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Legitimate repo-root residents.
KEEP = {
    "AGENTS.md", "README.md", "LICENSE", "LICENSE.md", "Makefile", "PROGRESS.md",
    "pyproject.toml", "pytest.ini", "uv.lock", ".gitignore", ".gitmodules",
    ".secret-patterns.txt",
}

DATA_EXT = (".csv", ".json", ".rpt")
CODE_EXT = (".py",)


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *args], capture_output=True, text=True, check=False
    ).stdout


def root_loose() -> list[str]:
    out = git("ls-tree", "--name-only", "HEAD")
    return [p for p in out.split("\n") if p and not p.endswith("/")]


def files_sharing_basename(name: str) -> int:
    """How many tracked files have this basename.

    `git ls-files REPORT.md` matches the EXACT path only, so it always returned 1 and the
    ambiguity guard never fired -- which is how REPORT.md once reported 48 phantom referrers.
    Compare basenames over the full tracked list instead.
    """
    out = git("ls-files")
    return len([p for p in out.split("\n") if p and p.rsplit("/", 1)[-1] == name])


# A mention counts as a reference to THIS file only when the path token it sits in
# resolves to the root file. Measured false positives this rejects:
#
#   docs/INTEGRATION-ASSESSMENT.md  -> a DIFFERENT file that exists in this repo
#   ~/worktrees/tg-proto-contract/TOLLGATE_API_SHAPE.md -> a sibling worktree
#   https://github.com/.../tree/feat/2g4-sweep/full-sweep-... -> another branch
#
# `../../full-sweep-report-200111.md` from docs/harmonized/ DOES resolve to the root
# file and is accepted, so a move must update it.
PATH_TOKEN = re.compile(r"[A-Za-z0-9_./\-]*")


def refers_to_root(line: str, name: str) -> bool:
    """True if some occurrence of `name` in `line` resolves to the repo-root `name`."""
    start = 0
    while True:
        k = line.find(name, start)
        if k < 0:
            return False
        start = k + 1
        # boundary on both sides
        if k and (line[k - 1].isalnum() or line[k - 1] in "_."):
            continue
        end = k + len(name)
        if end < len(line) and (line[end].isalnum() or line[end] in "_-"):
            continue
        # expand left to the whole path token, then strip relative prefixes
        left = k
        while left and (line[left - 1].isalnum() or line[left - 1] in "./_-"):
            left -= 1
        token = line[left:end]
        while token.startswith("../") or token.startswith("./"):
            token = token.split("/", 1)[1]
        if token == name:
            return True


def referrers(name: str, qualified_only: bool) -> list[str]:
    """Tracked files that reference the repo-root `name`. Excludes generated caches.

    `qualified_only` implements the documented generic-basename rule: when another tracked
    file shares the basename, a bare mention cannot be attributed to the root file, so only a
    path-qualified mention (one that carried a directory component, e.g. `../../name`) counts.
    The counts are a LOWER BOUND on real inbound links, which is the safe direction for a move.
    """
    hits = git("grep", "-l", "-F", name, "--", ":!graphify-out/cache").split("\n")
    hits = [h for h in hits if h and h != name]
    out = []
    for h in hits:
        lines = git("grep", "-n", "-F", "--", name, h).split("\n")
        for l in lines:
            parts = l.split(":", 2)
            if len(parts) < 3:
                continue
            text = parts[2]
            if not refers_to_root(text, name):
                continue
            k = text.find(name)
            left = k
            while left and (text[left - 1].isalnum() or text[left - 1] in "./_-"):
                left -= 1
            if qualified_only and left == k:
                continue  # bare mention, ambiguous basename -> not attributable
            out.append(h)
            break
    return out


def main() -> int:
    loose = root_loose()
    groups = {
        "MARKDOWN": [f for f in loose if f.endswith(".md")],
        "DATA": [f for f in loose if f.endswith(DATA_EXT)],
        "CODE": [f for f in loose if f.endswith(CODE_EXT)],
    }

    for label, items in groups.items():
        print(f"\n{'='*76}\n{label}  --  {len(items)} file(s)\n{'='*76}")
        for f in sorted(items):
            if f in KEEP:
                print(f"  {f}\n      KEEP AT ROOT (policy)")
                continue
            n_sharing = files_sharing_basename(f)
            ambiguous = n_sharing > 1
            hits = referrers(f, qualified_only=ambiguous)
            note = f"   [{n_sharing} files share this basename -> path-qualified only]" if ambiguous else ""
            if not hits:
                print(f"  {f}{note}\n      REAL inbound 0 -> moves freely")
            else:
                print(f"  {f}{note}\n      REAL inbound {len(hits)} -> update referrers in the SAME commit:")
                for h in hits[:7]:
                    print(f"          {h}")
                if len(hits) > 7:
                    print(f"          ... and {len(hits)-7} more")

    print(f"\n{'='*76}\nTotal loose at root: {sum(len(v) for v in groups.values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

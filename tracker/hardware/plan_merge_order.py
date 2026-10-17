"""Work out the MERGE ORDER for the open balloon branches by measuring file overlap.

WHY. Six branches carry real work and none is merged. Several touch the same files -- GATE-RESULTS.md
appears on three of them, fab_grade.sh on two, docs/fab/README.md on several. Merging in the wrong order
produces conflicts that are avoidable, and merging one branch's version of a shared file over another's
would silently discard work.

This does not merge anything. It prints, from the actual commits, which files each branch changes relative
to master, and which files are claimed by MORE THAN ONE branch -- i.e. the files where order matters.

Run: python3 tracker/hardware/plan_merge_order.py
"""
from __future__ import annotations

import collections
import subprocess
import sys

BRANCHES = [
    "pr/u1-footprint",
    "pr/hub-milestone",
    "pr/erc-classification",
    "pr/presentation",
    "pr/repo-cleanup",
    "pr/peel-coupon",
]
BASE = "origin/master"


def sh(args) -> str:
    r = subprocess.run(args, capture_output=True, text=True, timeout=180)
    return r.stdout if r.returncode == 0 else ""


def main() -> int:
    sh(["git", "fetch", "origin", "-q"])

    base = sh(["git", "rev-parse", "--short", BASE]).strip()
    print(f"base: {BASE} = {base}\n")

    changed: dict[str, set[str]] = {}
    commits: dict[str, int] = {}
    for b in BRANCHES:
        ref = f"origin/{b}"
        files = sh(["git", "diff", "--name-only", f"{BASE}...{ref}"]).splitlines()
        n = sh(["git", "rev-list", "--count", f"{BASE}..{ref}"]).strip()
        if not files:
            print(f"  {b}: NOT FOUND or no commits vs {BASE}")
            continue
        changed[b] = {f for f in files if f.strip()}
        commits[b] = int(n or 0)
        print(f"  {b}: {commits[b]} commit(s), {len(changed[b])} file(s) changed")

    # files claimed by more than one branch
    owners: dict[str, list[str]] = collections.defaultdict(list)
    for b, fs in changed.items():
        for f in fs:
            owners[f].append(b)

    shared = {f: bs for f, bs in owners.items() if len(bs) > 1}

    print(f"\n=== files claimed by MORE THAN ONE branch: {len(shared)} ===")
    for f, bs in sorted(shared.items(), key=lambda kv: -len(kv[1])):
        print(f"  {len(bs)}x  {f}")
        for b in bs:
            print(f"        {b}")

    # per-branch: how many of its files are contended
    print("\n=== contention per branch ===")
    for b in BRANCHES:
        if b not in changed:
            continue
        contended = [f for f in changed[b] if len(owners[f]) > 1]
        print(f"  {b:24} {len(contended):2} of {len(changed[b]):2} files contended")

    # suggested order: least-contended and most-foundational first
    print("\n=== SUGGESTED ORDER (measurement-based, not a decision) ===")
    print("  Rationale: merge the branch that ESTABLISHES a shared file's content first, so later")
    print("  branches merge ONTO it rather than over it. Counted from the overlaps above.")
    order = sorted(
        (b for b in BRANCHES if b in changed),
        key=lambda b: (sum(1 for f in changed[b] if len(owners[f]) > 1), -commits[b]),
    )
    for i, b in enumerate(order, 1):
        cont = sum(1 for f in changed[b] if len(owners[f]) > 1)
        print(f"  {i}. {b:24} {commits[b]:2} commit(s)   {cont} contended file(s)")

    print("\n=== NOTE ON THE GATE FILES ===")
    for f in ("tracker/hardware/fab_grade.sh", "docs/fab/GATE-RESULTS.md", "docs/fab/README.md"):
        bs = owners.get(f, [])
        if bs:
            print(f"  {f}")
            print(f"      claimed by: {', '.join(bs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

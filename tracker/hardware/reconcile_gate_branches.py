"""Reconcile the two branches' truth about fab_grade.sh -- measured, not asserted.

WHY. Two branches now disagree about the same gate:
  pr/u1-footprint    recorded "fab_grade.sh exit 0 -> NOT ORDERABLE" (the OLD script, which printed the
                     verdict and exited 0 -- commit a59f97de5)
  pr/hub-milestone   fixed the script so the verdict DRIVES the exit code (commit d3509e451), and verified
                     NOT ORDERABLE -> exit 1, CLEAN -> exit 0

The recorded results on pr/u1-footprint were therefore produced by a gate whose exit code did not carry its
verdict. That is not a falsehood in the recording -- the exit code genuinely was 0 -- but it means
GATE-RESULTS.md and the fixed script must land together, or the recorded result will not match the gate
that produced it.

This script prints, from BOTH worktrees, what each actually contains, so the reconciliation is decided from
the files rather than from memory of which branch has what.
"""
import hashlib
import os
import subprocess
import sys

ROOTS = {
    "pr/u1-footprint": "/home/c08r4d0r/worktrees/u1-footprint",
    "pr/hub-milestone": "/home/c08r4d0r/worktrees/hub-milestone",
}


def sh(cmd, cwd):
    r = subprocess.run(["bash", "-lc", cmd], cwd=cwd, capture_output=True, text=True, timeout=120)
    return (r.stdout or "").strip()


def main():
    for label, root in ROOTS.items():
        print(f"\n=== {label}  ({root}) ===")
        if not os.path.isdir(root):
            print("  ABSENT")
            continue
        script = os.path.join(root, "tracker/hardware/fab_grade.sh")
        if not os.path.exists(script):
            print("  fab_grade.sh ABSENT")
            continue
        blob = open(script, "rb").read()
        print(f"  fab_grade.sh sha256: {hashlib.sha256(blob).hexdigest()[:24]}")
        # does the script carry the verdict into the exit code?
        has_exit = "sys.exit(1 if bad else 0)" in blob.decode("utf-8", "replace")
        print(f"  verdict drives the exit code: {has_exit}")
        print(f"  HEAD: {sh('git log --oneline -1', root)}")
        print(f"  status: {sh('git status --short | head -3', root) or '(clean)'}")
        print(f"  remote: {sh('git ls-remote --heads origin ' + label, root)[:9]}")
        # what does GATE-RESULTS.md say about fab_grade's exit code?
        gr = os.path.join(root, "docs/fab/GATE-RESULTS.md")
        if os.path.exists(gr):
            txt = open(gr, encoding="utf-8", errors="replace").read()
            hits = [l.strip() for l in txt.splitlines()
                    if "fab_grade" in l and ("exit" in l.lower() or "NOT ORDERABLE" in l)]
            print(f"  GATE-RESULTS.md lines about fab_grade: {len(hits)}")
            for h in hits[:4]:
                print(f"      {h[:150]}")
        else:
            print("  GATE-RESULTS.md ABSENT")
    return 0


if __name__ == "__main__":
    sys.exit(main())

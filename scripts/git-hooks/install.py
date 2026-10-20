#!/usr/bin/env python3
"""Install the image-freshness pre-commit hook into THIS clone of this repo.

The hook script itself lives IN the repo (scripts/git-hooks/) so it is versioned and
reviewed. This installer wires it into this clone's LOCAL hook path (never the global
core.hooksPath -- 2026-10-20 lesson: writing the global hook path clobbered the fleet
credential-gate pre-commit and silently disabled secret blocking for every repo on
this host until it was restored).

LOCAL HOOK PATH RULE
  If core.hooksPath is UNSET: write .git/hooks/pre-commit in THIS repo (local default).
  If core.hooksPath is SET: it is a FLEET hook directory (cred gate lives there).
    Writing there is FORBIDDEN for a repo-local installer. Instead we install to
    .git/hooks/pre-commit and leave core.hooksPath alone -- but then git would use
    core.hooksPath and ignore .git/hooks. So when a fleet hooksPath is set, the
    installer REFUSES and prints the manual snippet to append to the fleet hook.

Run once per clone:   python3 scripts/git-hooks/install.py
Idempotent: re-running refreshes the hook to the committed version.
"""
import os
import stat
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOOK_SRC = os.path.join(REPO, "scripts", "git-hooks", "pre-commit-image-freshness.py")

LOCAL_TRAMPOLINE = """#!/bin/sh
# Installed by scripts/git-hooks/install.py -- do not edit; edits belong in the repo copy.
# Always execs the CURRENT committed hook, so 'git pull' updates the check.
REPO="$(git rev-parse --show-toplevel)"
exec python3 "$REPO/scripts/git-hooks/pre-commit-image-freshness.py"
"""

FLEET_APPEND_SNIPPET = """# --- image freshness (added by scripts/git-hooks/install.py, 2026-10-20) ---
REPO="$(git rev-parse --show-toplevel 2>/dev/null)"
IMG_HOOK="$REPO/scripts/git-hooks/pre-commit-image-freshness.py"
if [ -f "$IMG_HOOK" ]; then
  exec python3 "$IMG_HOOK"      # runs AFTER your existing fleet checks in the same hook
fi
"""


def main():
    if not os.path.exists(HOOK_SRC):
        print(f"installer: hook source missing: {HOOK_SRC}")
        return 1
    r = subprocess.run(["git", "config", "--get", "core.hooksPath"], cwd=REPO,
                       capture_output=True, text=True)
    hooks_path = (r.stdout or "").strip()

    if hooks_path:
        # FLEET hook dir: DO NOT WRITE. Never clobber the cred gate again.
        print(f"installer: core.hooksPath is set to '{hooks_path}'")
        print("installer: a fleet hook directory is in use (credential gate).")
        print("installer: REFUSING to write there -- it would disable the cred gate.")
        print("\nTo enable the image gate for this repo, append this to the END of the")
        print(f"fleet hook ({hooks_path}/pre-commit), AFTER the cred-gate invocation:\n")
        print(FLEET_APPEND_SNIPPET)
        print("(The fleet hook at ~/.git-hooks/pre-commit already carries this snippet")
        print(" as of 2026-10-20, applied with cred-gate-first ordering.)")
        return 0

    hooks_dir = os.path.join(REPO, ".git", "hooks")
    os.makedirs(hooks_dir, exist_ok=True)
    dst = os.path.join(hooks_dir, "pre-commit")
    if os.path.exists(dst):
        with open(dst) as fh:
            existing = fh.read()
        if "pre-commit-image-freshness.py" in existing and "installer" not in existing:
            pass  # already our trampoline from a prior version; overwrite is fine
    with open(dst, "w") as fh:
        fh.write(LOCAL_TRAMPOLINE)
    os.chmod(dst, os.stat(dst).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"installed pre-commit trampoline -> {dst}")
    print("the trampoline execs the CURRENT committed hook, so 'git pull' updates it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
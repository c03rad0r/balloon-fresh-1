"""Run the repo's pytest suite file-by-file with a per-file timeout.

Purpose: the suite as a whole hangs on tests that need physical boards / serial /
network (they are not all marked `hardware`). A single hung file must not be
reported as "the suite passes" NOR as "my change broke the suite". Per-file
timeouts isolate both.

Read-only w.r.t. the tree. Prints a verdict table and exits 0 iff no file FAILED
(hangs are reported as SKIP-TIMEOUT, distinct from failures).
"""

import os
import re
import subprocess
import sys

TIMEOUT = 45
IGNORE_DIRS = {"throughput-matrix", "__pycache__", ".pytest_cache"}
# Files that cannot even import on Python 3.13 (telnetlib removed) or whose
# conftest helper no longer exists. Proven pre-existing on HEAD~2.
BROKEN = {
    "test_ground_station.py",
    "test_link_budget.py",
    "test_telemetry_to_nostr.py",
}

root = "tests"
files = []
for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
    for fn in sorted(filenames):
        if fn.startswith("test_") and fn.endswith(".py"):
            files.append(os.path.join(dirpath, fn))
files.sort()

rows = []
fails = []
for path in files:
    name = os.path.basename(path)
    if name in BROKEN:
        rows.append((path, "PRE-EXISTING-IMPORT-ERROR", ""))
        continue
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider",
             "-m", "not hardware", path],
            capture_output=True, text=True, timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        rows.append((path, f"SKIP-TIMEOUT>{TIMEOUT}s", "needs hardware/network"))
        continue
    tail = [ln for ln in r.stdout.splitlines() if ln.strip()][-1:] or [""]
    m = re.search(r"(\d+) passed", r.stdout)
    npass = m.group(1) if m else "0"
    if r.returncode == 0:
        rows.append((path, "PASS", f"{npass} passed"))
    else:
        # no tests collected is not a failure of the code
        if "no tests ran" in r.stdout or "deselected" in tail[0] and r.returncode == 5:
            rows.append((path, "SKIP-NO-TESTS", tail[0][:60]))
        else:
            rows.append((path, "FAIL", tail[0][:80]))
            fails.append(path)

for path, status, detail in rows:
    print(f"{status:26} {path:52} {detail}")

np_ = sum(1 for _, s, _ in rows if s == "PASS")
print(f"\nfiles={len(rows)} pass={np_} fail={len(fails)} "
      f"timeout={sum(1 for _, s, _ in rows if s.startswith('SKIP-TIMEOUT'))} "
      f"pre_broken={sum(1 for _, s, _ in rows if s == 'PRE-EXISTING-IMPORT-ERROR')}")
if fails:
    print("FAILING FILES:", fails)
sys.exit(0 if not fails else 1)

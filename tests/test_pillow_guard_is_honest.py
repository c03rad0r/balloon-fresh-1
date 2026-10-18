"""Prove the Pillow guard actually fires, instead of eyeballing the except clause.

Simulates an environment with no PIL by putting a meta-path finder in front that refuses it, then runs the
geometry checker as __main__ and asserts the output is the specific message rather than a bare traceback.
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

CODE = """
import sys

class Blocker:
    # Python 3.12 consults find_spec, not the removed find_module hook. Using the old API here made the
    # "no PIL" simulation silently NOT block anything, and the test then reported a false failure --
    # a broken test double is the same class of defect as a broken gate.
    def find_spec(self, name, path=None, target=None):
        if name == "PIL" or name.startswith("PIL."):
            raise ImportError("blocked for test")
        return None

sys.meta_path.insert(0, Blocker())
for mod in [m for m in list(sys.modules) if m == "PIL" or m.startswith("PIL.")]:
    del sys.modules[mod]

import runpy
runpy.run_path("scripts/check_system_diagram_geometry.py", run_name="__main__")
"""


def main() -> int:
    r = subprocess.run(
        [sys.executable, "-c", CODE], cwd=REPO, capture_output=True, text=True
    )
    out = (r.stdout or "") + (r.stderr or "")

    print(f"exit: {r.returncode}")
    print(f"output: {out.strip()[:400]}")

    if r.returncode == 0:
        print("FAIL: the checker exited 0 without Pillow -- it must not pass when it cannot measure")
        return 1
    if "Pillow is not installed" not in out:
        print("FAIL: exited non-zero but without the specific 'Pillow is not installed' message")
        print("      a gate that fails without saying why is the defect this guard exists to prevent")
        return 1

    print("PASS: fails non-zero AND names the missing dependency")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Is U4's missing 3D model block OUR regression, or pre-existing on master?

Method: materialise master's hub_board_v9 from git into a temp file, run the SAME census function the
failing test uses against BOTH files, and compare. The question is not "does the test fail" -- it fails
on our tree -- but "did it fail on master too", because that decides whether this branch regressed the
repo or merely inherited a red test.

Run: compare_u4_model_vs_master.py
"""
import importlib.util
import os
import subprocess
import sys
import tempfile

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
HUB = os.path.join(REPO, "tracker", "hardware", "hub_board_v9.kicad_pcb")


def load_census_module():
    p = os.path.join(REPO, "tests", "test_model_resolution_census.py")
    spec = importlib.util.spec_from_file_location("tmrc", p)
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except Exception as e:
        print(f"  could not import the census module: {e}")
        return None
    return m


def main():
    # materialise master's board
    tf = os.path.join(tempfile.gettempdir(), "master_hub_v9.kicad_pcb")
    r = subprocess.run(["git", "show", "origin/master:tracker/hardware/hub_board_v9.kicad_pcb"],
                       cwd=REPO, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  master has no hub_board_v9.kicad_pcb ({r.stderr.strip()[:120]})")
        master_board = None
    else:
        open(tf, "w").write(r.stdout)
        master_board = tf
        print(f"  master board written to {tf}")

    m = load_census_module()
    for label, path in (("MASTER", master_board), ("OURS", HUB)):
        print(f"\n--- {label}: {path} ---")
        if not path:
            print("  (absent)")
            continue
        b = pcbnew.LoadBoard(path)
        n_model = sum(1 for f in b.GetFootprints() if len(list(f.Models())) > 0)
        total = len(list(b.GetFootprints()))
        print(f"  footprints {total}, with >=1 model block: {n_model}")
        u4 = b.FindFootprintByReference("U4")
        if u4 is None:
            print("  U4: ABSENT")
        else:
            mods = list(u4.Models())
            print(f"  U4: present, models={len(mods)}, fpid={u4.GetFPID().GetLibItemName()}")
        if m:
            try:
                c = m.census(path)
                print(f"  census: unresolved_local={len(c['unresolved_local'])} "
                      f"unresolved_other={len(c['unresolved_other'])} "
                      f"hidden={len(c['hidden_refs'])} "
                      f"without_model={len(c['without_model_set'])}")
                must = getattr(m, "HUB_MUST_BE_VISIBLE", None)
                if must:
                    miss = [x for x in must if x in c["without_model_set"]]
                    print(f"  HUB_MUST_BE_VISIBLE missing: {miss}")
            except Exception as e:
                print(f"  census failed: {type(e).__name__} {e}")

    print("\n" + "=" * 76)
    print("READING")
    print("=" * 76)
    print("  Compare the two HUB_MUST_BE_VISIBLE lists above. If MASTER's is also non-empty, this is")
    print("  a PRE-EXISTING red test and not a regression from this branch. If only OURS is non-empty,")
    print("  the placement work dropped a model block and this branch must restore it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

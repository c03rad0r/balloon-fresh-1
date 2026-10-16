#!/usr/bin/env python3
"""Reproduce the census module's own unresolved_package list, to see how it resolves paths.

My own scanner reported 0 unresolved and the test reports 1, so the two resolve
${KICAD9_3DMODEL_DIR} differently. Print the module's constant, then the list, rather than guessing.

Run: ~/venvs/kicad/bin/python show_census_unresolved.py
"""
import importlib.util
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
MOD = os.path.join(REPO, "scripts", "model_resolution_census.py")
BOARD = os.path.join(REPO, "tracker", "hardware", "hub_board_v9.kicad_pcb")


def main():
    spec = importlib.util.spec_from_file_location("mrc", MOD)
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except SystemExit:
        pass

    d = getattr(m, "KICAD_3DMODEL_DIR", None)
    print(f"module file      : {MOD}")
    print(f"KICAD_3DMODEL_DIR: {d!r}")
    print(f"  isdir          : {os.path.isdir(str(d))}")
    env = os.environ.get("KICAD9_3DMODEL_DIR")
    print(f"env KICAD9_3DMODEL_DIR: {env!r}")

    r = m.census(BOARD)
    print(f"\ncensus keys: {sorted(r.keys())}")
    for k in ("unresolved_package", "unresolved_local", "unresolved_other", "hidden_refs"):
        if k in r:
            v = r[k]
            print(f"\n{k}: {len(v)}")
            for x in (v if isinstance(v, (list, tuple)) else [v])[:8]:
                print(f"   {x}")
                # try to show the resolved path the module would test
                if isinstance(x, str) and "3DMODEL_DIR" in x:
                    rel = x.split("}/", 1)[-1]
                    cand = os.path.join(str(d), rel)
                    print(f"     -> resolved candidate: {cand}")
                    print(f"        exists: {os.path.exists(cand)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

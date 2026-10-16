#!/usr/bin/env python3
"""Why did the builder not attach a model to U4, when PART_MODELS contains it?

The builder does:
    HUB_PART_MODELS.update(_load_hub_part_models())   # read from scripts/gen_3d_models_hub.py
    rel = HUB_PART_MODELS.get(c["ref"])               # None if the ref is absent
    attach_model(fp, rel)

So a model present in PART_MODELS but absent on the board means ONE of:
  (a) _load_hub_part_models() returned something that lacks "U4"   (loader failure, silent)
  (b) the component loop never reached U4                          (iteration scope)
  (c) attach_model() was called with a path that failed to resolve and was skipped

This script calls the builder's own loader and reports what it actually returns. It does not guess.

Run with: ~/venvs/kicad/bin/python why_no_u4_model.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
BUILDER = os.path.join(REPO, "tracker", "hardware", "build_hub_board_v9.py")
GENERATOR = os.path.join(REPO, "scripts", "gen_3d_models_hub.py")


def main():
    print(f"builder  : {BUILDER}")
    print(f"generator: {GENERATOR}  exists={os.path.exists(GENERATOR)}")

    # (1) does the generator expose PART_MODELS, and does it contain U4?
    spec = importlib.util.spec_from_file_location("gen3d", GENERATOR)
    g = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(g)
        pm = getattr(g, "PART_MODELS", None)
        print(f"\ngenerator PART_MODELS: {type(pm).__name__}, {len(pm) if pm else 0} entries")
        if pm:
            for k in sorted(pm, key=lambda s: (not s.startswith("U"), s)):
                print(f"   {k:10} -> {pm[k]}")
    except Exception as e:
        print(f"\ngenerator import FAILED: {type(e).__name__}: {e}")
        pm = None

    # (2) what does the BUILDER's own loader return?
    spec2 = importlib.util.spec_from_file_location("bhb", BUILDER)
    b = importlib.util.module_from_spec(spec2)
    try:
        spec2.loader.exec_module(b)
    except SystemExit:
        pass
    except Exception as e:
        print(f"\nbuilder import raised {type(e).__name__}: {e}")

    loader = getattr(b, "_load_hub_part_models", None)
    if loader is None:
        print("\nbuilder has no _load_hub_part_models()")
    else:
        try:
            got = loader()
            print(f"\nbuilder _load_hub_part_models() -> {type(got).__name__}, {len(got)} entries")
            print(f"   contains U4? {'U4' in got}")
            for k in sorted(got):
                print(f"   {k:10} -> {got[k]}")
            if "U4" not in got:
                print("\n   *** THE LOADER DROPS U4 *** -- that is the regression.")
        except Exception as e:
            print(f"\nbuilder loader FAILED: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    # (3) compare against the board
    import pcbnew
    bd = pcbnew.LoadBoard(os.path.join(REPO, "tracker", "hardware", "hub_board_v9.kicad_pcb"))
    u4 = bd.FindFootprintByReference("U4")
    print(f"\nboard U4: present={u4 is not None}, models={len(list(u4.Models())) if u4 else 'n/a'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

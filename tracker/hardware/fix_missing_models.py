#!/usr/bin/env python3
"""Fix the U4 model regression: master has U4's model, our promoted board does not.

ROOT CAUSE (established): the H1 fix promoted the ROUTED board from docs/fab/handoff/ to the canonical
path tracker/hardware/hub_board_v9.kicad_pcb. That routed board was produced by the ROUTER +
stitcher chain, which manipulates copper only -- it does not run the builder's model-attachment step.
So the promoted board carries 58 of 59 model blocks and is missing U4's.

The builder DOES know how to attach it: HUB_PART_MODELS (loaded from scripts/gen_3d_models_hub.py)
contains "U4" -> "hub/u4_sx1280_qfn24_envelope.wrl", and the file exists on disk (3342 bytes). The
mapping is correct; it was simply never applied to the promoted artefact.

THIS FIX is deliberately narrow and additive: take the canonical board and attach ONLY the missing
model blocks, using the builder's own mapping and the builder's own MODEL_REF_PREFIX. It does not touch
geometry, nets, copper, or any other footprint. That keeps it out of the territory of builder rule R2
(no hand-typed coordinates) -- a model reference is not a coordinate.

WHY NOT JUST RE-RUN THE BUILDER: the builder re-publishes the PLACED board, which would DISCARD the
routing this branch worked to promote. That is the opposite of what is needed here.

Run: ~/venvs/kicad/bin/python fix_missing_models.py [--apply]
      (without --apply it reports what it would do and exits non-zero if anything is missing)
"""
import argparse
import importlib.util
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
BOARD = os.path.join(REPO, "tracker", "hardware", "hub_board_v9.kicad_pcb")
BUILDER = os.path.join(REPO, "tracker", "hardware", "build_hub_board_v9.py")


def load_builder_mapping():
    """Use the BUILDER's own loader, so this fix cannot drift from the builder's mapping."""
    spec = importlib.util.spec_from_file_location("bhb", BUILDER)
    b = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(b)
    except SystemExit:
        pass
    loader = getattr(b, "_load_hub_part_models", None)
    prefix = getattr(b, "MODEL_REF_PREFIX", "${KIPRJMOD}/3dmodels/")
    if loader is None:
        return None, prefix
    return loader(), prefix


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    mapping, prefix = load_builder_mapping()
    if not mapping:
        print("REFUSING: could not load the builder's part-model mapping")
        return 1
    print(f"builder mapping: {len(mapping)} entries, prefix {prefix!r}")

    b = pcbnew.LoadBoard(BOARD)
    missing, fixed, unresolved = [], [], []
    for fp in b.GetFootprints():
        if len(list(fp.Models())) > 0:
            continue
        ref = str(fp.GetReference())
        missing.append(ref)
        rel = mapping.get(ref)
        if not rel:
            unresolved.append(ref)
            print(f"  {ref:8} no model in the builder mapping -- NOT fixed")
            continue
        full = prefix + rel
        # verify the file the reference points at actually exists
        on_disk = os.path.join(os.path.dirname(BOARD), "3dmodels", rel)
        exists = os.path.exists(on_disk)
        print(f"  {ref:8} -> {full}   file_on_disk={exists}")
        if not exists:
            unresolved.append(ref)
            continue
        m = pcbnew.FP_3DMODEL()
        m.m_Filename = full
        m.m_Scale.x = m.m_Scale.y = m.m_Scale.z = 1.0
        m.m_Offset.x = m.m_Offset.y = m.m_Offset.z = 0.0
        m.m_Rotation.x = m.m_Rotation.y = m.m_Rotation.z = 0.0
        fp.Add3DModel(m)
        fixed.append(ref)

    print(f"\nmissing before: {len(missing)}  -> {missing}")
    print(f"fixable       : {len(fixed)}  -> {fixed}")
    print(f"unresolvable  : {len(unresolved)}  -> {unresolved}")

    if not a.apply:
        print("\nDRY RUN. Re-run with --apply to write.")
        return 0 if not unresolved else 3

    if unresolved:
        print("\nREFUSING to write: some footprints have no resolvable model. Fix the mapping first,")
        print("so the board cannot end up in a half-repaired state.")
        return 3

    b.Save(BOARD)
    # verify by reloading
    b2 = pcbnew.LoadBoard(BOARD)
    after = [str(f.GetReference()) for f in b2.GetFootprints() if len(list(f.Models())) == 0]
    print(f"\nwrote {BOARD}")
    print(f"verified: footprints still without a model = {len(after)} -> {after}")
    return 0 if not after else 4


if __name__ == "__main__":
    sys.exit(main())

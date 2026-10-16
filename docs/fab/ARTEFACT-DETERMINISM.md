# Deterministic artefacts — plots, diagrams and renders

**Every committed image in this repo is produced by a generator that can prove the committed file is
still what it produces.** This document is the contract; `make artefacts-check` is the enforcement.

## The problem this closes

Three failures, all the same shape — an artefact that LOOKED current and was not:

1. **The fab package drifted 20 footprints behind the board**, losing the entire SX1280 RF match/filter
   chain. No check compared the upload artefact against the design.
2. **A typo survived in a reviewed diagram** after its generator had been fixed, because the review
   looked at the **old render**. Fixed → reviewed without regenerating = the review was a lie.
3. **`make_board_gallery.py` needs `pcbnew`**, which the pytest interpreter does not have. So whether the
   generator worked depended on **which python invoked it** — environment non-determinism.

## The contract

| property | how it is enforced |
|---|---|
| **Deterministic** | two runs produce byte-identical output; no wall-clock, no randomness, no unordered iteration in emitted text |
| **Verifiable** | every generator accepts `--check`, which writes nothing and exits non-zero if a committed artefact differs |
| **Checkable failure** | the guard test deliberately corrupts an artefact and requires `--check` to FAIL — a check that cannot fail proves nothing |
| **No host paths** | no artefact embeds `/home/...`; a path baked into an artefact is not reproducible elsewhere |
| **Pinned interpreter** | `PY_KICAD` is chosen by **testing for `pcbnew`**, not by assuming a fixed path |

## Targets

```bash
make artefacts-status    # what generators exist, which interpreter, nothing judged
make artefacts           # regenerate everything, then verify
make artefacts-check     # THE GATE: writes nothing, non-zero if anything is stale
make figures             # the human-facing subset (board gallery + system diagram)
make determinism-check   # prove the machinery itself works (selftest + guard tests)
```

## The shared helper

`scripts/artefact.py` gives every generator the same two operations:

```python
from artefact import DeterministicWriter
w = DeterministicWriter(__file__)
w.add("docs/boards/x.svg", svg_text)        # bytes or str
w.add_file("docs/boards/x.png", png_tmp)    # from a temp render
return w.finish(check=args.check)           # 0 = current, 1 = stale/missing
```

It proves itself: `python3 scripts/artefact.py --selftest` writes an artefact, re-checks it (must pass),
then checks a deliberately-changed payload (must fail), and prints `SELFTEST: PASS`.

**Writes are atomic** — a temp file in the same directory, then `os.replace` — so a failure cannot leave
a half-written artefact.

## Generators covered

| generator | artefacts | needs `pcbnew` |
|---|---|---|
| `tracker/hardware/make_board_gallery.py` | `docs/boards/GALLERY.md` + 3 renders | yes |
| `tracker/hardware/make_system_diagram.py` | `docs/boards/system-diagram.svg` + `.png` | yes |
| `tracker/hardware/make_edge_section.py` | `docs/fab/jlc-query/edge-launch-cross-section.svg` + `.png` | yes |
| `tracker/hardware/draw_peel_coupon.py` | `docs/fab/hub-v9/peel-coupon-specimens.svg` + `.png` | no |
| `scripts/gen_3d_models_hub.py` | `tracker/hardware/3dmodels/hub/*.wrl` | no |
| `scripts/gen_3d_models_wing.py` | `tracker/hardware/3dmodels/wing/*.wrl` | no |

The two 3D-model generators already had `--check`; the image generators were added on 2026-10-16.

## The guard test

`tests/test_generators_deterministic.py` asserts, per generator:

1. `--check` exits **0** on a freshly-written tree
2. `--check` exits **non-zero on a deliberately corrupted artefact** — the property that makes a check
   worth having
3. two runs are **byte-identical**
4. no artefact contains an **absolute host path**
5. `scripts/artefact.py --selftest` passes

**Adding a generator means adding it to `GENERATORS` in that file**, so a new one is covered
deliberately rather than silently uncovered.

## Two bugs found while building this

Both the same class as the failures above, and both caught by the tooling rather than by reading:

- **`make_edge_section.py` consumed `--check` as a FILENAME** — it read `sys.argv[1]` at module level
  before `argparse` ran, so the check reported `MISSING --check` and wrote nothing. Options are now parsed
  in `main()`. (The SVG and PNG themselves were proven byte-stable across runs with `cmp`.)
- **The first `--check` compared only the markdown**, because the render step was skipped in check mode —
  so a stale **PNG** would still have passed. The renders are now registered in check mode too, and the
  gallery check went from 1 artefact to 4.

## What is NOT covered yet

`tools/plot_*.py` and `tools/balloon_pressure_test/plot_pressure.py` produce plots but are not yet wired
into `make artefacts-check` — they write to run directories rather than to committed paths, so they need
their own decision about what is a committed artefact. Listed here rather than silently omitted.

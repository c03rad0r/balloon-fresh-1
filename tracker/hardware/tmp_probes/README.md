# tmp_probes — DIAGNOSTIC SCRIPTS. READ THIS BEFORE RUNNING ANYTHING HERE.

These scripts are **one-off probes** written while chasing specific defects. They are kept
because they document *how* each defect was measured, not because they are safe to run.

## The hazard that caused this directory

On 2026-10-21 the v10 board was **silently overwritten three times** — including once in
`/tmp`, once by a probe that imported the builder module (which calls `main()` on import and
saves), and once by a name collision in `/tmp`. Each time the board became a near-empty file
(1 footprint, 8.6 KB) and **measurements were taken against it** before anyone noticed. The
worst case: a placement gate reported clean against a board containing one footprint.

## Rules for this directory

1. **Never run a probe against `hub_board_v10.kicad_pcb`.** Copy the board to a scratch path
   first and work on the copy. `poison_uc9.py` is the pattern to follow: it copies, mutates
   the copy, and reports — it never writes the real board.
2. **Never import a builder module from a probe.** `build_hub_board_v10.py` executes
   `main()` and writes the board on import. Run it as a subprocess if you must.
3. **Never use `/tmp` for a probe that touches a board.** Use unique filenames under this
   directory.
4. **Cite the object you measured.** Every probe output should say which file it read, so a
   stale file cannot masquerade as the real board.

## Clobber guard (added the same day)

`build_hub_board_v10.py` and both routers now **refuse to save a board with fewer than 20
footprints** — the exact signature of these clobbers. If you see
`REFUSED: refusing to save a board with only N footprints`, you have hit it.

## What each probe measured

| file | defect it documented |
|---|---|
| `poison_uc9.py` | plants a track on `U_C.9` and proves the clearance gate catches it (the operator's short) |
| `ucmeasure.py` | exact clearance from the old `/ANT3_2G4_RX` lane to every `U_C` pin — found the 0.000 mm hit |
| `samechip.py` | resolves track endpoints to pads; found the dead ends and same-footprint segments |
| `trackdump.py` | every track's endpoints and the pads beneath them |
| `layercheck.py` | `GetLayer()` vs `GetLayerSet()` — found bug B6 (back-side pads read as F.Cu) |
| `usbdn*.py`, `u1row.py`, `u2pads.py`, `paddbg.py` | pad coordinates used while chasing specific nets |
| `astardbg*.py` | A* endpoint reachability — found the endpoint-footprint walling |
| `dbg_uc9.py` | per-pad layer/attribute dump for the `U_C.9` investigation |
| `clean_dead_tracks.py` | removed zero-length tracks (CAD fiction) from an early board |
| `census2.py` | dedup of duplicate shield pads — found the 4 phantom "self-nets" |
| `conncheck_repo.py` | pad-touch verification per net |

## Filed here from the repository ROOT (2026-10-25)

The root had accumulated 23 loose files; `pr/root-file-tidy` filed them here. Two groups:

- **Moved in (7)** — were only ever at root: `make_progress_map.py`, `make_registry_view.py`,
  `render_cross_side.py`, `render_layer.py`, `render_layers_distinct.py`, `trackdbg.py`,
  `u2pads.py`, plus the scratch artefacts `poison_uc9.kicad_pcb` and `scratch.kicad_pro`.
- **De-duplicated (12)** — already existed here byte-for-byte, so the root copies were deleted:
  `census2.py`, `clean_dead_tracks.py`, `conncheck_repo.py`, `layercheck.py`, `dbg_uc9.py`,
  `paddbg.py`, `poison_uc9.py`, `samechip.py`, `trackdump.py`, `ucmeasure.py`, `ucnet.py`,
  `zoom_defect.py`.

Root is now allow-listed and gated (`tests/test_root_layout.py`, run from the pre-commit hook) —
see AGENTS.md §28–§30.

## KNOWN LIMITATION — this directory is NOT portable

**64 of the 65 scripts here hardcode `/home/c08r4d0r/worktrees/master-check/...`.** They therefore
only run when that exact worktree exists. This is a **pre-existing condition**, recorded rather
than hidden: it was not introduced by the move and was deliberately **not** fixed in that PR
(a 64-file change does not belong in a layout cleanup).

If you are wiring one of these into anything real, **replace the hardcoded path with a repo-relative
one resolved from `__file__`** — and cite the board you actually read, per rule 4 above.

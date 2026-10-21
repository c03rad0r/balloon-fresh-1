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

# t_73c3244e — drivers provenance fragment: REPORT

Status: COMPLETE. Committed `49d4d76f`, pushed to
`origin/pr/lr2021-drivers-manifest-fragment` (remote head verified equal to local
`49d4d76fc70c3c8f4fa4e9b4bfeb5f9e287b5952`).

## Deliverable

`SCRATCH/lr2021-manifest-parts/drivers.md` — 25,504 B, sha256
`6958ccb60a0dc66ca77686ab7243e6afe3ad2271e082c8afa6eeec5695b4aa77`.

Append-only on top of the prior pass's 3,851 B (sha256 `0343a048…`), which remain
a strict byte prefix. F1 is preserved verbatim, not retracted.

## The input gap, and what I did about it

The card pins its read-only INPUT at `docs/lr2021-research/drivers/provenance.md`.
That file has never existed on any ref of this clone. Its producer `t_c6dd8d63` is
`archived` with no completed run (only `scheduled`/61 and `blocked`/123). F1 already
records this and still stands.

New in this pass: I found the manager has **already ruled on this family** on the board.

- `t_6d053fcd` (done) archived 21 superseded LR2021 sourcing-duplicate cards —
  `t_c6dd8d63` is on that list — because the deliverable was published elsewhere.
- `t_72f4873c` (archived, superseded) records the driver class as DONE: RadioLib
  snapshot @ `75e486a573bbaad443ffcafa23f9e3e3d2499914` (7.7.1-dev), 15 LR2021 files
  + LR11x0 shared headers, provenance sha256
  `3ecd892c57b17664f03b1856901bf95d83184fcf9901072ca53041034cdab26a`, and names
  `docs/lr2021-research/SOURCES.md` (A6) as the published manifest.

So the corpus of record for drivers is `docs/lr2021-research/radiolib-master/PROVENANCE.md`,
not the pinned path. Rather than block a third time on a decision already made, I
normalised **that** record into the mandated shape as an appended ADDENDUM. I did not
resurrect `t_c6dd8d63`, did not invent entries for the absent path, and did not convert
F1 into a success.

## Counts (as requested)

| scope | entries | verified | HASH MISMATCH | FAILED |
|---|---|---|---|---|
| pinned input `drivers/provenance.md` (F1) | 0 | 0 | 0 | 1 |
| `radiolib-master/PROVENANCE.md` (addendum) | 18 | 18 | 0 | 0 |
| **total** | **18** | **18** | **0** | **1** |

- verified entries (path exists AND sha256 matches): **18**
- entries flagged HASH MISMATCH: **0**
- FAILED entries: **1** (the card-pinned input, absent — unchanged from pass 1)

## Method / honesty notes

- Every size and sha256 was recomputed from disk this pass (`sha256sum` + `stat -c %s`).
  No value was copied from the provenance record.
- The snapshot was obtained upstream by `git clone --depth 1` of the whole tree, so
  **no per-file HTTP status exists**. Rather than fabricate a `200` for 18 files, every
  entry records `n/a` with that reason. `final_gate.py` asserts no `200` appears and that
  all 18 disclosures are present.
- Origin URL is recorded as the clone source @ pinned SHA plus the in-repo path — not
  asserted as a per-file raw fetch that never happened.
- Append-only discipline: pre-bytes proved to be a strict prefix after both appends.

## Verification

Local only, no network used for sourcing:

- `verify/verify_drivers_fragment.py` → **148/148 PASS, 0 FAIL**
  (entry count, field order, sequential ids, paths cover inventory, per-entry size +
  sha256 vs disk, revision pinning, HTTP-status honesty, docs/ untouched)
- `verify/final_gate.py` → **ALL PASS** (independent re-derivation of all 18 sha256 +
  size triples; append-only chain; provenance sha256 matches the manager's recorded value;
  no register-behaviour claims)
- `git status --porcelain -- docs/lr2021-research` → empty. No file under
  `docs/lr2021-research/` was modified.
- Worktree clean apart from `verify/verify_fragment.py`, a stale script from the prior
  run, deliberately left uncommitted.

## Two verifier bugs found and fixed (disclosed)

1. Uniform FAIL on all 18 `field_order` checks — my regex `[a-zA-Z/ ]+` excluded digits
   and so could not match the `sha256:` label. Parser bug, not data. Fixed to
   `[a-zA-Z0-9/ ]+`; all 18 then passed. (Uniform failure across every row ⇒ suspect the
   parser.)
2. First draft asserted a reconstructed `raw.githubusercontent.com/…/<SHA>/…` URL per
   file as the "origin URL". That would have implied a per-file HTTP fetch that never
   happened. Corrected to the true origin (clone URL @ SHA + in-repo path) before the
   append, and the verifier now fails if a raw branch-name fetch is asserted.

Also: the remote branch had been rebased onto a newer base (`677c6f23`, with 5 unrelated
files changed) while my local was at `3865151e`, a non-ancestor. I reset onto the remote
head and regenerated the addendum there rather than force-pushing; the base fragment was
byte-identical (`0343a048…`), so the result was identical (`c3a10bfc…` pre-note).

## Remaining for the manager

The pinned-path gap in F1 is still open and is a manager decision, not a sourcing one.
Options unchanged: revive `t_c6dd8d63` to vendor into the pinned path and re-dispatch, or
re-scope this card's input to `radiolib-master/PROVENANCE.md` (which the addendum now
covers in the merged shape), or accept F1 as terminal. The merge card `t_95beac11` is
`archived` with zero runs, so nothing downstream currently consumes the fragment.

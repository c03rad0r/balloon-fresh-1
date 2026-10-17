# LR2021 fetch manifest — drivers fragment

- source file specified by the task (read only): `docs/lr2021-research/drivers/provenance.md`
- source file status: **ABSENT — does not exist on any ref of `felixfelix-bot/balloon-fresh`, in any worktree on this host, or in any path outside the repo**
- verified entries (path exists AND sha256 matches): `0`
- entries flagged HASH MISMATCH: `0`
- FAILED entries: `1`
- verification tooling: `sha256sum` (fallback `shasum -a 256`, then `sha256`), plus `test -f`
- network access: none

---

## FAILED

### F1 — `docs/lr2021-research/drivers/provenance.md` — SOURCE FILE NOT PRESENT

- local path: `docs/lr2021-research/drivers/provenance.md` (specified by the task; never created)
- origin URL: `n/a` — no retrieval was ever recorded, because the source file itself was never produced
- HTTP status: `n/a`
- version/revision: `n/a`
- retrieval date: `n/a`
- file size: `n/a`
- sha256: `n/a`
- explicit reason: **source file absent.** The producer card `t_c6dd8d63` ("Vendor RadioLib LR2021 driver sources at a pinned SHA into `docs/lr2021-research/drivers/`", `worker-base`, network fetch via `curl`) is `archived` with **no completed run** — its only two runs are `scheduled` (run 61) and `blocked` (run 123, `fleet-offload:dq05`). It never fetched anything, so `docs/lr2021-research/drivers/` and its `provenance.md` were never created. This card `t_73c3244e` names that absent file as its read-only INPUT, so there are no entries to normalise or re-verify.

---

## Evidence recorded during this pass

All commands below are local and read-only with respect to `docs/`; no network access was used.

1. `git log --all --oneline -- docs/lr2021-research/drivers` → empty. No commit on any branch, tag or remote ref in this clone ever added the path.
2. `git ls-tree -r --name-only origin/main | grep 'lr2021-research/drivers/'` → empty. The path is absent from the current default-branch tree.
3. `git ls-tree -r --name-only origin/main | grep -i 'lr2021-research/.*provenance'` → the provenance files that DO exist are:
   - `docs/lr2021-research/datasheets/.provenance/lr1110.md`
   - `docs/lr2021-research/datasheets/.provenance/lr1121.md`
   - `docs/lr2021-research/datasheets/provenance-lr11x0.md`
   - `docs/lr2021-research/datasheets/provenance.md`
   - `docs/lr2021-research/errata/provenance.md`
   - `docs/lr2021-research/radiolib-master/PROVENANCE.md`
   None is at the specified path.
4. Filesystem sweep of `/home/c03rad0r/{repos,worktrees,.hermes/.worktrees}/**/docs/lr2021-research/drivers/provenance.md` and of `**/lr2021-manifest-parts` → no `drivers/` directory exists anywhere on this host; the only `lr2021-manifest-parts` directory is the sibling fragment task's own scratch (`t_9c3e3b22`), which holds `datasheets.md` only.
5. Card state read read-only from `~/.hermes/kanban/boards/tollgate/kanban.db` (`mode=ro`): `t_c6dd8d63` → `status=archived`, `result=NULL`, `current_run_id=NULL`; `task_runs` for it → `[scheduled/61, blocked/123]`. No run ever produced the deliverable.

---

## Non-normative note for the merge step (sourcing only, no technical conclusions)

A driver-provenance record **does** exist in the corpus at a different path than the one this card names: `docs/lr2021-research/radiolib-master/PROVENANCE.md` (RadioLib `master` snapshot @ `75e486a573bbaad443ffcafa23f9e3e3d2499914`, commit date 2026-09-13, version macros 7.7.1-dev, retrieved 2026-09-14 UTC by `git clone --depth 1`), authored by task `t_dbcc7e9a`. It was **not** used to populate this fragment, because the card specifies `docs/lr2021-research/drivers/provenance.md` as its read-only INPUT and re-scoping a named input is a manager decision, not a sourcing decision. Recorded here so the merge step and the manager can see the gap rather than infer it.

---

END OF FRAGMENT

---

## ADDENDUM — drivers provenance record that EXISTS in the corpus

Read-only sourcing pass appended for card `t_73c3244e` (run 396). F1 above is preserved verbatim and still holds: the card-pinned input `docs/lr2021-research/drivers/provenance.md` is absent.

The only driver-provenance record in the published corpus is at a different path. The merge step needs the retrieval entries either way, so they are normalised below under the same seven mandated fields, in the same field order, with every value independently recomputed from disk in this pass (no value copied from the record).

- provenance record (read only, not modified): `docs/lr2021-research/radiolib-master/PROVENANCE.md`
- provenance record size: `1868` B
- provenance record sha256: `3ecd892c57b17664f03b1856901bf95d83184fcf9901072ca53041034cdab26a`
- upstream repository: `https://github.com/jgromes/RadioLib.git` (branch `master`)
- revision (pinned commit SHA): `75e486a573bbaad443ffcafa23f9e3e3d2499914`
- upstream commit date: `2026-09-13T09:24:04+02:00`
- retrieval date (ISO-8601): `2026-09-14`
- retrieval method recorded upstream: `git clone --depth 1` (whole-tree snapshot, not per-file HTTP)
- retrieval entries below: `18`
- composition: `15` from `src/modules/LR2021/`, `2` shared LR11x0-family headers from `src/modules/LR11x0/`, `1` licence file
- HTTP status: applies per entry, see the field text — the snapshot came from a git clone, so no per-file HTTP status exists to record

### Entry field note

Origin URL is recorded as the SHA-pinned upstream location: the recorded clone source plus the in-repo path at the recorded revision. It is NOT a per-file fetch log — the upstream record states a single `git clone --depth 1` of the whole tree, so no per-file HTTP status exists to record and none is asserted.

### N1 — `docs/lr2021-research/radiolib-master/LR2021-module/LR2021.cpp`

- local path: `docs/lr2021-research/radiolib-master/LR2021-module/LR2021.cpp`
- origin URL: `https://github.com/jgromes/RadioLib.git` @ `75e486a573bbaad443ffcafa23f9e3e3d2499914`, in-repo path `src/modules/LR2021/LR2021.cpp` (tree browse: `https://github.com/jgromes/RadioLib/blob/75e486a573bbaad443ffcafa23f9e3e3d2499914/src/modules/LR2021/LR2021.cpp`)
- HTTP status: n/a — obtained by `git clone --depth 1` of the whole tree; no per-file HTTP request was made
- version/revision: `75e486a573bbaad443ffcafa23f9e3e3d2499914` (commit date `2026-09-13T09:24:04+02:00`; upstream path `src/modules/LR2021/LR2021.cpp`)
- retrieval date: `2026-09-14`
- file size: `39656` B
- sha256: `7662c16d8a2e4d10cd1fee7d5910a85a5a246d79f3c76586195af16a2fbbbfa9`
- re-verification: `test -f` PASS; `sha256sum` == recorded value (recomputed this pass)

### N2 — `docs/lr2021-research/radiolib-master/LR2021-module/LR2021.h`

- local path: `docs/lr2021-research/radiolib-master/LR2021-module/LR2021.h`
- origin URL: `https://github.com/jgromes/RadioLib.git` @ `75e486a573bbaad443ffcafa23f9e3e3d2499914`, in-repo path `src/modules/LR2021/LR2021.h` (tree browse: `https://github.com/jgromes/RadioLib/blob/75e486a573bbaad443ffcafa23f9e3e3d2499914/src/modules/LR2021/LR2021.h`)
- HTTP status: n/a — obtained by `git clone --depth 1` of the whole tree; no per-file HTTP request was made
- version/revision: `75e486a573bbaad443ffcafa23f9e3e3d2499914` (commit date `2026-09-13T09:24:04+02:00`; upstream path `src/modules/LR2021/LR2021.h`)
- retrieval date: `2026-09-14`
- file size: `49778` B
- sha256: `f87cda0d64c9a32f41fbdc963bdc66c3e7fa9fe5c56136f30abc2abc186a4756`
- re-verification: `test -f` PASS; `sha256sum` == recorded value (recomputed this pass)

### N3 — `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_chip_control.cpp`

- local path: `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_chip_control.cpp`
- origin URL: `https://github.com/jgromes/RadioLib.git` @ `75e486a573bbaad443ffcafa23f9e3e3d2499914`, in-repo path `src/modules/LR2021/LR2021_cmds_chip_control.cpp` (tree browse: `https://github.com/jgromes/RadioLib/blob/75e486a573bbaad443ffcafa23f9e3e3d2499914/src/modules/LR2021/LR2021_cmds_chip_control.cpp`)
- HTTP status: n/a — obtained by `git clone --depth 1` of the whole tree; no per-file HTTP request was made
- version/revision: `75e486a573bbaad443ffcafa23f9e3e3d2499914` (commit date `2026-09-13T09:24:04+02:00`; upstream path `src/modules/LR2021/LR2021_cmds_chip_control.cpp`)
- retrieval date: `2026-09-14`
- file size: `15930` B
- sha256: `90dd9d8319f9d92b85bdbbed2a0327c3e7a406a7d99cc904a12e4548c1294d20`
- re-verification: `test -f` PASS; `sha256sum` == recorded value (recomputed this pass)

### N4 — `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_flrc.cpp`

- local path: `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_flrc.cpp`
- origin URL: `https://github.com/jgromes/RadioLib.git` @ `75e486a573bbaad443ffcafa23f9e3e3d2499914`, in-repo path `src/modules/LR2021/LR2021_cmds_flrc.cpp` (tree browse: `https://github.com/jgromes/RadioLib/blob/75e486a573bbaad443ffcafa23f9e3e3d2499914/src/modules/LR2021/LR2021_cmds_flrc.cpp`)
- HTTP status: n/a — obtained by `git clone --depth 1` of the whole tree; no per-file HTTP request was made
- version/revision: `75e486a573bbaad443ffcafa23f9e3e3d2499914` (commit date `2026-09-13T09:24:04+02:00`; upstream path `src/modules/LR2021/LR2021_cmds_flrc.cpp`)
- retrieval date: `2026-09-14`
- file size: `2580` B
- sha256: `1171c3367d782f8e53179a814d14b698a0704c5a7b49e46c505fa91f6fcd6c6c`
- re-verification: `test -f` PASS; `sha256sum` == recorded value (recomputed this pass)

### N5 — `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_gfsk.cpp`

- local path: `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_gfsk.cpp`
- origin URL: `https://github.com/jgromes/RadioLib.git` @ `75e486a573bbaad443ffcafa23f9e3e3d2499914`, in-repo path `src/modules/LR2021/LR2021_cmds_gfsk.cpp` (tree browse: `https://github.com/jgromes/RadioLib/blob/75e486a573bbaad443ffcafa23f9e3e3d2499914/src/modules/LR2021/LR2021_cmds_gfsk.cpp`)
- HTTP status: n/a — obtained by `git clone --depth 1` of the whole tree; no per-file HTTP request was made
- version/revision: `75e486a573bbaad443ffcafa23f9e3e3d2499914` (commit date `2026-09-13T09:24:04+02:00`; upstream path `src/modules/LR2021/LR2021_cmds_gfsk.cpp`)
- retrieval date: `2026-09-14`
- file size: `4542` B
- sha256: `9adc791f82c937bb662e079706ec97680bb27670617ed841ee5fa33f8758293a`
- re-verification: `test -f` PASS; `sha256sum` == recorded value (recomputed this pass)

### N6 — `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_lora.cpp`

- local path: `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_lora.cpp`
- origin URL: `https://github.com/jgromes/RadioLib.git` @ `75e486a573bbaad443ffcafa23f9e3e3d2499914`, in-repo path `src/modules/LR2021/LR2021_cmds_lora.cpp` (tree browse: `https://github.com/jgromes/RadioLib/blob/75e486a573bbaad443ffcafa23f9e3e3d2499914/src/modules/LR2021/LR2021_cmds_lora.cpp`)
- HTTP status: n/a — obtained by `git clone --depth 1` of the whole tree; no per-file HTTP request was made
- version/revision: `75e486a573bbaad443ffcafa23f9e3e3d2499914` (commit date `2026-09-13T09:24:04+02:00`; upstream path `src/modules/LR2021/LR2021_cmds_lora.cpp`)
- retrieval date: `2026-09-14`
- file size: `6377` B
- sha256: `dcb35998a2c4be194a70dff0e08f722bcb7c4297d07e1249347d7712e51d7b70`
- re-verification: `test -f` PASS; `sha256sum` == recorded value (recomputed this pass)

### N7 — `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_misc.cpp`

- local path: `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_misc.cpp`
- origin URL: `https://github.com/jgromes/RadioLib.git` @ `75e486a573bbaad443ffcafa23f9e3e3d2499914`, in-repo path `src/modules/LR2021/LR2021_cmds_misc.cpp` (tree browse: `https://github.com/jgromes/RadioLib/blob/75e486a573bbaad443ffcafa23f9e3e3d2499914/src/modules/LR2021/LR2021_cmds_misc.cpp`)
- HTTP status: n/a — obtained by `git clone --depth 1` of the whole tree; no per-file HTTP request was made
- version/revision: `75e486a573bbaad443ffcafa23f9e3e3d2499914` (commit date `2026-09-13T09:24:04+02:00`; upstream path `src/modules/LR2021/LR2021_cmds_misc.cpp`)
- retrieval date: `2026-09-14`
- file size: `1208` B
- sha256: `e074ebfa44d130e60a458d47feed202adbcd66aa2ea24b9f3847bbbf5d46e0ba`
- re-verification: `test -f` PASS; `sha256sum` == recorded value (recomputed this pass)

### N8 — `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_ook.cpp`

- local path: `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_ook.cpp`
- origin URL: `https://github.com/jgromes/RadioLib.git` @ `75e486a573bbaad443ffcafa23f9e3e3d2499914`, in-repo path `src/modules/LR2021/LR2021_cmds_ook.cpp` (tree browse: `https://github.com/jgromes/RadioLib/blob/75e486a573bbaad443ffcafa23f9e3e3d2499914/src/modules/LR2021/LR2021_cmds_ook.cpp`)
- HTTP status: n/a — obtained by `git clone --depth 1` of the whole tree; no per-file HTTP request was made
- version/revision: `75e486a573bbaad443ffcafa23f9e3e3d2499914` (commit date `2026-09-13T09:24:04+02:00`; upstream path `src/modules/LR2021/LR2021_cmds_ook.cpp`)
- retrieval date: `2026-09-14`
- file size: `4674` B
- sha256: `d6291cf793e9ac109e2f30a9b059ff127cdfa57a25d7dae018d0ca8af4113f00`
- re-verification: `test -f` PASS; `sha256sum` == recorded value (recomputed this pass)

### N9 — `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_oqpsk.cpp`

- local path: `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_oqpsk.cpp`
- origin URL: `https://github.com/jgromes/RadioLib.git` @ `75e486a573bbaad443ffcafa23f9e3e3d2499914`, in-repo path `src/modules/LR2021/LR2021_cmds_oqpsk.cpp` (tree browse: `https://github.com/jgromes/RadioLib/blob/75e486a573bbaad443ffcafa23f9e3e3d2499914/src/modules/LR2021/LR2021_cmds_oqpsk.cpp`)
- HTTP status: n/a — obtained by `git clone --depth 1` of the whole tree; no per-file HTTP request was made
- version/revision: `75e486a573bbaad443ffcafa23f9e3e3d2499914` (commit date `2026-09-13T09:24:04+02:00`; upstream path `src/modules/LR2021/LR2021_cmds_oqpsk.cpp`)
- retrieval date: `2026-09-14`
- file size: `2412` B
- sha256: `3a65cae9ed0e9a525796afeea04047aabe8abe0dd4a7587e72352e690f6651cf`
- re-verification: `test -f` PASS; `sha256sum` == recorded value (recomputed this pass)

### N10 — `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_radio.cpp`

- local path: `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_radio.cpp`
- origin URL: `https://github.com/jgromes/RadioLib.git` @ `75e486a573bbaad443ffcafa23f9e3e3d2499914`, in-repo path `src/modules/LR2021/LR2021_cmds_radio.cpp` (tree browse: `https://github.com/jgromes/RadioLib/blob/75e486a573bbaad443ffcafa23f9e3e3d2499914/src/modules/LR2021/LR2021_cmds_radio.cpp`)
- HTTP status: n/a — obtained by `git clone --depth 1` of the whole tree; no per-file HTTP request was made
- version/revision: `75e486a573bbaad443ffcafa23f9e3e3d2499914` (commit date `2026-09-13T09:24:04+02:00`; upstream path `src/modules/LR2021/LR2021_cmds_radio.cpp`)
- retrieval date: `2026-09-14`
- file size: `4811` B
- sha256: `e3a91830e44d33ffb21e7c88e6651709db81842d618153448ab87f7da81571e4`
- re-verification: `test -f` PASS; `sha256sum` == recorded value (recomputed this pass)

### N11 — `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_ranging.cpp`

- local path: `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_cmds_ranging.cpp`
- origin URL: `https://github.com/jgromes/RadioLib.git` @ `75e486a573bbaad443ffcafa23f9e3e3d2499914`, in-repo path `src/modules/LR2021/LR2021_cmds_ranging.cpp` (tree browse: `https://github.com/jgromes/RadioLib/blob/75e486a573bbaad443ffcafa23f9e3e3d2499914/src/modules/LR2021/LR2021_cmds_ranging.cpp`)
- HTTP status: n/a — obtained by `git clone --depth 1` of the whole tree; no per-file HTTP request was made
- version/revision: `75e486a573bbaad443ffcafa23f9e3e3d2499914` (commit date `2026-09-13T09:24:04+02:00`; upstream path `src/modules/LR2021/LR2021_cmds_ranging.cpp`)
- retrieval date: `2026-09-14`
- file size: `2644` B
- sha256: `9b299e48f8fbdec151f53b0c3096517ce5b09cef2c85420da46ced1b2447e946`
- re-verification: `test -f` PASS; `sha256sum` == recorded value (recomputed this pass)

### N12 — `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_commands.h`

- local path: `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_commands.h`
- origin URL: `https://github.com/jgromes/RadioLib.git` @ `75e486a573bbaad443ffcafa23f9e3e3d2499914`, in-repo path `src/modules/LR2021/LR2021_commands.h` (tree browse: `https://github.com/jgromes/RadioLib/blob/75e486a573bbaad443ffcafa23f9e3e3d2499914/src/modules/LR2021/LR2021_commands.h`)
- HTTP status: n/a — obtained by `git clone --depth 1` of the whole tree; no per-file HTTP request was made
- version/revision: `75e486a573bbaad443ffcafa23f9e3e3d2499914` (commit date `2026-09-13T09:24:04+02:00`; upstream path `src/modules/LR2021/LR2021_commands.h`)
- retrieval date: `2026-09-14`
- file size: `48984` B
- sha256: `39086a393e18eb4e304f5d92031ddea81859ab07715152e2721c9262493981b6`
- re-verification: `test -f` PASS; `sha256sum` == recorded value (recomputed this pass)

### N13 — `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_config.cpp`

- local path: `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_config.cpp`
- origin URL: `https://github.com/jgromes/RadioLib.git` @ `75e486a573bbaad443ffcafa23f9e3e3d2499914`, in-repo path `src/modules/LR2021/LR2021_config.cpp` (tree browse: `https://github.com/jgromes/RadioLib/blob/75e486a573bbaad443ffcafa23f9e3e3d2499914/src/modules/LR2021/LR2021_config.cpp`)
- HTTP status: n/a — obtained by `git clone --depth 1` of the whole tree; no per-file HTTP request was made
- version/revision: `75e486a573bbaad443ffcafa23f9e3e3d2499914` (commit date `2026-09-13T09:24:04+02:00`; upstream path `src/modules/LR2021/LR2021_config.cpp`)
- retrieval date: `2026-09-14`
- file size: `45527` B
- sha256: `93abba9b3ad9cab47c14009534530c6de41506bc483c776a6de4627d557c1fac`
- re-verification: `test -f` PASS; `sha256sum` == recorded value (recomputed this pass)

### N14 — `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_registers.h`

- local path: `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_registers.h`
- origin URL: `https://github.com/jgromes/RadioLib.git` @ `75e486a573bbaad443ffcafa23f9e3e3d2499914`, in-repo path `src/modules/LR2021/LR2021_registers.h` (tree browse: `https://github.com/jgromes/RadioLib/blob/75e486a573bbaad443ffcafa23f9e3e3d2499914/src/modules/LR2021/LR2021_registers.h`)
- HTTP status: n/a — obtained by `git clone --depth 1` of the whole tree; no per-file HTTP request was made
- version/revision: `75e486a573bbaad443ffcafa23f9e3e3d2499914` (commit date `2026-09-13T09:24:04+02:00`; upstream path `src/modules/LR2021/LR2021_registers.h`)
- retrieval date: `2026-09-14`
- file size: `1790` B
- sha256: `9969971a60b7220859bb2533a57224a6ca179f6cb6a2ff4870c22892d62f992a`
- re-verification: `test -f` PASS; `sha256sum` == recorded value (recomputed this pass)

### N15 — `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_types.h`

- local path: `docs/lr2021-research/radiolib-master/LR2021-module/LR2021_types.h`
- origin URL: `https://github.com/jgromes/RadioLib.git` @ `75e486a573bbaad443ffcafa23f9e3e3d2499914`, in-repo path `src/modules/LR2021/LR2021_types.h` (tree browse: `https://github.com/jgromes/RadioLib/blob/75e486a573bbaad443ffcafa23f9e3e3d2499914/src/modules/LR2021/LR2021_types.h`)
- HTTP status: n/a — obtained by `git clone --depth 1` of the whole tree; no per-file HTTP request was made
- version/revision: `75e486a573bbaad443ffcafa23f9e3e3d2499914` (commit date `2026-09-13T09:24:04+02:00`; upstream path `src/modules/LR2021/LR2021_types.h`)
- retrieval date: `2026-09-14`
- file size: `1154` B
- sha256: `bf24b54f9435f223f517a95af185646bd22c4a54876b5a1c3f18a7f2a523d4bf`
- re-verification: `test -f` PASS; `sha256sum` == recorded value (recomputed this pass)

### N16 — `docs/lr2021-research/radiolib-master/LR11x0_commands.h`

- local path: `docs/lr2021-research/radiolib-master/LR11x0_commands.h`
- origin URL: `https://github.com/jgromes/RadioLib.git` @ `75e486a573bbaad443ffcafa23f9e3e3d2499914`, in-repo path `src/modules/LR11x0/LR11x0_commands.h` (tree browse: `https://github.com/jgromes/RadioLib/blob/75e486a573bbaad443ffcafa23f9e3e3d2499914/src/modules/LR11x0/LR11x0_commands.h`)
- HTTP status: n/a — obtained by `git clone --depth 1` of the whole tree; no per-file HTTP request was made
- version/revision: `75e486a573bbaad443ffcafa23f9e3e3d2499914` (commit date `2026-09-13T09:24:04+02:00`; upstream path `src/modules/LR11x0/LR11x0_commands.h`)
- retrieval date: `2026-09-14`
- file size: `54737` B
- sha256: `f88ef5d433a2591625a5ec1b0204a78ae066386b01612decfc6efcd24c939525`
- re-verification: `test -f` PASS; `sha256sum` == recorded value (recomputed this pass)

### N17 — `docs/lr2021-research/radiolib-master/LR11x0_types.h`

- local path: `docs/lr2021-research/radiolib-master/LR11x0_types.h`
- origin URL: `https://github.com/jgromes/RadioLib.git` @ `75e486a573bbaad443ffcafa23f9e3e3d2499914`, in-repo path `src/modules/LR11x0/LR11x0_types.h` (tree browse: `https://github.com/jgromes/RadioLib/blob/75e486a573bbaad443ffcafa23f9e3e3d2499914/src/modules/LR11x0/LR11x0_types.h`)
- HTTP status: n/a — obtained by `git clone --depth 1` of the whole tree; no per-file HTTP request was made
- version/revision: `75e486a573bbaad443ffcafa23f9e3e3d2499914` (commit date `2026-09-13T09:24:04+02:00`; upstream path `src/modules/LR11x0/LR11x0_types.h`)
- retrieval date: `2026-09-14`
- file size: `6350` B
- sha256: `57b7677ba2290f70fcacd2c79559b522524776df3ae73045b470da2b9c2c4e90`
- re-verification: `test -f` PASS; `sha256sum` == recorded value (recomputed this pass)

### N18 — `docs/lr2021-research/radiolib-master/LICENSE.txt`

- local path: `docs/lr2021-research/radiolib-master/LICENSE.txt`
- origin URL: `https://github.com/jgromes/RadioLib.git` @ `75e486a573bbaad443ffcafa23f9e3e3d2499914`, in-repo path `license.txt` (tree browse: `https://github.com/jgromes/RadioLib/blob/75e486a573bbaad443ffcafa23f9e3e3d2499914/license.txt`)
- HTTP status: n/a — obtained by `git clone --depth 1` of the whole tree; no per-file HTTP request was made
- version/revision: `75e486a573bbaad443ffcafa23f9e3e3d2499914` (commit date `2026-09-13T09:24:04+02:00`; upstream path `license.txt`)
- retrieval date: `2026-09-14`
- file size: `1068` B
- sha256: `025378110a5679f82e8a59c19cf91b8ed760dc8752e5504596ef0c0592b8a3e8`
- re-verification: `test -f` PASS; `sha256sum` == recorded value (recomputed this pass)

### Counts for the addendum scope

- verified entries (path exists AND sha256 matches): `18`
- entries flagged HASH MISMATCH: `0`
- FAILED entries: `0`

---

## Combined counts (both scopes)

| scope | entries | verified | HASH MISMATCH | FAILED |
|---|---|---|---|---|
| pinned input `docs/lr2021-research/drivers/provenance.md` (F1) | 0 | 0 | 0 | 1 |
| `docs/lr2021-research/radiolib-master/PROVENANCE.md` (addendum) | 18 | 18 | 0 | 0 |
| **total** | **18** | **18** | **0** | **1** |

Unchanged from the first pass: the pinned input's `0 verified / 0 mismatch / 1 FAILED` still stands on its own. The addendum does not convert F1 into a success and does not close the gap F1 records.

RE-VERIFIED IN THIS PASS


---

## Scope note — why the addendum lives at a different provenance record

Bookkeeping only (no technical content). Recorded so the merge step and the manager
can audit the scope choice without re-deriving it.

The card `t_73c3244e` pins its read-only INPUT at `docs/lr2021-research/drivers/provenance.md`.
That path has never existed on any ref of this clone, and its producer card `t_c6dd8d63`
is terminal without having run. This is F1 above and it is not retracted.

The manager has already closed this family on the board:

- `t_6d053fcd` (done) archived 21 superseded LR2021 sourcing-duplicate cards, `t_c6dd8d63` among them, because the deliverable was published elsewhere.
- `t_72f4873c` (archived, superseded) records the decision in its own result: the RadioLib
  driver class is "DONE, snapshot @ 75e486a5 (7.7.1-dev), 15 LR2021 files + LR11x0 shared
  headers, provenance sha256 `3ecd892c57b17664f03b1856901bf95d83184fcf9901072ca53041034cdab26a`",
  and names `docs/lr2021-research/SOURCES.md` as the published manifest.

So the corpus of record for drivers is `docs/lr2021-research/radiolib-master/PROVENANCE.md`,
not the pinned path. The addendum above normalises that record so the merge step has the
drivers category in the mandated shape. It does not resurrect `t_c6dd8d63`, does not invent
entries for the absent path, and leaves F1's counts standing.

Verification for this pass (local only, no network):

- every size and sha256 in the addendum was recomputed from disk with `sha256sum` +
  `stat -c %s`; none was copied from the provenance record
- `verify/verify_drivers_fragment.py` -> `148/148 PASS, 0 FAIL`
- `docs/lr2021-research/` unmodified: `git status --porcelain -- docs/lr2021-research` empty
- the provenance record's own sha256 recomputed here equals the value `t_72f4873c` recorded
  (`3ecd892c...b26a`), so the record the addendum describes is the one the manager accepted
- append-only: the pre-existing 3851 B are a strict byte prefix of this file
  (prefix sha256 `0343a048fc669f07941dfc22743dca8ef14cc030ea746faa0d6f466c036a1a6b`)

No register-behaviour claims, no technical conclusions, no upstream prose paraphrased.

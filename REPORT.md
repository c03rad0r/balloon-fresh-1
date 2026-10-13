# REPORT — pre-push secret hook: range-scoped scan (worker-balloon/nsec-hygiene)

## Summary

The balloon-fresh pre-push secret-scanning hook (`.githooks/pre-push`, tracked,
repo-local `core.hooksPath=.githooks`) no longer scans full repo history. It now
scans **only the outgoing range** of each pushed ref, so the retired nsec living
in remote history since 647865d2a936 can no longer block legitimate pushes, while
new secrets in outgoing commits are still caught — proven by the TDD red/green
cycle below and by a live push with no `--no-verify`.

Branch: `worker-balloon/nsec-hygiene` (off `origin/main` @ 8a474218; never main).
Worktree: `~/worktrees/nsec-hygiene`.
Landed: `bf070c03` (RED) → `953b6933` (GREEN), both pushed to
`refs/heads/worker-balloon/nsec-hygiene` on the GitHub origin (verified by
`git ls-remote`: `953b6933e1e6...`).

## The bug (ground truth, observed)

Both hook copies in circulation were broken, in opposite directions:

1. **Over-broad (the --no-verify incident).** The e80bench worktree's copy
   (blob d8330e0, v1) ran `git log -p --all` — full history of every ref
   (~900+ refs) — and grepped it per-pattern. Since the retired nsec has been
   in remote history since commit 647865d2a936 ("RadioLib integration...",
   2026-05-20), every push re-matched it and printed `PUSH BLOCKED — secrets
   detected in commit history`, forcing `--no-verify`. Reproduced hermetically:
   the hook blocked a push whose range contains no new secret (RED run B, 5
   failures, block output quoting the remote-history key).
2. **Blind (silent fail-open).** The origin/main copy (blob 19720ec4, v2, the
   2026-10-08 "perf rewrite") still scanned `--all`, but piped into plain
   `grep -f` — BRE semantics, where `{20,}` is literal — so every quantified
   pattern was defanged. Its unquoted `SCAN_PATHS` list also glob-expanded at
   the cwd, so nested paths were never scanned at all. In-vivo: this copy
   exits 0 in 0.02s (impossible for a real `--all` walk) and misses planted
   secrets (RED run A, 7 failures, all "must catch" tests).
3. `grep -P` with `-f` (multi-pattern) is rejected by GNU grep 3.12 — my
   first GREEN attempt failed open there; the RED suite caught it immediately
   (7 failures) and the final hook matches one pattern per invocation.

647865d verification: GitHub API `repos/.../commits/647865d2a936...` →
"RadioLib integration, antenna-tracker consolidation, build fixes",
2026-05-20, ancestor of remote main (compare API: status diverged, main
ahead 2042, behind 1 — so the commit predates main's tip and is on it).

## RED — the failing test (commit bf070c03)

`tests/test_pre_push_hook.py`: 13 hermetic tests. Each builds a scratch git
repo emulating the balloon-fresh topology: an initial commit carrying a
synthetic retired nsec-shaped literal (standing in for the 647865d key), a
remote-tracking `origin/main`, and unpushed local commits on top. The hook is
invoked exactly as git does (stdin = ref lines).

Contract pinned:
- planted unpushed secret BLOCKS (nsec / bearer / nested dir / multi-ref)
- pre-existing remote-history secret does NOT block (the incident shape)
- scrub commit REMOVING the secret passes; empty range passes;
  ref-deletion push passes
- ref-creation fallback scans the new-commit set
  (`local --not --remotes`), never full history
- no-remote-tracking-refs fallback still catches first-push leaks
- multi-ref push: any leaky range blocks

Observed RED (right reasons):
- vs origin/main v2 hook: **7 failed / 6 passed** — all "must catch" tests.
- vs e80bench v1 hook: **5 failed / 8 passed** — all "must not block" tests,
  block output re-quoting the remote-history key (the exact incident).

The planted dummy nsec is synthetic (`"nsec1"+"fresh"+"leak"+"q"*60`),
constructed at runtime by concatenation; there is no contiguous secret-shaped
literal in the committed tree (verified: `git grep -E 'nsec1[a-z0-9]{20,}' HEAD`
→ no match). Nothing dummy remains to delete — the "delete the dummy" step is
satisfied by construction-by-concatenation plus the grep-in-HEAD proof.

## GREEN — the fix (commit 953b6933)

`.githooks/pre-push` rewritten (file mode 100755 preserved):
- stdin parsed once, exactly as git feeds it:
  `<local_ref> <local_sha> <remote_ref> <remote_sha>`
- normal push: added lines of `remote_sha..local_sha` only
- ref creation (all-zeros remote_sha, or tip unknown to this clone):
  scans `local_sha --not --remotes` — the new-commit set, never full history
- ref deletion (all-zeros local_sha): adds nothing, passes
- only ADDED diff lines judged (scrubs pass, remote history can never block)
- patterns matched per-pattern with `grep -P` (with `-E` fallback if grep
  lacks -P); the patterns' `{n,m}`/`\d` semantics restored
- quoted pathspecs (git globs them at every depth) — recursive coverage
  restored
- merges judged via first-parent diff (conflict-resolution leaks caught)
- `git log -p --all` eliminated entirely; never scans working tree or history

Makefile: `test-unit` now includes `tests/test_pre_push_hook.py`.

Green: 13/13. `make test-unit`: 94 passed / 13 skipped (hardware) / 0 failed.
Full suite `pytest tests/ -m "not hardware"`: **709 passed, 21 skipped,
16 deselected, 0 failed** (93s).

## Live proof (no --no-verify)

The GREEN commit's push ran the NEW hook for real on the real repo:

```
✓ pre-push secret scan: no new secrets in the outgoing range.
To https://github.com/felixfelix-bot/balloon-fresh.git
   bf070c03..953b6933  worker-balloon/nsec-hygiene -> worker-balloon/nsec-hygiene
```

`git ls-remote origin refs/heads/worker-balloon/nsec-hygiene` →
`953b6933e1e6359d43299caf1a34355d40fbea74` (matches local HEAD).

## Scope discipline

- Touched files: `.githooks/pre-push`, `tests/test_pre_push_hook.py`, `Makefile`
  (3 files, +528/−30). Nothing else. Key-rotation files (e.g.
  `docs/HANDOVER-KEY-ROTATION.md`, ngit remote npub) untouched.
- Branch `worker-balloon/nsec-hygiene` only; no commit to main; no merge.
- No `git filter-repo`, no force-push, no history rewrite of any kind.
- Deliberately NOT mirrored to ngit: the ngit remote URL embeds the compromised
  npub being rotated in parallel, and ngit's mirror main (4ba3e67d) is already
  drifted from origin/main — pushing there now would entangle this branch with
  the rotation work. Recommend mirroring after the rotation lands.
- Foreign build artifacts (`tracker/.../test_fips*` ELF binaries) that
  `make test-unit` rebuilt were restored, not committed (shared tree hygiene).
- One planned in-vivo diagnostic (manual hook invocation on the live range)
  was blocked by the host's approval gate and was skipped; the hermetic
  suite plus the live push cover that ground.

## Files

- `~/worktrees/nsec-hygiene/.githooks/pre-push` — the fixed hook (committed)
- `~/worktrees/nsec-hygiene/tests/test_pre_push_hook.py` — 13-test contract (committed)
- `~/worktrees/nsec-hygiene/Makefile` — test-unit wiring (committed)
- `~/worktrees/nsec-hygiene/PROGRESS.md` — status log (gitignored by repo rule)
- `~/worktrees/nsec-hygiene/REPORT.md` — this report (gitignored, worktree-local)

## Recommendation

Merge `worker-balloon/nsec-hygiene` into main at your discretion (2 commits,
clean fast-forward base at 8a474218). After merge, the e80bench/tollgate
linked worktrees pick up the new hook on their next rebase onto main. Note for
the key-rotation track: this hook no longer blocks scrub pushes, so the
rotation's history-clean work can proceed without `--no-verify` as long as
the outgoing commits add no new secret literals.
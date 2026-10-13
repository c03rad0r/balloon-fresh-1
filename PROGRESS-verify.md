# PROGRESS — independent verification of keymaterial suite (card t_4c98fbe7)

Worktree : /home/c03rad0r/worktrees/keymat-verify
Branch   : verify/keymat-verification-t_4c98fbe7  (pushed to github/balloon-fresh)
Base     : remotes/github/pr/keymaterial-env-sole-source @ b201428e
Status   : COMPLETE — all 6 briefed steps executed; verdict PASS w/ 4 hardening gaps.

## INPUT DISCREPANCY (material, found first)
Briefed paths DO NOT EXIST anywhere on this filesystem (`find /`):
  tools/tests/conftest.py                  -> ABSENT
  tools/tests/test_keymaterial_env.py      -> ABSENT
  tools/tests/test_keymaterial_safety.py   -> ABSENT
  tools/keymaterial.py (repo root)         -> ABSENT
Real layout:
  firmware/e80-stm32-bench/tools/keymaterial.py
  firmware/e80-stm32-bench/tools/test_keymaterial.py   (ONE module, 22 tests; no conftest)
Acceptance criteria sourced from the kanban card body, board e80-bench,
/boards/e80-bench/kanban.db tasks.id='t_4c98fbe7' -> 7 numbered ACCEPTANCE items.

## Log  (finding -> status -> files touched)
- [01] Located real artifacts + card ACCEPTANCE text; isolated worktree created
       under ~/worktrees/ (never ~/repos/).                                    status=done
- [02] pytest on the real file: 21 passed, 1 skipped (skip = coincurve absent).
       Literal `pytest tools/tests -q` -> "file or directory not found", 0 collected.
       Whole tools/ dir: 1015 passed, 9 skipped.                               status=done
- [03] Greps: ZERO nsec1 literals; the two 64-hex hits are the secp256k1 generator
       X and an obvious dummy, neither on the key path. Exactly one `def load_keys`.
       Single open() on the publish path hashes a radio preset, not a key.      status=done
- [04] git status clean but for this verifier's own files; no stray E80_* file;
       no E80_* env var set; audited commit touches only tools/ source+tests.   status=done
- [05] Independent smoke reproduction (own bech32 encoder, fresh keys):
       4/4 smokes OK (happy path, collision, missing var, repr+str redaction).  status=done
- [06] Five /tmp mutants (tools/ untouched): cached load_keys -> 12 fail (CAUGHT);
       leak in missing-var msg -> 1 fail (CAUGHT); __str__ unredacted -> 1 fail
       (CAUGHT); extra var names in msg -> SURVIVES; refusal phrase removed ->
       SURVIVES. The last two are gaps G1/G2.                                   status=done
- [07] REPORT-keymat-verification.md + verify-evidence/RAW-EVIDENCE.md written;
       own artifacts rescanned and redacted so they pass the 64-hex/nsec gate they
       audit. Committed + pushed; remote head verified == 03df044f.             status=done

## Verdict
PASS against the 7 ACCEPTANCE criteria. Of the brief's four assertion-strength
claims: (a) PASS, (b) FAIL, (c) PARTIAL FAIL (pubkey yes, phrase no), (d) PASS.
Gaps G1-G4 are test-strength, not correctness. Fixes deliberately NOT applied —
the verifier must not edit the artifact it grades. Full detail in the report.

## Residual risks
G1 "other four names absent" not asserted; G2 refusal phrase not pinned;
G3 ACCEPTANCE 1/2 are grep-only (no automated test); G4 "exactly one accessor"
not pinned; G6 test_keymaterial.py is in no Makefile target (ungated in CI);
G7 coincurve skip leaves the pure-Python secp256k1 derivation unvalidated here;
G8 e28/cvm_board_server still take --nsec/--server-hex from argv (outside the
card's gift-wrap scope, pre-existing).

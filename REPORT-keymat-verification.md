# REPORT — Independent verification of the keymaterial test suite & acceptance evidence

Card              : t_4c98fbe7 "Make env-only key accessor sole key source in e80-stm32-bench"
Board             : e80-bench
Artifact audited  : remotes/github/pr/keymaterial-env-sole-source @ b201428e
Verifier worktree : /home/c03rad0r/worktrees/keymat-verify (branch verify/keymat-verification)
Host              : Linux; Python 3.11.15; pytest 9.1.1; pluggy 1.6.0
Raw evidence      : verify-evidence/RAW-EVIDENCE.md (this directory)
Constraint honoured: NO file under tools/ was modified. Zero typos needed fixing.

================================================================================
## VERDICT

  ACCEPTANCE (the 7 numbered criteria in the card body) .......... PASS
  Test suite health (21 passed / 1 skipped; tools/ 1015 passed / 9 skipped) . PASS
  Secret-hygiene evidence (no nsec literals, no key file read, no stray artifact) . PASS

  BUT the brief's FOUR assertion-strength sub-claims, taken literally .... 2 of 4 FAIL

   (a) no-caching test would fail if load_keys() cached results ....... PASS  (proved by mutation)
   (b) missing-var tests assert the OTHER four variable names are absent  FAIL  (survives mutation)
   (c) collision test asserts the exact x-only pubkey AND a refusal phrase  PARTIAL FAIL
   (d) redaction tests check BOTH repr and str for zero leakage ....... PASS  (proved by mutation)

  NET: the suite is sound and non-vacuous, and it does prove every acceptance
  criterion that the card actually states. Two of the four extra strength claims
  in the verification brief are NOT met by the tests as written -- those are
  hardening opportunities, not correctness defects. See RESIDUAL GAPS.

================================================================================
## 0. BLOCKING INPUT DISCREPANCY (read first)

Three of the four files named as INPUTS in the task do not exist:

  tools/tests/conftest.py                    ABSENT
  tools/tests/test_keymaterial_env.py        ABSENT
  tools/tests/test_keymaterial_safety.py     ABSENT
  tools/keymaterial.py (repo root)           ABSENT

Verified absent filesystem-wide (`find /`), not just in this worktree:

  $ ls tools/keymaterial* tools/tests/test_keymaterial* tools/tests/conftest.py
  ls: cannot access 'tools/keymaterial*': No such file or directory
  ls: cannot access 'tools/tests/keymaterial*': No such file or directory
  ls: cannot access 'tools/tests/test_keymaterial*': No such file or directory
  ls: cannot access 'tools/tests/conftest.py': No such file or directory

  $ find / -name 'test_keymaterial_env.py' -o -name 'test_keymaterial_safety.py'
  (no output)
  $ find /home/c03rad0r -type d -path '*/tools/tests'
  (no output)

The inputs as described do not exist in this repository on any ref. The suite is
NOT split into an "env" file and a "safety" file, and there is no conftest.py:
the actual deliverable is a SINGLE test module.

What actually exists (git ls-files | grep keymaterial):
  firmware/e80-stm32-bench/tools/keymaterial.py        (346 lines, the module)
  firmware/e80-stm32-bench/tools/test_keymaterial.py   (315 lines, 22 tests)

Consequence: the briefed command `python -m pytest tools/tests -q` cannot work
(it exits non-zero with "ERROR: file or directory not found: tools/tests"). I
re-based the verification on the real artifacts and took the authoritative
acceptance criteria from the kanban card body for t_4c98fbe7, which contains
SEVEN numbered ACCEPTANCE items (the brief's "six numbered test cases" is off by
one; the canonical set is 1..7 — three of them are the "smoke tests"). The
coverage table below maps all seven.

================================================================================
## 1. COMMANDS RUN + RAW OUTPUT (full output in RAW-EVIDENCE.md)

1. `python3 -m pytest tools/tests -q`   (the literal command)
   -> ERROR: file or directory not found: tools/tests / "no tests ran in 0.01s"
      collected 0 items. Exit 0 (pytest treats 0 collected as success).

2. `python3 -m pytest firmware/e80-stm32-bench/tools/test_keymaterial.py -q`
   -> collected 22 items
   -> FINAL SUMMARY LINE: 21 passed, 1 skipped in 3.37s
   The single skip is TestDerivation::test_xonly_matches_coincurve (coincurve
   not installed -> self.skipTest by design).

3. `cd firmware/e80-stm32-bench/tools && python3 -m pytest test_keymaterial.py -v`
   -> 21 passed, 1 skipped in 3.46s   (all 22 test IDs listed in RAW-EVIDENCE §1c)

4. `python3 -m pytest firmware/e80-stm32-bench/tools -q -p no:cacheprovider`
   -> 1015 passed, 9 skipped in 14.44s   (whole-directory independent regression)
   (HEAD body claims "1016 passed, 8 skipped": the delta is exactly the coincurve
    skip — environment difference, not a regression.)

5. `grep -rnE 'nsec1[0-9a-z]{20,}' firmware/e80-stm32-bench/tools/`  -> ZERO hits
   `grep -rnE 'nsec1[0-9a-z]{58}'  firmware/e80-stm32-bench/tools/`  -> ZERO hits
   `grep -rnE 'nsec1[0-9a-z]{20,}' tools/tests/`  -> "No such file or directory"
   `grep -rnE '\b[0-9a-fA-F]{64}\b' firmware/e80-stm32-bench/tools/` -> 2 hits, both benign:
     test_nostr_giftwrap.py:41  TX_HEX = 79be667e...81798  == secp256k1 GENERATOR X
                                (== _GX at keymaterial.py:103). A PUBLIC curve
                                constant used as a stand-in recipient pubkey.
     test_nostr_giftwrap.py:68  "aabbccdd...8899"          == obvious dummy hex.
   Neither is on the key path, neither is a private scalar, neither is injected
   into any E80_*/CVM_* env var. No privkey literal exists.

6. `git status --porcelain` -> `?? PROGRESS-verify.md`  (ONLY this verifier's file)
   `git status --porcelain -uall | grep -iE 'E80_|\.env|key'` -> (none)
   `find . -name 'E80_*'` -> (none)
   `env | grep -E '^E80_'` -> NONE SET
   `git show --stat b201428e` -> 6 files, all under
   firmware/e80-stm32-bench/tools/ (4 source + 2 test). No key file, no config
   dump, no secret artifact created or read. NO STRAY E80_* FILE.

7. Independent smoke reproduction with MY OWN bech32 encoder and fresh in-process
   keys (/tmp/indep_smoke.py, not the author's tests) — all four smokes OK:
   happy path distinct; collision raises KeyCollisionError naming the x-only
   pubkey, not the secret, with the phrase "refusing to publish"; missing var
   names the variable and leaks nothing; repr AND str both redact; keymaterial.py
   contains neither open( nor read_text.

8. `grep -nE 'open\(|read_text|read_bytes|Path\(' nostr_giftwrap.py cvm_armed_publisher.py`
   -> exactly ONE hit: cvm_armed_publisher.py:174 `open(path,"rb")` inside
      `preset_hash_for()` — it SHA-256s a RADIO PRESET file, not a key.
      nostr_giftwrap.py: zero hits. No key file read on the publish path.

9. `grep -rn 'def load_keys' firmware/e80-stm32-bench/tools/` -> EXACTLY 1 hit
   (keymaterial.py:282). Publish-path call sites: nostr_giftwrap.py:449,499;
   cvm_armed_publisher.py:256,497; cvm_tx_listener.py:233.
   (e28_board_server.py:442 / cvm_board_server.py:625 are unrelated
    `_load_keys` helpers parsing --server-hex/--nsec CLI args — not the accessor.)
   `import keymaterial; km.__all__` -> public functions == ['dataclass','field','load_keys']
   i.e. exactly ONE public accessor.

10. Mutation sanity check (all mutants are /tmp copies; tools/ never touched):
    A module-level cache regression -> 12 failed  (CAUGHT)
    B missing-var msg also names the other vars -> 17 passed (SURVIVES)
    C refusal phrase removed -> 17 passed (SURVIVES)
    D missing-var msg leaks the server secret -> 1 failed (CAUGHT)
    E __str__ stops redacting (repr still does) -> 1 failed (CAUGHT)

================================================================================
## 2. COVERAGE TABLE — canonical ACCEPTANCE items 1..7 vs concrete test functions

| # | ACCEPTANCE criterion (card t_4c98fbe7)                                   | Covering test / method                                                                                    | Verdict |
|---|--------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------|---------|
| 1 | no `nsec1[0-9a-z]{20,}` and no privkey 64-hex literal in tools/           | NO TEST. Verified by grep (this audit). Zero nsec; 2 benign 64-hex = generator X + dummy string.           | PASS (manual, UNGUARDED) |
| 2 | no key file opened/read on the publish path                              | NO TEST. Verified by grep (this audit). One open() = radio preset hash, not a key.                        | PASS (manual, UNGUARDED) |
| 3 | both call sites use load_keys(); exactly one accessor symbol exists       | PARTIAL: TestPublishPathWiring::test_builder_resolves_keys_via_load_keys, ::test_publisher_resolves_keys_via_load_keys (patch km.load_keys, assert both routes go through it). No test asserts the "exactly one def" grep property. Both wiring tests SKIP when the module is absent. | PARTIAL (behavioural evidence; uniqueness UNGUARDED) |
| 4 | Smoke 1 happy path: distinct keys, client_pubkey != server_pubkey        | TestHappyPath::test_smoke1_distinct_nsec_keys                                                             | PASS |
| 5 | Smoke 2 collision: distinct error type, message names pubkey, no secret  | TestCollision::test_smoke2_same_key_raises_collision, ::test_collision_via_pubkey_side, ::test_collision_is_a_runtimeerror. Pubkey asserted (assertIn of x-only hex); secret absence asserted (nsec + raw hex). Refusal phrase NOT asserted. | PASS on type+pubkey+no-secret; GAP on refusal phrase |
| 6 | Smoke 3 missing var: error names the variable, contains no key value     | TestMissing::test_smoke3_missing_client_names_variable, ::test_missing_server_names_variable. Names the variable: yes. No secret value: yes. Other four names asserted absent: NO. | PASS on primary claim; GAP on "other names absent" |
| 7 | repr(load_keys()) contains no secret material                            | TestHygiene::test_smoke_repr_redacts_all_secrets — loops over BOTH repr(k) and str(k)                     | PASS |

Supplementary tests beyond the 7 criteria (all passing):
  TestDerivation::test_npub_decodes_to_pubkey; ::test_xonly_matches_coincurve [SKIP: no coincurve]
  TestHappyPath::test_server_pubkey_only / test_server_npub_accepted / test_client_hexkey /
    test_client_nsec_and_hexkey_agree / test_client_nsec_and_hexkey_disagree_refused /
    test_server_nsec_and_pubkey_disagree_refused / test_relay_auth_read_here
  TestHygiene::test_call_time_read_not_import_time / test_no_module_level_secret_constants
  TestPublishPathWiring::test_error_taxonomy_shared_with_the_accessor /
    test_publisher_main_exits_cleanly_on_missing_key

=> NO numbered ACCEPTANCE item is left with zero coverage. Items 1, 2 and the
   "exactly one" half of 3 have NO automated test — they are grep/manual evidence
   only, so nothing in CI would fail if they regressed.

================================================================================
## 3. ASSERTION-STRENGTH AUDIT (the brief's four claims), each PROVED by mutation

(a) Would the no-caching test fail if load_keys() cached results?  --- YES (PASS)
    Mutant A: module-level dict cache, early-return, populate-then-return.
    Result: 12 failed, 5 passed, 5 skipped. test_call_time_read_not_import_time
    among the failures (observed '0328...' != '6fde...' — the stale first value).
    The suite is NOT vacuous and this property IS enforced.

(b) Do the missing-var tests assert the OTHER four variable names are absent? --- NO (FAIL)
    Neither TestMissing test contains an assertNotIn for any of the four other
    env names; the only assertNotIn is on the secret VALUE (the nsec string).
    Mutant B (missing-client message additionally names E80_SERVER_NSEC and
    E80_SERVER_PUBKEY): 17 passed, 5 skipped -> SURVIVES.
    Enforced instead: the variable that IS missing is named (assertIn), and no
    secret value leaks (assertNotIn of the nsec; proved by Mutant D, which was
    caught). So the no-secret half of (b) is solid; the "other names absent"
    half is not implemented.

(c) Does the collision test assert the exact x-only pubkey AND a refusal phrase? --- PARTIAL (FAIL on phrase)
    Exact x-only pubkey: YES — test_smoke2_same_key_raises_collision asserts
      assertIn(_hexpub(secret), msg), where _hexpub derives from the SAME local
      key, so it is a real equality of the derived x-only value. It also asserts
      assertNotIn(nsec) and assertNotIn(raw hex).
    Refusal phrase: NO — `grep -rn -i 'refus' test_keymaterial.py` matches only
      two TEST FUNCTION NAMES ("..._disagree_refused"), never an assertion.
    Mutant C (phrase "refusing to publish" deleted from the production message):
      17 passed, 5 skipped -> SURVIVES.
    => the phrase requirement is documented in the module but not pinned by a test.

(d) Do the redaction tests check both repr and str for zero secret leakage? --- YES (PASS)
    test_smoke_repr_redacts_all_secrets iterates `for blob in (repr(k), str(k))`
    and for each asserts absence of _nsec(client), _nsec(server), client raw hex,
    relay raw hex, and presence of "redacted"; then asserts both pubkeys ARE shown.
    Mutant E (a __str__ that no longer redacts while repr still does):
      1 failed -> CAUGHT. The str half is genuinely load-bearing.

================================================================================
## 4. RESIDUAL GAPS AND RISKS

G1 (LOW-MED, test-strength) — "other four names absent" not asserted.
   An over-eager error message that names every env var would still pass. Fix is
   a two-line assertNotIn per missing-var test.

G2 (LOW-MED, test-strength) — refusal phrase not pinned.
   The collision contract's "refusing to publish" wording can silently disappear.
   Fix: assertIn("refusing", msg) in test_smoke2_same_key_raises_collision.

G3 (MED, coverage) — ACCEPTANCE 1 & 2 have no automated test.
   "no nsec literal" and "no key-file read" are pure grep evidence. A future
   commit could add a hard-coded nsec or a key-file read and every test would
   still pass. Fix: a hygiene test that scans the tools/ source text (and/or the
   module's own __dict__) for nsec1{20,} / 64-hex literals and for open()/read_text
   on the publish path — this is exactly the class of check the card asks for.

G4 (MED, coverage) — ACCEPTANCE 3's "exactly one accessor" is not pinned.
   Only the behavioural wiring is tested (both entry points route through
   load_keys). A second reader would not necessarily fail anything.

G5 (LOW, structural) — the brief's "env" / "safety" split does not exist.
   There is one test module. Anyone (human or agent) following the brief's paths
   will find nothing; the brief should be corrected to
   firmware/e80-stm32-bench/tools/test_keymaterial.py.

G6 (LOW, CI wiring) — test_keymaterial.py is NOT referenced by any Makefile.
   `make range-test-host` runs test_e80_range_split.py, test_range_check.py,
   test_cvm_armed_publisher.py, test_cvm_verdict_publisher.py,
   test_cvm_tx_listener.py — test_keymaterial.py is absent from that list.
   The commit body's "22 passed" was therefore a manual run, not a gated one.
   It passes under a directory-wide pytest, but no repo target exercises it.
   (Same blind spot the repo's other tools/ tests share — they are collected by
   directory, not by an enumerated target. Note test_cvm_armed_publisher.py IS
   enumerated and DOES exercise load_keys indirectly.)

G7 (LOW, environment) — the independent secp256k1 cross-check is skipped.
   coincurve is not installed here, so the pure-Python derivation (keymaterial's
   most intricate code: bech32 + affine double-and-add) is unvalidated against a
   reference on this host. I partially compensated: my own smoke run derived
   distinct x-only pubkeys through the same code and the 4-key happy path plus
   the collision path behaved correctly, and test_npub_decodes_to_pubkey proves
   bech32 round-trip consistency. But there is NO external vector check for the
   point multiplication in this environment. Recommend installing coincurve in
   CI so that test actually runs rather than self-skipping.

G8 (INFORMATIONAL) — pre-existing, NOT introduced by this card (pre-existing on
   the branch, unchanged by b201428e): e28_board_server.py and cvm_board_server.py
   still read `--server-hex`/`--nsec` from argv for the CVM/socket server, and
   they define their own `_load_keys` helpers. They are outside the gift-wrap
   publish path the card scopes to, so this is not an acceptance failure — but if
   the "env is the ONLY source" rule is meant to be repo-wide, those two entry
   points are out of compliance and would need the same treatment.

================================================================================
## 5. WHAT WAS AND WAS NOT DONE

DONE: every command in the brief (re-based to real paths), with raw output; the
seven-item ACCEPTANCE mapping; the four-part assertion-strength audit proved by
four mutants that survive/fail exactly as predicted; workspace isolated in
~/worktrees/, never ~/repos/; nothing under tools/ modified.

NOT DONE / OUT OF SCOPE: no change to any source or test file (the brief allows
only typo fixes; none were needed). The hardening fixes for G1–G4 are RECOMMENDED
in this report but deliberately NOT applied, because as the independent verifier I
must not edit the artifact I am grading — applying them would invalidate the
verification. A follow-up card should carry G1–G4.

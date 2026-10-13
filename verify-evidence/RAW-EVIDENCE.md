# RAW EVIDENCE — independent verification, card t_4c98fbe7 (keymaterial)

Verifier worktree : /home/c03rad0r/worktrees/keymat-verify
Branch            : verify/keymat-verification (from remotes/github/pr/keymaterial-env-sole-source)
Base commit       : b201428e  "feat(e80-cvm): env-only key material is the sole key source on the publish path"
Host              : Linux, Python 3.11.15, pytest 9.1.1, pluggy 1.6.0

---------------------------------------------------------------------------
## 0. PATH DISCREPANCY (blocking finding)

The briefed paths do not exist anywhere on this filesystem:

  tools/tests/conftest.py                  -> ABSENT
  tools/tests/test_keymaterial_env.py      -> ABSENT
  tools/tests/test_keymaterial_safety.py   -> ABSENT
  tools/keymaterial.py (repo root)         -> ABSENT

  $ ls tools/keymaterial* tools/tests/test_keymaterial* tools/tests/conftest.py
  ls: cannot access 'tools/keymaterial*': No such file or directory
  ls: cannot access 'tools/tests/keymaterial*': No such file or directory
  ls: cannot access 'tools/tests/test_keymaterial*': No such file or directory
  ls: cannot access 'tools/tests/conftest.py': No such file or directory

  $ find / -name 'test_keymaterial_env.py' -o -name 'test_keymaterial_safety.py'
  (no output)
  $ find /home/c03rad0r -type d -path '*/tools/tests'
  (no output)

REAL layout on the branch (git ls-files | grep keymaterial):
  firmware/e80-stm32-bench/tools/keymaterial.py
  firmware/e80-stm32-bench/tools/test_keymaterial.py      <-- ONE file, 22 tests
No conftest.py exists near tools/ (tests are path-injected, run from tools/).
Verification was therefore re-based on the ACTUAL artifacts. The six "numbered test
cases in the original task" named by the brief are the seven numbered ACCEPTANCE
items (1..7) in the kanban card body for t_4c98fbe7 (board e80-bench).

---------------------------------------------------------------------------
## 1. TEST SUITE

### 1a. The LITERAL briefed command (from repo root)
$ python3 -m pytest tools/tests -q
ERROR: file or directory not found: tools/tests

============================= test session starts ==============================
platform linux -- Python 3.11.15, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/c03rad0r/worktrees/keymat-verify
configfile: pytest.ini (WARNING: ignoring pytest config in pyproject.toml!)
plugins: cov-7.1.0, timeout-2.4.0
collected 0 items

============================ no tests ran in 0.01s =============================

(exit 0 despite collecting nothing -- pytest treats "no tests ran" as success here)

### 1b. From repo root, real path
$ python3 -m pytest firmware/e80-stm32-bench/tools/test_keymaterial.py -q
collected 22 items
firmware/e80-stm32-bench/tools/test_keymaterial.py .s................... [ 95%]
.                                                                        [100%]
======================== 21 passed, 1 skipped in 3.37s =========================

### 1c. Canonical cwd (tools/), verbose  -- 21 passed, 1 skipped in 3.46s
$ cd firmware/e80-stm32-bench/tools && python3 -m pytest test_keymaterial.py -v
test_keymaterial.py::TestDerivation::test_npub_decodes_to_pubkey PASSED  [  4%]
test_keymaterial.py::TestDerivation::test_xonly_matches_coincurve SKIPPED [  9%]
test_keymaterial.py::TestHappyPath::test_client_hexkey PASSED            [ 13%]
test_keymaterial.py::TestHappyPath::test_client_nsec_and_hexkey_agree PASSED [ 18%]
test_keymaterial.py::TestHappyPath::test_client_nsec_and_hexkey_disagree_refused PASSED [ 22%]
test_keymaterial.py::TestHappyPath::test_relay_auth_read_here PASSED     [ 27%]
test_keymaterial.py::TestHappyPath::test_server_npub_accepted PASSED     [ 31%]
test_keymaterial.py::TestHappyPath::test_server_nsec_and_pubkey_disagree_refused PASSED [ 36%]
test_keymaterial.py::TestHappyPath::test_server_pubkey_only PASSED       [ 40%]
test_keymaterial.py::TestHappyPath::test_smoke1_distinct_nsec_keys PASSED [ 45%]
test_keymaterial.py::TestCollision::test_collision_is_a_runtimeerror PASSED [ 50%]
test_keymaterial.py::TestCollision::test_collision_via_pubkey_side PASSED [ 54%]
test_keymaterial.py::TestCollision::test_smoke2_same_key_raises_collision PASSED [ 59%]
test_keymaterial.py::TestMissing::test_missing_server_names_variable PASSED [ 63%]
test_keymaterial.py::TestMissing::test_smoke3_missing_client_names_variable PASSED [ 68%]
test_keymaterial.py::TestHygiene::test_call_time_read_not_import_time PASSED [ 72%]
test_keymaterial.py::TestHygiene::test_no_module_level_secret_constants PASSED [ 77%]
test_keymaterial.py::TestHygiene::test_smoke_repr_redacts_all_secrets PASSED [ 81%]
test_keymaterial.py::TestPublishPathWiring::test_builder_resolves_keys_via_load_keys PASSED [ 86%]
test_keymaterial.py::TestPublishPathWiring::test_error_taxonomy_shared_with_the_accessor PASSED [ 90%]
test_keymaterial.py::TestPublishPathWiring::test_publisher_main_exits_cleanly_on_missing_key PASSED [ 95%]
test_keymaterial.py::TestPublishPathWiring::test_publisher_resolves_keys_via_load_keys PASSED [100%]
======================== 21 passed, 1 skipped in 3.46s =========================

FINAL PASS/FAIL SUMMARY LINE: 21 passed, 1 skipped
The single skip: TestDerivation::test_xonly_matches_coincurve
  -> coincurve is NOT installed on this host; the test self-skips by design
     (try: import coincurve / except ImportError: self.skipTest).
  => The pure-Python secp256k1 derivation is NOT independently cross-checked on
     this host. Covered instead by this verifier's own smoke run (§4).

### 1d. Whole tools/ directory (independent regression scope)
$ python3 -m pytest firmware/e80-stm32-bench/tools -q -p no:cacheprovider
======================= 1015 passed, 9 skipped in 14.44s =======================
(HEAD commit body claims "1016 passed, 8 skipped" -- delta of 1 is exactly the
 coincurve skip above, i.e. an environment difference, not a regression.)

---------------------------------------------------------------------------
## 2. LITERAL-NSEC GREPS

$ grep -rnE 'nsec1[0-9a-z]{20,}' firmware/e80-stm32-bench/tools/
(zero hits -- rc=1)

$ grep -rnE 'nsec1[0-9a-z]{58}' firmware/e80-stm32-bench/tools/
(zero hits -- rc=1, exact-length bech32 sweep)

$ grep -rnE 'nsec1[0-9a-z]{20,}' tools/tests/
grep: tools/tests/: No such file or directory   (rc=2 -- the briefed path is absent)

=> ZERO nsec literals. The only nsec strings anywhere in tools/ are the
   "nsec1..." references inside human-readable docstrings/help text, swallowed
   by {20,}. No constructable nsec value exists in tools/.

$ grep -rnE '\b[0-9a-fA-F]{64}\b' firmware/e80-stm32-bench/tools/
firmware/e80-stm32-bench/tools/test_nostr_giftwrap.py:41:TX_HEX = "79be667e...16f81798"
firmware/e80-stm32-bench/tools/test_nostr_giftwrap.py:68:    "author": "aabbccdd...66778899",
(values truncated here on purpose: this evidence file must itself pass the very
 64-hex-literal gate it audits. Re-run the grep above to see the full lines.)

REDACTION NOTE: no full 64-hex literal and no nsec literal is reproduced in this
file. Ephemeral pubkeys from the smoke run are summarised by hash below rather
than pasted, for the same reason.

JUSTIFICATION OF BOTH 64-HEX HITS:
  * TX_HEX == 79be66...81798 == the secp256k1 GENERATOR X coordinate (the
    well-known public constant; equals _GX in keymaterial.py:103). It is a
    PUBLIC curve constant used as a stand-in recipient PUBKEY, not a private key.
  * "aabbccdd...8899" is the canonical obvious-non-secret dummy hex string.
  * Neither is on the key path: both live in a TEST file, neither is ever
    exported into E80_* / CVM_* env vars, neither is a private scalar in use.
  => No privkey literal. Both hits are benign and explainable.

EXPLICITLY CHECKED: no nsec-shaped numeric literal (12, 32, 22, 34, 40, 45, 52,
58 chars) exists -- §1's {20,} sweep and the {58} sweep are the matcher.

---------------------------------------------------------------------------
## 3. GIT STATUS / STRAY ARTIFACTS

$ git status --porcelain
?? PROGRESS-verify.md
(that is the ONLY entry -- this verifier's own progress file. The tree is
 otherwise CLEAN: no tools/ file was modified by verification.)

$ git status --porcelain --untracked-files=all | grep -iE 'E80_|\.env|key'
(none)

$ find . -name 'E80_*' | grep -v '/\.git/'
(none)

$ env | grep -E '^E80_'
NONE SET

$ git show --stat b201428e        # files touched by the audited commit
 firmware/e80-stm32-bench/tools/cvm_armed_publisher.py   |  47 +--
 firmware/e80-stm32-bench/tools/cvm_tx_listener.py       |  33 +-
 firmware/e80-stm32-bench/tools/keymaterial.py           | 346 ++++
 firmware/e80-stm32-bench/tools/nostr_giftwrap.py        |  34 +-
 firmware/e80-stm32-bench/tools/test_keymaterial.py      | 315 ++++
 firmware/e80-stm32-bench/tools/test_nostr_giftwrap.py   |  44 +-
 6 files changed, 764 insertions(+), 55 deletions(-)

=> Only source/test files under firmware/e80-stm32-bench/tools/ were changed.
   NO key file, NO config dump, NO secret artifact was added or read.
   NO stray E80_* file exists in the worktree.

---------------------------------------------------------------------------
## 4. INDEPENDENT SMOKE REPRODUCTION (own script, not the author's test file)

/tmp/indep_smoke.py -- own bech32 encoder, fresh keys in-process.

=== SMOKE 1 happy path ===
 (two distinct random x-only pubkeys derived; values withheld on purpose -- see
  REDACTION NOTE above. Observed: 64-lowercase-hex each, and unequal.)
 OK distinct: True
=== SMOKE 2 same key -> collision ===
 type     = KeyCollisionError
 message  = client key and server key resolve to the same pubkey (x-only <64-hex x-only pubkey>); refusing to publish
 pubkey in msg: True      secret in msg: False False
 refusal phrase 'refusing' in msg: True
 OK
=== SMOKE 3 missing E80_CLIENT_NSEC ===
 type    = MissingKeyError
 message = E80_CLIENT_NSEC or E80_CLIENT_HEXKEY is not set; export one before publishing
 names E80_CLIENT_NSEC: True      leaks key material: False
 OK
=== SMOKE 7 repr/str redaction ===
  repr = KeyMaterial(client_pubkey='<64-hex x-only pubkey>', server_pubkey='<64-hex x-only pubkey>', client_secret={redacted}, server_secret={redacted}, relay_auth={redacted})
  str  = (identical)
 OK no secret in repr or str; pubkeys visible
=== SMOKE 4 no key-file read on publish path ===
 keymaterial.py references open/read_text: False
 ALL SMOKES PASSED   (exit 0)

(Real generated ephemeral key values are REDACTED in this file on purpose; the
 unredacted run output is in the session transcript. All secrets were fresh,
 in-process, and never persisted.)

---------------------------------------------------------------------------
## 5. KEY-FILE READ GREP (ACCEPTANCE 2)

$ grep -nE 'open\(|read_text|read_bytes|Path\(' nostr_giftwrap.py cvm_armed_publisher.py
cvm_armed_publisher.py:174:        with open(path, "rb") as fh:

CONTEXT (line 170-177) -- it is NOT a key read:
    def preset_hash_for(path: Optional[str]) -> str:
        """Short content hash of a preset file (KNOW the preset you armed on)."""
        if not path: return ""
        try:
            with open(path, "rb") as fh:
                return hashlib.sha256(fh.read()).hexdigest()[:12]
  -> reads a RADIO PRESET file to hash it. nostr_giftwrap.py has ZERO
     open/read_text/read_bytes.
  => No key file is read on the publish path. PASS.

---------------------------------------------------------------------------
## 6. ACCESSOR-UNIQUENESS GREP (ACCEPTANCE 3)

$ grep -rn 'def load_keys' firmware/e80-stm32-bench/tools/
firmware/e80-stm32-bench/tools/keymaterial.py:282:def load_keys() -> KeyMaterial:
COUNT = 1   PASS

$ grep -rn 'load_keys(' firmware/e80-stm32-bench/tools/   (publish-path call sites)
nostr_giftwrap.py:449:    keys = keys or keymaterial.load_keys()
nostr_giftwrap.py:499:    keys = keys or keymaterial.load_keys()
cvm_armed_publisher.py:256:    km = keymaterial.load_keys()
cvm_armed_publisher.py:497:    km = keymaterial.load_keys()
cvm_tx_listener.py:233:    km = keymaterial.load_keys()
NOTE: the same symbols in e28_board_server.py:442 and cvm_board_server.py:625 are
UNRELATED helpers named `_load_keys` (leading underscore) that build nostr_sdk
Keys from --server-hex/--nsec CLI args (pre-existing, not on the E80 gift-wrap
publish path). They are not `def load_keys` and do not shadow the accessor.

$ python3 -c "import keymaterial as km; print(km.__all__)"
['load_keys', 'KeyMaterial', 'KeyMaterialError', 'MissingKeyError',
 'KeyCollisionError', 'ENV_CLIENT_NSEC', 'ENV_CLIENT_HEXKEY', 'ENV_SERVER_NSEC',
 'ENV_SERVER_PUBKEY', 'ENV_RELAY_AUTH']
public functions == ['dataclass', 'field', 'load_keys'] -> exactly ONE accessor.

---------------------------------------------------------------------------
## 7. MUTATION SANITY CHECK (tools/ untouchable -- all mutants are /tmp copies)

### Mutant A -- module-level cache (the briefed regression)
Diffs vs the shipped file:
  +_KEY_CACHE = {}                      # module-level cache
  +    if _KEY_CACHE:
  +        return _KEY_CACHE["km"]       # top of load_keys()
  +    _KEY_CACHE["km"] = KeyMaterial(...)  ; return _KEY_CACHE["km"]   # tail

$ cd /tmp/mut && PYTHONPATH=/tmp/mut python3 -m pytest test_keymaterial.py -q
FAILED test_keymaterial.py::TestHappyPath::test_client_nsec_and_hexkey_agree
FAILED test_keymaterial.py::TestHappyPath::test_client_nsec_and_hexkey_disagree_refused
FAILED test_keymaterial.py::TestHappyPath::test_relay_auth_read_here
FAILED test_keymaterial.py::TestHappyPath::test_server_npub_accepted
FAILED test_keymaterial.py::TestHappyPath::test_server_nsec_and_pubkey_disagree_refused
FAILED test_keymaterial.py::TestHappyPath::test_server_pubkey_only
FAILED test_keymaterial.py::TestHappyPath::test_smoke1_distinct_nsec_keys
FAILED test_keymaterial.py::TestCollision::test_collision_via_pubkey_side
FAILED test_keymaterial.py::TestCollision::test_smoke2_same_key_raises_collision
FAILED test_keymaterial.py::TestMissing::test_missing_server_names_variable
FAILED test_keymaterial.py::TestMissing::test_smoke3_missing_client_names_variable
FAILED test_keymaterial.py::TestHygiene::test_call_time_read_not_import_time
=================== 12 failed, 5 passed, 5 skipped in 1.12s ====================
=> CAUGHT. Sanity check passes: the suite is not vacuous. Copy discarded.

### Mutant B -- missing-client error ALSO names E80_SERVER_NSEC/E80_SERVER_PUBKEY
$ pytest test_keymaterial.py -q  ->  17 passed, 5 skipped   EXIT=0
=> SURVIVES. No test asserts the other variable names are ABSENT from the
   missing-var message. Audit item (b) FAILS.

### Mutant C -- drop the "refusing to publish" phrase
$ pytest test_keymaterial.py -q  ->  17 passed, 5 skipped   EXIT=0
=> SURVIVES. No test asserts the refusal phrase. Audit item (c) FAILS on the
   phrase half. The exact x-only pubkey half IS asserted
   (test_smoke2_same_key_raises_collision: self.assertIn(_hexpub(secret), msg)).

### Mutant D -- missing-client message LEAKS the server secret
$ pytest test_keymaterial.py -q  ->  1 failed, 16 passed, 5 skipped
FAILED ...TestMissing::test_smoke3_missing_client_names_variable
    AssertionError: 'nsec1<...>' unexpectedly found in 'E80_CLIENT_NSEC or
    E80_CLIENT_HEXKEY is not set; server want is nsec1<...>; export one'
=> CAUGHT. The no-secret half of (b) IS enforced.

### Mutant E -- __str__ no longer redacts (repr still does)
$ pytest test_keymaterial.py -q  ->  1 failed, 16 passed, 5 skipped
FAILED ...TestHygiene::test_smoke_repr_redacts_all_secrets
=> CAUGHT. Audit item (d) (both repr AND str) IS enforced.

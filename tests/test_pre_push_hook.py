"""
test_pre_push_hook.py — hermetic tests for .githooks/pre-push range scoping.

Regression guard for the incident where the pre-push hook scanned
`git log -p --all` (FULL repo history, every ref) instead of the outgoing
(unpushed) range. A retired nsec-shaped key has lived in remote history
since 647865d2a936 ("RadioLib integration...", 2026-05-20), so the
over-scanning hook re-matched it on every legitimate push and forced
`git push --no-verify`.

Contract under test (the hook MUST):

1. Scan ONLY what the push introduces (the unpushed range), never full
   history: a push whose range contains no new secret-shaped content must
   pass even though remote history already carries a retired key.
2. Still catch NEW secrets: an unpushed commit that ADDS secret-shaped
   content must block the push.
3. Ref creation (remote_sha all zeros): fall back to the new-commit set —
   commits reachable from the local ref that are not on any
   remote-tracking ref — never the entire local history.
4. Only ADDED lines are judged: a scrub commit that REMOVES a secret line
   passes.
5. No remote-tracking refs at all: scan the full commit set reachable from
   the pushed ref (a first-push leak still blocks).

Every fixture secret is a synthetic, obviously-fake literal built at
runtime by string concatenation (never a real key, and never a contiguous
pattern match in this file's own source, so committing this test cannot
trip the repo's pre-commit gate).

Run: python3 -m pytest tests/test_pre_push_hook.py -v -m "not hardware"
Set HOOK_UNDER_TEST=<path> to exercise a different hook copy (used once to
capture RED evidence against the pre-fix hooks; the suite default is this
repo's own .githooks/pre-push).
"""

import os
import subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(REPO_ROOT, ".githooks", "pre-push")

# --- synthetic secret material (fake, runtime-constructed) -----------------
# Retired nsec-shaped literal standing in for the leaked key that has lived
# in remote history since 647865d2a936. bech32 shape, not a real key.
OLD_REMOTE_NSEC = "nsec1" + "old" + "q" * 60
# A freshly leaked key planted inside the unpushed range.
PLANTED_NSEC = "nsec1" + "fresh" + "leak" + "q" * 60
# A synthetic bearer token for the second pattern.
PLANTED_BEARER = "Bea" + "rer " + "abcdefgh" + "0123456789" + "xyz"

PATTERNS = "\n".join(
    [
        "# secret patterns (test fixture)",
        "nsec1[a-z0-9]{20,}",
        "Bearer [A-Za-z0-9\\-._~+/]{20,}",
        "",
    ]
)

GIT_AUTHOR = ["-c", "user.name=t", "-c", "user.email=t@t"]


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(content)


def _sh(*args, cwd, check=True):
    return subprocess.run(
        args,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _git(repo, *args, check=True):
    return _sh("git", *args, cwd=repo, check=check)


def run_hook(repo, ref_lines, hook=None):
    """Invoke the pre-push hook the way git does: stdin = ref lines.

    ref_lines: "<local_ref> <local_sha> <remote_ref> <remote_sha>" strings.
    """
    hook = hook or os.environ.get("HOOK_UNDER_TEST") or HOOK
    stdin_payload = "".join(f"{line}\n" for line in ref_lines)
    return subprocess.run(
        [os.path.abspath(hook)],
        cwd=repo,
        input=stdin_payload,
        capture_output=True,
        text=True,
        timeout=120,
    )


class ScratchRepo:
    """A tiny repo emulating the balloon-fresh topology.

    - an initial commit carrying OLD_REMOTE_NSEC (the key that landed in
      remote history at 647865d2a936 and stays there),
    - a remote-tracking ref (origin/main) at that base,
    - local unpushed commits on top.
    """

    def __init__(self, base_dir, remote_has_secret=True, upstream=True):
        self.base_dir = str(base_dir)
        self.repo = os.path.join(self.base_dir, "repo")
        os.makedirs(self.repo, exist_ok=True)
        self.upstream = upstream
        self._build(remote_has_secret=remote_has_secret, upstream=upstream)

    def _commit(self, msg):
        _git(self.repo, "add", "-A")
        _git(self.repo, *GIT_AUTHOR, "commit", "-q", "-m", msg)

    def _build(self, remote_has_secret, upstream):
        _git(self.repo, "init", "-q", "-b", "main")
        # Hermetic isolation: point the scratch repo at its own (empty) hook
        # dir so the MACHINE's global hooksPath cannot refuse the synthetic
        # fixture commits below (they contain fake secrets BY DESIGN). The
        # hook under test is invoked directly, never via git, so this does
        # not weaken anything under test.
        os.makedirs(os.path.join(self.repo, ".githooks-fixture"), exist_ok=True)
        _git(self.repo, "config", "core.hooksPath", ".githooks-fixture")
        _write(os.path.join(self.repo, ".secret-patterns.txt"), PATTERNS)
        if remote_has_secret:
            # Root-level on purpose: this is the incident shape (the retired
            # key living in remote history since 647865d, in a file every
            # scanner sees). Over-scanning hooks re-match it on every push.
            _write(
                os.path.join(self.repo, "legacy_remote_material.md"),
                f"# legacy note\n\nretired key: {OLD_REMOTE_NSEC}\n",
            )
        self._commit("initial")
        self.base_sha = self.head()

        if upstream:
            # a dummy remote makes refs/remotes/origin/main a genuine
            # remote-tracking ref; the dummy path never needs to exist
            _git(self.repo, "remote", "add", "origin", os.path.join(self.base_dir, "remote-dummy.git"))
            _git(self.repo, "update-ref", "refs/remotes/origin/main", self.base_sha)

        _write(os.path.join(self.repo, "readme.md"), "# scratch\n")
        self._commit("add readme")

    def head(self):
        return _git(self.repo, "rev-parse", "HEAD").stdout.strip()

    def upstream_sha(self):
        return _git(self.repo, "rev-parse", "refs/remotes/origin/main").stdout.strip()

    def plant(self, filename, content, msg="plant"):
        """Add an unpushed commit containing the given secret material.

        filename may contain directories (created on demand) so fixtures
        can live BELOW the repo root — the hook must scan recursively.
        """
        full = os.path.join(self.repo, filename)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        _write(full, content)
        self._commit(msg)
        return self.head()


def _ref(local_ref, local_sha, remote_ref, remote_sha):
    return f"{local_ref} {local_sha} {remote_ref} {remote_sha}"


# ---------------------------------------------------------------------------
# Contract 2 — new secrets in the unpushed range MUST block.
# ---------------------------------------------------------------------------


def test_planted_unpushed_secret_blocks_push(tmp_path):
    """A planted fake nsec inside the unpushed range trips the gate."""
    scratch = ScratchRepo(tmp_path)
    scratch.plant(
        "leak.md",
        f"# config\n\nsk: {PLANTED_NSEC}\n",
        msg="accidentally add a fresh key",
    )
    ref = _ref("refs/heads/main", scratch.head(), "refs/heads/main", scratch.upstream_sha())
    proc = run_hook(scratch.repo, [ref])
    assert proc.returncode != 0, (
        f"hook must FAIL (catch) an unpushed planted nsec: "
        f"rc={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )


def test_planted_bearer_token_blocks_push(tmp_path):
    """A planted bearer token inside the unpushed range trips the gate."""
    scratch = ScratchRepo(tmp_path)
    scratch.plant(
        "leak.md",
        f"# auth\n\ntoken: {PLANTED_BEARER}\n",
        msg="accidentally add a fresh token",
    )
    ref = _ref("refs/heads/main", scratch.head(), "refs/heads/main", scratch.upstream_sha())
    proc = run_hook(scratch.repo, [ref])
    assert proc.returncode != 0, (
        f"hook must FAIL (catch) an unpushed planted bearer token: "
        f"rc={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )


def test_planted_secret_in_subdirectory_blocks_push(tmp_path):
    """A secret planted in a nested path (not repo root) must be caught.

    Pins recursive scan coverage: the old hook's unquoted SCAN_PATHS glob
    expanded against the cwd, so files below the repo root were never
    actually scanned.
    """
    scratch = ScratchRepo(tmp_path)
    scratch.plant(
        "docs/deep/nested/leak.md",
        f"# config\n\nsk: {PLANTED_NSEC}\n",
        msg="leak in a nested directory",
    )
    ref = _ref("refs/heads/main", scratch.head(), "refs/heads/main", scratch.upstream_sha())
    proc = run_hook(scratch.repo, [ref])
    assert proc.returncode != 0, (
        f"hook must FAIL (catch) an unpushed planted nsec in a nested dir: "
        f"rc={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )


def test_multi_ref_push_with_one_leaky_range_blocks(tmp_path):
    """A push of several refs blocks if ANY one range adds a secret."""
    scratch = ScratchRepo(tmp_path)
    _git(scratch.repo, "checkout", "-q", "-b", "clean")
    _write(os.path.join(scratch.repo, "docs", "clean_doc.md"), "# clean\n")
    scratch._commit("clean change on side branch")
    clean_sha = _git(scratch.repo, "rev-parse", "clean").stdout.strip()
    _git(scratch.repo, "checkout", "-q", "main")
    scratch.plant(
        "docs/leak.md",
        f"sk: {PLANTED_NSEC}\n",
        msg="leaky change on main",
    )
    refs = [
        _ref("refs/heads/clean", clean_sha, "refs/heads/clean", "0" * 40),
        _ref("refs/heads/main", scratch.head(), "refs/heads/main", scratch.upstream_sha()),
    ]
    proc = run_hook(scratch.repo, refs)
    assert proc.returncode != 0, (
        f"a multi-ref push where one range is leaky must fail: "
        f"rc={proc.returncode} stdout={proc.stdout!r}"
    )


# ---------------------------------------------------------------------------
# Contract 1 — pre-existing remote-history secrets must NOT block.
# ---------------------------------------------------------------------------


def test_known_remote_secret_does_not_block_push(tmp_path):
    """The incident shape: remote history already carries the retired key.

    The unpushed range contains no new secret — only the README commit —
    so the push must pass even though the retired literal is in the repo's
    (remote) history.
    """
    scratch = ScratchRepo(tmp_path)
    ref = _ref("refs/heads/main", scratch.head(), "refs/heads/main", scratch.upstream_sha())
    proc = run_hook(scratch.repo, [ref])
    assert proc.returncode == 0, (
        f"hook must PASS when the only secret is already on the remote: "
        f"rc={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )


def test_scrub_commit_removing_secret_passes(tmp_path):
    """A commit REMOVING the old literal (the scrub) must not be blocked."""
    scratch = ScratchRepo(tmp_path)
    path = os.path.join(scratch.repo, "legacy_remote_material.md")
    current = open(path).read()
    _write(path, "# legacy note\n\nretired key: [REDACTED]\n")
    scratch._commit("scrub the old key from the tip")
    ref = _ref("refs/heads/main", scratch.head(), "refs/heads/main", scratch.upstream_sha())
    proc = run_hook(scratch.repo, [ref])
    assert proc.returncode == 0, (
        f"a scrub commit that REMOVES the retired key must pass: "
        f"rc={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )


def test_noop_push_range_passes(tmp_path):
    """remote_sha == local_sha: nothing new is being pushed."""
    scratch = ScratchRepo(tmp_path)
    head = scratch.head()
    ref = _ref("refs/heads/main", head, "refs/heads/main", head)
    proc = run_hook(scratch.repo, [ref])
    assert proc.returncode == 0, (
        f"an empty push range must pass: rc={proc.returncode} stdout={proc.stdout!r}"
    )


def test_deleted_remote_ref_push_passes(tmp_path):
    """Deleting a remote ref (local_sha all zeros) introduces nothing."""
    scratch = ScratchRepo(tmp_path)
    ref = _ref("refs/heads/main", "0" * 40, "refs/heads/main", scratch.upstream_sha())
    proc = run_hook(scratch.repo, [ref])
    assert proc.returncode == 0, (
        f"a ref deletion push must pass: rc={proc.returncode} stdout={proc.stdout!r}"
    )


# ---------------------------------------------------------------------------
# Contract 3 — first push of a new ref (remote_sha all zeros).
# ---------------------------------------------------------------------------


def test_first_push_new_branch_catches_new_secret(tmp_path):
    """Ref creation carrying a fresh secret must still block."""
    scratch = ScratchRepo(tmp_path)
    _git(scratch.repo, "checkout", "-q", "-b", "feature")
    scratch.plant(
        "feature_leak.md",
        f"token: {PLANTED_BEARER}\n",
        msg="feature branch adds a token",
    )
    ref = _ref("refs/heads/feature", scratch.head(), "refs/heads/feature", "0" * 40)
    proc = run_hook(scratch.repo, [ref])
    assert proc.returncode != 0, (
        f"first push of a new branch carrying a fresh secret must fail: "
        f"rc={proc.returncode} stdout={proc.stdout!r}"
    )


def test_first_push_new_branch_ignores_remote_history(tmp_path):
    """Ref creation whose new commits are clean must pass.

    The branch's base commit carries the retired literal, but that commit
    is already on a remote-tracking ref, so the fallback new-commit set
    (local ref, minus everything on any remote-tracking ref) must not
    include it — never the entire history.
    """
    scratch = ScratchRepo(tmp_path)
    _git(scratch.repo, "checkout", "-q", "-b", "feature")
    _write(os.path.join(scratch.repo, "feature_doc.md"), "# clean feature\n")
    scratch._commit("clean feature commit")
    ref = _ref("refs/heads/feature", scratch.head(), "refs/heads/feature", "0" * 40)
    proc = run_hook(scratch.repo, [ref])
    assert proc.returncode == 0, (
        f"first push of a clean new branch must not rescan remote history: "
        f"rc={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )


# ---------------------------------------------------------------------------
# Contract 5 — no remote-tracking refs at all (bare first push).
# ---------------------------------------------------------------------------


def test_no_remotes_at_all_still_catches_new_secret(tmp_path):
    """No remotes: the fallback must still scan the full new-commit set."""
    scratch = ScratchRepo(tmp_path, upstream=False)
    scratch.plant(
        "fresh_leak.md",
        f"key = {PLANTED_NSEC}\n",
        msg="first ever push includes a leak",
    )
    ref = _ref("refs/heads/main", scratch.head(), "refs/heads/main", "0" * 40)
    proc = run_hook(scratch.repo, [ref])
    assert proc.returncode != 0, (
        f"first push with no remotes at all must still catch a new secret: "
        f"rc={proc.returncode} stdout={proc.stdout!r}"
    )


def test_no_remotes_at_all_clean_passes(tmp_path):
    """No remotes + no secret anywhere: first push passes clean."""
    scratch = ScratchRepo(tmp_path, remote_has_secret=False, upstream=False)
    ref = _ref("refs/heads/main", scratch.head(), "refs/heads/main", "0" * 40)
    proc = run_hook(scratch.repo, [ref])
    assert proc.returncode == 0, (
        f"clean first push must pass: rc={proc.returncode} stdout={proc.stdout!r}"
    )


def test_no_remotes_at_all_initial_secret_blocks(tmp_path):
    """Degenerate no-remote case: every commit reachable from the pushed
    ref is 'new', so the initial commit's retired literal must block.

    This pins the fallback semantics (scan the full new-commit set, which
    with no remotes is the branch's whole history). The real repo always
    has remote-tracking refs, so the incident shape is covered by
    test_known_remote_secret_does_not_block_push instead.
    """
    scratch = ScratchRepo(tmp_path, remote_has_secret=True, upstream=False)
    ref = _ref("refs/heads/main", scratch.head(), "refs/heads/main", "0" * 40)
    proc = run_hook(scratch.repo, [ref])
    assert proc.returncode != 0, (
        "with no remote-tracking refs the initial commit's secret is in the "
        f"new-commit set and must block: rc={proc.returncode} stdout={proc.stdout!r}"
    )
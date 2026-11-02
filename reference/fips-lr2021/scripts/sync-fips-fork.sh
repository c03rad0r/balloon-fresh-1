#!/usr/bin/env bash
# Fast-forward the fork mirror, rebase the transport branch, test, and pin.
# Upstream is fetch-only. No PR is opened against jmcorgan/fips.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"
repo="${FIPS_DIR:-$HOME/repos/fips-fork}"
branch="${FIPS_BRANCH:-balloon-lr2021}"
pin="$root/fips/fips-pin.txt"
patch="$root/fips/patches/0001-lr2021-transport.patch"

if [ ! -d "$repo/.git" ]; then
  echo "not a git repo: $repo (set FIPS_DIR)" >&2
  exit 1
fi
cd "$repo"

git remote get-url upstream >/dev/null 2>&1 || \
  git remote add upstream https://github.com/jmcorgan/fips.git

echo "== fetching upstream (read-only)"
git fetch upstream master
git fetch origin "$branch" 2>/dev/null || true

echo "== syncing fork master"
git checkout master
git merge --ff-only upstream/master
git push origin master

echo "== rebasing $branch"
git checkout "$branch"
if ! git rebase master; then
  echo "rebase conflict: resolve on a sync/YYYYMMDD branch; event pin untouched" >&2
  git rebase --abort || true
  exit 1
fi

echo "== host tests"
cargo test -p fips-lr2021
cargo check -p fips-mesh
cargo build -p fips-lr2021 --bins

echo "== updating vendored patch and pin"
git diff upstream/master..HEAD > "$patch"
commit="$(git rev-parse HEAD)"
base="$(git rev-parse upstream/master)"
cat > "$pin" <<EOF
fork:          $(git remote get-url origin)
branch:        $branch
upstream_base: $base
fork_commit:   $commit
event_tag:     event-2026-11
last_sync:     $(date -u +%Y-%m-%dT%H:%M:%SZ)
sync_script:   scripts/sync-fips-fork.sh
EOF

echo "== pushing to fork only"
git push --force-with-lease origin "$branch"
git tag -f event-2026-11
git push -f origin event-2026-11

echo "synced $branch to $commit (upstream base $base)"
echo "pin: $pin"
echo "patch: $patch"

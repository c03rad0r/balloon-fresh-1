#!/usr/bin/env bash
# Clone the pinned FIPS fork and check out the event commit.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"
pin="$root/fips/fips-pin.txt"
dest="${FIPS_DIR:-$root/build/fips}"

fork="$(awk '/^fork:/{print $2}' "$pin")"
commit="$(awk '/^fork_commit:/{print $2}' "$pin")"
branch="$(awk '/^branch:/{print $2}' "$pin")"

if [ -z "${fork:-}" ] || [ -z "${commit:-}" ]; then
  echo "cannot read fork/commit from $pin" >&2
  exit 1
fi

mkdir -p "$(dirname "$dest")"
if [ ! -d "$dest/.git" ]; then
  git clone "$fork" "$dest"
fi

cd "$dest"
git fetch origin "$branch" --tags
git checkout "$commit"
echo "FIPS_DIR=$dest"
echo "fork=$fork branch=$branch commit=$commit"

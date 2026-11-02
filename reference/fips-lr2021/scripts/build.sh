#!/usr/bin/env bash
# Build the patched FIPS binaries and the host tools.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"
fips="${FIPS_DIR:-$root/build/fips}"

if [ ! -d "$fips/.git" ]; then
  "$here/bootstrap-fips.sh"
fi

cd "$fips"
cargo build --release -p fips-lr2021 --bins
cargo build --release -p fips-mesh

echo "binaries:"
ls -1 "$fips/target/release/fips" \
      "$fips/target/release/fips-lr2021d" \
      "$fips/target/release/fips-lr2021ctl" 2>/dev/null || true

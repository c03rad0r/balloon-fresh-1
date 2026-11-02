#!/usr/bin/env bash
# Run the host-side test suite for the pinned fork.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"
fips="${FIPS_DIR:-$root/build/fips}"

if [ ! -d "$fips/.git" ]; then
  "$here/bootstrap-fips.sh"
fi

cd "$fips"
cargo test -p fips-lr2021
cargo test -p fips-mesh lr2021_transport_parses --lib
cargo check -p fips-mesh
cargo build -p fips-lr2021 --bins

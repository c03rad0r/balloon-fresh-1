#!/usr/bin/env bash
# Configure a third bridge as a transparent relay.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"
band="${BAND:-us915}"
relay="${SERIAL_RELAY:-/dev/ttyACM2}"
fips="${FIPS_DIR:-$root/build/fips}"
ctl="$fips/target/release/fips-lr2021ctl"

if [ ! -x "$ctl" ]; then
  "$here/build.sh"
fi

echo "== configuring relay ($relay) for $band"
"$ctl" --serial "$relay" cfg --band "$band" --relay
"$ctl" --serial "$relay" status

cat <<EOF

Relay is transparent. Run demo-2node.sh for the ground ends, then compare
direct vs relayed at the same positions. Record the result in docs/RESULTS.md.
EOF

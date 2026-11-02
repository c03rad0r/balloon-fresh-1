#!/usr/bin/env bash
# Run repeated PER bursts and log delivery, RSSI and bridge counters.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../.." && pwd)"
fips="${FIPS_DIR:-$root/build/fips}"
ctl="$fips/target/release/fips-lr2021ctl"
band="${BAND:-us915}"
a="${SERIAL_A:-/dev/ttyACM0}"
b="${SERIAL_B:-/dev/ttyACM1}"
seconds="${1:-600}"
out="${2:-$root/docs/soak-$(date -u +%Y%m%dT%H%M%SZ).log}"

[ -x "$ctl" ] || "$root/scripts/build.sh"

end=$((SECONDS + seconds))
{
  echo "# soak band=$band start=$(date -u +%FT%TZ)"
  while [ "$SECONDS" -lt "$end" ]; do
    "$ctl" --serial "$a" status || true
    "$ctl" --serial "$b" status || true
    "$root/tests/hardware/per.sh" 20 64 || true
    sleep 10
  done
  echo "# soak end=$(date -u +%FT%TZ)"
} | tee "$out"

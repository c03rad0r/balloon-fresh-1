#!/usr/bin/env bash
# Same-host PER: B runs the link responder, A sends. For two machines, run the
# echo command on B yourself and the per command on A.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../.." && pwd)"
fips="${FIPS_DIR:-$root/build/fips}"
ctl="$fips/target/release/fips-lr2021ctl"
band="${BAND:-us915}"
a="${SERIAL_A:-/dev/ttyACM0}"
b="${SERIAL_B:-/dev/ttyACM1}"
count="${1:-100}"
size="${2:-64}"

[ -x "$ctl" ] || "$root/scripts/build.sh"

"$ctl" --serial "$b" echo --band "$band" --seconds "$((count / 2 + 10))" >/tmp/fips-lr2021-echo.log 2>&1 &
echo_pid=$!
trap 'kill "$echo_pid" 2>/dev/null || true' EXIT
sleep 1

"$ctl" --serial "$a" cfg --band "$band"
"$ctl" --serial "$a" per --band "$band" --count "$count" --size "$size" --peer-id 2
wait "$echo_pid" || true
cat /tmp/fips-lr2021-echo.log

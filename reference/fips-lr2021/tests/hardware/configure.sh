#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/../.." && pwd)"
fips="${FIPS_DIR:-$root/build/fips}"
ctl="$fips/target/release/fips-lr2021ctl"
band="${BAND:-us915}"
a="${SERIAL_A:-/dev/ttyACM0}"
b="${SERIAL_B:-/dev/ttyACM1}"

[ -x "$ctl" ] || "$root/scripts/build.sh"
"$ctl" --serial "$a" cfg --band "$band"
"$ctl" --serial "$b" cfg --band "$band"
"$ctl" --serial "$a" hello
"$ctl" --serial "$b" hello
"$ctl" --serial "$a" status
"$ctl" --serial "$b" status

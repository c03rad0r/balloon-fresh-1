#!/usr/bin/env bash
# E80 STM32 bridge setup for two machines. Run the cfg block on each machine's
# own bridge, then start FIPS with the e80-us915-node-a/b configs.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"
fips="${FIPS_DIR:-$root/build/fips}"
ctl="$fips/target/release/fips-lr2021ctl"
serial="${SERIAL:-/dev/ttyUSB6}"
band="${BAND:-us915}"

[ -x "$ctl" ] || "$here/build.sh"

"$ctl" --serial "$serial" --baud 115200 bridge
"$ctl" --serial "$serial" --baud 115200 hello
"$ctl" --serial "$serial" --baud 115200 cfg --band "$band"
"$ctl" --serial "$serial" --baud 115200 status

cat <<EOF

Configured $serial for $band at 115200.
Start FIPS with:
  $fips/target/release/fips --config $root/fips/configs/e80-us915-node-a.yaml
(or -b on the second machine). Then ping6/iperf3 between the FIPS addresses.
EOF

#!/usr/bin/env bash
# Configure two local bridges and print the two-node FIPS commands.
# For two machines, run the same cfg command on each side.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"
band="${BAND:-us915}"
a="${SERIAL_A:-/dev/ttyACM0}"
b="${SERIAL_B:-/dev/ttyACM1}"
fips="${FIPS_DIR:-$root/build/fips}"
ctl="$fips/target/release/fips-lr2021ctl"

if [ ! -x "$ctl" ]; then
  "$here/build.sh"
fi

echo "== configuring A ($a) and B ($b) for $band"
"$ctl" --serial "$a" cfg --band "$band"
"$ctl" --serial "$b" cfg --band "$band"
"$ctl" --serial "$a" status
"$ctl" --serial "$b" status

cat <<EOF

== next
On machine A:
  $fips/target/release/fips --config $root/fips/configs/us915-node-a.yaml

On machine B:
  $fips/target/release/fips --config $root/fips/configs/us915-node-b.yaml

Then:
  ping6 -I fips0 <peer-address>
  iperf3 -u -c <peer-address> -b 100k -t 10

For the stock-FIPS fallback, run on each machine:
  $fips/target/release/fips-lr2021d --serial $a --band $band --udp-bind 127.0.0.1:2122
EOF

#!/usr/bin/env bash
# Flash the RP2040 bridge. Requires the PlatformIO RP2040 core and BOOTSEL.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"
port="${1:-${PORT:-}}"

if ! command -v pio >/dev/null 2>&1; then
  echo "pio not found; install PlatformIO or pre-flash on the bench host" >&2
  exit 1
fi

args=(run -d "$root/firmware/rp2040-bridge" -e rp2040-bridge -t upload)
if [ -n "$port" ]; then
  args+=(--upload-port "$port")
fi
pio "${args[@]}"

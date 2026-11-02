#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$unit_dir"
cp "$here/fips-fork-sync.service" "$here/fips-fork-sync.timer" "$unit_dir/"
systemctl --user daemon-reload
systemctl --user enable --now fips-fork-sync.timer
echo "installed fips-fork-sync.timer; logs: journalctl --user -u fips-fork-sync"

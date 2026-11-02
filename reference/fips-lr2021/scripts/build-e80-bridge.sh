#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"
repo="$(cd "$root/../.." && pwd)"
make -C "$repo/firmware/e80-stm32-bench" firmware
ls -l "$repo/firmware/e80-stm32-bench/build-fw/e80_bench"

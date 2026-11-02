#!/usr/bin/env bash
# Flash the E80 STM32 bridge via CMSIS-DAP. Set PROBE to the probe serial.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"
repo="$(cd "$root/../.." && pwd)"
probe="${PROBE:-}"
elf="${ELF:-$repo/firmware/e80-stm32-bench/build-fw/e80_bench}"

if [ -z "$probe" ]; then
  echo "set PROBE to the CMSIS-DAP serial (e.g. 203584200D2D0D42)" >&2
  exit 1
fi
if [ ! -f "$elf" ]; then
  "$here/build-e80-bridge.sh"
fi

openocd -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg \
  -c "adapter speed 100; cmsis_dap_serial $probe; reset_config none separate; init; program $elf verify reset exit"

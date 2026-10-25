#!/usr/bin/env bash
# Rebuild + route the wing interconnect board in ONE command.
#
# WHY THIS EXISTS
# ---------------
# The generator is a pure function of its spec, so running it WIPES all copper. Routing is
# therefore a second, separate step. That split bit twice during development: a mutation
# test that re-ran the generator left the board with 6 unconnected items and the gate suite
# went red for a reason unrelated to the mutation being tested. Anyone regenerating the
# board by hand hits the same trap.
#
# `pcbnew` lives in the distro python's site-packages (see docs/fab/KICAD-PYTHON-ENV.md),
# so the router runs under /usr/bin/python3, not the venv interpreter.
#
# Usage:  bash tracker/hardware/rebuild_wing_interconnect.sh [--check]
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
BOARD="$HERE/wing_interconnect/wing_interconnect_v1.kicad_pcb"
PY=/usr/bin/python3

if [[ "${1:-}" == "--check" ]]; then
    python3 "$HERE/build_wing_footprints.py" --check
    python3 "$HERE/build_wing_interconnect.py" --out /tmp/_wing_check.kicad_pcb >/dev/null
    echo "ok: footprints + generator are deterministic"
    exit 0
fi

echo "== 1/3 footprints =="
python3 "$HERE/build_wing_footprints.py" >/dev/null

echo "== 2/3 generator (wipes copper by design) =="
python3 "$HERE/build_wing_interconnect.py" | tail -2

echo "== 3/3 route the two multi-pad nets =="
# SOLAR_P and SOLAR_N are emitted as deterministic straight geometry by the generator
# itself (they are collinear pad pairs). Only the two MID nets need the A* router, and it
# cannot solve all four at once on a board this size -- measured, 2 of 4 in every ordering.
"$PY" "$HERE/route_v10_astar.py" --board "$BOARD" --expect-footprints 7 \
      --append --nets SOLAR_MID1,SOLAR_MID2 | tail -3

echo "== verify =="
cd "$REPO"
kicad-cli pcb drc "$BOARD" 2>&1 | grep -E "violations|unconnected"
"$PY" -c "
import pcbnew
b = pcbnew.LoadBoard('$BOARD')
b.BuildConnectivity()
n = b.GetConnectivity().GetUnconnectedCount(False)
print('unrouted:', n)
raise SystemExit(0 if n == 0 else 1)
"

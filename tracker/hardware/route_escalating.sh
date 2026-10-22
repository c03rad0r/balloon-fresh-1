#!/bin/bash
# Escalating-resolution route (B36): coarse pass first, then retry ONLY the failures on a
# finer grid.
#
# Why: measured 2026-10-22 -- a full route at pitch 0.05 does not finish (700s timeout, no
# output), because EVERY net pays the 4x cell cost even when it would route trivially at 0.1.
# But the finer grid genuinely recovers nets the coarse one cannot (SPI2 trio: 1/3 at 0.10,
# 2/3 at 0.05). So: use 0.05 only where it is needed.
#
# Uses the router's --append mode: the coarse pass writes its copper, then the fine pass
# routes the failures onto that board, treating the existing copper as obstacles AND as
# routed copper for the isolation self-check.
set -u
WT=/home/c08r4d0r/worktrees/master-check
PY=/home/c08r4d0r/venvs/kicad/bin/python
cd "$WT" || exit 1

echo "=== pass 1: build + route at pitch 0.10"
"$PY" tracker/hardware/build_hub_board_v10.py >/dev/null 2>&1 || { echo "BUILD FAILED"; exit 1; }
"$PY" tracker/hardware/route_v10_astar.py --max-expansions 2000000 > /tmp/esc_p1.log 2>&1
echo "pass1 exit=$?"
grep -E '^routed|^failed' /tmp/esc_p1.log | cut -c1-400

# extract the failed net names from the printed list
FAILED=$("$PY" - <<'EOF'
import re
txt = open('/tmp/esc_p1.log').read()
m = re.search(r"^failed \d+: \[(.*)\]", txt, re.M)
if not m:
    print("")
else:
    names = re.findall(r"\('([^']+)'", m.group(1))
    print(",".join(names))
EOF
)
COUNT=$(echo "$FAILED" | tr ',' '\n' | grep -c . || true)
echo "=== pass 2: retry $COUNT failure(s) at pitch 0.05 (append mode)"
if [ "$COUNT" -eq 0 ]; then
  echo "nothing to retry"
else
  "$PY" tracker/hardware/route_v10_astar.py --append --pitch 0.05 --max-expansions 5000000 \
      --nets "$FAILED" > /tmp/esc_p2.log 2>&1
  echo "pass2 exit=$?"
  grep -E '^routed|^failed|^APPEND' /tmp/esc_p2.log | cut -c1-400
fi

echo "=== gates"
for g in check_lane_clearance check_lane_integrity check_copper_under_body check_lane_isolation \
         check_lane_vs_pad_layer check_cross_side_collision check_hole_clearance check_board_geometry; do
  out=$("$PY" "tracker/hardware/$g.py" --board tracker/hardware/hub_board_v10.kicad_pcb 2>/dev/null | tail -1)
  echo "$g EXIT=$? :: $out"
done
echo "=== tracks/vias"
"$PY" - <<'EOF' 2>/dev/null
import pcbnew
b = pcbnew.LoadBoard("tracker/hardware/hub_board_v10.kicad_pcb")
print("tracks", len([t for t in b.GetTracks() if "TRACK" in str(type(t))]),
      "vias", len([t for t in b.GetTracks() if "VIA" in str(type(t))]))
EOF
echo DONE

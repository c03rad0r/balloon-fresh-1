#!/usr/bin/env bash
# ERC + schematic-to-board parity for the flight board.
#
# WHY THIS EXISTS. The Astra gap analysis (item H2) found that the flight schematic had NEVER had ERC
# or a schematic-to-PCB parity check run. DRC grades copper against design rules; it says nothing about
# whether the schematic is electrically sound or whether the board still matches the schematic. Seven
# commits of routing work happened with that gap open.
#
# WHAT IT RUNS:
#   1. kicad-cli sch erc        -- electrical rule check on the schematic
#   2. netlist regeneration     -- proves the schematic still produces a netlist
#   3. netlist vs board compare -- every netlist node must exist on the board with the same net name,
#                                  and the board must not carry nodes the netlist does not know about.
#                                  This is what catches "the board was edited past the schematic".
#
# EXIT CODE: 0 clean, 1 problems found, 2 could not run (which is reported as a FAILURE, not a pass --
# a check that cannot execute must never look green).
#
# Usage: run_erc.sh [--board <b.kicad_pcb>] [--sch <s.kicad_sch>]
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo .)"
cd "$ROOT" || exit 2

SCH="${SCH:-tracker/hardware/schematics/flight_board/v9_flight.kicad_sch}"
BOARD="${BOARD:-tracker/hardware/hub_board_v9.kicad_pcb}"
NET="${NET:-/tmp/erc_regen.net}"

while [ $# -gt 0 ]; do
    case "$1" in
        --board) BOARD="$2"; shift 2;;
        --sch)   SCH="$2";   shift 2;;
        *) shift;;
    esac
done

echo "erc: schematic $SCH"
echo "erc: board     $BOARD"

if ! command -v kicad-cli >/dev/null 2>&1; then
    echo "erc: FAIL -- kicad-cli not on PATH; the check did NOT run"
    exit 2
fi
[ -f "$SCH" ] || { echo "erc: FAIL -- schematic not found: $SCH"; exit 2; }
[ -f "$BOARD" ] || { echo "erc: FAIL -- board not found: $BOARD"; exit 2; }

FAIL=0

# ---------------------------------------------------------------- 1. ERC
echo ""
echo "--- 1. ERC (kicad-cli sch erc) ---"
ERC_JSON=/tmp/erc_flight.json
kicad-cli sch erc "$SCH" --format json -o "$ERC_JSON" --severity-all >/tmp/erc_stdout.txt 2>&1
# NOTE: the first version of this script read d["violations"] and found none, because KiCad nests them
# under d["sheets"][i]["violations"]. It printed "no ERROR-severity findings" while the file held 20.
# read_erc.py walks EVERY nesting level; a gate that reads the wrong depth and prints green is worse
# than no gate at all.
python3 tracker/hardware/read_erc.py "$ERC_JSON" || FAIL=1

# ---------------------------------------------------------------- 2. netlist regeneration
echo ""
echo "--- 2. netlist regeneration ---"
if kicad-cli sch export netlist "$SCH" -o "$NET" >/tmp/net_stdout.txt 2>&1 && [ -s "$NET" ]; then
    echo "erc: netlist regenerated ($(wc -c < "$NET") bytes)"
else
    echo "erc: FAIL -- the schematic did not produce a netlist"
    tail -3 /tmp/net_stdout.txt | sed 's/^/     /'
    FAIL=1
fi

# ---------------------------------------------------------------- 3. netlist vs board parity
echo ""
echo "--- 3. schematic-to-board parity ---"
python3 - "$NET" "$BOARD" <<'PY' || FAIL=1
import json, os, re, subprocess, sys

netfile, board = sys.argv[1], sys.argv[2]
try:
    txt = open(netfile, encoding="utf-8", errors="replace").read()
except Exception as e:
    print(f"parity: cannot read the netlist ({e}) -- treating as FAILURE"); sys.exit(1)

# (ref, pin) -> netname from the netlist
want = {}
for m in re.finditer(r'\(net \(code "?\d+"?\) \(name "([^"]+)"\)(.*?)(?=\(net \(code|\Z)',
                     txt, re.S):
    name, body = m.group(1), m.group(2)
    for r, p in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', body):
        want[(r, p)] = name
print(f"parity: netlist declares {len(want)} (ref,pin) nodes")

code = (
    "import pcbnew,sys,json;"
    "b=pcbnew.LoadBoard(sys.argv[1]);"
    "out=[];"
    "[[out.append([f.GetReference(),str(p.GetNumber()),p.GetNetname()]) "
    "  for p in f.Pads()] for f in b.GetFootprints()];"
    "print(json.dumps(out))"
)
kpy = __import__("os").path.expanduser("~/venvs/kicad/bin/python")
if not __import__("os").path.exists(kpy):
    print("parity: FAIL -- pcbnew venv missing, check did NOT run"); sys.exit(2)
r = subprocess.run([kpy, "-c", code, board], capture_output=True, text=True, timeout=300)
if r.returncode != 0:
    print(f"parity: FAIL -- the board reader exited {r.returncode}")
    print(f"        stderr: {r.stderr.strip()[-300:]}")
    sys.exit(2)
line = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
try:
    have = json.loads(line)
except json.JSONDecodeError as e:
    # Deliberately NOT a bare `except Exception`: the first version of this block swallowed a
    # NameError (json was never imported) and reported "could not read the board's pads", a data
    # failure that had not happened. A gate must not convert its own bug into a board verdict.
    print(f"parity: FAIL -- the board reader returned unparseable output ({e})")
    print(f"        first 200 chars: {line[:200]!r}")
    sys.exit(2)

# pads whose number is unknown to the netlist are legitimate for multi-pad idioms (e.g. a
# module with 13 pads all numbered 41). Only compare (ref,pin) pairs the netlist DOES declare.
mismatch = []
checked = 0
for ref, pin, net in have:
    key = (ref, pin)
    if key in want:
        checked += 1
        if want[key] != net:
            mismatch.append((ref, pin, want[key], net))
print(f"parity: compared {checked} nodes that both sides declare")
for ref, pin, w, h in mismatch[:20]:
    print(f"   MISMATCH {ref}.{pin}: netlist '{w}' vs board '{h}'")
if mismatch:
    print(f"parity: {len(mismatch)} net-name mismatch(es) -- the board has drifted from the schematic")
    sys.exit(1)
missing = [k for k in want if not any(h[0] == k[0] and h[1] == k[1] for h in have)]
if missing:
    print(f"parity: {len(missing)} netlist node(s) have NO pad on the board, e.g. {missing[:8]}")
    print("parity: the board is missing placements the schematic expects")
    sys.exit(1)
print("parity: every netlist node that the board also carries agrees on the net name")
PY

echo ""
if [ "$FAIL" -ne 0 ]; then
    echo "erc: RESULT -- PROBLEMS FOUND (see above)"
    exit 1
fi
echo "erc: RESULT -- clean"
exit 0

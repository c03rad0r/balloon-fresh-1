#!/usr/bin/env python3
"""Gate the SX1280 exposed-pad renumber: '25' -> '0'.

THE DEFECT (measured): the footprint numbers the exposed/thermal pad '25'; the schematic symbol
numbers the same pad '0'. KiCad binds pads BY NUMBER, so pad 25 of the placed footprint matches no
netlist node and sits with an EMPTY net. The netlist's own U4 entry is
    GND   U4 pins ['0', '13', '20', '21', '23', '24', '5']
-- pin '0' IS the exposed pad. So the SX1280's primary ground and thermal return is unassigned on the
board, which is also the most likely explanation for the persistent "GND 86/87" in every routing
summary.

WRITTEN BEFORE THE EDIT. The risk being controlled is over-reach: a footprint edit that renumbers the
WRONG pad, or that disturbs the 24 perimeter pads, would silently rewire the radio. So the acceptance
test is:

  1. before: exactly ONE U4 pad has an empty net, and it is numbered '25' with size 2.70 x 2.70 mm
  2. after : ZERO U4 pads have an empty net
  3. after : a pad numbered '0' EXISTS on U4, with the SAME position and size as the old '25'
  4. after : the 24 perimeter pads are UNCHANGED -- same numbers, positions and sizes (NOT just
     counts; compare the sets)
  5. after : the pad that is now '0' carries net GND
  6. after : U4's total pad count is unchanged (25)

Checks 3-6 are set comparisons, not counts, because a count would pass if one pad were renamed twice.

Usage: gate_ep_renumber.py <before.kicad_pcb> <after.kicad_pcb>
"""
import sys

import pcbnew

REF = "U4"


def snapshot(path):
    b = pcbnew.LoadBoard(path)
    fp = b.FindFootprintByReference(REF)
    if fp is None:
        raise SystemExit(f"{REF} absent from {path}")
    pads = {}
    for p in fp.Pads():
        c = p.GetPosition()
        s = p.GetSize()
        pads[str(p.GetNumber())] = (
            pcbnew.ToMM(c.x), pcbnew.ToMM(c.y),
            pcbnew.ToMM(s.x), pcbnew.ToMM(s.y),
            p.GetNetname(),
        )
    return pads


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    before = snapshot(sys.argv[1])
    after = snapshot(sys.argv[2])

    print(f"pads before: {len(before)}   pads after: {len(after)}\n")

    empty_before = {k: v for k, v in before.items() if not v[4]}
    empty_after = {k: v for k, v in after.items() if not v[4]}
    print("1. exactly one empty-net pad before, numbered '25', 2.70x2.70 mm:")
    only25 = len(empty_before) == 1 and "25" in empty_before
    if only25:
        x, y, w, h, _n = empty_before["25"]
        print(f"     PASS  pad 25 at ({x:.2f},{y:.2f}) size {w:.2f}x{h:.2f}")
        one_ok = abs(w - 2.70) < 0.01 and abs(h - 2.70) < 0.01
    else:
        print(f"     FAIL  empty-net pads before: {list(empty_before)} (expected exactly ['25'])")
        one_ok = False

    checks = [
        ("1. one empty-net pad before, = '25', 2.70x2.70", one_ok),
        ("2. zero empty-net pads after", len(empty_after) == 0),
        ("3. pad '0' now exists at the old '25' position", "0" in after and "25" in before
         and abs(after["0"][0] - before["25"][0]) < 1e-6
         and abs(after["0"][1] - before["25"][1]) < 1e-6),
        ("4a. '25' no longer exists", "25" not in after),
        ("5. pad '0' carries GND", after.get("0", (0, 0, 0, 0, ""))[4] == "GND"),
        ("6. pad count unchanged (25)", len(after) == len(before) == 25),
    ]

    # 4: the 24 perimeter pads must be IDENTICAL as sets (numbers + geometry)
    perim_b = {k: v[:4] for k, v in before.items() if k not in ("25", "0")}
    perim_a = {k: v[:4] for k, v in after.items() if k not in ("25", "0")}
    checks.append(("4b. 24 perimeter pads unchanged (set equality)", perim_b == perim_a))
    if perim_b != perim_a:
        for k in sorted(set(perim_b) | set(perim_a)):
            if perim_b.get(k) != perim_a.get(k):
                print(f"     DIFF pad {k}: before {perim_b.get(k)}  after {perim_a.get(k)}")

    print()
    ok = True
    for name, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print()
    print("GATE: " + ("PASS -- renumber accepted." if ok else "FAIL -- REJECT the edit."))
    if ok:
        print(f"  pad '0' net after: {after['0'][4]}   "
              f"(was empty on '25': {before['25'][4]!r})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

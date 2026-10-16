#!/usr/bin/env python3
"""Decide, EXACTLY, whether J_W1's duplicate pads are coincident or genuinely different copper.

MY PREVIOUS INSTRUMENT WAS WRONG TWICE. inspect_jw_duplicates.py printed two visually IDENTICAL rows and
labelled them "DIFFERENT -> overlapping copper". Two causes were suspected; one was fixed (LayerSet.FmtHex
returns a buffer that is not stable across calls) and the pad still compared as different.

SO THIS SCRIPT STOPS GUESSING and compares ONLY raw integers taken straight from the SWIG objects --
positions, sizes and drills in KiCad's internal nanometre units, plus the shape enum and the net name.
No floats, no mm conversion, no formatted buffers, nothing whose string form could vary between calls.
If two pads differ, the exact integer that differs will be printed.

Run: ~/venvs/kicad/bin/python compare_jw_pads_exact.py [board]
"""
import collections
import hashlib
import sys

import pcbnew

B = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"


def sig(p):
    """Raw integers only. Nothing here has a string conversion in it."""
    c = p.GetPosition()
    s = p.GetSize()
    d = p.GetDrillSize()
    return (c.x, c.y, s.x, s.y, d.x, d.y, int(p.GetShape()), str(p.GetNetname()))


FIELDS = ("x", "y", "w", "h", "drillx", "drilly", "shape", "net")


def main():
    print(f"board : {B}")
    print(f"sha256: {hashlib.sha256(open(B, 'rb').read()).hexdigest()[:24]}\n")
    b = pcbnew.LoadBoard(B)
    fp = b.FindFootprintByReference("J_W1")
    if fp is None:
        print("J_W1 absent")
        return 1

    pads = list(fp.Pads())
    print(f"J_W1: {len(pads)} pad objects")
    groups = collections.defaultdict(list)
    for p in pads:
        groups[str(p.GetNumber())].append(p)

    print(f"numbers: {sorted(groups)}\n")
    for num in sorted(groups):
        g = groups[num]
        if len(g) < 2:
            continue
        sigs = [sig(p) for p in g]
        uniq = sorted(set(sigs))
        verdict = "IDENTICAL (coincident duplicate)" if len(uniq) == 1 else "DIFFERENT (real overlap)"
        print(f"number {num!r}: {len(g)} objects -> {verdict}")
        for s in uniq:
            print("      " + "  ".join(f"{k}={v}" for k, v in zip(FIELDS, s)))
        if len(uniq) > 1:
            # show exactly WHICH field differs, so the finding is actionable
            for i in range(len(FIELDS)):
                vals = {s[i] for s in uniq}
                if len(vals) > 1:
                    print(f"      ^ differs in '{FIELDS[i]}': {sorted(vals)}")

    # ---- and the same exact test on U1, where the earlier diagnosis claimed a real collision
    print("\n--- U1 (the reported 13x '41') ---")
    u1 = b.FindFootprintByReference("U1")
    if u1 is not None:
        g41 = [p for p in u1.Pads() if str(p.GetNumber()) == "41"]
        sigs41 = [sig(p) for p in g41]
        uniq41 = sorted(set(sigs41))
        print(f"  13-or-so objects with number '41': {len(g41)} -> {len(uniq41)} distinct signature(s)")
        sizes = collections.Counter(f"{s[2]}x{s[3]}" for s in sigs41)
        print(f"  size distribution: {dict(sizes)}")
        print(f"  => {'COINCIDENT duplicates' if len(uniq41) == 1 else 'REAL collision on distinct copper'}")
        empt = [p for p in u1.Pads() if str(p.GetNumber()) == ""]
        print(f"  unnamed pads: {len(empt)} -> nets {sorted({str(p.GetNetname()) or '(none)' for p in empt})}")
        if empt:
            es = sorted({sig(p) for p in empt})
            print(f"  unnamed distinct signatures: {len(es)}")
            for s in es[:4]:
                print("      " + "  ".join(f"{k}={v}" for k, v in zip(FIELDS, s)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

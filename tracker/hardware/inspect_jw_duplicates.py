#!/usr/bin/env python3
"""Inspect J_W1's duplicate pads: are the two objects per number IDENTICAL, or different copper?

Found by tracker/hardware/pad_audit.py: each of J_W1..J_W4 reports pad numbers 1,2,3,4 appearing 2x at
1 distinct position. Two explanations with very different consequences:
  (a) COINCIDENT DUPLICATES -- the same pad object written twice. Cosmetic; harmless electrically.
  (b) TWO PADS AT THE SAME PLACE with different sizes/nets -- real overlapping copper, which DRC and any
      net-based reasoning will mis-handle.

This decides between them by comparing size, net, layer set, shape and drill for each pair.

Run: ~/venvs/kicad/bin/python inspect_jw_duplicates.py [board]
"""
import collections
import hashlib
import sys

import pcbnew

B = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"


def main():
    print(f"board : {B}")
    print(f"sha256: {hashlib.sha256(open(B, 'rb').read()).hexdigest()[:24]}\n")
    b = pcbnew.LoadBoard(B)
    for ref in ("J_W1", "J_W2", "J_W3", "J_W4"):
        fp = b.FindFootprintByReference(ref)
        if fp is None:
            print(f"{ref}: ABSENT")
            continue
        pads = list(fp.Pads())
        by = collections.defaultdict(list)
        for p in pads:
            by[str(p.GetNumber())].append(p)
        print(f"--- {ref}  ({len(pads)} pad objects, {len(by)} numbers) ---")
        for num in sorted(by):
            group = by[num]
            if len(group) < 2:
                continue
            sigs = []
            for p in group:
                c = p.GetPosition()
                s = p.GetSize()
                d = p.GetDrillSize()
                sigs.append((
                    round(pcbnew.ToMM(c.x), 4), round(pcbnew.ToMM(c.y), 4),
                    round(pcbnew.ToMM(s.x), 4), round(pcbnew.ToMM(s.y), 4),
                    round(pcbnew.ToMM(d.x), 4), round(pcbnew.ToMM(d.y), 4),
                    str(p.GetNetname()) or "(none)",
                    int(p.GetShape()),
                    # Do NOT use LayerSet.FmtHex() here: it returns a buffer whose string form was not
                    # stable across calls, so two IDENTICAL pads compared as DIFFERENT and the report
                    # wrongly said "overlapping copper". Build the layer descriptor explicitly from the
                    # per-layer booleans, which are plain ints.
                    tuple(i for i in range(64) if p.GetLayerSet().Contains(i)),
                ))
            identical = len(set(sigs)) == 1
            print(f"   number {num!r}: {len(group)} objects, "
                  f"{'IDENTICAL -> coincident duplicate' if identical else 'DIFFERENT -> overlapping copper'}")
            if not identical:
                for s in sorted(set(sigs), key=str):
                    print(f"      pos=({s[0]},{s[1]}) size={s[2]}x{s[3]} drill={s[4]}x{s[5]} "
                          f"net={s[6]} shape={s[7]} nlayers={len(s[8])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

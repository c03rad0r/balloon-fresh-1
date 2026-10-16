#!/usr/bin/env python3
"""Diagnose U1's three footprint defects, precisely, from the BOARD.

ESTABLISHED FACTS (re-confirm here so the PR rests on measurement, not on a summary):
  - U1 = ESP32-S3-WROOM-1U-N8R8, 62 pad objects
  - pad number '41' appears 13 times, at 13 distinct positions, ALL net=GND
  - pad number '' appears 9 times, at 9 distinct positions, ALL net=(none)

THIS SCRIPT answers three further questions the fix depends on, none of which the earlier diagnosis
settled:
  1. Does the board's footprint ID carry a LIBRARY NICKNAME? (KiCad needs 'lib:footprint'; the netlist
     says 'RF_Module:ESP32-S3-WROOM-1U', so a bare 'ESP32-S3-WROOM-1U' on the board would be a
     resolution break.)
  2. Is that nickname absence UNIQUE to U1, or common to the board? (If common, it is not the defect.)
  3. Which footprints appear MULTIPLE times on the board? (A duplicated footprint inflates the pad
     count and would explain '41' x13 more simply than a corrupted footprint.)

Run: ~/venvs/kicad/bin/python diagnose_u1_footprint.py [board]
"""
import hashlib
import sys
from collections import Counter

import pcbnew

B = sys.argv[1] if len(sys.argv) > 1 else "tracker/hardware/hub_board_v9.kicad_pcb"


def main():
    print(f"board    : {B}")
    print(f"sha256   : {hashlib.sha256(open(B, 'rb').read()).hexdigest()[:24]}")
    b = pcbnew.LoadBoard(B)
    fps = list(b.GetFootprints())
    print(f"footprints: {len(fps)}\n")

    # --- 1 & 2: library nickname presence
    noprefix = []
    for f in fps:
        fid = f.GetFPID()
        lib = str(fid.GetLibNickname())
        item = str(fid.GetLibItemName())
        if not lib:
            noprefix.append((str(f.GetReference()), item))
    print(f"footprints with NO library nickname: {len(noprefix)}")
    for ref, item in sorted(noprefix)[:20]:
        print(f"   {ref:10} {item}")
    if not noprefix:
        print("   (none -- every fpid is lib:item)")

    # --- 3: duplicated REFERENCES (a better explanation for a 13x pad number than corruption)
    refs = Counter(str(f.GetReference()) for f in fps)
    dups = {k: v for k, v in refs.items() if v > 1}
    print(f"\nduplicated REFERENCES: {len(dups)}")
    for k, v in sorted(dups.items()):
        print(f"   {k} x{v}")

    # --- duplicated FOOTPRINT IDs
    fids = Counter(f"{f.GetFPID().GetLibNickname()}:{f.GetFPID().GetLibItemName()}" for f in fps)
    dupf = {k: v for k, v in fids.items() if v > 1}
    print(f"\nduplicated footprint IDs: {len(dupf)}")
    for k, v in sorted(dupf.items()):
        print(f"   {k} x{v}")

    # --- U1 in detail
    print("\n--- U1 ---")
    u1 = b.FindFootprintByReference("U1")
    if u1 is None:
        print("   ABSENT")
        return 1
    print(f"   value      : {u1.GetValue()}")
    print(f"   fpid raw   : lib={u1.GetFPID().GetLibNickname()!r} item={u1.GetFPID().GetLibItemName()!r}")
    print(f"   position   : ({pcbnew.ToMM(u1.GetPosition().x):.3f}, {pcbnew.ToMM(u1.GetPosition().y):.3f})")
    pads = list(u1.Pads())
    print(f"   pad objects: {len(pads)}")
    nums = Counter(p.GetNumber() for p in pads)
    print(f"   distinct numbers: {len(nums)}")
    for n, c in sorted(nums.items(), key=lambda kv: (kv[0] == '', kv[0])):
        if c > 1 or n == '':
            sub = [p for p in pads if p.GetNumber() == n]
            nets = sorted({p.GetNetname() or "(none)" for p in sub})
            sizes = sorted({f"{pcbnew.ToMM(p.GetSize().x):.2f}x{pcbnew.ToMM(p.GetSize().y):.2f}" for p in sub})
            print(f"     number {n!r:5} x{c:<3} nets={nets} sizes={sizes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

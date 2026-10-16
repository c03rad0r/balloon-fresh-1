#!/usr/bin/env python3
"""Compare the WORKING-TREE canonical board against the HEAD version, and report the routing counts."""
import os
import subprocess
import sys
import tempfile

import pcbnew

REL = "tracker/hardware/hub_board_v9.kicad_pcb"


def counts(path):
    b = pcbnew.LoadBoard(path)
    if b is None:
        return None
    t = list(b.GetTracks())
    tr = [x for x in t if x.Type() != pcbnew.PCB_VIA_T]
    vi = [x for x in t if x.Type() == pcbnew.PCB_VIA_T]
    return {"tracks": len(tr), "vias": len(vi),
            "nets": len(set(x.GetNetname() for x in tr))}


def main():
    root = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                          capture_output=True, text=True).stdout.strip()
    wt = os.path.join(root, REL)
    print(f"working tree : {counts(wt)}")
    data = subprocess.run(["git", "show", f"HEAD:{REL}"], capture_output=True).stdout
    tmp = tempfile.mktemp(suffix=".kicad_pcb")
    with open(tmp, "wb") as fh:
        fh.write(data)
    print(f"HEAD         : {counts(tmp)}")
    os.remove(tmp)

    # is the working tree file actually DIFFERENT from HEAD?
    d = subprocess.run(["git", "diff", "--stat", "HEAD", "--", REL],
                       capture_output=True, text=True).stdout.strip()
    print(f"git diff HEAD: {d or '(no difference)'}")
    st = subprocess.run(["git", "status", "--short", "--", REL],
                        capture_output=True, text=True).stdout.strip()
    print(f"git status   : {st or '(clean)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

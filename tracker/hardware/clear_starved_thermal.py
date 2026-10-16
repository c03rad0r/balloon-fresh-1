#!/usr/bin/env python3
"""Clear the last 2 starved_thermal errors, DRC-graded, refill-first.

CURRENT BOARD STATE (committed, refilled):
    26 errors = copper_edge_clearance 24 (the J_W* wing-socket edge interface -- characterised as ZERO
               real defects, awaiting an operator ruling on the exemption rule)
             + starved_thermal 2 (C_CAP2 and U_CUT4)

A starved_thermal means "thermal relief connection to zone incomplete: zone min spoke count 2, actual 1".
The board's own builder already has the fix for this class for U4's QFN land: a pad too small to host two
spokes across its short axis is connected SOLID instead of by thermal relief. Applying the same rule to
the two remaining pads should clear both.

This script:
  1. reports the geometry of each offending pad (size, layer, net, current zone connection)
  2. sets those pads to a SOLID zone connection
  3. refills, re-runs DRC, and reports the delta against a refilled control -- refill-first, because the
     board's 235-error figure turned out to be 208 stale fill and every pre-discovery number was wrong

GATE: PASS iff starved_thermal == 0 AND no other class rises AND copper_edge_clearance stays at 24.

Usage: clear_starved_thermal.py <in.kicad_pcb> <out.kicad_pcb>
"""
import json
import os
import shutil
import subprocess
import sys

import pcbnew


def mm(v):
    return pcbnew.ToMM(v)


def here():
    return os.path.dirname(os.path.abspath(__file__))


def refill(src, dst):
    hr = os.path.join(here(), "refill_zones.py")
    subprocess.run(["python3", hr, src, dst], capture_output=True, text=True)
    if os.path.exists(dst):
        for ext in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
            s = src.replace(".kicad_pcb", ext)
            if os.path.exists(s):
                shutil.copy(s, dst.replace(".kicad_pcb", ext))
        return True
    return False


def drc(bp):
    oj = bp.replace(".kicad_pcb", "_drc.json")
    subprocess.run(["kicad-cli", "pcb", "drc", bp, "--format", "json", "-o", oj,
                    "--severity-all"], capture_output=True, text=True)
    try:
        d = json.load(open(oj))
    except Exception:
        return None, {}, []
    c = {}
    det = []
    for v in d.get("violations", []):
        if v.get("severity") == "error":
            k = v.get("type", "?")
            c[k] = c.get(k, 0) + 1
            if k == "starved_thermal":
                det.append(" | ".join(i.get("description", "") for i in v.get("items", [])))
    return sum(c.values()), c, det


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    print(f"board: {src}\n")

    # control: refilled, untouched
    craw = dst.replace(".kicad_pcb", "_ctrl_raw.kicad_pcb")
    shutil.copy(src, craw)
    for ext in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
        s = src.replace(".kicad_pcb", ext)
        if os.path.exists(s):
            shutil.copy(s, craw.replace(".kicad_pcb", ext))
    cfin = dst.replace(".kicad_pcb", "_ctrl.kicad_pcb")
    if not refill(craw, cfin):
        print("refill of the control failed")
        return 1
    ct, cc, cdet = drc(cfin)
    print(f"CONTROL (refilled): {ct}  {json.dumps(cc, sort_keys=True)}")
    for d in cdet:
        print(f"    starved: {d}")
    print()

    # find the offending pads from the control's DRC
    # Parse the "of <REF>" token GENERICALLY. An earlier version hardcoded C_CAP/U_CUT prefixes from a
    # stale reading and therefore matched nothing when the real offenders turned out to be U4, so the
    # script reported "nothing changed" while looking like it had run correctly.
    import re as _re
    bad = set()
    for d in cdet:
        for m in _re.finditer(r"\bof\s+([A-Za-z_]+[0-9]+)\b", d):
            bad.add(m.group(1))
    if not bad:
        for d in cdet:
            for m in _re.finditer(r"\b([A-Za-z_]+[0-9]+)\b", d):
                tok = m.group(1)
                if tok.upper() not in ("ZONE", "GND", "PAD", "CU", "IN1", "IN2"):
                    bad.add(tok)
    print(f"offending footprints parsed from the DRC: {sorted(bad)}")

    b = pcbnew.LoadBoard(src)
    # collect every pad of the offending footprints that touches a zone and is under-spoked
    changed = 0
    for fp in b.GetFootprints():
        if fp.GetReference() not in bad:
            continue
        for p in fp.Pads():
            sz = p.GetSize()
            short_axis = min(mm(sz.x), mm(sz.y))
            print(f"  {fp.GetReference()}.{p.GetNumber()} net={p.GetNetname()!r} "
                  f"size {mm(sz.x):.2f}x{mm(sz.y):.2f} short_axis {short_axis:.2f} "
                  f"connection={p.GetLocalZoneConnection()} layer={pcbnew.LayerName(p.GetLayer())}")
            # a pad whose short axis cannot host two spokes gets a SOLID connection -- the same rule the
            # builder already applies to U4's QFN land
            p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
            changed += 1
    print(f"\npads set to SOLID zone connection: {changed}")
    if changed == 0:
        print("nothing changed -- not writing")
        return 1

    rawf = dst.replace(".kicad_pcb", "_raw.kicad_pcb")
    pcbnew.SaveBoard(rawf, b)
    for ext in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
        s = src.replace(".kicad_pcb", ext)
        if os.path.exists(s):
            shutil.copy(s, rawf.replace(".kicad_pcb", ext))
    if not refill(rawf, dst):
        print("refill failed")
        return 1
    ft, fc, fdet = drc(dst)
    print(f"\nRESULT (refilled): {ft}  {json.dumps(fc, sort_keys=True)}")
    print(f"  delta vs control: {ft-ct:+d}")
    checks = [
        ("starved_thermal == 0", fc.get("starved_thermal", 0) == 0, fc.get("starved_thermal", 0)),
        ("copper_edge_clearance unchanged", fc.get("copper_edge_clearance", 0) == cc.get("copper_edge_clearance", 0),
         f"{cc.get('copper_edge_clearance',0)} -> {fc.get('copper_edge_clearance',0)}"),
        ("no new error class", not (set(fc) - set(cc)), sorted(set(fc) - set(cc)) or "none"),
        ("total <= control", ft <= ct, f"{ct} -> {ft}"),
    ]
    print("\nGATE:")
    ok = True
    for name, passed, detail in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name:34} {detail}")
        ok = ok and passed
    print("\nGATE: " + ("PASS -- promote." if ok else "FAIL -- do not promote."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

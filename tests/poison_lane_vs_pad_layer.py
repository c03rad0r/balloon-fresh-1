#!/usr/bin/env python3
"""POISON TEST for check_lane_vs_pad_layer.py -- prove the gate can FAIL.

A gate that cannot fail is not a gate. This test plants real defects on COPIES of the
board (the real board is never touched) and asserts the gate's EXIT CODE flips to 1.

Lessons baked in (all measured 2026-10-21):
  * pcbnew's connectivity engine RE-ASSIGNS a track's net on SaveBoard based on what it
    touches. Planting a netless track across one pad comes back belonging to that pad's
    net -- i.e. legal copper -- so an earlier version of this test proved nothing. The
    plant now spans TWO different-net pads, which cannot be resolved to either.
  * asserting on stdout substrings is unsafe: the gate prints a "REAL SHORTS: 0" HEADER,
    so `"SHORT" in out` is always true. Assert on the EXIT CODE.
  * a VECTOR2I needs python ints; passing `c.x - 1e6` (a float) raises TypeError, and a
    bare `except` would have hidden it -- let the exception fail the test loudly instead.

Cases:
  P1 same-layer copper overlap between two different nets -> exit 1, >=2 SHORT lines
  P2 clean board                                          -> exit 0
  P3 the gate must name the foreign nets it is shorting
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pcbnew

UM = 1_000_000
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "tracker", "hardware", "hub_board_v10.kicad_pcb")
GATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "..", "tracker", "hardware", "check_lane_vs_pad_layer.py")
VENV = "/home/c08r4d0r/venvs/kicad/bin/python"


def gate(board=None):
    cmd = [VENV, GATE]
    if board:
        cmd += ["--board", board]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def plant_short():
    """A B.Cu track spanning two different-net pads of U3 -> an unambiguous short."""
    b = pcbnew.LoadBoard(SRC)
    fp = b.FindFootprintByReference("U3")
    pa = [p for p in fp.Pads() if p.GetNumber() == "4"][0]
    pb = [p for p in fp.Pads() if p.GetNumber() == "3"][0]
    ca, cb = pa.GetPosition(), pb.GetPosition()
    t = pcbnew.PCB_TRACK(b)
    t.SetLayer(pcbnew.B_Cu)
    t.SetWidth(int(0.2 * UM))
    t.SetStart(pcbnew.VECTOR2I(int(ca.x), int(ca.y)))
    t.SetEnd(pcbnew.VECTOR2I(int(cb.x), int(cb.y)))
    b.Add(t)
    d = tempfile.mkdtemp(prefix="poison_lane_")
    dst = os.path.join(d, "poison.kicad_pcb")
    pcbnew.SaveBoard(dst, b)
    return d, dst


def main():
    failures = []

    # P1: the planted short must be caught
    d, dst = plant_short()
    try:
        rc, out = gate(dst)
        n_short = len(re.findall(r"^\s+SHORT\s", out, re.M))
        print(f"P1 planted short: exit={rc} SHORT lines={n_short} (want exit 1, >=2)")
        if rc != 1:
            failures.append("P1 not caught (exit 0)")
        if n_short < 2:
            failures.append(f"P1 named only {n_short} shorts")
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # P3: it must name the actual nets, not just a count
    # (re-plant because the dir was removed)
    d, dst = plant_short()
    try:
        _, out = gate(dst)
        for net in ("/SPI1_MISO", "/SPI1_MOSI"):
            if net not in out:
                failures.append(f"P3 gate did not name {net}")
        print(f"P3 names both foreign nets: {'/SPI1_MISO' in out and '/SPI1_MOSI' in out}")
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # P2: the real board must pass
    rc, out = gate()
    hard = re.search(r"HARD DEFECTS:\s+(\d+)", out)
    n = int(hard.group(1)) if hard else -1
    print(f"P2 clean board: exit={rc} HARD DEFECTS={n} (want exit 0, 0)")
    if rc != 0:
        failures.append(f"P2 clean board exit {rc}")
    if n != 0:
        failures.append(f"P2 clean board reports {n} hard defects")

    if failures:
        print("\nPOISON TEST FAILED:")
        for f in failures:
            print("  - " + f)
        return 1
    print("\nPOISON TEST PASSED -- the gate fails on a planted short and passes on the board")
    return 0


if __name__ == "__main__":
    sys.exit(main())
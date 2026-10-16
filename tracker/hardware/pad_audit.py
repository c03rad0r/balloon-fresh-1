#!/usr/bin/env python3
"""PAD-LEVEL board audit -- the checks that COUNT-BASED gates structurally cannot make.

WHY THIS EXISTS. test_netlist_integrity.py checks FOOTPRINT COUNTS and REFERENCE DESIGNATORS. It never
looks at PAD NUMBERS. So a footprint can carry 62 pad objects where the part has 41, with thirteen pads
all numbered '41' and nine pads numbered '' on no net, and pass every check in that file -- because the
footprint is present, its reference resolves, and every pad carries a net or (none), which nothing
interrogates.

MEASURED on hub_board_v9 (2026-10-16, board sha256 90a8aeaa17a199ba...): exactly that. U1 (the ESP32-S3
module) carries 13 pads numbered '41' at 13 distinct positions, and 9 unnamed pads with no net. THE NINE
UNNAMED PADS ARE FLOATING COPPER -- a real electrical gap that no existing gate reports.

WHAT THIS ASSERTS, all decidable without an LLM and in well under a second:
  1. no pad number repeats within a footprint
  2. no pad has an empty or whitespace number
  3. every footprint's ID carries a library nickname (KiCad needs 'lib:footprint')
  4. every (model ...) reference resolves to a file that exists

Each is a FACT about the board, not a judgement, which is why it can run as a hook on every commit.

EXIT: 0 = clean, 1 = findings, 2 = could not run (never a silent pass).
Usage: pad_audit.py [board.kicad_pcb ...]      (default: the hub board)
"""
from __future__ import annotations

import collections
import os
import sys

# KiCad's python bindings are only importable under an interpreter that has pcbnew. Fail with a clear
# message rather than an ImportError traceback, because a gate that cannot run must say so.
try:
    import pcbnew
except ImportError:  # pragma: no cover
    print("PAD-AUDIT: SKIPPED -- this interpreter has no pcbnew.", file=sys.stderr)
    print("  Run with ~/venvs/kicad/bin/python (or whatever `make artefacts-status` reports).",
          file=sys.stderr)
    sys.exit(2)

DEFAULT_BOARDS = ["tracker/hardware/hub_board_v9.kicad_pcb"]


def pad_sig(p):
    """Exact identity of a pad, from RAW internal integers only.

    No mm conversion, no float rounding, no formatted buffer -- anything whose string form could vary
    between two calls must not appear here. That was the bug in the previous version.
    """
    c = p.GetPosition()
    s = p.GetSize()
    d = p.GetDrillSize()
    return (c.x, c.y, s.x, s.y, d.x, d.y, int(p.GetShape()), str(p.GetNetname()))


def model_paths(fp):
    for m in fp.Models():
        yield str(m.m_Filename)


def audit_board(path: str) -> tuple[list[str], list[str]]:
    """Return (findings, warnings). Findings are errors; warnings are cosmetic-but-reportable."""
    findings: list[str] = []
    warnings: list[str] = []
    if not os.path.exists(path):
        return [f"{path}: ABSENT"], []

    b = pcbnew.LoadBoard(path)
    if b is None:
        return [f"{path}: could not be read by pcbnew"], []

    base = os.path.dirname(os.path.abspath(path))

    for fp in b.GetFootprints():
        ref = str(fp.GetReference())
        item = str(fp.GetFPID().GetLibItemName())
        lib = str(fp.GetFPID().GetLibNickname())

        # --- 1 & 2: pad numbers.
        #
        # COMPARE RAW INTEGERS, NEVER FORMATTED STRINGS. An earlier version of this audit used
        # LayerSet.FmtHex() in the signature; that returns a buffer whose string form is not stable
        # across calls, so two IDENTICAL pads compared as different and the audit reported
        # "overlapping copper" for a coincident duplicate. Measured on J_W1..J_W4: raw comparison
        # shows IDENTICAL integers, i.e. coincident duplicates, which are a COUNTING nuisance rather
        # than an electrical fault. The two cases must not share a severity.
        nums = collections.Counter(str(p.GetNumber()) for p in fp.Pads())
        for num, count in sorted(nums.items()):
            if num.strip() == "":
                empties = [p for p in fp.Pads() if str(p.GetNumber()) == ""]
                sigs = {pad_sig(p) for p in empties}
                nets = sorted({str(p.GetNetname()) or "(none)" for p in empties})
                findings.append(
                    f"{ref} ({item}): {len(empties)} pad(s) with an EMPTY number at {len(sigs)} "
                    f"distinct position(s), nets={nets} -- unnamed copper; if the net is (none) it "
                    f"connects nothing")
                continue
            if count > 1:
                group = [p for p in fp.Pads() if str(p.GetNumber()) == num]
                sigs = {pad_sig(p) for p in group}
                if len(sigs) == 1:
                    warnings.append(
                        f"{ref} ({item}): pad number {num!r} appears {count}x at the SAME position "
                        f"with identical geometry -- coincident duplicate (cosmetic; inflates counts)")
                else:
                    findings.append(
                        f"{ref} ({item}): pad number {num!r} appears {count}x at {len(sigs)} "
                        f"DISTINCT positions -- KiCad cannot address them separately")

        # --- 3: library nickname
        if not lib:
            findings.append(f"{ref} ({item}): footprint ID has NO library nickname "
                            f"(KiCad expects 'lib:footprint')")

        # --- 4: model references resolve
        for mp in model_paths(fp):
            if "${KIPRJMOD}" in mp:
                rel = mp.split("}", 1)[-1].lstrip("/")
                full = os.path.join(base, rel)
            elif "${KICAD" in mp or "3DMODEL_DIR" in mp:
                # system-library reference: resolve against the installed package if we can find it
                kdir = os.environ.get("KICAD9_3DMODEL_DIR") or "/usr/share/kicad/3dmodels"
                rel = mp.split("}", 1)[-1].lstrip("/")
                full = os.path.join(kdir, rel)
            else:
                full = mp
            if not os.path.exists(full):
                findings.append(f"{ref} ({item}): model reference does not resolve: {mp}")
    return findings, warnings


def main(argv: list[str]) -> int:
    boards = argv[1:] or DEFAULT_BOARDS
    total = 0
    tot_warn = 0
    for b in boards:
        f, w = audit_board(b)
        if f or w:
            if f:
                print(f"--- {b}: {len(f)} finding(s) ---")
                for line in f:
                    print(f"  ERROR    {line}")
                total += len(f)
            if w:
                print(f"--- {b}: {len(w)} warning(s) (cosmetic, not fatal) ---")
                for line in w:
                    print(f"  WARN     {line}")
                tot_warn += len(w)
        else:
            if os.path.exists(b):
                print(f"--- {b}: clean ---")
    if tot_warn:
        print(f"\n  {tot_warn} warning(s): coincident duplicates inflate pad counts but are not")
        print("  electrical faults. Reported so a count-based check is not silently misled.")
    if total:
        print(f"\nPAD-AUDIT: FAIL -- {total} finding(s). These are decidable facts, not style.")
        print("  A footprint with unaddressable or unnamed pads passes every count-based check, which is")
        print("  why this exists. See docs/fab/U1-FOOTPRINT-DIAGNOSIS.md for the measured case.")
        return 1
    print("\nPAD-AUDIT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

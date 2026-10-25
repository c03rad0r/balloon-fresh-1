#!/usr/bin/env python3
"""PAD-LEVEL board audit -- the checks that COUNT-BASED gates structurally cannot make.

WHY THIS EXISTS. test_netlist_integrity.py checks FOOTPRINT COUNTS and REFERENCE DESIGNATORS, never PAD
NUMBERS and never PAD LAYERS. So a footprint can carry 62 pad objects where the part has 41 and pass
every check in that file.

THE RULES HERE WERE WRONG ONCE, AND THIS FILE RECORDS HOW. A first version reported 8 "errors" on the hub
board: 13 pads sharing number '41', 9 pads with no number, four U.FL connectors with pad '2' three times.
The builder was about to be sent to "fix" them. Then the SOURCE OF TRUTH was read -- the stock KiCad
libraries:

  /usr/share/kicad/footprints/RF_Module.pretty/ESP32-S3-WROOM-1U.kicad_mod
      13 pads numbered '41'  (thru_hole circle)  -- a thermal-via array
       9 pads with NO number (smd rect) on F.Paste ONLY -- paste apertures, no copper at all
  /usr/share/kicad/footprints/Connector_Coaxial.pretty/U.FL_Molex_MCRF_73412-0110_Vertical.kicad_mod
      1 pad '1' + 3 pads '2'  -- one signal, three ground tabs

A library footprint carries no nets, so the repeated numbers are the OFFICIAL CONVENTION for "several
physical pads, one net". The corrected rules follow from that:

  REPEATED NUMBER is NOT a defect. It is an error ONLY when the pads DISAGREE ON A NET, because one
  number can carry only one net -- that is the case KiCad cannot express. Measured on the hub: 20
  repeated-number groups all agree on one net, 0 disagree. So there were no collisions at all.

  UNNAMED PAD is NOT a defect when it is PASTE-ONLY. Measured: all 10 unnamed pads on the hub are on
  F.Paste with no copper layer. A pad that carries no copper connects nothing and cannot be floating.

  UNNAMED PAD is NOT a defect when it is a MECHANICAL BORE. An `np_thru_hole` pad is a NON-PLATED hole:
  it has no copper annulus, so "copper connected to nothing" is not a condition that can exist. Again the
  library says so -- read it before believing a layer list:

    /usr/share/kicad/footprints/MountingHole.pretty/MountingHole_2.2mm_M2.kicad_mod
        (pad "" np_thru_hole circle (at 0 0) (size 2.2 2.2) (drill 2.2) (layers "*.Cu" "*.Mask"))

  That `*.Cu` entry is NOMINAL -- it is what made this audit report the wing board's three mounting holes
  (H1/H2/H3) as defects, on a footprint byte-for-byte the same form as the stock one above. The fault was
  the CHECK, not the board. Measured 2026-10-17; the hub board carries no NPTH pads, which is why the
  false positive only surfaced on the wing.

WHAT SURVIVES AS A REAL FINDING: a footprint ID with no library nickname. Measured: U4 reads
`SX1280_QFN24` where the netlist says `balloon_flight_v9:SX1280_QFN24`, and every other part on the board
carries a nickname. That is a genuine netlist/board disagreement.

Run: ~/venvs/kicad/bin/python pad_audit.py [--root DIR] [board.kicad_pcb ...]
  --root DIR  the KiCad PROJECT directory that ${KIPRJMOD} resolves against. Pass it when auditing a
              staged copy in a temp dir, so model references resolve against the real tree.
Exit: 0 clean, 1 findings, 2 could not run.
"""
from __future__ import annotations

import os
import sys

try:
    import pcbnew
except ImportError:  # reported loudly by main(); never silently passed
    pcbnew = None

DEFAULT_BOARDS = ["tracker/hardware/hub_board_v9.kicad_pcb"]

# Copper layers, by KiCad name suffix. A pad with none of these cannot be electrically connected.
COPPER_SUFFIXES = (".Cu",)

# 3D model variable expansion. THE RULES ARE NOT INVENTED HERE -- they are the ones
# tests/test_model_resolution_census.py already established, and their docstring explains why:
#
#   ${KIPRJMOD}              -> the board's OWN directory
#   ${KICAD<n>_3DMODEL_DIR}  -> the COMPILED-IN default (/usr/share/kicad/3dmodels), NOT the shell
#                               environment: that variable is UNSET in this shell and the renderer does
#                               not read it from there. Expanding from os.environ would report a part
#                               missing that the renderer draws, or vice versa.
#
# Measured cost of getting this wrong: substituting only ${KIPRJMOD} made every stock-library part on the
# hub board report "model reference does not resolve" -- 37 false findings in one run. The audit has now
# been wrong in BOTH directions (8 false errors calling correct design a defect; 45 calling every stock
# part broken), which is why this expansion is copied from the tool that had it right.
KICAD_3DMODEL_PREFIX = "/usr/share/kicad/3dmodels"


def expand_model_ref(ref: str, board_dir: str) -> str:
    """Expand the two KiCad path variables a board may use, per the census rules above."""
    import re
    out = ref.replace("${KIPRJMOD}", board_dir)
    out = re.sub(r"\$\{KICAD[0-9]+_3DMODEL_DIR\}", KICAD_3DMODEL_PREFIX, out)
    return out


def pad_layers(pad) -> list[str]:
    """Layer names for a pad, from per-layer booleans (not FmtHex -- see the note in the tests)."""
    ls = pad.GetLayerSet()
    return [str(i) for i in range(64) if ls.Contains(i)]


def has_copper(pad) -> bool:
    """True if the pad sits on any copper layer, i.e. it can carry current."""
    ls = pad.GetLayerSet()
    for i in range(64):
        if ls.Contains(i) and pcbnew.LayerName(i).endswith(COPPER_SUFFIXES):
            return True
    return False


def is_mechanical_bore(pad) -> bool:
    """True for a NON-PLATED hole -- a bore, not copper.

    KiCad's own MountingHole.pretty/MountingHole_2.2mm_M2.kicad_mod ships
    `(pad "" np_thru_hole circle (at 0 0) (size 2.2 2.2) (drill 2.2) (layers "*.Cu" "*.Mask"))`.
    An unnamed `np_thru_hole` pad is therefore the LIBRARY'S idiom, and the `*.Cu` in its layer list is
    nominal: a non-plated hole has no annulus to connect, so it cannot be "copper connected to nothing".
    Flagging it was a false positive on the wing board (H1/H2/H3), measured 2026-10-17.
    """
    try:
        return int(pad.GetAttribute()) == int(pcbnew.PAD_ATTRIB_NPTH)
    except Exception:
        return False


def pad_sig(pad):
    """Exact identity, from RAW INTERNAL INTEGERS only.

    An earlier version included GetLayerSet().FmtHex(), whose string form is NOT STABLE ACROSS CALLS: two
    IDENTICAL pads compared as DIFFERENT and the audit reported "overlapping copper" for a coincident
    duplicate. Nothing whose string form can vary between calls may appear here.
    """
    c, s, d = pad.GetPosition(), pad.GetSize(), pad.GetDrillSize()
    return (c.x, c.y, s.x, s.y, d.x, d.y, int(pad.GetShape()), str(pad.GetNetname()))


def model_paths(fp):
    """MODELS THAT ARE ACTUALLY DRAWN. A reference with m_Show=False is excluded from the 3D
    view by KiCad itself, so it cannot be "silently absent" -- there is nothing to resolve and
    nothing to warn about. MEASURED: without this filter a deliberately-disabled reference was
    reported as "does not resolve", which is a false finding: the user asked for no model.
    Only a model that is SHOWN but unresolvable is the hazard AGENTS.md describes
    ("kicad-cli pcb render exits 0 and prints no warning when a footprint's model does not
    resolve -- the part is silently absent")."""
    return [m.m_Filename for m in fp.Models() if getattr(m, "m_Show", True)]


def audit_board(path: str, root: str | None = None) -> tuple[list[str], list[str]]:
    """Return (findings, warnings). Findings are errors; warnings are cosmetic-but-reportable."""
    if not os.path.exists(path):
        return [f"{path}: ABSENT"], []
    board = pcbnew.LoadBoard(path)
    if board is None:
        return [f"{path}: could not be read by pcbnew"], []

    base = os.path.abspath(root) if root else os.path.dirname(os.path.abspath(path))
    findings: list[str] = []
    warnings: list[str] = []

    for fp in board.GetFootprints():
        ref = fp.GetReference()
        item = str(fp.GetFPID().GetLibItemName())

        # --- real finding 1: NO LIBRARY NICKNAME.
        # Measured: U4 = 'SX1280_QFN24' while the netlist says 'balloon_flight_v9:SX1280_QFN24'. Every
        # other part carries a nickname. This is a netlist/board disagreement, not a style question.
        nick = str(fp.GetFPID().GetLibNickname())
        if not nick.strip():
            findings.append(
                f"{ref} ({item}): footprint ID has NO library nickname -- every other part on the board "
                f"has one, and the netlist names a library, so the two disagree")

        # --- real finding 2: repeated number whose pads DISAGREE on a net.
        # NOT a defect merely because it repeats: 13x'41' on GND and 3x'2' on GND are the standard
        # multi-pad-single-net idiom (thermal vias, U.FL ground tabs). Only a net DISAGREEMENT is
        # unexpressible in KiCad's model.
        groups: dict[str, list] = {}
        for pad in fp.Pads():
            num = str(pad.GetNumber())
            if num.strip():
                groups.setdefault(num, []).append(pad)
        for num, group in sorted(groups.items()):
            if len(group) < 2:
                continue
            nets = {str(p.GetNetname()) for p in group if str(p.GetNetname()).strip()}
            if len(nets) > 1:
                findings.append(
                    f"{ref} ({item}): pad number {num!r} appears {len(group)}x with DIFFERENT nets "
                    f"{sorted(nets)} -- one number can carry one net, so this is unexpressible")
            else:
                # correct idiom, or an unconnected group -- report the net for the record
                net = next(iter(nets)) if nets else "(no net)"
                warnings.append(
                    f"{ref} ({item}): pad number {num!r} appears {len(group)}x, all on {net} "
                    f"-- standard multi-pad single-net idiom")

        # --- real finding 3: UNNAMED pad that is ON COPPER. Two correct-by-design idioms are excluded,
        # each with its library citation in the module docstring: a PASTE-ONLY aperture (no copper at
        # all) and a MECHANICAL BORE (np_thru_hole -- non-plated, so no annulus to connect). What is
        # left is an unnamed PLATED pad on copper: copper connected to nothing.
        unnamed = [p for p in fp.Pads() if not str(p.GetNumber()).strip()]
        if unnamed:
            bores = [p for p in unnamed if is_mechanical_bore(p)]
            copper_ones = [p for p in unnamed if has_copper(p) and not is_mechanical_bore(p)]
            paste_only = [p for p in unnamed if not has_copper(p)]
            if copper_ones:
                nets = sorted({str(p.GetNetname()) or "(none)" for p in copper_ones})
                findings.append(
                    f"{ref} ({item}): {len(copper_ones)} UNNAMED pad(s) ON COPPER, nets={nets} -- "
                    f"copper connected to nothing")
            if bores:
                warnings.append(
                    f"{ref} ({item}): {len(bores)} unnamed NPTH pad(s) -- MECHANICAL BORE(s), not copper: "
                    f"a non-plated hole has no annulus to connect (KiCad's own MountingHole_2.2mm_M2 uses "
                    f"the identical '(pad \"\" np_thru_hole ...)' form)")
            if paste_only:
                warnings.append(
                    f"{ref} ({item}): {len(paste_only)} unnamed pad(s), PASTE-ONLY (no copper layer) "
                    f"-- paste apertures, correct by design; they carry no current")

        # --- model references
        for mp in model_paths(fp):
            rel = expand_model_ref(mp, base)
            if not os.path.exists(rel):
                findings.append(f"{ref} ({item}): model reference does not resolve: {mp}")

    return findings, warnings


def main(argv: list[str]) -> int:
    if pcbnew is None:
        print("PAD-AUDIT: CANNOT RUN -- pcbnew is not importable by this interpreter.", file=sys.stderr)
        print(f"  interpreter: {sys.executable}", file=sys.stderr)
        print("  This gate is NOT passing; it is not running.", file=sys.stderr)
        return 2

    root = None
    args = argv[1:]
    if "--root" in args:
        i = args.index("--root")
        if i + 1 >= len(args):
            print("--root needs a directory", file=sys.stderr)
            return 2
        root = args[i + 1]
        args = args[:i] + args[i + 2:]
    boards = args or DEFAULT_BOARDS

    total = warns = 0
    for b in boards:
        f, w = audit_board(b, root=root)
        if f:
            print(f"--- {b}: {len(f)} finding(s) ---")
            for line in f:
                print(f"  ERROR    {line}")
            total += len(f)
        elif os.path.exists(b):
            print(f"--- {b}: no findings ---")
        if w:
            print(f"  ({len(w)} warning(s) -- correct idioms, recorded for the count audit)")
            for line in w[:6]:
                print(f"  WARN     {line}")
            if len(w) > 6:
                print(f"  WARN     ... and {len(w) - 6} more of the same kind")
            warns += len(w)

    if total:
        print(f"\nPAD-AUDIT: FAIL -- {total} finding(s), {warns} warning(s).")
        print("  Findings are defects: an unnamed COPPER pad, a repeated number whose pads disagree on a")
        print("  net, an unresolvable model, or a footprint ID with no library nickname.")
        return 1
    print(f"\nPAD-AUDIT: PASS -- 0 findings, {warns} warning(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

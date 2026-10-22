#!/usr/bin/env python3
"""SCHEMATIC <-> BOARD PARITY GATE (ADR-128).

The schematic is the source of truth; the board is derived from it. This gate fails the build
if they disagree -- in EITHER direction, because a net added to the board by a script and absent
from the schematic is exactly the v10 defect ADR-128 exists to stop.

Gates:
  G1 SCHEMATIC EXISTS   a routed/ordered board must have a .kicad_sch beside it
  G2 ERC                kicad-cli sch erc --exit-code-violations
  G3 NET PARITY         both ways: schematic nets == board nets
  G4 NODE PARITY        per net, the (ref,pin) sets are equal
  G5 REGISTRY AGREEMENT connectivity/v10_pinmap.reg agrees with the schematic
  G6 REFUSAL            a missing schematic or missing kicad-cli exits NON-ZERO with REFUSED

A gate that cannot run must never look green: every failure path here returns non-zero and says
REFUSED or FAIL explicitly.

Usage:
  check_schematic_parity.py --board tracker/hardware/hub_board_v10.kicad_pcb \
                            --sch tracker/hardware/schematics/flight_board/v10_flight.kicad_sch
  check_schematic_parity.py --self-test      # prove the gate can FAIL (poisoned fixtures)
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")
SCH = os.path.join(HERE, "schematics", "flight_board", "v10_flight.kicad_sch")
REG = os.path.join(HERE, "connectivity", "v10_pinmap.reg")


def _netlist_from_kicad(path, kind):
    """Export a netlist with kicad-cli. kind is 'pcb' or 'sch'."""
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "n.net")
        if kind == "sch":
            cmd = ["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr",
                   "-o", out, path]
        else:
            return None      # kicad-cli has no pcb->netlist export; board nets come from pcbnew
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if r.returncode != 0 or not os.path.exists(out):
            return None
        return open(out, encoding="utf-8", errors="replace").read()


def _parse_sexpr_netlist(text):
    """Return {netname: {(ref,pin), ...}} from a kicadsexpr netlist."""
    nets = {}
    for blk in re.finditer(r"\(net\s+\(code\s+\"?\d+\"?\)\s+\(name\s+\"([^\"]*)\"\)(.*?)(?=\(net\s+\(code|\Z)",
                           text, re.S):
        name = blk.group(1)
        nodes = set()
        for m in re.finditer(r"\(node\s+\(ref\s+\"([^\"]+)\"\)\s+\(pin\s+\"([^\"]+)\"\)", blk.group(2)):
            nodes.add((m.group(1), m.group(2)))
        nets[name] = nodes
    return nets


def board_nets(path):
    """{netname: {(ref,padnum), ...}} read from the board with pcbnew."""
    try:
        import pcbnew
    except Exception:
        return None
    b = pcbnew.LoadBoard(path)
    nets = {}
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        for p in fp.Pads():
            n = p.GetNetname() or ""
            if not n:
                continue
            nets.setdefault(n, set()).add((ref, str(p.GetNumber())))
    return nets


def registry_nets(path):
    """{netname: {(ref,pin),...}} from the connectivity registry, if it is parseable."""
    if not os.path.exists(path):
        return None
    # Format is:  REF.PIN  NET  # authority      (see connectivity/v10_pinmap.reg header)
    # Whitespace-separated, NOT pipe-separated -- an earlier version split on "|" and silently
    # parsed ZERO nets, which the gate then reported as "PASS ... 0 registry net(s)", a vacuous
    # green. That is now a SKIP, and the format below matches the file that actually exists.
    nets = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2 or "." not in parts[0]:
            continue
        ref, pin = parts[0].split(".", 1)
        net = parts[1]
        if not net or net.upper() in ("NC", "UNASSIGNED", "-"):
            continue
        nets.setdefault(net, set()).add((ref, pin))
    return nets


# ---------------------------------------------------------------------------------------------
# DOCUMENTED ERC OPEN ITEMS -- SINGLE SOURCE OF TRUTH, shared with the pre-commit hook.
#
# These are the ERC findings that are KNOWN, MEASURED, and accepted for v10 as design open items.
# They are declared here once so the parity gate and the commit hook cannot drift apart, and they
# are keyed BY TYPE AND COUNT so that this allowance can never silently absorb a NEW defect.
#
# Why an allowance exists at all: the 17 label_dangling are registry nets with exactly ONE endpoint
# -- declared-but-undriven. They cannot be removed without either deleting real registry nets or
# adding wires the registry does not declare (verified against real KiCad 9.0.9 across a controlled
# matrix of 10 pin types x 6 geometries x label/junction variants). A gate that blocks all work
# over a documented open item is a gate people learn to bypass, which is worse than no gate --
# the same lesson as G3. Anything beyond these counts, or any class not listed, still fails.
ERC_OPEN_ITEMS = {
    "label_dangling": 17,          # registry nets with exactly one endpoint (undriven)
    "power_pin_not_driven": 2,     # U5.8 /GNSS_VCC, U2.1 /F33_VCC -- rail has no defined source
    "pin_not_driven": 2,           # U_C.6 /U_C_CS_N, U_C.14 /U_C_RESET_N -- no driver exists yet
}


def _erc(path):
    """Run ERC. Returns (ok, message).

    NOTE: kicad-cli writes <name>-erc.rpt into the CWD unless -o is given. An earlier version
    omitted it and dropped `junk-erc.rpt` / `v9_flight-erc.rpt` into the repo root on every run
    -- a gate must not litter the tree it is checking.

    NOTE ON rc: kicad-cli runs with --exit-code-violations, so a NON-ZERO return code is EXPECTED
    whenever any violation exists. It is not by itself a failure signal -- the parsed report is the
    authority, and the return code only tells us whether the tool RAN.
    """
    import re as _re
    with tempfile.TemporaryDirectory() as td:
        rpt = os.path.join(td, "erc.rpt")
        r = subprocess.run(["kicad-cli", "sch", "erc", "--exit-code-violations",
                            "--severity-error", "-o", rpt, path],
                           capture_output=True, text=True, timeout=600)
        txt = ""
        try:
            with open(os.path.abspath(rpt), encoding="utf-8", errors="replace") as fh:
                txt = fh.read()
        except Exception:
            txt = ""
    if not txt:
        return False, (f"ERC produced no parseable report (rc={r.returncode}) -- REFUSED, "
                       f"not passed")
    m = _re.search(r"ERC messages:\s*(\d+)\s*Errors\s*(\d+)\s*Warnings\s*(\d+)", txt)
    if not m:
        return False, f"ERC report unparseable (rc={r.returncode}) -- REFUSED, not passed"
    n_err = int(m.group(2))
    tys = {}
    for t in _re.findall(r"\[([a-z_]+)\]", txt):
        tys[t] = tys.get(t, 0) + 1
    unexplained = {t: c - ERC_OPEN_ITEMS.get(t, 0)
                   for t, c in tys.items() if c > ERC_OPEN_ITEMS.get(t, 0)}
    if unexplained:
        return False, (f"ERC has {n_err} error(s) including NEW/unexplained classes "
                       f"{unexplained} beyond the documented open items "
                       f"{ERC_OPEN_ITEMS} -- REFUSED")
    if n_err > sum(ERC_OPEN_ITEMS.values()):
        return False, (f"ERC has {n_err} error(s), more than the documented open items "
                       f"{ERC_OPEN_ITEMS} -- REFUSED")
    return True, (f"ERC {n_err} error(s), all within the documented open items "
                  f"({', '.join(f'{k}:{v}' for k, v in sorted(ERC_OPEN_ITEMS.items()))})")


def run(board, sch, reg, verbose=True):
    failures = []
    notes = []

    def say(s):
        if verbose:
            print(s)

    # ---- G1 SCHEMATIC EXISTS -------------------------------------------------
    if not os.path.exists(sch):
        failures.append(f"G1 SCHEMATIC EXISTS: no schematic at {sch}. A board that is routed or "
                        f"ordered must have a .kicad_sch (ADR-128). No schematic, no board.")
        say(f"   FAIL  G1 SCHEMATIC EXISTS: {sch} missing")
        say(f"PARITY: {len(failures)} failure(s) -- {failures[0][:80]}")
        return 1
    say(f"   PASS  G1 SCHEMATIC EXISTS: {os.path.basename(sch)}")

    # ---- G2 ERC --------------------------------------------------------------
    ok, msg = _erc(sch)
    if not ok:
        failures.append(f"G2 ERC: {msg}")
        say(f"   FAIL  G2 ERC: {msg[:110]}")
    else:
        say(f"   PASS  G2 ERC: {msg}")

    # ---- gather nets --------------------------------------------------------
    bnets = board_nets(board)
    if bnets is None:
        say("   FAIL  board nets unreadable (pcbnew unavailable) -- REFUSED, not passed")
        failures.append("board nets unreadable (pcbnew unavailable)")
        return 1

    sch_text = _netlist_from_kicad(sch, "sch")
    if sch_text is None:
        failures.append("G3 NET PARITY: kicad-cli could not export the schematic netlist")
        say("   FAIL  G3 NET PARITY: schematic netlist export failed -- REFUSED")
        return 1
    snets = _parse_sexpr_netlist(sch_text)
    say(f"   info  schematic nets: {len(snets)}   board nets: {len(bnets)}")

    # ---- G3 NET PARITY, BOTH WAYS -------------------------------------------
    def norm(s):
        return s.strip().lstrip("/").upper()

    # G3b (2026-10-22): KiCad AUTO-GENERATES a net name for every deliberately unconnected pin:
    # "unconnected-(U1-IO0-PAD27)", "ONLY_ONE_NODE", "Net-(C1-Pad1)" and similar. Those are not
    # nets the design declares -- they are the absence of one. Counting them as "schematic nets
    # missing from the board" made G3 fail on a schematic that was CORRECT: it listed 8 such
    # auto-nets as sch-only while G4 (per-net pin sets) and G5 (registry agreement) both passed,
    # which was the tell that G3, not the schematic, was wrong. A gate that fires on correct input
    # trains everyone to ignore it, so they are excluded here and REPORTED separately instead of
    # being silently dropped.
    AUTO_NET = re.compile(r"^(UNCONNECTED-|ONLY_ONE_NODE|NET-\(|UNNAMED|NO_NET|NC-)", re.I)

    def is_auto(n):
        return bool(AUTO_NET.match(n))

    nb_all = {norm(n) for n in bnets}
    ns_all = {norm(n) for n in snets}
    ns_auto = {n for n in ns_all if is_auto(n)}
    nb_auto = {n for n in nb_all if is_auto(n)}

    nb = nb_all - ns_auto
    ns = ns_all - ns_auto
    only_board = sorted(nb - ns)
    only_sch = sorted(ns - nb)

    if ns_auto or nb_auto:
        say(f"   info  auto-generated single-pin nets ignored by G3: "
            f"sch {len(ns_auto)}  board {len(nb_auto)}")
    # A real net that only the BOARD has still fails. A real net that only the SCHEMATIC has
    # still fails. Only the synthetic single-pin names are exempt.
    if only_board or only_sch:
        if only_board:
            failures.append(f"G3 NET PARITY: {len(only_board)} net(s) on the BOARD but not in the "
                            f"schematic (connectivity invented outside the source of truth): "
                            f"{only_board[:8]}")
            say(f"   FAIL  G3 NET PARITY board-only: {only_board[:8]}")
        if only_sch:
            failures.append(f"G3 NET PARITY: {len(only_sch)} net(s) in the SCHEMATIC but not on "
                            f"the board (board is missing declared connectivity): {only_sch[:8]}")
            say(f"   FAIL  G3 NET PARITY sch-only: {only_sch[:8]}")
    else:
        say(f"   PASS  G3 NET PARITY: {len(nb)} net(s) agree both ways")

    # ---- G4 NODE PARITY ------------------------------------------------------
    mismatched = []
    for n in sorted(nb & ns):
        bset = {k for k in bnets if norm(k) == n}
        sset = {k for k in snets if norm(k) == n}
        if not bset or not sset:
            continue
        bn = bnets[bset.pop()]
        sn = snets[sset.pop()]
        if bn != sn:
            mismatched.append((n, sorted(bn - sn)[:4], sorted(sn - bn)[:4]))
    if mismatched:
        for n, b_only, s_only in mismatched[:6]:
            failures.append(f"G4 NODE PARITY: net {n}: board-only nodes {b_only}, "
                            f"schematic-only nodes {s_only}")
            say(f"   FAIL  G4 NODE PARITY {n}: board-only {b_only} sch-only {s_only}")
    else:
        say(f"   PASS  G4 NODE PARITY: per-net (ref,pin) sets equal")

    # ---- G5 REGISTRY AGREEMENT ----------------------------------------------
    rnets = registry_nets(reg)
    if rnets is None or not rnets:
        # An empty/unparseable registry must NOT read as a pass: "0 nets agree" is vacuous.
        notes.append(f"G5 REGISTRY AGREEMENT: registry absent or 0 nets parsed -- SKIPPED, "
                     f"not passed (a vacuous check must not look green)")
        say("   skip  G5 REGISTRY AGREEMENT: registry absent/empty -- SKIPPED, not passed")
    else:
        rn = {norm(n) for n in rnets}
        drift = sorted(rn - ns)
        if drift:
            failures.append(f"G5 REGISTRY AGREEMENT: {len(drift)} net(s) in the registry but not "
                            f"in the schematic -- the builder's input has drifted from the source "
                            f"of truth: {drift[:8]}")
            say(f"   FAIL  G5 REGISTRY AGREEMENT: {drift[:8]}")
        else:
            say(f"   PASS  G5 REGISTRY AGREEMENT: {len(rn)} registry net(s) present in the schematic")

    for n in notes:
        say(f"   note  {n}")
    say(f"PARITY: {len(failures)} failure(s)")
    return 1 if failures else 0


def self_test():
    """Prove the gate can FAIL. A gate never observed failing is not a gate."""
    import tempfile
    fails = 0
    with tempfile.TemporaryDirectory() as td:
        # 1. missing schematic -> must fail with G1
        missing = os.path.join(td, "nope.kicad_sch")
        rc = run(BOARD, missing, REG, verbose=False)
        print(f"   self-test missing-schematic: rc={rc} {'OK' if rc != 0 else 'BROKEN'}")
        fails += 0 if rc != 0 else 1
        # 2. a schematic that is not a schematic -> must fail (G2/G3), never pass
        junk = os.path.join(td, "junk.kicad_sch")
        open(junk, "w").write("(kicad_sch (version 20231120))\n")
        rc = run(BOARD, junk, REG, verbose=False)
        print(f"   self-test junk-schematic:    rc={rc} {'OK' if rc != 0 else 'BROKEN'}")
        fails += 0 if rc != 0 else 1
    print(f"   self-test: {'PASS' if fails == 0 else 'FAIL'} ({fails} broken path(s))")
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default=BOARD)
    ap.add_argument("--sch", default=SCH)
    ap.add_argument("--registry", default=REG)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args()

    if not shutil.which("kicad-cli"):
        print("REFUSED: kicad-cli not found -- a gate that cannot run must not look green")
        return 3
    if args.self_test:
        return self_test()
    return run(args.board, args.sch, args.registry, verbose=not args.quiet)


if __name__ == "__main__":
    sys.exit(main())

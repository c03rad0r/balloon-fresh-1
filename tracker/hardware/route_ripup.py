#!/usr/bin/env python3
"""route_ripup.py -- rip-up-and-reroute for the v10 A* router.

WHY (2026-10-22). The router is GREEDY with no undo: whichever net routes first keeps its
corridor, and a later net that needs that corridor fails PERMANENTLY. Measured on the committed
board: 26 of 29 nets route, and the three that fail (/EN, /SPI2_SCK, /F33_RESET_N) each route
fine on an EMPTY board -- they are blocked by accumulated copper, not by geometry and not by
layer count.

`--promote` only REORDERS the greedy pass; it is not a rip-up, and it measured worse (24 nets).
Widening U1's pad gap measured worse too (24 nets). So the untested lever is a real rip-up.

ALGORITHM (per blocked net, bounded and deterministic):
  1. Route everything with the normal pass order -> a set of routed nets and a set of failures.
  2. For each failure F, in sorted order:
       a. Ask the router which net blocks F: route F with --nets F alone on a board that still
          holds all the other copper; the validator's rejection names the blocking net
          ("self-check: isolation vs routed <net>"), and a hard A* failure is reported per
          leg. Both are parsed.
       b. Strip the blocker's copper (strip_net.py).
       c. Route F alone (it now has the corridor).
       d. Re-route the stripped blocker alone.
       e. ACCEPT the swap only if BOTH succeeded. Otherwise restore the board from a backup
          and leave F unrouted. This is what makes it safe: a swap that does not strictly
          help is rolled back, so the net count can never go DOWN.
  3. Repeat for a bounded number of rounds; stop when a round adds nothing.

SAFETY: every mutation is preceded by a copy of the board. A rejected swap restores that copy,
so the script is idempotent and can never leave the board in a worse state than it found it.
The caller is responsible for a final gate + DRC run; this script only moves copper.

Usage:
    route_ripup.py [--board B] [--rounds 3] [--workdir DIR] [--dry-run]

Exit: 0 = finished (see the printed net count); 2 = could not run.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = os.path.expanduser("~/venvs/kicad/bin/python")
ROUTER = os.path.join(HERE, "route_v10_astar.py")
STRIP = os.path.join(HERE, "strip_net.py")
DEFAULT_BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")


def run(cmd, timeout=3600):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def routed_nets(board):
    """Nets that currently have copper on the board."""
    code = (
        "import pcbnew\n"
        f"b=pcbnew.LoadBoard({board!r})\n"
        "s=set()\n"
        "for t in b.GetTracks():\n"
        "    if 'TRACK' in str(type(t)):\n"
        "        s.add(t.GetNetname())\n"
        "print('NETS=' + ','.join(sorted(s)))\n"
    )
    rc, out = run([PY, "-c", code], timeout=120)
    m = re.search(r"NETS=(.*)", out)
    return set(n for n in (m.group(1).split(",") if m else []) if n)


def route(board, nets=None, pitch=None, max_exp=None, append=False):
    """Invoke the router. Returns (rc, routed_list, failed_list, raw)."""
    cmd = [PY, ROUTER, "--board", board]
    if append:
        cmd.append("--append")
    if nets:
        cmd += ["--nets", ",".join(sorted(nets))]
    if pitch:
        cmd += ["--pitch", str(pitch)]
    if max_exp:
        cmd += ["--max-expansions", str(max_exp)]
    rc, raw = run(cmd)
    routed = re.findall(r"'([^']+)'", (re.search(r"^routed \d+ net\(s\): \[(.*?)\]", raw, re.M) or
                                       type("m", (), {"group": lambda s, i: ""})()).group(1)) \
        if re.search(r"^routed ", raw, re.M) else []
    failed = re.findall(r"\('([^']+)',", (re.search(r"^failed \d+: \[(.*)", raw, re.M) or
                                          type("m", (), {"group": lambda s, i: ""})()).group(1))
    return rc, routed, failed, raw


def blockers_of(failed_name, raw):
    """Which net(s) blocked `failed_name`, from the router's own rejection text."""
    names = set()
    for m in re.finditer(r"isolation vs routed (?:via )?(/[A-Za-z0-9_]+)", raw):
        names.add(m.group(1))
    names.discard(failed_name)
    return sorted(names)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default=DEFAULT_BOARD)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--pitch", type=float, default=0.05)
    ap.add_argument("--max-expansions", type=int, default=5000000)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--targets", default="",
                    help="comma-separated nets to try rip-up on. Empty = every missing net, "
                         "which includes the poured rails (GND/+3V3) and declared-undriven "
                         "artefacts -- almost always you want an explicit list.")
    args = ap.parse_args()

    if not os.path.exists(ROUTER) or not os.path.exists(STRIP):
        print("RIPUP: CANNOT RUN -- router or strip_net.py missing")
        return 2

    board = args.board
    work = board + ".ripup.bak"
    shutil.copy(board, work)
    print(f"RIPUP: baseline backed up to {work}")

    before = routed_nets(board)
    print(f"RIPUP: baseline has {len(before)} routed net(s)")

    for rnd in range(1, args.rounds + 1):
        # which nets still need routing? everything in the netlist without copper.
        rc, raw = run([PY, "-c",
                       "import sys; sys.path.insert(0,'" + HERE + "')\n"
                       "import route_v10_astar as R\n"
                       "w=R.load_world('" + board + "')\n"
                       "print('ALL=' + ','.join(sorted({n for (_c,n) in w['net_pads']})))\n"],
                      timeout=180)
        m = re.search(r"ALL=(.*)", raw)
        all_nets = set(n for n in (m.group(1).split(",") if m else []) if n)
        have = routed_nets(board)
        missing = sorted(all_nets - have)
        # Never attempt the poured rails or an explicit target filter.
        missing = [n for n in missing if n not in ("GND", "+3V3")]
        want = [n for n in args.targets.split(",") if n]
        if want:
            missing = [n for n in missing if n in want]
        if not missing:
            print(f"RIPUP: round {rnd}: nothing missing -- all {len(all_nets)} nets routed")
            break
        print(f"RIPUP: round {rnd}: {len(missing)} net(s) missing: {missing}")

        progress = 0
        for f in missing:
            if args.dry_run:
                print(f"RIPUP-DRY: would attempt {f}")
                continue
            # what blocks it?
            rc, _r, _f, raw = route(board, nets=[f], pitch=args.pitch,
                                    max_exp=args.max_expansions, append=True)
            blk = blockers_of(f, raw)
            if not blk:
                # No named blocker means the ROUTER found no path at all (a hard A* failure).
                # Distinguish that from "a blocker exists but my parser missed it": print the
                # router's own reason verbatim. Measured 2026-10-22: all three targets return
                # "/EN: U1.3 -> J_PROG.3", i.e. a plain no-path failure -- there is no copper
                # to strip, so rip-up has nothing to act on for them.
                reason = ""
                m = re.search(r"failed \d+: \[(.*)\]", raw)
                if m:
                    reason = m.group(1)[:200]
                print(f"RIPUP: {f}: NO NAMED BLOCKER -- router reason: {reason}")
                print(f"RIPUP:   (a hard no-path failure: no copper to strip, rip-up cannot help)")
                continue
            for bname in blk:
                shutil.copy(board, work)
                # strip the blocker, route F, then re-route the blocker
                rc1, o1 = run([PY, STRIP, "--board", board, "--net", bname])
                rc2, r2, f2, raw2 = route(board, nets=[f], pitch=args.pitch,
                                          max_exp=args.max_expansions, append=True)
                ok_f = f in r2
                rc3, r3, f3, raw3 = route(board, nets=[bname], pitch=args.pitch,
                                          max_exp=args.max_expansions, append=True)
                ok_b = bname in r3
                if ok_f and ok_b:
                    print(f"RIPUP: {f} <-> {bname}: SWAP OK (both routed)")
                    progress += 1
                    break
                shutil.copy(work, board)  # roll back: never leave it worse
                print(f"RIPUP: {f} <-> {bname}: swap failed "
                      f"(F={'ok' if ok_f else 'no'}, blocker={'ok' if ok_b else 'no'}) -- rolled back")
        after = routed_nets(board)
        print(f"RIPUP: round {rnd} done: {len(after)} net(s) routed (was {len(before)})")
        if progress == 0 and len(after) <= len(before):
            print("RIPUP: no progress this round -- stopping")
            break
        before = after

    final = routed_nets(board)
    print(f"RIPUP: FINAL {len(final)} routed net(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

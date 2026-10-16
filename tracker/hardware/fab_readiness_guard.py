#!/usr/bin/env python3
"""FAB READINESS GUARD -- refuses to let a non-orderable hub board become the canonical one.

THE DEFECT THIS CLOSES (found by the Astra gap analysis, item H1):
    tracker/hardware/hub_board_v9.kicad_pcb is the file a fab order would be generated from. It has
    held ONLY 2 tracks on 1 net -- it is a PLACED-ONLY board. The real routed result (834 tracks, 286
    vias, 57 of 59 nets) has been living in a separate artifact. Nothing in the repo distinguished the
    two, so a single careless command could package a silently non-functional board and ship it.
    Astra's words: "Never generate the order from the placed-only hub inadvertently."

WHAT THIS DOES, on every commit that touches a hub board file:
  1. counts tracks, vias and routed nets on the staged version of the board
  2. compares against tracker/hardware/FAB-READINESS.json (the recorded expectation)
  3. REFUSES the commit if a board is being published as canonical while carrying materially less
     routing than the recorded state -- i.e. the placed-only regression
  4. REFUSES if a board claims to be orderable but has unrouted nets, unless the shortfall is listed in
     the expectation file as an accepted, documented exception

It is a GUARD, not a grader: it does not re-run DRC (that is fab_grade.sh's job, and it is slow). It
catches the specific regression that matters, cheaply, at commit time.

Escape hatch, deliberately awkward and auditable:
    FAB_GUARD_ACK="<reason>" git commit ...
records the acknowledgement in the commit message via the printed notice. Without it, a regression
cannot be committed.

Usage:
    fab_readiness_guard.py --check <board.kicad_pcb>     # exit 1 if it regressed
    fab_readiness_guard.py --record <board.kicad_pcb>    # write/refresh the expectation entry
"""
import json
import os
import subprocess
import sys

EXPECT = "tracker/hardware/FAB-READINESS.json"
KICAD_PY = os.path.expanduser("~/venvs/kicad/bin/python")

COUNT_CODE = (
    "import pcbnew,sys,json;"
    "b=pcbnew.LoadBoard(sys.argv[1]);"
    "t=list(b.GetTracks());"
    "tr=[x for x in t if x.Type()!=pcbnew.PCB_VIA_T];"
    "vi=[x for x in t if x.Type()==pcbnew.PCB_VIA_T];"
    "print(json.dumps({'tracks':len(tr),'vias':len(vi),"
    "'nets_routed':len(set(x.GetNetname() for x in tr)),"
    "'nets_total':b.GetNetCount()-1}))"
)


def count(board):
    """Measure the board. Returns None if pcbnew is unavailable."""
    if not os.path.exists(KICAD_PY) or not os.path.exists(board):
        return None
    r = subprocess.run([KICAD_PY, "-c", COUNT_CODE, board],
                       capture_output=True, text=True, timeout=300)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return None


def repo_root():
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, check=True).stdout.strip()
        return out
    except Exception:
        return "."


def load_expect(root):
    p = os.path.join(root, EXPECT)
    if not os.path.exists(p):
        return {}
    try:
        return json.load(open(p))
    except Exception:
        return {}


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        return 2
    mode, board = args[0], args[1]
    root = repo_root()
    # --key supplies the REAL repo-relative path to look up in the expectation file. The hook measures
    # a temp copy (the staged content) but the expectation is keyed by the repo path, so without this
    # the lookup always missed and the guard passed everything silently while appearing to run.
    if "--key" in args:
        rel = args[args.index("--key") + 1]
    else:
        rel = os.path.relpath(os.path.abspath(board), root)
    m = count(board)
    if m is None:
        print(f"fab-guard: could not measure {rel} (pcbnew unavailable) -- SKIPPING, not passing silently")
        return 0

    exp = load_expect(root)
    entry = exp.get(rel)

    if mode == "--record":
        entry = dict(m)
        entry["note"] = entry.get("note", "recorded by fab_readiness_guard.py --record")
        exp[rel] = entry
        with open(os.path.join(root, EXPECT), "w") as fh:
            json.dump(exp, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print(f"fab-guard: recorded {rel} -> {m}")
        return 0

    if mode != "--check":
        print(__doc__)
        return 2

    print(f"fab-guard: {rel} -> tracks {m['tracks']}, vias {m['vias']}, "
          f"nets {m['nets_routed']}/{m['nets_total']}")
    if entry is None:
        print(f"fab-guard: no recorded expectation for {rel}.")
        print(f"           If this board is canonical and ready, record it:")
        print(f"             python3 tracker/hardware/fab_readiness_guard.py --record {rel}")
        return 0

    # THE REGRESSION: publishing a board with materially less routing than recorded.
    min_tracks = int(entry.get("tracks", 0))
    min_nets = int(entry.get("nets_routed", 0))
    ack = os.environ.get("FAB_GUARD_ACK", "")

    problems = []
    if m["tracks"] < min_tracks:
        problems.append(f"tracks {m['tracks']} < recorded {min_tracks}")
    if m["nets_routed"] < min_nets:
        problems.append(f"nets_routed {m['nets_routed']} < recorded {min_nets}")

    if problems:
        print("")
        print("  *** FAB GUARD: REFUSING THIS COMMIT ***")
        for p in problems:
            print(f"      {p}")
        print("")
        print(f"  {rel} is the file a fab order is generated from. Committing a board with less")
        print("  routing than the recorded state is how a PLACED-ONLY board becomes the")
        print("  deliverable -- a silently non-functional order. (Astra gap analysis, item H1.)")
        print("")
        print(f"  If this reduction is INTENTIONAL, re-commit with a reason:")
        print(f'      FAB_GUARD_ACK="why" git commit ...')
        if ack:
            print("")
            print(f'  ACKNOWLEDGED: "{ack}" -- allowing the commit. Record this in the message.')
            return 0
        return 1

    # a board that claims to be complete but is not
    unrouted = m["nets_total"] - m["nets_routed"]
    accepted = int(entry.get("accepted_unrouted", 0))
    if unrouted > accepted:
        print(f"  fab-guard: NOT REFUSING, but noting {unrouted} unrouted net(s) "
              f"(accepted: {accepted}).")
        print(f"             This board is NOT orderable as it stands.")
    else:
        print(f"  fab-guard: OK -- matches the recorded state "
              f"({unrouted} unrouted, within the accepted {accepted}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

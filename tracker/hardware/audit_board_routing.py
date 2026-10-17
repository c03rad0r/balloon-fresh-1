"""Audit EVERY committed board's routing primitives -- the check that was missing.

WHY. A "package audit" commit was suspected of replacing the wing v9 board with an unrouted one. That
suspicion turned out to be WRONG, and it was wrong because of a bug in THIS FILE'S FIRST VERSION. That bug
is the reason this docstring exists.

=== THE INSTRUMENT BUG, AND WHY IT IS DOCUMENTED HERE ===

The first version counted with `text.count("(segment ")` -- WITH A TRAILING SPACE. KiCad changed its writer
format between revisions:

    old writer   (segment (start 3 12.5) (end 2 12.5)     <- matches "(segment " WITH the trailing space
    KiCad 9      (segment                                  <- on its own line, NO trailing space

So the tool reported `segments=0` for a board that `pcbnew.LoadBoard()` shows carries 20 segments, 8 vias and
a 10 F.Cu / 10 B.Cu split. It reported the SAME zero for the canonical hub board, which carries 834 segments
and 286 vias -- and that should have been the obvious tell.

A reformat is not a deletion, and a whitespace-sensitive delimiter cannot tell the two apart.

=== THE RULE THIS TOOL NOW FOLLOWS ===

Count with a WORD BOUNDARY, never a trailing space: `\\(segment\\b`. And VALIDATE AGAINST A KNOWN-GOOD
OBJECT before trusting the output -- a parser that returns 0 for an 834-segment board is broken, not
informative. `--selftest` does exactly that, and it runs automatically.

THE AUTHORITATIVE READER IS pcbnew. This tool stays text-based because it must also read historical revisions
straight out of git (`git show REV:path`), where a parser is the only option -- but for the WORKING TREE,
`pcbnew.LoadBoard()` is the arbiter, and `tests/` should use it rather than a delimiter split.

Exit code: 0 = no board lost routing vs its previous revision; 1 = at least one did, OR the selftest failed.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# WORD BOUNDARY, not a trailing space. This is the whole point of the correction.
PRIMITIVES = {
    "segment": re.compile(r"\(segment\b"),
    "via": re.compile(r"\(via\b"),
    "arc": re.compile(r"\(arc\b"),
    "zone": re.compile(r"\(zone\b"),
}

# A board that is known-good, used to prove the parser works before trusting it.
# If this ever reports zero, the parser is broken -- not the board.
KNOWN_GOOD = "tracker/hardware/hub_board_v9.kicad_pcb"
KNOWN_GOOD_MIN_SEGMENTS = 800


def count(text: str) -> dict[str, int]:
    return {name: len(rx.findall(text)) for name, rx in PRIMITIVES.items()}


def per_layer(text: str) -> dict[str, int]:
    """Segment layer split -- the measure ADR-065 is about."""
    layers: dict[str, int] = {}
    for chunk in re.split(r"\(segment\b", text)[1:]:
        m = re.search(r'\(layer "([^"]+)"\)', chunk)
        if m:
            layers[m.group(1)] = layers.get(m.group(1), 0) + 1
    return layers


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *args], capture_output=True, text=True, check=False
    ).stdout


def boards() -> list[str]:
    out = git("ls-files", "*.kicad_pcb")
    return [p for p in out.split("\n") if p and "/gerbers/" not in p and "/output/" not in p]


def selftest() -> bool:
    """Prove the parser against a board whose state is already known.

    THE STEP THAT WAS SKIPPED. Without it, a broken parser reads as a finding.
    """
    path = REPO / KNOWN_GOOD
    if not path.is_file():
        print(f"SELFTEST SKIPPED: {KNOWN_GOOD} is not present in this tree")
        return True
    c = count(path.read_text(errors="replace"))
    ok = c["segment"] >= KNOWN_GOOD_MIN_SEGMENTS
    print(f"selftest: {KNOWN_GOOD} -> segments={c['segment']} vias={c['via']} "
          f"(expect >= {KNOWN_GOOD_MIN_SEGMENTS} segments)")
    if not ok:
        print("  ** SELFTEST FAILED -- the PARSER is broken, not the board. Refusing to report findings.")
    return ok


def main() -> int:
    print("=" * 72)
    if not selftest():
        return 1
    print("=" * 72)

    paths = boards()
    if not paths:
        print("no boards found -- refusing to report a pass on an empty set")
        return 1

    print(f"\nboards audited: {len(paths)}\n")
    regressions = []

    for path in paths:
        text = (REPO / path).read_text(errors="replace")
        now = count(text)
        now_layers = per_layer(text)

        prev_rev = git("log", "-2", "--format=%H", "--", path).split()
        prev = None
        if len(prev_rev) >= 2:
            prev_text = git("show", f"{prev_rev[1]}:{path}")
            if prev_text:
                prev = count(prev_text)

        status = "routed" if now["segment"] or now["zone"] else "unrouted"
        print(f"  {path}")
        print(f"    now:  segments={now['segment']:4d}  vias={now['via']:3d}  "
              f"arcs={now['arc']:3d}  zones={now['zone']:3d}   [{status}]")
        if now_layers:
            print("    layer split: " + "  ".join(f"{k}={v}" for k, v in sorted(now_layers.items())))

        if prev is not None:
            lost = {k: prev[k] - now[k] for k in prev if prev[k] > now[k]}
            if lost:
                print("    ** REGRESSION vs previous revision: "
                      + "  ".join(f"{k}: {prev[k]} -> {now[k]}" for k in sorted(lost)))
                if prev["segment"] and not now["segment"]:
                    print("       ^^ the board LOST ALL ROUTING -- check with pcbnew before believing it")
                regressions.append((path, lost))
            else:
                print("    no loss vs previous revision")

    print()
    if regressions:
        print(f"RESULT: {len(regressions)} board(s) LOST routing in the last revision:")
        for path, lost in regressions:
            print(f"  - {path}: " + "  ".join(f"{k} -{v}" for k, v in sorted(lost.items())))
        print("\nBefore acting: confirm with pcbnew.LoadBoard(), which is the arbiter. A text parser")
        print("disagreeing with pcbnew means the parser is wrong.")
        return 1

    print("RESULT: no board lost routing in the last revision")
    return 0


if __name__ == "__main__":
    sys.exit(main())

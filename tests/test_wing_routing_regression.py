#!/usr/bin/env python3
"""Gate: the WING board's ROUTING must survive a commit -- a recorded baseline, checked per layer.

WHY THIS FILE EXISTS
--------------------
Nothing in this repo checked that a committed board still CARRIES the routing a previous
revision had.  That gap produced a red master: a commit re-serialized
`tracker/hardware/wing_board/wing_board_v9.kicad_pcb` with pcbnew, which reformatted

    (segment (start 2 12.5) (end 2 9.8) (width 0.4) (layer "F.Cu") (net 1) (uuid "..."))

into

    (segment
      (start 2 12.5)
      (end 2 9.8)
      ...

and the repo's text gates -- which split on the literal `'(segment '`, with a space --
could no longer see any of the board's 20 segments.  `tests/test_3d_models_wing.py`
reported "AssertionError: 0 segments" and CI went red, while the board itself was
perfectly routed: `pcbnew.LoadBoard()` returned 10 F.Cu tracks, 10 B.Cu tracks and 8 vias
the whole time.

Two lessons, and this file is both of them:

  1. **A routing count is load-bearing.**  The wing's cells sit on BOTH faces (ADR-065);
     the back series string is wired on B.Cu and tied to the front by 8 through vias.  If
     those tracks disappear the back string is electrically ISOLATED, which is exactly the
     defect the 20-segment assertion exists to catch.  A board with zero tracks is not
     orderable, and the wing is the second board in the JLCPCB order.
  2. **A gate must not be defeatable by whitespace.**  So the parser here is
     whitespace-tolerant (it walks balanced `(tag ...)` s-expressions, as
     `tests/test_3d_models_wing.py::_blocks` does), and it reports the PER-LAYER split
     rather than a bare total -- the total-only form of this check passed for a year while
     the back string was isolated.

The baseline below is a RECORDED EXPECTATION, not a computed one: it is the routing the
human-audited ADR-065 change landed (commit 0ed25484e, "fix(wing): wire the B.Cu solar
back string"), re-recorded against the board as it stands after the WING v9 package audit
and the restore of this branch.  Geometry is never invented here -- the test only checks
that what landed is still there.

Run:  ~/venvs/ho-test/bin/python -m pytest tests/test_wing_routing_regression.py -q
"""
from __future__ import annotations

import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[1]
BOARD = REPO / 'tracker' / 'hardware' / 'wing_board' / 'wing_board_v9.kicad_pcb'

# --------------------------------------------------------------------------- the baseline
# Recorded from tracker/hardware/wing_board/wing_board_v9.kicad_pcb at
#   commit f8243e2f9 ("fix(wing): restore the board to its generator's form, ...")
#   sha256 34f103774bfba921eacbac99a9a73dc0fd2f28a680cf6f665e9556ba55fcd2fa
#
# 20 segments = 10 F.Cu + 10 B.Cu is the ADR-065 double-sided solar string: the front
# string on F.Cu, the same string mirrored on B.Cu, and 8 through vias (two per string
# node, redundant) tying each back node to its front counterpart.  The per-layer split is
# the load-bearing part -- see the docstring.
BASELINE = {
    'segments_total': 20,
    'segments_by_layer': {'F.Cu': 10, 'B.Cu': 10},
    'vias': 8,
    'footprints': 15,
    'model_blocks': 12,
}

# What each missing piece MEANS, so the failure names the consequence and not just a count.
MEANING = {
    'segments_total': 'the ADR-065 solar string is not fully routed',
    'F.Cu': 'the FRONT series string (SOLAR_P -> SOLAR_N through SOLAR_MID1/2) is open',
    'B.Cu': 'the BACK series string is ELECTRICALLY ISOLATED -- cells sit on B.Cu, so the '
            'board looks wired on screen and is open in copper (the exact defect ADR-065 '
            'and the 20-segment assertion exist to prevent)',
    'vias': 'each back string node is no longer tied to its front counterpart',
    'footprints': 'placed parts were lost from the board',
    'model_blocks': 'a placed part lost its 3D model assignment',
}


def _board_text() -> str:
    return BOARD.read_text()


def _blocks(text: str, tag: str):
    """Every balanced `(tag ...)` s-expression in text.

    Deliberately whitespace-tolerant and NOT `text.split('(tag ')`: that form is what let
    a pcbnew re-serialization hide 20 segments from the gate.
    """
    out = []
    for m in re.finditer(r'\(' + tag + r'\b', text):
        depth = 0
        for j in range(m.start(), len(text)):
            if text[j] == '(':
                depth += 1
            elif text[j] == ')':
                depth -= 1
                if depth == 0:
                    out.append(text[m.start():j + 1])
                    break
    return out


def routing_report(text: str) -> dict:
    """The routing primitives a board carries: per-layer segment counts and via count."""
    by_layer: dict[str, int] = {}
    for block in _blocks(text, 'segment'):
        m = re.search(r'\(layer "([^"]+)"\)', block)
        layer = m.group(1) if m else '(no layer)'
        by_layer[layer] = by_layer.get(layer, 0) + 1
    return {
        'segments_total': sum(by_layer.values()),
        'segments_by_layer': by_layer,
        'vias': len(_blocks(text, 'via')),
        'footprints': len(_blocks(text, 'footprint')),
        'model_blocks': len(_blocks(text, 'model')),
    }


def routing_losses(actual: dict, baseline: dict = BASELINE) -> list[str]:
    """Every primitive the baseline has that `actual` is MISSING, named with its consequence."""
    losses = []
    for key in ('segments_total', 'vias', 'footprints', 'model_blocks'):
        got, want = actual[key], baseline[key]
        if got < want:
            losses.append(
                f'{key}: {want} recorded -> {got} present ({want - got} LOST) -- {MEANING[key]}')
    want_layers = baseline['segments_by_layer']
    got_layers = actual['segments_by_layer']
    for layer, want in want_layers.items():
        got = got_layers.get(layer, 0)
        if got < want:
            losses.append(
                f'{layer} segments: {want} recorded -> {got} present ({want - got} LOST) -- '
                f'{MEANING[layer]}')
    # A layer that vanished entirely is the isolation case, so name it explicitly.
    for layer in got_layers:
        if layer not in want_layers and got_layers[layer]:
            losses.append(f'{layer} segments: {got_layers[layer]} present, none recorded '
                          f'-- the routing moved layers, which is a different design')
    return losses


def test_wing_board_routing_matches_the_recorded_baseline():
    """The wing board must still carry the ADR-065 routing a previous revision had.

    This is the guard the repo was missing: it fails LOUDLY, and names what was lost and
    what that means electrically, if a future commit silently drops the board's routing.
    """
    actual = routing_report(_board_text())
    losses = routing_losses(actual)
    assert not losses, (
        'the WING board has LOST routing that a previous revision carried.\n'
        + '\n'.join(f'  - {line}' for line in losses)
        + f'\n\nbaseline: {BASELINE}'
        + f'\nactual:   {actual}'
        + f'\n\nDo not "fix" this by editing the baseline: the routing is the deliverable. '
          f'Regenerate with\n  python3 tracker/hardware/wing_board/build_wing_v9.py\n'
          f'and re-record the baseline only if the ADR-065 routing was legitimately changed.')


def test_the_routing_check_can_actually_fail():
    """The guard above is worthless unless it fails on a board that lost its routing.

    A gate that cannot fail looks green. So drop the B.Cu segments from the board TEXT
    (the isolation defect) and require the check to report the loss by NAME. The mutation
    is done on a string, never on the board file.
    """
    text = _board_text()
    stripped = text
    for block in _blocks(text, 'segment'):
        if '(layer "B.Cu")' in block:
            stripped = stripped.replace(block, '')
    assert stripped != text, 'the fixture did not remove any B.Cu segment -- the test is broken'

    losses = routing_losses(routing_report(stripped))
    joined = '\n'.join(losses)
    assert losses, 'removing every B.Cu segment produced NO reported loss -- the gate is blind'
    assert 'B.Cu' in joined, f'the loss is not attributed to B.Cu:\n{joined}'
    assert 'ISOLATED' in joined, (
        f'the failure does not say what the loss MEANS (the back string is isolated):\n{joined}')

    # ...and the same for the TOTAL, on the unmodified board, so a loss that keeps the
    # per-layer split plausible still cannot slip through.
    one_less = re.sub(r'\(segment\b', '(seGment', text, count=1)
    assert one_less != text, 'the fixture did not rename any segment -- the test is broken'
    total_losses = routing_losses(routing_report(one_less))
    assert total_losses, \
        'a board missing one segment reported no loss -- the total is not checked'
    assert 'segments_total' in '\n'.join(total_losses), \
        f'the single-segment loss was not reported against the total:\n{total_losses}'

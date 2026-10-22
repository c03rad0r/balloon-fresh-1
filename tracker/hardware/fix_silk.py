#!/usr/bin/env python3
"""fix_silk.py -- one deterministic pass that makes the silkscreen legible.

WHY THIS IS A SEPARATE STEP AND NOT PART OF THE BUILDER (2026-10-22)
-------------------------------------------------------------------
The board builder (build_hub_board_v10.py) must be a pure function of its spec: same spec in,
byte-identical board out. It was verified deterministic before this work.

Folding cosmetic silk repair into the builder broke that: the repair needs kicad-cli feedback
(which reference fields collide), so the builder's output became a function of a DRC run rather
than of its spec. Measured: two consecutive builds differed by 12,242 lines. That is the wrong
trade -- reproducibility of the SOURCE is worth more than saving one command.

So the pipeline is:
    build_hub_board_v10.py   -> deterministic board from the spec
    fix_silk.py              -> deterministic silk cleanup (this file)
    check_silk.py            -> GATE: must report 0, and the hook enforces it

fix_silk.py IS deterministic: it is driven by the DRC report, and for a given input board the
same violations lead to the same moves (every direction and offset is computed, never random).

WHAT IT DOES, in order -- each step is the measured fix for a measured class:
  1. REFERENCE TEXT SIZE. Every designator is set to 0.80mm/0.15mm. That is JLCPCB's minimum
     legible silkscreen text; KiCad's default is 1.00mm. The board is dense (45 parts on
     72x80mm) and a free-space sweep found only the left/right margins genuinely empty, so
     shrinking to the fab minimum is what lets designators fit between parts at all.
  2. MODULE OUTLINES OFF PADS. Stock module footprints draw a body rectangle on SilkS across
     their own pads. The fab CLIPS silk where mask is open, so the outline is broken at every
     pad -- the boundary becomes unreadable exactly where it is needed for alignment. Those
     segments are MOVED to F.Fab/B.Fab, which is what the fab layers are for. Lossless.
     (An earlier attempt TRIMMED them to dodge pads: measured 9 -> 12 violations, worse, because
     each cut created a new crossing. Moving the whole segment is correct.)
  3. DESIGNATOR COLLISIONS. Reference fields that overlap another label or part silk are moved
     away from the thing they collide with, iteratively, with kicad-cli as the oracle. Two
     labels can each sit in "free space" and still print on top of each other, so every relocated
     label reserves a slot and the next one keeps 2.2 x 1.6mm clear of it.
  4. MARGIN FALLBACK. Local nudging plateaus because the front is full. Stubborn designators are
     relocated into the free left/right margin at the SAME Y as their part, so the label still
     reads on the part's row.

WHAT IT NEVER TOUCHES: pads, tracks, vias, zones, courtyards, the outline, connectivity.
Only silkscreen text and silkscreen graphics.

Usage:
    fix_silk.py [--board PATH] [--passes N]
Exit: 0 = fixed and check_silk would pass; 1 = something remains; 2 = could not run.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

import pcbnew

UM = 1_000_000.0
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")

SILK_FAIL = ("silk_overlap", "silk_over_copper", "silk_edge_clearance")
REF_RE = re.compile(r"^Reference field of (\S+)$")

SILK_TEXT_H = 0.80   # mm -- JLCPCB minimum legible silkscreen text height
SILK_TEXT_W = 0.15   # mm -- JLCPCB minimum silkscreen line width


def drc(board, out_json):
    exe = shutil.which("kicad-cli")
    if not exe:
        return None
    if os.path.exists(out_json):
        os.unlink(out_json)
    subprocess.run([exe, "pcb", "drc", "--format", "json", "-o", out_json, board],
                   capture_output=True, text=True)
    if not os.path.exists(out_json):
        return None
    try:
        with open(out_json, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return None


def silk_vs(doc):
    """Silk violations, in a DETERMINISTIC order.

    DETERMINISM (2026-10-22): kicad-cli runs DRC multi-threaded, so the ORDER of violations in
    the report is not stable between runs. That matters here because the repair walks the list
    and each move can change the next decision -- measured: two runs of the identical pipeline
    produced different designator positions for C4, R_BAL1 and U_HUB_CVT. Sorting by a key
    derived only from the violation's own content removes the dependence on report order.
    """
    vs = [v for v in (doc.get("violations") or []) if v.get("type") in SILK_FAIL]
    return sorted(vs, key=lambda v: (
        v.get("type", ""),
        tuple(sorted(i.get("description", "") for i in (v.get("items") or []))),
    ))


def snap(v):
    return round(round(v / 0.05) * 0.05, 2)


def step1_text_size(b):
    n = 0
    for fp in b.GetFootprints():
        rf = fp.Reference()
        rf.SetTextSize(pcbnew.VECTOR2I(int(SILK_TEXT_H * UM), int(SILK_TEXT_H * UM)))
        rf.SetTextThickness(int(SILK_TEXT_W * UM))
        n += 1
    return f"text size -> {SILK_TEXT_H}mm/{SILK_TEXT_W}mm on {n} designator(s)"


def step2_outlines_off_pads(b):
    """Move silk graphics that cross ANY pad's mask opening to the Fab layer."""
    all_pads = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            all_pads.append(p.GetBoundingBox())
    moved = 0
    for fp in b.GetFootprints():
        for gi in list(fp.GraphicalItems()):
            lay = gi.GetLayer()
            if lay not in (pcbnew.F_SilkS, pcbnew.B_SilkS):
                continue
            if not isinstance(gi, pcbnew.PCB_SHAPE):
                continue
            if gi.GetShape() == pcbnew.SHAPE_T_SEGMENT and gi.GetStart() == gi.GetEnd():
                continue
            gb = gi.GetBoundingBox()
            for pb in all_pads:
                if (gb.GetX() <= pb.GetX() + pb.GetWidth() and
                        pb.GetX() <= gb.GetX() + gb.GetWidth() and
                        gb.GetY() <= pb.GetY() + pb.GetHeight() and
                        pb.GetY() <= gb.GetY() + gb.GetHeight()):
                    gi.SetLayer(pcbnew.F_Fab if lay == pcbnew.F_SilkS else pcbnew.B_Fab)
                    moved += 1
                    break
    return f"{moved} silk graphic(s) moved off pad mask openings -> Fab layer"


def step3_nudge(b, doc, board, tmp_json, passes, move_pts_fn):
    """Move reference fields away from what they collide with, until kicad-cli is happy."""
    moved = 0
    for _ in range(passes):
        vs = silk_vs(doc)
        if not vs:
            break
        fp_by_ref = {f.GetReference(): f for f in b.GetFootprints()}
        plans = {}
        for v in vs:
            refs, others = [], []
            for it in v.get("items") or []:
                m = REF_RE.match(it.get("description", ""))
                if m and m.group(1) in fp_by_ref:
                    refs.append((m.group(1), it.get("pos") or {}))
                else:
                    others.append(it.get("pos") or {})
            if len(refs) == 1:
                ref, rpos = refs[0]
            elif len(refs) == 2:
                # two labels on top of each other: move the later one alphabetically (arbitrary
                # but DETERMINISTIC)
                refs.sort(key=lambda t: t[0])
                ref, rpos = refs[1]
            else:
                continue
            rx, ry = rpos.get("x", 0), rpos.get("y", 0)
            if others:
                ox = sum(o.get("x", 0) for o in others) / len(others)
                oy = sum(o.get("y", 0) for o in others) / len(others)
            elif move_pts_fn:
                near = move_pts_fn(rx, ry)
                if near is None:
                    continue
                ox, oy = near
            else:
                continue
            dx, dy = rx - ox, ry - oy
            n = (dx * dx + dy * dy) ** 0.5
            if n < 1e-6:
                dx, dy, n = 1.0, -1.0, 2 ** 0.5
            plans.setdefault(ref, [0.0, 0.0])
            plans[ref][0] += 0.35 * dx / n
            plans[ref][1] += 0.35 * dy / n
        if not plans:
            break
        for ref, (ddx, ddy) in plans.items():
            rf = fp_by_ref[ref].Reference()
            p = rf.GetPosition()
            rf.SetPosition(pcbnew.VECTOR2I(int(round(snap(p.x / UM + ddx) * UM)),
                                          int(round(snap(p.y / UM + ddy) * UM))))
            moved += 1
        pcbnew.SaveBoard(board, b)
        b = pcbnew.LoadBoard(board)
        doc = drc(board, tmp_json)
        if doc is None:
            return moved, None, b
    return moved, doc, b


def step4_margin(b, doc, board, tmp_json, W, H):
    """Relocate stubborn designators to the free left/right margin at the same Y as their part."""
    fp_by_ref = {f.GetReference(): f for f in b.GetFootprints()}
    occ = []
    for f in b.GetFootprints():
        bb = f.GetBoundingBox(True, False)
        occ.append((bb.GetX() / UM, bb.GetY() / UM,
                    bb.GetX() / UM + bb.GetWidth() / UM,
                    bb.GetY() / UM + bb.GetHeight() / UM, f.IsFlipped()))

    def free_at(cx, cy, margin, side):
        for x0, y0, x1, y1, flip in occ:
            if (side == "B") != flip:
                continue
            if x0 - margin <= cx <= x1 + margin and y0 - margin <= cy <= y1 + margin:
                return False
        return True

    slots = []
    moved = 0
    for v in silk_vs(doc):
        refs = []
        for it in v.get("items") or []:
            m = REF_RE.match(it.get("description", ""))
            if m and m.group(1) in fp_by_ref:
                refs.append(m.group(1))
        if not refs:
            continue
        ref = sorted(refs)[-1] if len(refs) > 1 else refs[0]
        f = fp_by_ref[ref]
        rf = f.Reference()
        cy = snap(rf.GetPosition().y / UM)
        side = "B" if f.IsFlipped() else "F"
        px = f.GetPosition().x / UM
        for mx in ((3.6, 67.0) if px < W / 2 else (67.0, 3.6)):
            for dy in (0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6, 7, -7, 8, -8):
                ty = snap(cy + dy)
                if not (1.5 <= ty <= H - 1.5):
                    continue
                if not free_at(mx, ty, 1.4, side):
                    continue
                # a LABEL is not a courtyard: keep relocated labels off each other too
                if any(sd == side and abs(px2 - mx) < 2.2 and abs(py2 - ty) < 1.6
                       for px2, py2, sd in slots):
                    continue
                rf.SetPosition(pcbnew.VECTOR2I(int(round(mx * UM)), int(round(ty * UM))))
                slots.append((mx, ty, side))
                moved += 1
                break
            else:
                continue
            break
    if moved:
        pcbnew.SaveBoard(board, b)
    return moved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default=DEFAULT_BOARD)
    ap.add_argument("--passes", type=int, default=30)
    ap.add_argument("--json", default="/tmp/fix_silk_drc.json")
    args = ap.parse_args()

    doc = drc(args.board, args.json)
    if doc is None:
        print("FIX-SILK: CANNOT RUN -- kicad-cli missing or report unreadable")
        return 2

    b = pcbnew.LoadBoard(args.board)
    W = H = None
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            bb = d.GetBoundingBox()
            W, H = bb.GetX() / UM + bb.GetWidth() / UM, bb.GetY() / UM + bb.GetHeight() / UM
            break
    if not W:
        W, H = 72.0, 80.0

    print("FIX-SILK: before:", len(silk_vs(doc)), "violation(s)")
    print("FIX-SILK:", step1_text_size(b))
    print("FIX-SILK:", step2_outlines_off_pads(b))
    pcbnew.SaveBoard(args.board, b)

    def nearest_mask(x, y):
        # tie-break on (ref, pad number) so equal-distance candidates always resolve the same way
        best = None
        for fp in b.GetFootprints():
            for p in fp.Pads():
                q = p.GetPosition()
                d2 = (q.x / UM - x) ** 2 + (q.y / UM - y) ** 2
                key = (d2, fp.GetReference(), p.GetNumber())
                if best is None or key < best[0]:
                    best = (key, (q.x / UM, q.y / UM))
        return best[1] if best else None

    doc = drc(args.board, args.json)
    moved, doc, b = step3_nudge(b, doc, args.board, args.json, args.passes, nearest_mask)
    print(f"FIX-SILK: {moved} designator nudge(s)")
    if doc is None:
        print("FIX-SILK: CANNOT RUN -- DRC failed mid-repair")
        return 2

    # OUTER FIXPOINT LOOP (2026-10-22). One pass of nudge-then-margin is not always enough:
    # measured, a single invocation left 1 violation behind and a second invocation cleared it.
    # Two reasons: (a) moving a label can create a NEW collision somewhere else, and (b) the
    # margin fallback can place a label that then needs nudging. Looping until kicad-cli reports
    # zero (or until a round makes no progress, which means we are stuck for a real reason) makes
    # one invocation of this script sufficient, so the hook can run it once.
    for rnd in range(4):
        v = step4_margin(b, doc, args.board, args.json, W, H)
        doc = drc(args.board, args.json)
        if doc is None:
            print("FIX-SILK: CANNOT RUN -- DRC failed after margin fallback")
            return 2
        left = len(silk_vs(doc))
        print(f"FIX-SILK: round {rnd + 1}: {v} relocated to margin, {left} violation(s) left")
        if left == 0:
            break
        before = left
        moved, doc, b = step3_nudge(b, doc, args.board, args.json, args.passes, nearest_mask)
        doc = drc(args.board, args.json)
        if doc is None:
            print("FIX-SILK: CANNOT RUN -- DRC failed mid-loop")
            return 2
        if len(silk_vs(doc)) >= before and v == 0:
            print("FIX-SILK: no further progress possible in this pass")
            break

    remaining = silk_vs(doc)
    if not remaining:
        print("FIX-SILK: done -- silkscreen is legible (run check_silk.py to confirm)")
        return 0
    print(f"FIX-SILK: {len(remaining)} violation(s) remain")
    for x in remaining[:10]:
        desc = " <-> ".join(i.get("description", "?") for i in x.get("items") or [])
        print(f"           {x.get('type')}: {desc}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

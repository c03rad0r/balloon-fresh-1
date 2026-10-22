#!/usr/bin/env python3
"""place_silk_refs.py -- make the silkscreen legible by moving REFERENCE FIELDS, driven by kicad-cli.

Operator directive (2026-10-22): "please make sure that the silk screen is legible and doesn't
overlap with parts or other silk screens before you start routing the board."

DESIGN CHOICE: this does NOT re-implement silk geometry. It asks kicad-cli DRC which reference
fields collide, moves them, and asks again. kicad-cli is the oracle (AGENTS.md section 14: when a
custom check and kicad-cli disagree, the custom check is wrong until proven otherwise -- so there
is no custom check here at all).

WHAT IT MOVES, AND WHAT IT REFUSES TO MOVE:
  * MOVES   'Reference field of X' -- a designator is free text; moving it changes nothing
            electrical and nothing mechanical.
  * REFUSES footprint silk GRAPHICS ('Segment of X on F.Silkscreen') and pads. Those are part
            geometry: moving them means editing a footprint, which is a different decision. If
            only a graphic can fix a collision, this tool reports it and exits non-zero so a human
            decides -- it never silently edits a library part.

ALGORITHM (deterministic, no randomness):
  for pass in 1..MAX_PASSES:
      run DRC -> collect violations of the silk classes
      for each violation, if it names exactly one movable reference field and one OTHER item:
          step that field directly AWAY from the other item's centre by STEP mm
      if nothing moved: stop
  Reference-field centre placement is snapped to 0.05mm so the result is byte-stable.

Usage:
    place_silk_refs.py [--board PATH] [--passes N] [--step MM] [--dry-run]
Exit: 0 = no silk violations remain, 1 = violations remain (reported), 2 = could not run.
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


def silk_violations(doc):
    return [v for v in (doc.get("violations") or []) if v.get("type") in SILK_FAIL]


def snap(v):
    return round(round(v / 0.05) * 0.05, 2)


def make_free_at(board):
    """Return free_at(cx, cy, margin) -> bool: is this point clear of every courtyard?

    Courtyard-based and SIDE-AWARE is deliberately NOT used: a designator lives on the same
    physical side as its part, and a front part's label cannot be printed over a back part's
    courtyard because that is the other side of the board. So the occupancy test is per-side.
    """
    occ = []
    for f in board.GetFootprints():
        bb = f.GetBoundingBox(True, False)  # courtyard
        x0, y0 = bb.GetX() / UM, bb.GetY() / UM
        x1, y1 = x0 + bb.GetWidth() / UM, y0 + bb.GetHeight() / UM
        occ.append((x0, y0, x1, y1, f.IsFlipped()))

    def free_at(cx, cy, margin, side=None):
        for x0, y0, x1, y1, flip in occ:
            if side == "B" and not flip:
                continue
            if side == "F" and flip:
                continue
            if x0 - margin <= cx <= x1 + margin and y0 - margin <= cy <= y1 + margin:
                return False
        return True

    return free_at


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default=DEFAULT_BOARD)
    ap.add_argument("--passes", type=int, default=24)
    ap.add_argument("--step", type=float, default=0.35)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", default="/tmp/silk_refs_drc.json")
    args = ap.parse_args()

    tmp_json = args.json
    doc = drc(args.board, tmp_json)
    if doc is None:
        print("SILK-REFS: CANNOT RUN -- kicad-cli missing or report unreadable")
        return 2

    b = pcbnew.LoadBoard(args.board)
    if b is None:
        print(f"SILK-REFS: CANNOT RUN -- cannot load {args.board}")
        return 2

    fp_by_ref = {f.GetReference(): f for f in b.GetFootprints()}
    free_at = make_free_at(b)
    W, H = None, None
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            bb = d.GetBoundingBox()
            W, H = bb.GetX() / UM + bb.GetWidth() / UM, bb.GetY() / UM + bb.GetHeight() / UM
            break

    moved_total = 0
    for p in range(1, args.passes + 1):
        vs = silk_violations(doc)
        if not vs:
            print(f"SILK-REFS: clear after {p - 1} pass(es); {moved_total} field move(s)")
            if moved_total and not args.dry_run:
                pcbnew.SaveBoard(args.board, b)
            return 0

        # Build a move request per violation that has exactly ONE movable reference field.
        #
        # Two different DRC shapes must be handled, and they behave differently (measured):
        #   silk_overlap        -> items = [ref field, the other thing]   -> direction: away from it
        #   silk_over_copper    -> items = [ref field] ONLY, described as "Silkscreen clipped by
        #                          solder mask". KiCad names no second item, so there is nothing to
        #                          run away from. For these we find the NEAREST solder-mask opening
        #                          on the board (pads and mask apertures) and step away from that.
        #   silk_edge_clearance -> items = [edge, ref field] -> direction: away from the edge line
        mask_pts = []
        for f in b.GetFootprints():
            for pad in f.Pads():
                p = pad.GetPosition()
                mask_pts.append((p.x / UM, p.y / UM))
        plans = {}
        unmovable = 0
        for v in vs:
            items = v.get("items") or []
            refs, others = [], []
            for it in items:
                m = REF_RE.match(it.get("description", ""))
                if m and m.group(1) in fp_by_ref:
                    refs.append((m.group(1), it.get("pos") or {}))
                else:
                    others.append(it.get("pos") or {})
            if len(refs) != 1:
                unmovable += 1
                continue
            ref, rpos = refs[0]
            rx, ry = rpos.get("x", 0), rpos.get("y", 0)
            if others:
                ox = sum(o.get("x", 0) for o in others) / len(others)
                oy = sum(o.get("y", 0) for o in others) / len(others)
            elif mask_pts:
                ox, oy = min(mask_pts, key=lambda q: (q[0] - rx) ** 2 + (q[1] - ry) ** 2)
            else:
                unmovable += 1
                continue
            dx, dy = rx - ox, ry - oy
            n = (dx * dx + dy * dy) ** 0.5
            if n < 1e-6:
                # coincident centres: pick a deterministic direction from the ref name
                dx, dy, n = 1.0, -1.0, 2 ** 0.5
            plans.setdefault(ref, [0.0, 0.0])
            plans[ref][0] += args.step * dx / n
            plans[ref][1] += args.step * dy / n

        if not plans:
            print(f"SILK-REFS: {len(vs)} violation(s) remain but none is fixable by moving a "
                  f"reference field ({unmovable} involve part graphics or pads only).")
            print("           Fixing those means editing a footprint or moving the PART -- a human "
                  "decision, not a scripted one.")
            for v in vs[:8]:
                desc = " <-> ".join(i.get("description", "?") for i in v.get("items") or [])
                print(f"           {v.get('type')}: {desc}")
            return 1

        for ref, (ddx, ddy) in plans.items():
            f = fp_by_ref[ref]
            rf = f.Reference()
            pos = rf.GetPosition()
            nx, ny = snap(pos.x / UM + ddx), snap(pos.y / UM + ddy)
            if W and H:  # never park a designator off the board
                nx = min(max(nx, 1.5), W - 1.5)
                ny = min(max(ny, 1.5), H - 1.5)
            rf.SetPosition(pcbnew.VECTOR2I(int(round(nx * UM)), int(round(ny * UM))))
            moved_total += 1
        if args.dry_run:
            print(f"SILK-REFS: pass {p} would move {len(plans)} field(s) (dry-run)")
        else:
            pcbnew.SaveBoard(args.board, b)
            b = pcbnew.LoadBoard(args.board)
            fp_by_ref = {f.GetReference(): f for f in b.GetFootprints()}
        doc = drc(args.board, tmp_json)
        if doc is None:
            print("SILK-REFS: CANNOT RUN -- DRC failed mid-repair")
            return 2

    vs = silk_violations(doc) if doc else []
    if vs and not args.dry_run:
        # ---------------------------------------------------------------------------------
        # MARGIN FALLBACK (2026-10-22). Local nudging plateaus on this board: 45 parts on
        # 72x80mm, and a free-space sweep showed the FRONT has only the left margin (x<7) and the
        # right margin (x>65) genuinely empty -- every interior cell is occupied by a courtyard.
        # There is nowhere local for a designator to go, which is why 40 passes could not clear it.
        #
        # This is the standard dense-board solution: the designator does not have to sit on the
        # part. Relocate the stubborn ones into the free margin AT THE SAME Y as their part, so
        # the label still reads on the part's row and a reader can follow it across. Deterministic
        # (nearest free margin point, snapped to 0.05mm), and it only touches reference TEXT --
        # never a part, never a pad, never footprint graphics.
        moved = 0
        used_slots = []   # (x, y, side) of designators already placed
        for v in vs:
            items = v.get("items") or []
            refs = [REF_RE.match(i.get("description", "")) for i in items]
            refs = [m.group(1) for m in refs if m and m.group(1) in fp_by_ref]
            if len(refs) == 0:
                continue
            if len(refs) == 2:
                # TWO designators on top of each other -- one of them must move, and which one is
                # arbitrary but must be DETERMINISTIC, so take the later ref name alphabetically.
                # (Measured cases: R_MON1/R_MON2, C_CAP1/R_BAL1, R_BAL2/R_DIV1, D_HUB2/J_PROG.)
                ref = sorted(refs)[1]
            else:
                ref = refs[0]
            f = fp_by_ref[ref]
            rf = f.Reference()
            cy = snap(rf.GetPosition().y / UM)
            # pick the margin (left/right) nearest the part, then the free y nearest the part
            px = f.GetPosition().x / UM
            order = ([(3.6, "L"), (67.0, "R")] if px < W / 2 else [(67.0, "R"), (3.6, "L")])
            placed = False
            for mx, _side in order:
                for dy in [0, 1.0, -1.0, 2.0, -2.0, 3.0, -3.0, 4.0, -4.0, 5.0, -5.0]:
                    ty = snap(cy + dy)
                    if not (1.5 <= ty <= H - 1.5):
                        continue
                    side = "B" if f.IsFlipped() else "F"
                    if not free_at(mx, ty, 1.4, side):
                        continue
                    # A LABEL is not a courtyard: two designators can each be "in free space"
                    # and still print on top of each other. Require 2.2mm separation (0.8mm text
                    # height plus the width of a 5-character designator) from every label already
                    # relocated on the same side. Measured cause: this was why the fallback moved
                    # 9-17 labels and still left R_BAL1/C_CAP1 and R_BAL2/R_DIV2 overlapping.
                    if any(sd == side and abs(px2 - mx) < 2.2 and abs(py2 - ty) < 1.6
                           for px2, py2, sd in used_slots):
                        continue
                    rf.SetPosition(pcbnew.VECTOR2I(int(round(mx * UM)), int(round(ty * UM))))
                    used_slots.append((mx, ty, side))
                    placed = True
                    moved += 1
                    break
                if placed:
                    break
        if moved:
            pcbnew.SaveBoard(args.board, b)
            b = pcbnew.LoadBoard(args.board)
            fp_by_ref = {f.GetReference(): f for f in b.GetFootprints()}
            doc = drc(args.board, tmp_json)
            vs = silk_violations(doc) if doc else []
            print(f"SILK-REFS: margin fallback relocated {moved} designator(s); "
                  f"{len(vs)} violation(s) remain")
    if not vs:
        print("SILK-REFS: clear")
        return 0
    print(f"SILK-REFS: {len(vs)} violation(s) remain after local moves AND margin fallback")
    for v in vs[:10]:
        desc = " <-> ".join(i.get("description", "?") for i in v.get("items") or [])
        print(f"           {v.get('type')}: {desc}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

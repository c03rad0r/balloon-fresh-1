#!/usr/bin/env python3
"""Stitch v3 -- OFFSET stitching vias with a stub, for pads with no room at centre.

WHY v3 EXISTS (measured 2026-10-14)
-----------------------------------
v2 asked "does a 0.60 mm via fit AT THE PAD CENTRE?" and correctly REJECTED 63 pads
where it does not. That was the right safety call, but it left 4 pads unconnected --
pads on C_MON, J_W1, J_W3 and C_HF that the router had already given a short GND
stub track, and which the v2 check would not stitch.

The correct fix is not to shrink the via (a sub-0.60 mm via would violate the frozen
rule set) and not to accept the open. It is to put the SAME 0.60 mm via SOMEWHERE
THAT FITS and join it to the pad with a short GND track. A GND stub plus an offset
via is a normal, manufacturable plane tap.

WHAT v3 DOES
  For every GND pad not already stitched:
    1. search outward on a 0.25 mm ring (r = 0.6 .. 4.0 mm) around the pad centre for
       a via position that clears every FOREIGN net by (via_d/2 + clearance)
    2. if found, drop the via there AND add a GND track from the pad to the via
    3. if no position on any ring qualifies, report the pad as UNRESOLVABLE rather
       than silently leaving it (so the remaining count is honest)

  It never moves a part, never deletes, and never shrinks the via. It is idempotent:
  a pad within 1.0 mm of an existing GND via is left alone.

Run:
  python3 stitch_gnd_planes.py <in.kicad_pcb> <out.kicad_pcb>            # v2 behaviour
  python3 stitch_gnd_planes.py <in.kicad_pcb> <out.kicad_pcb> --offset   # v3
"""
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

VIA_D = 0.6
VIA_DRILL = 0.3
CLEARANCE = 0.2
TRACK_W = 0.2
RING_STEP = 0.25
R_MAX = 4.0


def mm(v):
    return pcbnew.ToMM(v)


def bbox_of(item):
    bb = item.GetBoundingBox()
    return (mm(bb.GetX()), mm(bb.GetY()),
            mm(bb.GetX() + bb.GetWidth()), mm(bb.GetY() + bb.GetHeight()))


def main():
    argv = sys.argv[1:]
    offset_mode = "--offset" in argv
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 2:
        print(__doc__)
        return 2
    src, dst = args

    board = pcbnew.LoadBoard(src)
    if board is None:
        print(f"cannot load {src}")
        return 2

    gcode = None
    for code, net in board.GetNetInfo().NetsByNetcode().items():
        if net.GetNetname() == "GND":
            gcode = code
    if gcode is None:
        print("no GND net")
        return 2

    foreign = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() != gcode:
                foreign.append(bbox_of(pad))
    for t in board.GetTracks():
        if t.GetNetCode() != gcode:
            foreign.append(bbox_of(t))

    r_test = VIA_D / 2.0 + CLEARANCE

    # ---------------------------------------------------------------------------------------------
    # WHY THIS PREDICATE WAS WRONG (measured 2026-10-15)
    # ---------------------------------------------------------------------------------------------
    # The original `free()` tested the candidate via centre against the AXIS-ALIGNED BOUNDING BOX of
    # every foreign item, with an inside-corner distance test. Two independent defects followed:
    #
    #   1. A bbox is not a shape. A diagonal track's bounding box is a large rectangle, so a point can
    #      clear the box corner and still sit ON the track; conversely a legitimately empty spot next
    #      to a diagonal can be rejected. Vias therefore ended up colliding with COPPER.
    #   2. Hole-to-hole spacing was NEVER tested. That is a DRILL rule, and this predicate only ever
    #      used the COPPER diameter, so two drills could be arbitrarily close.
    #
    # Measured consequence of enabling offset mode with the old predicate: errors 29 -> 56, including
    # `shorting_items` 5 (REAL SHORTS), `hole_to_hole` 34, `tracks_crossing` 2, `holes_co_located` 2.
    # It reduced "unresolvable pads" 55 -> 12 -- the metric it optimises -- while breaking the board.
    #
    # The fix uses KiCad's own geometry: every foreign item is turned into a real polygon (arcs
    # approximated), so the test is shape-accurate, and hole spacing is checked separately against the
    # same minimum the frozen ruleset enforces.
    HOLE_TO_HOLE = 0.25          # jlcpcb-s1-frozen.kicad_dru: hole-to-hole minimum
    ARC_ERR = 5000               # max error 0.005 mm when approximating arcs

    def _polys(item):
        """Real shape polygon(s) for a pad, track or via, as KiCad itself computes them.

        NOTE (measured 2026-10-15): `PAD::TransformShapeToPolygon` ASSERTS on UNDEFINED_LAYER in
        KiCad 9 -- "UNDEFINED_LAYER is no longer allowed". Passing it made _polys() throw for every
        pad, so pads were silently dropped from the copper test and "UNRESOLVABLE" fell to 0 while 71
        vias were placed. A predicate that silently tests NOTHING is worse than one that is too loose,
        because it reports success. Use a real layer: the pad's own first layer, F_Cu for tracks.
        """
        try:
            ps = pcbnew.SHAPE_POLY_SET()
            layer = pcbnew.F_Cu
            if hasattr(item, "GetLayerSet"):
                seq = [int(x) for x in item.GetLayerSet().Seq()]
                if seq:
                    layer = seq[0]
            item.TransformShapeToPolygon(ps, layer, 0, ARC_ERR, pcbnew.ERROR_INSIDE)
            return ps
        except Exception:
            return None

    def _polys_ok(item):
        """_polys() but LOUD: a pad/track we cannot convert is a hole in the safety test."""
        ps = _polys(item)
        if ps is None:
            raise SystemExit(
                "[FATAL] could not convert an item to a polygon, so the clearance test would "
                "silently ignore it. That is the exact defect this predicate was rewritten to fix. "
                "Refusing to place vias against an incomplete test."
            )
        return ps

    # Build once: (polygon, drill_circle) for every foreign item.
    # `foreign` already holds only NON-GND pads/tracks; add their drills for the hole test.
    foreign_polys = []
    foreign_holes = []            # (cx, cy, radius) of every drill/via hole
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            # ONLY foreign (non-GND) copper blocks a GND via. Adding the GND pad's OWN polygon made
            # every pad centre read as blocked, so 0 centre vias and 71 offsets were placed -- a
            # self-collision artifact, caught by comparing against the pre-fix "vias at pad centre: 15".
            if pad.GetNetCode() != gcode:
                foreign_polys.append((_polys_ok(pad), bbox_of(pad)))
                ds = pad.GetDrillSize()
                d_x, d_y = int(ds.x), int(ds.y)
                if d_x > 0 or d_y > 0:
                    p = pad.GetPosition()
                    foreign_holes.append((mm(p.x), mm(p.y), mm(max(d_x, d_y)) / 2.0))
    for t in board.GetTracks():
        if t.GetNetCode() != gcode:
            foreign_polys.append((_polys_ok(t), bbox_of(t)))
        if t.GetNetCode() != gcode and t.GetClass() == "PCB_VIA":
            dv = float(mm(int(t.GetDrillValue()))) if hasattr(t, "GetDrillValue") \
                else float(mm(int(t.GetViaDrill())))
            p = t.GetPosition()
            foreign_holes.append((mm(p.x), mm(p.y), dv / 2.0))

    def free(cx, cy):
        """True only if a via of VIA_D centred here clears all copper, and its drill clears all holes.

        Two gates, because they are two different fabricator rules:
          * COPPER: distance from the point to the real (non-bbox) polygon >= (VIA_D/2 + CLEARANCE)
          * HOLES : drill centre distance >= (OUR_DRILL/2 + HOLE_TO_HOLE + other_drill/2)
        Both are checked. The old code did neither correctly.
        """
        need = r_test
        # --- copper, against true geometry ---
        for ps, bb in foreign_polys:
            x0, y0, x1, y1 = bb
            # cheap reject: if the bbox is further than `need`, skip the exact test
            nx = min(max(cx, x0), x1)
            ny = min(max(cy, y0), y1)
            if (cx - nx) ** 2 + (cy - ny) ** 2 > (need + 1.0) ** 2:
                continue
            try:
                pt = pcbnew.VECTOR2I(int(round(cx * 1e6)), int(round(cy * 1e6)))
                if ps.Distance(pt) < int(need * 1e6):
                    return False
            except Exception:
                # if the exact test is unavailable, fall back to the conservative bbox test
                if (cx - nx) ** 2 + (cy - ny) ** 2 < need ** 2:
                    return False
        # --- holes, drill to drill ---
        for hx, hy, hr in foreign_holes:
            if (cx - hx) ** 2 + (cy - hy) ** 2 < (VIA_DRILL / 2.0 + HOLE_TO_HOLE + hr) ** 2:
                return False
        return True

    def near_gnd_via(cx, cy):
        for t in board.GetTracks():
            if t.GetClass() == "PCB_VIA" and t.GetNetCode() == gcode:
                p = t.GetPosition()
                if (cx - mm(p.x)) ** 2 + (cy - mm(p.y)) ** 2 < 1.0 ** 2:
                    return True
        return False

    added_here = added_offset = already = unresolvable = 0
    bad = []

    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() != gcode:
                continue
            ls = pad.GetLayerSet()
            if not (ls.Contains(pcbnew.F_Cu) or ls.Contains(pcbnew.B_Cu)):
                continue
            p = pad.GetPosition()
            cx, cy = mm(p.x), mm(p.y)
            if near_gnd_via(cx, cy):
                already += 1
                continue

            if free(cx, cy):
                site, off = (cx, cy), False
            elif offset_mode:
                site = None
                ring = VIA_D / 2.0 + CLEARANCE
                while ring <= R_MAX and site is None:
                    n = max(8, int(2 * math.pi * ring / 0.2))
                    for k in range(n):
                        a = 2 * math.pi * k / n
                        tx, ty = cx + ring * math.cos(a), cy + ring * math.sin(a)
                        if free(tx, ty):
                            site = (tx, ty)
                            break
                    ring += RING_STEP
                off = True if site else False
                if site is None:
                    unresolvable += 1
                    bad.append(f"{fp.GetReference()}.{pad.GetNumber()}")
                    continue
            else:
                unresolvable += 1
                bad.append(f"{fp.GetReference()}.{pad.GetNumber()}")
                continue

            sx, sy = site
            # stub track from the pad to the via, when offset
            if off:
                tr = pcbnew.PCB_TRACK(board)
                tr.SetStart(pcbnew.VECTOR2I(int(round(cx * 1e6)), int(round(cy * 1e6))))
                tr.SetEnd(pcbnew.VECTOR2I(int(round(sx * 1e6)), int(round(sy * 1e6))))
                tr.SetWidth(int(TRACK_W * 1e6))
                tr.SetLayer(pcbnew.F_Cu)
                tr.SetNetCode(gcode)
                board.Add(tr)

            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(int(round(sx * 1e6)), int(round(sy * 1e6))))
            v.SetWidth(int(VIA_D * 1e6))
            v.SetDrill(int(VIA_DRILL * 1e6))
            v.SetNetCode(gcode)
            v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            board.Add(v)

            if off:
                added_offset += 1
            else:
                added_here += 1

    pcbnew.SaveBoard(dst, board)
    print(f"vias at pad centre      : {added_here}")
    print(f"vias OFFSET + GND stub  : {added_offset}")
    print(f"pads already stitched   : {already}")
    print(f"UNRESOLVABLE            : {unresolvable}")
    if bad:
        print("  unresolved pads:", ", ".join(bad[:20]))
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

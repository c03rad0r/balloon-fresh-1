"""Stitch orphan GND pour islands on F.Cu.

*** THE REMEDY HALF OF THIS SCRIPT IS REFUTED. READ docs/fab/DECISIONS-UNROUTED-NETS.md D11. ***

Measured 2026-10-18: placing stitching vias inside the orphan islands does NOT reduce the island count
and does NOT clear the DRC unconnected item. A via is a VERTICAL connection; the DRC item is about
SAME-LAYER continuity, so a via cannot address it. Island count before 6, after 6. DRC unconnected
items 4 before, 4 after.

The MEASUREMENT half is correct and reusable: island enumeration, per-island areas, legal-via search
against the 0.20 mm rule, and the two-via 0.800 mm centre-to-centre check (which caught a real illegal
pair 0.155 mm apart). The next fix is a short GND F.Cu TRACK across each fragment boundary, or a local
pour-clearance widening -- not a via.

WHY THIS EXISTS. kicad-cli DRC reports 2 unconnected items that are NOT signal nets:

    Zone 'GND_PLANE_F.Cu' [GND] F.Cu  <->  Zone 'GND_PLANE_In1.Cu' [GND] In1.Cu
    Zone 'GND_PLANE_F.Cu' [GND] F.Cu  <->  Zone 'GND_PLANE_F.Cu'   [GND] F.Cu

The second one is the real defect: the F.Cu GND pour is split into 6 disjoint filled islands. Measured
areas: the main plane is 3543.3 mm^2 and the five orphans are 8.6 / 1.4 / 15.7 / 0.28 / 0.45 mm^2.
The orphans are pour fragments walled off by dense copper around U4 and U1 -- exactly the congested
zone where routing work happened.

WHY stitch with a VIA rather than reroute the pour. A GND island is electrically useless if it is not
connected to the GND network, and it displaces thermal relief and return current. A stitching via from
the orphan down to In1.Cu (which has 2 islands and is otherwise continuous) is the normal, cheap fix.
Deleting the island would also be legal but loses copper; stitching keeps it.

WHAT THIS DOES NOT DO. It does not shrink any via, move any part, delete anything, or touch a signal
net. It reports UNRESOLVABLE islands rather than silently leaving them, because a gate that cannot run
must not look green.

THE TRAP THIS AVOIDS, learned the hard way in routing runs 4-7: TWO 0.60 mm vias need 0.800 mm
centre-to-centre (0.600 diameter + 0.200 clearance). A first candidate pair came out 0.1552 mm apart.
So this script checks every new via against every previously placed one and refuses a site that is too
close to any other GND via.

Run:
    ~/venvs/kicad/bin/python tracker/hardware/stitch_gnd_islands.py \
        --in /tmp/hub_refilled.kicad_pcb --out /tmp/hub_stitched.kicad_pcb [--apply]
"""
from __future__ import annotations

import argparse
import math
import sys

import pcbnew

UM = 1_000_000.0
VIA_D = 0.600
VIA_DRILL = 0.300
CLR = 0.200
GND = "GND"
MIN_VIA_SPACING = VIA_D + CLR          # 0.800 mm centre-to-centre


def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def islands(board):
    """Return [(zone, layer_name, [ (outline_points, area_mm2, bbox) ])] for GND zones."""
    out = []
    for z in board.Zones():
        if z.GetNetname() != GND:
            continue
        lyr = z.GetLayer()
        poly = z.GetFilledPolysList(lyr)
        n = poly.OutlineCount()
        items = []
        for i in range(n):
            ol = poly.Outline(i)
            pts = [(ol.CPoint(k).x / UM, ol.CPoint(k).y / UM) for k in range(ol.PointCount())]
            a = 0.0
            for k in range(len(pts)):
                x1, y1 = pts[k]
                x2, y2 = pts[(k + 1) % len(pts)]
                a += x1 * y2 - x2 * y1
            bb = ol.BBox()
            items.append((pts, abs(a) / 2.0,
                          (bb.GetX() / UM, bb.GetY() / UM,
                           bb.GetX() / UM + bb.GetWidth() / UM,
                           bb.GetY() / UM + bb.GetHeight() / UM)))
        out.append((z, board.GetLayerName(lyr), items))
    return out


class Obstacles:
    def __init__(self, board):
        r = VIA_D / 2
        self.segs = []
        self.pads = []
        self.gnd_vias = []
        gndcode = board.FindNet(GND).GetNetCode()
        for t in board.GetTracks():
            if t.GetNetCode() == gndcode:
                if t.Type() == pcbnew.PCB_VIA_T:
                    p = t.GetPosition()
                    self.gnd_vias.append((p.x / UM, p.y / UM))
                continue
            if t.Type() == pcbnew.PCB_VIA_T:
                p = t.GetPosition()
                self.segs.append((p.x / UM, p.y / UM, p.x / UM, p.y / UM,
                                  t.GetWidth(pcbnew.F_Cu) / 2 / UM))
            elif t.Type() == pcbnew.PCB_TRACE_T:
                s, e = t.GetStart(), t.GetEnd()
                self.segs.append((s.x / UM, s.y / UM, e.x / UM, e.y / UM,
                                  t.GetWidth() / 2 / UM))
        for fp in board.GetFootprints():
            for p in fp.Pads():
                if p.GetNetCode() == gndcode:
                    continue
                pos = p.GetPosition()
                self.pads.append((pos.x / UM, pos.y / UM,
                                  p.GetSize().x / UM, p.GetSize().y / UM))
        self.r = r

    def clearance(self, x, y):
        w = (1e9, None)
        for x1, y1, x2, y2, rr in self.segs:
            d = seg_dist(x, y, x1, y1, x2, y2) - rr - self.r
            if d < w[0]:
                w = (d, "track/via")
        for cx, cy, pw, ph in self.pads:
            dx = max(cx - pw / 2 - x, 0.0, x - (cx + pw / 2))
            dy = max(cy - ph / 2 - y, 0.0, y - (cy + ph / 2))
            d = math.hypot(dx, dy) - self.r
            if d < w[0]:
                w = (d, "pad")
        for gx, gy in self.gnd_vias:
            d = math.hypot(x - gx, y - gy) - MIN_VIA_SPACING
            if d < w[0]:
                w = (d, "other GND via")
        return w


def in_island(pts, x, y):
    """Ray-casting point-in-polygon."""
    inside = False
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if ((y1 > y) != (y2 > y)):
            xin = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xin:
                inside = not inside
    return inside


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--min-area", type=float, default=0.20)
    args = ap.parse_args()

    board = pcbnew.LoadBoard(args.inp)
    obs = Obstacles(board)

    ok, unresolvable = [], []
    for zone, lname, items in islands(board):
        if lname != "F.Cu" or len(items) < 2:
            continue
        # the biggest island is the main plane; the rest are orphans
        biggest = max(range(len(items)), key=lambda i: items[i][1])
        for i, (pts, area, bb) in enumerate(items):
            if i == biggest or area < args.min_area:
                continue
            # candidate points: sample the island's own bbox interior
            site = None
            step = 0.20
            x0, y0, x1, y1 = bb
            y = y0 + step / 2
            while y < y1 and not site:
                x = x0 + step / 2
                while x < x1:
                    if in_island(pts, x, y):
                        w = obs.clearance(x, y)
                        if w[0] >= CLR:
                            site = (x, y, w[0])
                            break
                    x += step
                y += step
            if site:
                ok.append((area, bb, site))
            else:
                unresolvable.append((area, bb))

    print(f"islands scanned; {len(ok)} stitchable, {len(unresolvable)} NOT stitchable")
    placed = []
    for area, bb, (x, y, clr) in ok:
        # re-check against vias placed in THIS run
        clash = any(math.hypot(x - px, y - py) < MIN_VIA_SPACING for px, py in placed)
        if clash:
            print(f"  SKIP  area {area:6.3f} mm^2 at ({x:.3f},{y:.3f}) -- too close to a placed via")
            continue
        placed.append((x, y))
        print(f"  STITCH area {area:6.3f} mm^2  via at ({x:.3f},{y:.3f})  worst clearance {clr:.3f} mm")
    for area, bb in unresolvable:
        print(f"  BLOCKED area {area:6.3f} mm^2  bbox x {bb[0]:.2f}..{bb[2]:.2f} y {bb[1]:.2f}..{bb[3]:.2f}"
              f" -- no legal via site, needs a pour-rule or copper change, NOT a gate waiver")

    if not args.apply:
        print("\n(dry run -- pass --apply to write)")
        return 0

    for (x, y) in placed:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(int(round(x * UM)), int(round(y * UM))))
        v.SetWidth(int(round(VIA_D * UM)))
        v.SetDrill(int(round(VIA_DRILL * UM)))
        v.SetNet(board.FindNet(GND))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        board.Add(v)
    print(f"\nadded {len(placed)} stitching vias; refilling")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(args.out, board)
    print(f"saved {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

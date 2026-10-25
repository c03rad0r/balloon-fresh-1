#!/usr/bin/env python3
"""hand_route_test.py -- can a HUMAN place the stubborn nets on 2 layers?

WHY (2026-10-22). The router reports /EN, /SPI2_SCK and /F33_RESET_N as plain NO-PATH
failures, and every automated lever failed to add them (five measured). "No path found"
is also the exact symptom a WEAK SEARCH produces, so the router's failure does not prove
the board lacks capacity.

This test answers the capacity question directly and independently of the router: for each
stubborn net, walk a straight line from pad to pad and report whether a normal track corridor
exists. It does NOT route -- it measures whether one is available.

Method: sample the line between the two pad centres at a fine step; at each sample ask the
connector-aware obstacle model whether that point is free on F.Cu or B.Cu (with the track's
half-width and the clearance rule applied). A hop is "clear on one layer" if ANY single layer
is unobstructed for the whole run. If neither layer is clear, report WHERE it is first blocked
and by what, which is what a human needs to judge a detour.

This is deliberately a STRAIGHT-LINE test, not a router: it can only under-report feasibility
(a human may detour). So:
    straight line clear  -> capacity is NOT the limit; the router's search is the problem
    straight line blocked -> inconclusive, but the blocking item is printed for a human to
                            judge whether a detour exists

Usage: hand_route_test.py [--board B] [--net /EN] [--net /SPI2_SCK ...] [--step 0.05]
Exit: 0 = every net has a clear straight corridor on some layer; 1 = at least one is blocked;
      2 = could not run.
"""
import argparse
import os
import sys

import pcbnew

UM = 1_000_000.0
CLEAR = 0.200          # mm copper-to-copper (project rule, min_clearance)
TRACK_W = 0.200        # mm
EDGE_CLEAR = 0.500     # mm min_copper_edge_clearance


def rects_and_edges(board):
    """All pad rects (with net) plus the board/seat edge segments."""
    pads = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            pads.append({
                "ref": ref, "num": p.GetNumber(), "net": p.GetNetname() or "",
                "x0": bb.GetX() / UM, "y0": bb.GetY() / UM,
                "x1": (bb.GetX() + bb.GetWidth()) / UM,
                "y1": (bb.GetY() + bb.GetHeight()) / UM,
                "layers": [l for l in (pcbnew.F_Cu, pcbnew.B_Cu) if p.IsOnLayer(l)],
            })
    # EDGE handling. The board's OWN outline is one diagonal PCB_SHAPE whose bounding box is the
    # whole board -- treating that bbox as an obstacle blocks EVERY sample on the board, which is
    # what my first version did (every net "BLOCKED by edge (-0.1,-0.1)-(72.0,80.0)" at its own
    # start pad). Only FOOTPRINT-OWNED edge cuts are interior cutouts that copper must avoid, and
    # each of those is a thin segment whose bbox is a valid proxy.
    edges = []
    for fp in board.GetFootprints():
        for gi in fp.GraphicalItems():
            if gi.GetLayer() == pcbnew.Edge_Cuts:
                bb = gi.GetBoundingBox()
                edges.append((bb.GetX() / UM, bb.GetY() / UM,
                              (bb.GetX() + bb.GetWidth()) / UM,
                              (bb.GetY() + bb.GetHeight()) / UM))
    tracks = []
    for t in board.GetTracks():
        if "VIA" in str(type(t)):
            p = t.GetPosition()
            tracks.append(("via", t.GetNetname() or "", None, p.x / UM, p.y / UM,
                           p.x / UM, p.y / UM, 0.5))
        elif "TRACK" in str(type(t)):
            s, e = t.GetStart(), t.GetEnd()
            tracks.append(("track", t.GetNetname() or "", t.GetLayer(),
                           s.x / UM, s.y / UM, e.x / UM, e.y / UM, TRACK_W))
    return pads, edges, tracks


def pt_rect_dist(x, y, r):
    dx = max(r[0] - x, 0.0, x - r[2])
    dy = max(r[1] - y, 0.0, y - r[3])
    return (dx * dx + dy * dy) ** 0.5


def pt_seg_dist(px, py, x1, y1, x2, y2):
    vx, vy = x2 - x1, y2 - y1
    L2 = vx * vx + vy * vy
    if L2 < 1e-12:
        return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - x1) * vx + (py - y1) * vy) / L2))
    qx, qy = x1 + t * vx, y1 + t * vy
    return ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5


def blockers_at(x, y, layer, own, pads, edges, tracks):
    """Return (kind, name) for the first thing too close to (x,y) on `layer`, else None."""
    hw = TRACK_W / 2
    for p in pads:
        if p["net"] == own:
            continue
        if p["layers"] and layer not in p["layers"]:
            continue
        d = pt_rect_dist(x, y, (p["x0"], p["y0"], p["x1"], p["y1"]))
        if d < CLEAR + hw:
            return ("pad", f'{p["ref"]}.{p["num"]} ({p["net"]})')
    for kind, net, tlayer, x1, y1, x2, y2, w in tracks:
        if net == own:
            continue
        if kind == "track" and tlayer != layer:
            continue
        d = pt_seg_dist(x, y, x1, y1, x2, y2)
        if d < CLEAR + hw + w / 2:
            return (kind, net)
    for (ex0, ey0, ex1, ey1) in edges:
        # treat an edge cutout as a line of zero width
        if pt_rect_dist(x, y, (ex0, ey0, ex1, ey1)) < EDGE_CLEAR:
            return ("edge", f"({ex0:.1f},{ey0:.1f})-({ex1:.1f},{ey1:.1f})")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "hub_board_v10.kicad_pcb"))
    ap.add_argument("--net", action="append", default=[])
    ap.add_argument("--step", type=float, default=0.05)
    args = ap.parse_args()

    if not os.path.exists(args.board):
        print(f"HANDTEST: CANNOT RUN -- no board at {args.board}")
        return 2
    b = pcbnew.LoadBoard(args.board)
    pads, edges, tracks = rects_and_edges(b)

    nets = args.net or sorted({p["net"] for p in pads if p["net"] and
                               p["net"] not in ("GND", "+3V3")})
    verdicts = {}
    for net in nets:
        ps = [p for p in pads if p["net"] == net]
        if len(ps) != 2:
            print(f"HANDTEST: {net}: {len(ps)} pad(s) -- skipping (need exactly 2)")
            continue
        a, c = ps
        ax, ay = (a["x0"] + a["x1"]) / 2, (a["y0"] + a["y1"]) / 2
        cx, cy = (c["x0"] + c["x1"]) / 2, (c["y0"] + c["y1"]) / 2
        dist = ((cx - ax) ** 2 + (cy - ay) ** 2) ** 0.5
        n = max(2, int(dist / args.step))
        res = {}
        for layer, lname in ((pcbnew.F_Cu, "F.Cu"), (pcbnew.B_Cu, "B.Cu")):
            first = None
            for i in range(1, n):
                t = i / n
                x, y = ax + (cx - ax) * t, ay + (cy - ay) * t
                blk = blockers_at(x, y, layer, net, pads, edges, tracks)
                if blk:
                    first = (blk, x, y)
                    break
            res[lname] = first
        clear = [ln for ln, f in res.items() if f is None]
        verdicts[net] = bool(clear)
        print(f"\nHANDTEST: {net}  {a['ref']}.{a['num']} -> {c['ref']}.{c['num']}  "
              f"{dist:.2f}mm  pads both on "
              f"{'F.Cu' if pcbnew.F_Cu in a['layers'] else '?'}")
        if clear:
            print(f"   CLEAR on: {', '.join(clear)}  <- a straight corridor EXISTS")
        else:
            for ln, f in res.items():
                blk, x, y = f
                print(f"   {ln}: BLOCKED at ({x:.2f},{y:.2f}) by {blk[0]} {blk[1]}")

    ok = sum(1 for v in verdicts.values() if v)
    print(f"\nHANDTEST: {ok}/{len(verdicts)} net(s) have a clear straight corridor on ONE layer")
    if ok == len(verdicts) and verdicts:
        print("HANDTEST: VERDICT -- capacity is NOT the limit; the router's SEARCH is.")
        return 0
    print("HANDTEST: VERDICT -- inconclusive (straight line blocked); see the blocker above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

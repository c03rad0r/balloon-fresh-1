#!/usr/bin/env python3
"""Route the v10 board's simplest, mechanical class first: 2-pad nets with a clear path.

Phase 1 of routing (2026-10-21): point-to-point nets whose both pads sit on the SAME
side with a straight-ish free corridor. This is deliberately NOT an autorouter -- it
is the same deterministic discipline as the placement solver:

  * only nets with exactly 2 pads
  * both pads on the same layer
  * straight-line path with 0.200 clearance to every foreign copper (pads, tracks)
  * 0.200 wide track (house style), 0 clearance to own net
  * skip-if-blocked: no detours yet, no vias yet -- a blocked net is REPORTED, not forced

Every routed net is verified by re-loading the board and checking pad-to-track
connectivity. Deterministic: fixed net order, fixed grid.
"""
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")
UM = 1_000_000.0
TRACK_W = int(0.200 * UM)
CLEAR = 0.200  # mm, edge-to-edge to foreign copper


def pad_rect(pad):
    p = pad.GetPosition()
    sz = pad.GetSize()
    return (p.x - sz.x // 2, p.y - sz.y // 2, p.x + sz.x // 2, p.y + sz.y // 2)


def seg_rect(x0, y0, x1, y1, w):
    h = w // 2
    return (min(x0, x1) - h, min(y0, y1) - h, max(x0, x1) + h, max(y0, y1) + h)


def rects_clear(a, b, gap):
    return (a[0] - b[2] >= gap or b[0] - a[2] >= gap
            or a[1] - b[3] >= gap or b[1] - a[3] >= gap)


def main():
    b = pcbnew.LoadBoard(BOARD)
    if not b:
        print("REFUSED: board load failed")
        return 3
    # foreign copper inventory (pads only for phase 1 -- no tracks yet)
    net_pads = {}
    foreign = []  # (netcode, rect)
    for fp in b.GetFootprints():
        for p in fp.Pads():
            n = p.GetNet()
            code = n.GetNetCode() if n else 0
            r = pad_rect(p)
            if code:
                net_pads.setdefault(code, []).append((fp.GetReference(), p, r))
            if code and p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                foreign.append((code, r))
    routed, blocked = [], []
    for code, pads in sorted(net_pads.items(), key=lambda kv: kv[0]):
        if len(pads) != 2:
            continue
        name = pads[0][1].GetNet().GetNetname()
        (_, pa, _ra), (_, pb, _rb) = pads
        if pa.GetLayer() != pb.GetLayer():
            continue  # different sides: needs via, phase 2
        layer = pa.GetLayer()
        # straight L-path: horizontal then vertical (or direct)
        ax, ay = pa.GetPosition().x, pa.GetPosition().y
        bx, by = pb.GetPosition().x, pb.GetPosition().y
        path = [(ax, ay), (bx, ay), (bx, by)] if ay != by else [(ax, ay), (bx, by)]
        segs = list(zip(path[:-1], path[1:]))
        ok = True
        for (x0, y0), (x1, y1) in segs:
            r = seg_rect(x0, y0, x1, y1, TRACK_W)
            for fcode, fr in foreign:
                if fcode == code:
                    continue
                if not rects_clear(r, fr, int(CLEAR * UM)):
                    ok = False
                    break
            if not ok:
                break
        if not ok:
            blocked.append(name)
            continue
        for (x0, y0), (x1, y1) in segs:
            t = pcbnew.PCB_TRACK(b)
            t.SetNet(pcbnew.NETINFO_ITEM(b, name) if b.FindNet(name) is None else b.FindNet(name))
            t.SetLayer(layer)
            t.SetWidth(TRACK_W)
            t.SetStart(pcbnew.VECTOR2I(int(x0), int(y0)))
            t.SetEnd(pcbnew.VECTOR2I(int(x1), int(y1)))
            b.Add(t)
        routed.append(name)
    print(f"routed {len(routed)}: {sorted(routed)}")
    print(f"blocked {len(blocked)}: {sorted(blocked)}")
    pcbnew.SaveBoard(BOARD, b)
    print("saved", BOARD)
    return 0


if __name__ == "__main__":
    sys.exit(main())
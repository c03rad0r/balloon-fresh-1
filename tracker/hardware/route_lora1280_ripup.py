#!/usr/bin/env python3
"""Rip-up-and-retry pass for the LoRa1280 interface.

The base router (route_lora1280_independent.py) routes 6/9 with a hard-first ordering. Ordering
alone cannot fix the last three: SPI1_SCK, E28_DIO2 and E28_DIO3 lose their corridor to copper that
an EARLIER net legitimately occupies. The only way past that is to take the earlier net out, route
the blocked one, then put the removed net back -- rip-up and retry.

Method, bounded on purpose:

  1. Route the whole set hard-first, remembering for each net the claim boxes its copper stamped
     into the obstacle grid.
  2. For each failed net F, try removing ONE already-routed net X at a time -- cheapest first, and
     only those whose claims come near F's direct corridor. Rebuild the grid from the base plus
     every kept net's claims, route F, then route X. Accept the first pair that both succeed.
  3. Repeat for a few rounds, under a wall-clock budget.

Nothing here relaxes a rule. CLEAR stays 0.30 mm (= 0.20 board clearance + 0.10 track half-width),
the board-edge keep-out stays 0.60 mm, and zones are refilled before saving so the GND pour knits
around the result instead of fighting it.

Usage:
    route_lora1280_ripup.py --board <in> --out <out> [--budget 300]
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lora1280_independent as R   # noqa: E402

MM = R.MM
F, B = R.F, R.B
CLEAR = R.CLEAR
NETS = R.NETS
HARD_FIRST = R.HARD_FIRST


def boxes_for(run):
    """The exact claim rectangles a run stamps (mirrors R.stamp, without touching a grid)."""
    out = []
    for k in range(1, len(run)):
        la, ia, ja = run[k - 1]
        lb, ib, jb = run[k]
        if la != lb:
            px, py = R.Grid.pos(CUR[0], ia, ja)
            for lay in (la, lb):
                out.append((lay, px - R.VIA_D / 2 - CLEAR, py - R.VIA_D / 2 - CLEAR,
                            px + R.VIA_D / 2 + CLEAR, py + R.VIA_D / 2 + CLEAR))
            continue
        xa, ya = R.Grid.pos(CUR[0], ia, ja)
        xb, yb = R.Grid.pos(CUR[0], ib, jb)
        out.append((la, min(xa, xb) - R.TRACK_W / 2 - CLEAR, min(ya, yb) - R.TRACK_W / 2 - CLEAR,
                    max(xa, xb) + R.TRACK_W / 2 + CLEAR, max(ya, yb) + R.TRACK_W / 2 + CLEAR))
    return out


CUR = [None]        # holds the reference Grid, so pos() can be called without a live grid


def blank(base):
    g = R.Grid.__new__(R.Grid)
    g.__dict__.update(base.__dict__)
    g.b = {F: [r[:] for r in base.b[F]], B: [r[:] for r in base.b[B]]}
    return g


def replay(g, claims, skip=()):
    for net, boxes in claims.items():
        if net in skip:
            continue
        for lay, x0, y0, x1, y1 in boxes:
            g.claim(lay, x0, y0, x1, y1, net_codes[net])


net_codes = {}


def endpoints(pads, net):
    pl = pads.get(net, [])
    if len(pl) < 2:
        return None
    a, b = pl[0], pl[1]
    return a, b


def try_route(g, pads, net, cache):
    a, b = endpoints(pads, net)
    if a is None:
        return None, "no pads"
    (_, r1, n1, x0, y0, x1, y1, l1, code), (_, r2, n2, u0, v0, u1, v1, l2, _c) = a, b
    start = (*g.cell((x0 + x1) / 2, (y0 + y1) / 2), l1[0])
    goal = (*g.cell((u0 + u1) / 2, (v0 + v1) / 2), l2[0])
    path, why = R.route(g, start, goal, cache, code)
    if not path:
        return None, why
    return R.simplify(path), None


def near(boxes, target, margin=3.0):
    tx0, ty0, tx1, ty1 = target
    for _lay, x0, y0, x1, y1 in boxes:
        if x0 < tx1 + margin and x1 > tx0 - margin and y0 < ty1 + margin and y1 > ty0 - margin:
            return True
    return False


def corridor(pads, net):
    a, b = endpoints(pads, net)
    return (min(a[3], b[3]), min(a[4], b[4]), max(a[5], b[5]), max(a[6], b[6]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--budget", type=float, default=300.0)
    a = ap.parse_args()
    t0 = time.time()

    board = pcbnew.LoadBoard(a.board)
    ds = board.GetDesignSettings()
    R.VIA_DRILL = max(ds.m_MinThroughDrill / MM, 0.30)
    ring = getattr(ds, "m_ViasMinAnnularWidth", 0) / MM
    R.VIA_D = max(0.50, R.VIA_DRILL + 2.0 * ring + 0.04)
    print(f"via drill {R.VIA_DRILL:.2f} dia {R.VIA_D:.2f}")

    base, padlist = R.build(board)
    CUR[0] = base
    pads = {}
    for p in padlist:
        pads.setdefault(p[0], []).append(p)
        net_codes[p[0]] = p[8]
    cache = {}

    order = HARD_FIRST + [n for n in NETS if n not in HARD_FIRST]
    g = blank(base)
    runs, claims = {}, {}
    for net in order:
        run, why = try_route(g, pads, net, cache)
        if not run:
            print(f"  {net}: FAILED ({why})")
            continue
        runs[net] = run
        claims[net] = boxes_for(run)
        R.stamp(g, run, net_codes[net])
        print(f"  {net}: routed")
    print(f"pass 1: {len(runs)}/{len(NETS)}")

    for rnd in range(3):
        failed = [n for n in NETS if n not in runs]
        if not failed:
            break
        progress = False
        for fn in failed:
            if time.time() - t0 > a.budget:
                print("budget reached")
                break
            target = corridor(pads, fn)
            cands = sorted(runs, key=lambda n: len(claims[n]))
            for x in cands:
                if not near(claims[x], target):
                    continue
                g2 = blank(base)
                replay(g2, claims, skip=(x,))
                run_f, why = try_route(g2, pads, fn, cache)
                if not run_f:
                    continue
                R.stamp(g2, run_f, net_codes[fn])
                run_x, why2 = try_route(g2, pads, x, cache)
                if not run_x:
                    continue
                # both fit -> accept
                runs[fn], claims[fn] = run_f, boxes_for(run_f)
                runs[x], claims[x] = run_x, boxes_for(run_x)
                print(f"  rip-up round {rnd}: {x} removed -> {fn} routed, {x} re-routed")
                progress = True
                break
        if not progress:
            print(f"  rip-up round {rnd}: no further improvement")
            break

    print(f"final {len(runs)}/{len(NETS)}: {sorted(runs)}")
    missing = [n for n in NETS if n not in runs]
    if missing:
        print(f"still missing: {missing}")

    for net, run in runs.items():
        ncode = board.FindNet(net).GetNetCode()
        for k in range(1, len(run)):
            la, ia, ja = run[k - 1]
            lb, ib, jb = run[k]
            if la != lb:
                px, py = R.Grid.pos(base, ia, ja)
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pcbnew.VECTOR2I(int(px * MM), int(py * MM)))
                v.SetWidth(int(R.VIA_D * MM))
                v.SetDrill(int(R.VIA_DRILL * MM))
                v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetLayerPair(F, B)
                v.SetNetCode(ncode)
                board.Add(v)
                continue
            xa, ya = R.Grid.pos(base, ia, ja)
            xb, yb = R.Grid.pos(base, ib, jb)
            if abs(xa - xb) < 1e-9 and abs(ya - yb) < 1e-9:
                continue
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(int(xa * MM), int(ya * MM)))
            t.SetEnd(pcbnew.VECTOR2I(int(xb * MM), int(yb * MM)))
            t.SetWidth(int(R.TRACK_W * MM))
            t.SetLayer(la)
            t.SetNetCode(ncode)
            board.Add(t)

    if board.Zones():
        print(f"refilling {len(board.Zones())} zone(s)")
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(a.out, board)
    print(f"wrote {a.out} in {time.time()-t0:.0f}s")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())

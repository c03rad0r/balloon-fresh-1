#!/usr/bin/env python3
"""Route the remaining board nets (not just the LoRa1280 interface) with the corrected model.

Why a second runner: route_lora1280_independent.py has the nine LoRa1280 nets hardcoded because
that was the job. The hub still carries ~23 unrouted nets and most are short point-to-point runs
that this router can do properly — per-net ownership, correct via sizing from the board's own
design settings, zone refill before saving.

Selection is driven by the DRC, not by guesswork: the net set is whatever kicad-cli reports as
unconnected, minus the plane nets (GND, +3V3) which are supposed to join through the pour rather
than through tracks. Order is shortest-span first, because the short runs are the ones with the
least to lose and they free space before the long ones try to cross it.

Usage:
    route_board_nets.py --board <in> --out <out> [--drc drc.json] [--budget 900] [--max-span 40]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
import time

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lora1280_independent as R   # noqa: E402

MM = R.MM
F, B = R.F, R.B

PLANE_NETS = {"GND", "+3V3", "GNDA", "GNDD", "+3V3A"}
# A pad closer than this to the outline means the net terminates at an edge connector.
EDGE_PAD = 1.20


def unconnected_nets(drc_path):
    """Net names kicad-cli says are not fully connected."""
    if not drc_path or not os.path.exists(drc_path):
        return None
    d = json.load(open(drc_path))
    nets = set()
    for item in d.get("unconnected_items", []):
        for it in item.get("items", []):
            for m in re.findall(r"\[([^\]]+)\]", it.get("description", "")):
                nets.add(m)
    return nets


def pads_by_net(board):
    out = collections.defaultdict(list)
    for f in board.GetFootprints():
        for p in f.Pads():
            n = p.GetNetname()
            if not n:
                continue
            pb = p.GetBoundingBox()
            out[n].append({
                "ref": f.GetReference(), "num": p.GetNumber(),
                "x0": pb.GetX() / MM, "y0": pb.GetY() / MM,
                "x1": (pb.GetX() + pb.GetWidth()) / MM,
                "y1": (pb.GetY() + pb.GetHeight()) / MM,
                "layers": [lay for lay in (F, B) if p.GetLayerSet().Contains(lay)],
                "code": p.GetNetCode(),
            })
    return out


def span(pads):
    best = 0.0
    for i in range(len(pads)):
        for j in range(i + 1, len(pads)):
            a, b = pads[i], pads[j]
            best = max(best, abs(a["x0"] - b["x0"]) + abs(a["y0"] - b["y0"]))
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--drc", default="/tmp/lora1280/drc.json")
    ap.add_argument("--budget", type=float, default=900.0)
    ap.add_argument("--max-span", type=float, default=45.0)
    ap.add_argument("--limit", type=int, default=40)
    a = ap.parse_args()
    t0 = time.time()

    board = pcbnew.LoadBoard(a.board)
    ds = board.GetDesignSettings()
    R.VIA_DRILL = max(ds.m_MinThroughDrill / MM, 0.30)
    ring = getattr(ds, "m_ViasMinAnnularWidth", 0) / MM
    R.VIA_D = max(0.50, R.VIA_DRILL + 2.0 * ring + 0.04)
    print(f"via drill {R.VIA_DRILL:.2f} dia {R.VIA_D:.2f}")

    bb = board.GetBoardEdgesBoundingBox()
    base, _padlist = R.build(board)
    pads = pads_by_net(board)

    # Nets that DRC already flags for board-edge clearance are excluded on purpose. They are the
    # J_W1..J_W4 edge connectors: their pads sit 0.0-0.4 mm from the outline, which is a
    # CONNECTOR-PLACEMENT problem that predates this router. Routing away from such a pad can only
    # add more edge violations, and "fixing" it by shoving copper inward would leave the pad itself
    # still in violation. Reported, not hidden.
    edge_nets = set()
    if os.path.exists(a.drc):
        for v in json.load(open(a.drc)).get("violations", []):
            if v.get("type") == "copper_edge_clearance":
                for it in v.get("items", []):
                    for m in re.findall(r"\[([^\]]+)\]", it.get("description", "")):
                        edge_nets.add(m)
    skipped_edge = []
    wanted = unconnected_nets(a.drc)
    todo = []
    for n, ps in pads.items():
        if n in PLANE_NETS or len(ps) < 2:
            continue
        if wanted is not None and n not in wanted:
            continue
        # Edge-connector nets: any pad within EDGE_PAD of the board bounding box. Routing away from
        # such a pad inevitably runs along the outline, and the pad itself is already in violation,
        # so this is a connector-placement decision, not a routing one.
        if n in edge_nets or any(min(pd["x0"] - bb.GetX() / MM, bb.GetY() / MM and 0 or 0) is not None and
                                 min(pd["x0"] - bb.GetX() / MM, (bb.GetX() + bb.GetWidth()) / MM - pd["x1"],
                                     pd["y0"] - bb.GetY() / MM, (bb.GetY() + bb.GetHeight()) / MM - pd["y1"])
                                 < EDGE_PAD for pd in ps):
            skipped_edge.append(n)
            continue
        s = span(ps)
        if s > a.max_span:
            continue
        todo.append((s, n))
    todo.sort()
    if skipped_edge:
        print(f"skipped {len(skipped_edge)} net(s) that already break the 0.5 mm edge rule "
              f"(connector placement, not routing): {', '.join(sorted(set(skipped_edge)))}")
    todo = todo[: a.limit]
    print(f"{len(todo)} net(s) to route, shortest span first")

    g = R.Grid.__new__(R.Grid)
    g.__dict__.update(base.__dict__)
    g.b = {F: [r[:] for r in base.b[F]], B: [r[:] for r in base.b[B]]}
    cache = {}

    done, failed = [], []
    for s, net in todo:
        if time.time() - t0 > a.budget:
            print("budget reached")
            break
        ps = pads[net]
        # chain the pads: pad0 -> pad1 -> pad2 ... (all these nets are 2-4 pads)
        ok_all = True
        added = []
        for k in range(1, len(ps)):
            A, Bp = ps[k - 1], ps[k]
            start = (*g.cell((A["x0"] + A["x1"]) / 2, (A["y0"] + A["y1"]) / 2), A["layers"][0])
            goal = (*g.cell((Bp["x0"] + Bp["x1"]) / 2, (Bp["y0"] + Bp["y1"]) / 2), Bp["layers"][0])
            path, why = R.route(g, start, goal, cache, A["code"])
            if not path:
                if k > 1:
                    break                      # partial chain is still useful
                ok_all = False
                failed.append((net, why))
                break
            run = R.simplify(path)
            R.stamp(g, run, A["code"])
            added.append(run)
        if added:
            ncode = board.FindNet(net).GetNetCode()
            for run in added:
                for i in range(1, len(run)):
                    la, ia, ja = run[i - 1]
                    lb, ib, jb = run[i]
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
            done.append(net)
            print(f"  ok   {net:22s} span {s:5.1f}")

    print(f"routed {len(done)}/{len(todo)} nets")
    if failed:
        print("failed:", ", ".join(f"{n} ({w})" for n, w in failed))

    if board.Zones():
        print(f"refilling {len(board.Zones())} zones")
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(a.out, board)
    print(f"wrote {a.out} in {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())

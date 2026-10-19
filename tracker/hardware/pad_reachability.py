#!/usr/bin/env python3
"""pad_reachability.py — DRC-legal pad escape measurement (corrected 2026-10-19).

The predecessor answered "is the pad legally reachable to clear B.Cu?" by
(a) measuring B.Cu for F.Cu-only SMD pads, (b) comparing millimetres against
nanometre thresholds, and (c) printing PAD ESCAPE CLEAR while tagging every
obstacle BLOCKING. See the case study:
manager skill firmware/kicad-board-audit-rules/references/pad-escape-verdict-contradiction.md

This implementation is the validated kernel (same as
skills/firmware/kicad-board-audit-rules/scripts/fcu_escape_feasibility.py):
- pad escape ring = half-diagonal + clearance (pad EDGE), never track_w/2+clearance;
- millimetres throughout;
- measures the layers the pad's own LayerSet can reach (SMD: F.Cu only);
- self-checks the verdict against its own obstacles/vias before printing and
  exits non-zero on any disagreement.

WHAT IT CANNOT ESTABLISH: escapable != routable. It says a pad's own copper can
legally leave its local pad field; it says nothing about a path to the other
endpoint and it is not a DRC run.

Usage (KiCad python):
  ~/venvs/kicad/bin/python tracker/hardware/pad_reachability.py \
      [--board tracker/hardware/hub_board_v9.kicad_pcb] \
      [--pad U1.8 --pad U4.17 ...] [--json]
"""
from __future__ import annotations

import argparse
import json
import math
import sys

import pcbnew

try:
    from pad_geometry_kernel import (U, Item, poly_edges, poly_pts, pad_item,
                                     collect, point_in_poly, validate)
except ImportError:  # pragma: no cover
    raise SystemExit("pad_geometry_kernel.py must sit beside pad_reachability.py")

DEFAULT_BOARD = "tracker/hardware/hub_board_v9.kicad_pcb"
DEFAULT_PADS = ["U1.8", "U1.22", "U4.17", "U4.18"]
COPPER_LAYERS = [(pcbnew.F_Cu, "F.Cu"), (pcbnew.In1_Cu, "In1.Cu"),
                 (pcbnew.In2_Cu, "In2.Cu"), (pcbnew.B_Cu, "B.Cu")]
EPS = 1e-9

class Rules:
    def __init__(self, board):
        ds = board.GetDesignSettings()
        self.clearance = max(ds.m_MinClearance, ds.GetSmallestClearanceValue()) / U
        self.track_w = ds.GetCurrentTrackWidth() / U
        self.via_dia = ds.GetCurrentViaSize() / U
        self.via_drill = ds.GetCurrentViaDrill() / U
        self.via_min_dia = ds.m_ViasMinSize / U
        self.hole_to_hole = ds.m_HoleToHoleMin / U

    @property
    def trace_edge_to_copper(self):
        return self.track_w / 2.0 + self.clearance


def pad_geometry(pad):
    sz = pad.GetSize()
    w, h = sz.x / U, sz.y / U
    pos = pad.GetPosition()
    return {"w": w, "h": h, "half_diag": math.hypot(w / 2.0, h / 2.0),
            "centre": (pos.x / U, pos.y / U), "angle": pad.GetOrientationDegrees(),
            "shape": pad.GetShape()}


def ring_obstacles(board, pad, layer, radius):
    g = pad_geometry(pad)
    cx, cy = g["centre"]
    win = (cx - radius - 1, cy - radius - 1, cx + radius + 1, cy + radius + 1)
    me = pad_item(pad, layer)
    rows = []
    for it in collect(board, layer, pad.GetNetCode(), win):
        d = me.gap_to(it)
        if d <= radius:
            rows.append((d, it.kind, it.label))
    rows.sort(key=lambda r: r[0])
    return rows


def pour_gap(board, pad, layer):
    """GND pour measured SEPARATELY. A uniform gap == zone clearance == re-pourable."""
    for z in board.Zones():
        if not z.IsOnLayer(layer) or z.GetNetCode() == pad.GetNetCode() or not z.IsFilled():
            continue
        it = Item(poly_edges(z.GetFilledPolysList(layer)), 0.0, z.GetNetCode(), "zone", z.GetNetname())
        return pad_item(pad, layer).gap_to(it), it.label, z.GetLocalClearance() / U
    return None, None, None


def fcu_reachability(board, pad, rules, half=2.5, step=0.05):
    """DRC-legal flood fill on F.Cu. Answers 'can the pad's copper leave?', not 'where?'."""
    g = pad_geometry(pad)
    cx, cy = g["centre"]
    win = (cx - half - 1, cy - half - 1, cx + half + 1, cy + half + 1)
    obst = collect(board, pcbnew.F_Cu, pad.GetNetCode(), win)
    need = rules.trace_edge_to_copper
    n = int(round(2 * half / step)) + 1
    xs = [cx - half + i * step for i in range(n)]
    ys = [cy - half + j * step for j in range(n)]
    legal = [[False] * n for _ in range(n)]
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            d = min((it.d_point(x, y) for it in obst), default=float("inf"))
            legal[i][j] = d >= need - EPS
    me = pad_item(pad, pcbnew.F_Cu)
    seeds = [(i, j) for j, y in enumerate(ys) for i, x in enumerate(xs)
             if legal[i][j] and point_in_poly(x, y, me.pts)]
    if not seeds:
        return {"escaped": False, "reach": 0.0, "cells": 0, "half": half, "step": step,
                "note": "no legal cell inside the pad"}
    seen = [[False] * n for _ in range(n)]
    stack = list(seeds)
    for i, j in seeds:
        seen[i][j] = True
    cells, far, edge = 0, 0.0, False
    while stack:
        i, j = stack.pop()
        cells += 1
        far = max(far, math.hypot(xs[i] - cx, ys[j] - cy))
        if i in (0, n - 1) or j in (0, n - 1):
            edge = True
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            a, b = i + di, j + dj
            if not (0 <= a < n and 0 <= b < n) or seen[a][b] or not legal[a][b]:
                continue
            if di and dj and not (legal[i + di][j] and legal[i][j + dj]):
                continue  # no corner cutting
            seen[a][b] = True
            stack.append((a, b))
    return {"escaped": edge, "reach": far, "cells": cells, "half": half, "step": step,
            "note": "reached sampling-window edge" if edge else "cannot leave the local pad field"}


def collect_holes(board, skip_net):
    out = []
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T and t.GetNetCode() != skip_net:
            p = t.GetPosition()
            out.append((p.x / U, p.y / U, t.GetDrill() / U / 2.0, t.GetNetname()))
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetCode() == skip_net:
                continue
            ds = p.GetDrillSize()
            if ds.x > 0:
                pos = p.GetPosition()
                out.append((pos.x / U, pos.y / U, ds.x / U / 2.0,
                            "%s.%s" % (fp.GetReference(), p.GetNumber())))
    return out


def via_search(board, pad, rules, r_max=2.0, step_deg=3.0, step_r=0.05):
    """Legal via placements. Dogbone only — via-in-pad counted separately."""
    g = pad_geometry(pad)
    cx, cy = g["centre"]
    net = pad.GetNetCode()
    win = (cx - r_max - 3, cy - r_max - 3, cx + r_max + 3, cy + r_max + 3)
    obst = {L: collect(board, L, net, win) for L, _ in COPPER_LAYERS}
    holes = collect_holes(board, net)
    centre = (cx, cy)
    me = pad_item(pad, pcbnew.F_Cu)
    sizes = sorted({d for d in (rules.via_dia, rules.via_min_dia) if d > 0})
    results = {}
    for vd in sizes:
        legal, near, inpad = [], None, 0
        for ri in range(1, int(round(r_max / step_r)) + 1):
            R = ri * step_r
            for ki in range(int(round(360 / step_deg))):
                ang = math.radians(ki * step_deg)
                vx, vy = cx + R * math.cos(ang), cy + R * math.sin(ang)
                wc, who = float("inf"), None
                for L, lname in COPPER_LAYERS:
                    for it in obst[L]:
                        b = it.bbox
                        if math.hypot(max(b[0] - vx, 0.0, vx - b[2]),
                                      max(b[1] - vy, 0.0, vy - b[3])) - vd / 2.0 > wc:
                            continue
                        v = it.d_point(vx, vy) - vd / 2.0
                        if v < wc:
                            wc, who = v, (lname, it.kind, it.label)
                wh = min((math.hypot(hx - vx, hy - vy) - rules.via_drill / 2.0 - hr
                          for hx, hy, hr, _ in holes), default=float("inf"))
                wa, wao = float("inf"), None
                for it in obst[pcbnew.F_Cu]:
                    v = it.d_seg(centre, (vx, vy)) - rules.track_w / 2.0
                    if v < wa:
                        wa, wao = v, (it.kind, it.label)
                ok = (wc >= rules.clearance - EPS and wh >= rules.hole_to_hole - EPS
                      and wa >= rules.clearance - EPS)
                in_pad = me.d_point(vx, vy) < vd / 2.0   # over the pad's OWN land
                rec = {"R": R, "deg": ki * step_deg, "cu": wc, "cu_by": who, "h2h": wh,
                       "appr": wa, "appr_by": wao, "in_pad": in_pad}
                if ok and not in_pad:
                    legal.append(rec)
                elif ok and in_pad:
                    inpad += 1
                m = min(wc, wh, wa)
                if near is None or m > near["margin"]:
                    rec["margin"] = m
                    near = rec
        results[vd] = {"legal": legal, "near": near, "inpad": inpad}
    return results


def existing_net_copper(board, pad, rules):
    """Own-net copper already on the board. A via is only an escape if copper continues."""
    net = pad.GetNetCode()
    g = pad_geometry(pad)
    cx, cy = g["centre"]
    out = []
    for t in board.GetTracks():
        if t.GetNetCode() != net:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            p = t.GetPosition()
            vpos = (p.x / U, p.y / U)
            win = (vpos[0] - 2, vpos[1] - 2, vpos[0] + 2, vpos[1] + 2)
            worst = min((it.d_point(*vpos) - t.GetWidth(pcbnew.F_Cu) / U / 2.0
                         for L, _ in COPPER_LAYERS for it in collect(board, L, net, win)),
                        default=float("inf"))
            cont, clay = False, None
            for u in board.GetTracks():
                if (u.GetNetCode() == net and u.Type() == pcbnew.PCB_TRACE_T
                        and u.GetLayer() in (pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)):
                    s, e = u.GetStart(), u.GetEnd()
                    if Item([((s.x / U, s.y / U), (e.x / U, e.y / U))],
                            u.GetWidth() / U / 2.0, net).d_point(*vpos) <= 1.0:
                        cont, clay = True, board.GetLayerName(u.GetLayer())
                        break
            out.append({"kind": "via", "pos": vpos, "dia": t.GetWidth(pcbnew.F_Cu) / U,
                        "dist": math.hypot(vpos[0] - cx, vpos[1] - cy),
                        "in_pad": pad_item(pad, pcbnew.F_Cu).d_point(*vpos)
                                  < t.GetWidth(pcbnew.F_Cu) / U / 2.0,
                        "legal": worst >= rules.clearance - EPS,
                        "continues": (cont, clay)})
        elif t.Type() == pcbnew.PCB_TRACE_T:
            s, e = t.GetStart(), t.GetEnd()
            out.append({"kind": "trace", "pos": (s.x / U, s.y / U),
                        "dist": math.hypot(s.x / U - cx, s.y / U - cy)})
    return out


def self_check(verdict, ring_rows, via_res, existing):
    """Refuse a verdict that disagrees with the data that produced it."""
    p = []
    if [r for r in ring_rows if r[0] < 0.0]:
        p.append("obstacle overlaps the pad copper itself")
    if verdict["kind"] == "F_CU" and not verdict.get("fcu_escaped"):
        p.append("says F.Cu-escapable but the flood fill never left the pad field")
    if verdict["kind"] == "VIA" and not any(v["legal"] for v in via_res.values()):
        p.append("says via-escapable but no legal candidate was found")
    if verdict["kind"] == "BLOCKED":
        if verdict.get("fcu_escaped"):
            p.append("says blocked but the F.Cu flood fill escaped")
        if any(v["legal"] for v in via_res.values()):
            p.append("says blocked but a legal via exists")
    if verdict["kind"] == "STUB_VIA" and not [e for e in existing
                                             if e["kind"] == "via" and e["legal"]
                                             and e["in_pad"] and not e["continues"][0]]:
        p.append("says stub via but none found")
    return p


def measure(board, rules, ref, num):
    fp = board.FindFootprintByReference(ref)
    pad = next(p for p in fp.Pads() if str(p.GetNumber()) == num)
    g = pad_geometry(pad)
    ring_r = g["half_diag"] + rules.clearance
    ring = ring_obstacles(board, pad, pcbnew.F_Cu, ring_r)
    reach = fcu_reachability(board, pad, rules)
    vias = via_search(board, pad, rules)
    existing = existing_net_copper(board, pad, rules)

    live_inpad = [e for e in existing if e["kind"] == "via" and e["legal"] and e["in_pad"]]
    if live_inpad:
        e = min(live_inpad, key=lambda x: x["dist"])
        if e["continues"][0]:
            verdict = {"kind": "VIA", "fcu_escaped": reach["escaped"],
                       "text": "ESCAPABLE only via layer transition (%s) -- via already on board"
                               % e["continues"][1]}
        else:
            verdict = {"kind": "STUB_VIA", "fcu_escaped": reach["escaped"],
                       "text": "ESCAPABLE via layer transition -- existing in-pad via is a STUB"}
    elif reach["escaped"]:
        verdict = {"kind": "F_CU", "fcu_escaped": True, "text": "ESCAPABLE on F.Cu"}
    else:
        sizes = sorted(vd for vd, v in vias.items() if v["legal"])
        if sizes:
            v = min(vias[sizes[0]]["legal"], key=lambda r: r["R"])
            verdict = {"kind": "VIA", "fcu_escaped": False,
                       "text": "ESCAPABLE only via layer transition (F.Cu -> In1/In2/B.Cu)",
                       "detail": "legal via at R=%.2f @%.0f deg dia %.2f, cu=%.4f h2h=%.4f"
                                 % (v["R"], v["deg"], sizes[0], v["cu"], v["h2h"])}
        else:
            small = min(vias)
            near = vias[small]["near"]
            parts = [("copper clearance", near["cu"], rules.clearance, near["cu_by"]),
                     ("hole-to-hole", near["h2h"], rules.hole_to_hole, None),
                     ("F.Cu pad-to-via approach", near["appr"], rules.clearance, near["appr_by"])]
            name, got, need, by = min(parts, key=lambda t: t[1] - t[2])
            verdict = {"kind": "BLOCKED", "fcu_escaped": False,
                       "text": "NOT ESCAPABLE at current rules",
                       "detail": "best dogbone dia %.2f R=%.2f@%.0f misses by %.4f mm on %s "
                                 "(%.3f required, %.4f achieved); neighbour %s"
                                 % (small, near["R"], near["deg"], need - got, name,
                                    need, got, by)}
    return {"ref": "%s.%s" % (ref, num), "net": pad.GetNetname(), "geom": g,
            "layers": [board.GetLayerName(l) for l in pad.GetLayerSet().Seq()],
            "ring_r": ring_r, "ring": ring, "reach": reach, "vias": vias,
            "existing": existing, "verdict": verdict,
            "problems": self_check(verdict, ring, vias, existing)}


def _parse_pad(token):
    ref, _, num = token.rpartition(".")
    if not ref or not num:
        raise argparse.ArgumentTypeError(f"pad must be REF.NUMBER, got {token!r}")
    return ref, num


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--board", default=DEFAULT_BOARD)
    ap.add_argument("--pad", action="append", type=_parse_pad,
                    dest="pads", metavar="REF.NUM")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    pads = a.pads or [_parse_pad(p) for p in DEFAULT_PADS]

    board = pcbnew.LoadBoard(a.board)
    if board is None:
        raise SystemExit("LoadBoard returned None -- path needs a .kicad_pcb suffix")
    rules = Rules(board)
    if not a.json:
        print("clearance %.3f  track %.3f  via %.3f/%.3f  h2h %.3f"
              % (rules.clearance, rules.track_w, rules.via_dia, rules.via_drill,
                 rules.hole_to_hole))
        print("board %s  pads %s" % (a.board, [f"{r}.{n}" for r, n in pads]))
    results = [measure(board, rules, r, n) for r, n in pads]

    if a.json:
        out = [{
            "ref": r["ref"], "net": r["net"],
            "layers": r["layers"],
            "ring_r": r["ring_r"],
            "reach": {"escaped": r["reach"]["escaped"],
                      "reach": round(r["reach"]["reach"], 4)},
            "verdict": r["verdict"]["kind"],
            "verdict_text": r["verdict"]["text"],
            "detail": r["verdict"].get("detail"),
            "problems": r["problems"],
        } for r in results]
        print(json.dumps({"board": a.board, "rules": {
            "clearance": rules.clearance, "track_w": rules.track_w,
            "via_dia": rules.via_dia, "via_drill": rules.via_drill,
            "hole_to_hole": rules.hole_to_hole}, "pads": out}, indent=1))
    else:
        for r in results:
            g, v = r["geom"], r["verdict"]
            print("\n%s  net %s" % (r["ref"], r["net"]))
            print("  pad %.2fx%.2f mm  half-diag %.4f  layers %s"
                  % (g["w"], g["h"], g["half_diag"], r["layers"]))
            print("  escape ring %.4f mm    F.Cu obstacles inside (from pad edge):" % r["ring_r"])
            for d, k, l in r["ring"]:
                print("    %+8.4f mm  %-6s %s" % (d, k, l))
            print("  F.Cu flood fill: %s (reach %.2f mm)" % (r["reach"]["note"], r["reach"]["reach"]))
            for e in r["existing"]:
                if e["kind"] == "via":
                    print("  existing via %.2f at (%.3f,%.3f) d=%.4f in_pad=%s legal=%s continues=%s"
                          % (e["dia"], e["pos"][0], e["pos"][1], e["dist"], e["in_pad"],
                             e["legal"], e["continues"]))
            for vd in sorted(r["vias"]):
                vv = r["vias"][vd]
                if vv["legal"]:
                    v0 = min(vv["legal"], key=lambda x: x["R"])
                    print("  via %.2f: %d legal dogbone; nearest R=%.2f @%.0f cu=%.4f h2h=%.4f appr=%.4f (+%d in-pad)"
                          % (vd, len(vv["legal"]), v0["R"], v0["deg"], v0["cu"], v0["h2h"],
                             v0["appr"], vv["inpad"]))
                else:
                    nm = vv["near"]
                    print("  via %.2f: NONE legal dogbone; best min-margin %.4f (cu=%.4f h2h=%.4f appr=%.4f)"
                          % (vd, nm["margin"], nm["cu"], nm["h2h"], nm["appr"]))
            print("  VERDICT %s" % v["text"])
            if v.get("detail"):
                print("           %s" % v["detail"])
            print("  SELF-CHECK %s" % ("OK" if not r["problems"] else "FAIL: " + "; ".join(r["problems"])))

    bad = [r for r in results if r["problems"]]
    if bad:
        print("\nconsistency: FAILURES " + str([r["ref"] for r in bad]), file=sys.stderr)
        return 1
    if not a.json:
        print("\nconsistency: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

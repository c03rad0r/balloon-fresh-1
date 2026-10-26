#!/usr/bin/env python3
"""Antenna + pigtail VOLUME reservation for the hub (ADR-137, operator directive 2026-10-25).

THE DIRECTIVE
-------------
"please make sure you reserve space for the antennas in your 3D models of the circuit from now on"

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------
It is a **3D volume** reservation around each radio's antenna ATTACH POINT -- enough room for the
connector, the pigtail and its minimum bend radius, and the antenna body -- so future placement and
mechanical work cannot consume that space. It is deliberately **not** a blanket copper keep-out:
ADR-137 removes RF copper, and a keep-out in the wrong place silently forbids routing where the
antenna is not while leaving the real antenna unprotected.

HONESTY ABOUT THE NUMBERS (read before trusting any figure below)
----------------------------------------------------------------
Every module's `access` and `side` is UNCONFIRMED. The measured facts we have are:

  * LR2021 **bare chip** requires off-chip PA matching, harmonic filtering and an antenna match
    (datasheet Rev2.1 lines 1615-1621, 1792-1800, 2950-2952) -> that is exactly the RF design
    ADR-137 forbids; the module handles it instead.
  * `docs/F33-MODULE-PLAN.md` (a PROJECT plan, not vendor verification) lists pin 9 = ANT sub-GHz
    50 ohm and pin 10 = ANT-2G4 50 ohm, on the left and right sides respectively.
  * Nothing in this repo establishes the antenna access of U_E28 (SX1280 board), U3, U_C or U5.

So this script reserves a volume at the **module's own connector location as placed on the board**
-- which is a real, measured location -- and labels every entry with its evidence status. It
refuses to invent a side it cannot justify; where the side is unknown it reports the volume as
PROVISIONAL rather than silently picking one.

VOLUME MODEL (per module)
-------------------------
    antenna body : 32 x 8 x 3 mm   (2.4 GHz whip / sub-GHz whip envelope; placeholder, see below)
    connector    : 4 x 4 x 3 mm    (U.FL / IPEX body + latch)
    pigtail bend : 8 mm radius     (min bend radius for 1.13 mm coax, conservative)

The antenna body figure is a PLACEHOLDER sized for a 433 MHz quarter-wave whip's mechanical
envelope, NOT a datasheet part. It is marked as such in the output so it cannot be mistaken for a
measured requirement.

Run:  /usr/bin/python3 tracker/hardware/reserve_antenna_volume.py [--json OUT]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")

# Volume defaults, mm. PLACEHOLDER dimensions are flagged in the output.
ANT_BODY = dict(w=32.0, d=8.0, h=3.0, status="PLACEHOLDER (433 MHz whip envelope, not a datasheet part)")
CONNECTOR = dict(w=4.0, d=4.0, h=3.0, status="U.FL/IPEX body + latch, typical")
PIGTAIL_BEND_R = 8.0

# access: what plugs in at the module.  side: which module edge it exits.  evidence: where the
# claim comes from, and how strong it is.
MODULES = {
    "U2": dict(access="module pin (50 ohm)", side="west", evidence="PROJECT PLAN: docs/F33-MODULE-PLAN.md pins 9/10 (ANT, ANT-2G4); not vendor-verified"),
    "U_C": dict(access="unknown", side=None, evidence="NO EVIDENCE in repo -- castellated LR2021 module"),
    "U_E28": dict(access="unknown", side=None, evidence="NO EVIDENCE in repo -- E28/SX1280 module board"),
    "U3": dict(access="unknown", side=None, evidence="NO EVIDENCE in repo -- castellated LR2021 module"),
    "U5": dict(access="unknown", side=None, evidence="NO EVIDENCE in repo -- MAX-M10S antenna pin"),
}


def pad_bbox(fp):
    xs, ys = [], []
    for p in fp.Pads():
        bb = p.GetBoundingBox()
        xs += [bb.GetX() / 1e6, (bb.GetX() + bb.GetWidth()) / 1e6]
        ys += [bb.GetY() / 1e6, (bb.GetY() + bb.GetHeight()) / 1e6]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write the volume list here")
    args = ap.parse_args()

    board = pcbnew.LoadBoard(BOARD)
    bb = board.GetBoardEdgesBoundingBox()
    BW, BH = bb.GetWidth() / 1e6, bb.GetHeight() / 1e6

    out = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if ref not in MODULES:
            continue
        info = MODULES[ref]
        pb = pad_bbox(fp)
        if not pb:
            continue
        x1, y1, x2, y2 = pb
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        side = info["side"]
        confirmed = side is not None
        if side is None:
            # propose the side facing the nearest board edge, but mark it provisional
            d = {"west": x1, "east": BW - x2, "north": y1, "south": BH - y2}
            side = min(d, key=d.get)

        # anchor the volume at the module edge the antenna exits
        if side == "west":
            ax, ay = x1, cy
        elif side == "east":
            ax, ay = x2, cy
        elif side == "north":
            ax, ay = cx, y1
        else:
            ax, ay = cx, y2

        # volume spans outward from the anchor: connector, then bend, then antenna body
        if side in ("west", "east"):
            sgn = -1 if side == "west" else 1
            x_from = ax + sgn * (CONNECTOR["d"] + PIGTAIL_BEND_R)
            x_to = x_from + sgn * ANT_BODY["w"]
            vol = dict(x1=min(x_from, x_to), x2=max(x_from, x_to),
                       y1=ay - ANT_BODY["d"] / 2, y2=ay + ANT_BODY["d"] / 2)
        else:
            sgn = -1 if side == "north" else 1
            y_from = ay + sgn * (CONNECTOR["d"] + PIGTAIL_BEND_R)
            y_to = y_from + sgn * ANT_BODY["w"]
            vol = dict(y1=min(y_from, y_to), y2=max(y_from, y_to),
                       x1=ax - ANT_BODY["d"] / 2, x2=ax + ANT_BODY["d"] / 2)
        vol["z_mm"] = ANT_BODY["h"]

        inside = (vol["x1"] >= 0 and vol["y1"] >= 0 and vol["x2"] <= BW and vol["y2"] <= BH)
        out.append(dict(ref=ref, side=side, side_confirmed=confirmed, anchor=[round(ax, 2), round(ay, 2)],
                        volume={k: round(v, 2) for k, v in vol.items()},
                        access=info["access"], evidence=info["evidence"],
                        entirely_on_board=inside,
                        status="CONFIRMED" if confirmed else "PROVISIONAL"))

    print(f"antenna volume reservation -- {len(out)} radio(s), board {BW:.1f} x {BH:.1f} mm")
    print(f"  model: body {ANT_BODY['w']}x{ANT_BODY['d']}x{ANT_BODY['h']} mm "
          f"[{ANT_BODY['status']}]")
    print(f"         connector {CONNECTOR['w']}x{CONNECTOR['d']}x{CONNECTOR['h']} mm "
          f"[{CONNECTOR['status']}]")
    print(f"         pigtail min bend radius {PIGTAIL_BEND_R} mm")
    print()
    for e in out:
        v = e["volume"]
        print(f"  {e['ref']:<6} {e['status']:<11} exits {e['side']:<5} "
              f"x {v['x1']:.1f}..{v['x2']:.1f}  y {v['y1']:.1f}..{v['y2']:.1f}  z 0..{v['z_mm']:.0f}")
        print(f"         access: {e['access']}")
        print(f"         basis : {e['evidence']}")
        if not e["entirely_on_board"]:
            print("         NOTE  : volume extends past the PCB outline -- it is AIR space above/")
            print("                 beyond the board. That is intended: an antenna is not on the PCB.")

    prov = [e["ref"] for e in out if e["status"] == "PROVISIONAL"]
    print()
    if prov:
        print(f"PROVISIONAL (antenna side not confirmed, nearest-edge heuristic used): {', '.join(prov)}")
        print("  The VOLUME SIZE is usable as a reservation; the SIDE is a guess. Confirm each")
        print("  module's antenna access before mechanical/enclosure work relies on it.")

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(dict(board=os.path.basename(BOARD), board_mm=[BW, BH],
                           model=dict(ant_body=ANT_BODY, connector=CONNECTOR,
                                      pigtail_bend_r=PIGTAIL_BEND_R),
                           volumes=out), fh, indent=2)
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

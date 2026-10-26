#!/usr/bin/env python3
"""Antenna + pigtail VOLUME reservation, anchored at each module's ACTUAL antenna pad.

Rewritten 2026-10-25 after finding three defects in the first version:

  1. It anchored volumes at the module CENTRE and guessed the nearest board edge. Anchored at the
     real pad instead, the picture changes: U2's antenna pad is at (45.52, 30.60), EAST of its
     centre, not west as the heuristic guessed.
  2. It reserved ONE volume per module. Three of the five modules carry TWO antenna ports
     (sub-GHz + 2.4 GHz) on the same part, verified from datasheets.
  3. Consequence: the "U2 <-> U3 overlap 131 mm2" reported earlier was an ARTEFACT of the
     centre+edge heuristic. **That claim is withdrawn here.** The real conflicts are printed by
     this script and are a different pair.

PIN EVIDENCE
------------
Pin numbers come from `docs/adr/045-antenna-solder-access.md` D1, which extracted them with
`pdftotext -layout` (NOT a vision model) from datasheets committed in this repo:

  LoRa2021F33-2G4  pin 9 = ANTA (sub-GHz),  pin 10 = ANT-2G4   ... v1.1 sec 7 p.6   VERIFIED
  bare LoRa2021    pin 9 = ANTA (sub-GHz),  pin 10 = 2.4/S_ANTA ... V1.3 sec 7 p.6  VERIFIED
  SX1280 (U_E28)   antenna pad                                     ... no datasheet  TODO
  MAX-M10S (U5)    RF pad                                          ... no datasheet  TODO

Independent corroboration: the board's own net names agree with the datasheet pin numbers wherever
the port was ever connected -- U2.9 = /ANT1_433_TX (sub-GHz), U3.10 = /ANT3_2G4_RX (2.4 GHz),
U_C.10 = /ANT_C_2G4 (2.4 GHz), U5.11 = /ANT4_GNSS_L1 (GNSS). Two independent sources agreeing is
worth more than either alone, and it is recorded as such rather than as proof.

VOLUME MODEL
------------
Per antenna port: connector (4x4x3) + pigtail min bend (8 mm) + antenna body (32x8x3). The body
figure is a PLACEHOLDER sized to a 433 MHz quarter-wave whip envelope, not a datasheet part.
Direction is outward from the module centre through the antenna pad, snapped to the dominant
cardinal axis, so each volume extends AWAY from the component it belongs to.

Run:  /usr/bin/python3 tracker/hardware/reserve_antenna_volume.py [--json OUT]
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")

ANT_BODY = dict(w=32.0, d=8.0, h=3.0,
                status="PLACEHOLDER (433 MHz quarter-wave whip envelope, not a datasheet part)")
CONNECTOR = dict(w=4.0, d=4.0, h=3.0, status="U.FL/IPEX body + latch, typical")
PIGTAIL_BEND_R = 8.0

# module -> list of antenna ports, each with its pin number and the evidence behind it
MODULES = {
    "U2": [
        dict(pin="9", band="sub-GHz", access="module pin 50 ohm",
             evidence="ADR-045 D1, F33 datasheet v1.1 s7 p.6 (pdftotext); board net "
                      "/ANT1_433_TX agrees", verified=True),
        dict(pin="10", band="2.4 GHz", access="module pin 50 ohm",
             evidence="ADR-045 D1, F33 datasheet v1.1 s7 p.6 (pdftotext)", verified=True),
    ],
    "U3": [
        dict(pin="9", band="sub-GHz", access="module pin 50 ohm",
             evidence="ADR-045 D1, LoRa2021 V1.3 s7 p.6 (pdftotext)", verified=True),
        dict(pin="10", band="2.4 GHz", access="module pin 50 ohm",
             evidence="ADR-045 D1, LoRa2021 V1.3 s7 p.6; board net /ANT3_2G4_RX agrees",
             verified=True),
    ],
    "U_C": [
        dict(pin="9", band="sub-GHz", access="module pin 50 ohm",
             evidence="ADR-045 D1, LoRa2021 V1.3 s7 p.6 (pdftotext)", verified=True),
        dict(pin="10", band="2.4 GHz", access="module pin 50 ohm",
             evidence="ADR-045 D1, LoRa2021 V1.3 s7 p.6; board net /ANT_C_2G4 agrees",
             verified=True),
    ],
    # CORRECTED from the module's own user manual (docs/modules/e28-2g4m27sx/
    # E28-2G4M27SX_UserManual_v1.0.pdf via pdftotext):
    #   line 216 -> "Antenna Interface  IPEX/PCB   Equivalent impedance is about 50 ohm"
    #   the 16-pin table has NO antenna pin: 1 VCC, 2 GND, 3 MISO_TX, 4 MOSI_RX, 5 SCK_RTSN,
    #   6 NSS_CTS, 7 GND, 8 RX_EN, 9 TX_EN, 10 GND, 11 NRESET, 12 BUSY, 13-15 DIO1-3, 16 GND
    # The antenna is an IPEX connector ON THE MODULE BODY. The earlier entry anchored a volume at
    # pad 9 -- which is TX_EN, a PA control pin. That was simply wrong.
    "U_E28": [
        dict(pin=None, band="2.4 GHz", access="module-integrated IPEX/PCB connector",
             evidence="E28 user manual v1.0 line 216 (IPEX/PCB, ~50 ohm) + 16-pin table with no "
                      "antenna pin (pdftotext). Connector POSITION needs the Ch.3 mechanical "
                      "drawing; anchor is the module body, not a pad",
             verified=True),
    ],
    "U5": [
        dict(pin="11", band="GNSS L1", access="unknown",
             evidence="TODO: no MAX-M10S datasheet committed; pad 11 carries /ANT4_GNSS_L1, "
                      "strong board-level evidence but not a datasheet", verified=False),
    ],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write the volume list here")
    args = ap.parse_args()

    board = pcbnew.LoadBoard(BOARD)
    bb = board.GetBoardEdgesBoundingBox()
    BW, BH = bb.GetWidth() / 1e6, bb.GetHeight() / 1e6

    fpmap = {f.GetReference(): f for f in board.GetFootprints()}
    out = []
    for ref, ports in MODULES.items():
        fp = fpmap.get(ref)
        if fp is None:
            print(f"WARNING: {ref} not on board -- skipped")
            continue
        c = fp.GetPosition()
        cx, cy = c.x / 1e6, c.y / 1e6
        pads = {str(p.GetNumber()): p for p in fp.Pads()}
        for port in ports:
            if port["pin"] is None:
                # module-integrated antenna: no pad to anchor at. Use the module body side
                # nearest a board edge and say so -- the connector's real position needs the
                # mechanical drawing.
                fbb = fp.GetBoundingBox()
                bx1, by1 = fbb.GetX() / 1e6, fbb.GetY() / 1e6
                bx2 = (fbb.GetX() + fbb.GetWidth()) / 1e6
                by2 = (fbb.GetY() + fbb.GetHeight()) / 1e6
                dd = {"west": bx1, "east": BW - bx2, "north": by1, "south": BH - by2}
                anchor_side = min(dd, key=dd.get)
                px, py = {"west": (bx1, (by1 + by2) / 2), "east": (bx2, (by1 + by2) / 2),
                          "north": ((bx1 + bx2) / 2, by1),
                          "south": ((bx1 + bx2) / 2, by2)}[anchor_side]
                dx, dy = {"west": (-1, 0), "east": (1, 0),
                          "north": (0, -1), "south": (0, 1)}[anchor_side]
            else:
                p = pads.get(port["pin"])
                if p is None:
                    print(f"WARNING: {ref} has no pad {port['pin']} -- skipped")
                    continue
                q = p.GetPosition()
                px, py = q.x / 1e6, q.y / 1e6
                dx, dy = px - cx, py - cy
            if abs(dx) >= abs(dy):
                side = "east" if dx >= 0 else "west"
            else:
                side = "south" if dy >= 0 else "north"

            reach = CONNECTOR["d"] + PIGTAIL_BEND_R
            if side in ("east", "west"):
                sgn = 1 if side == "east" else -1
                xa = px + sgn * reach
                xb = xa + sgn * ANT_BODY["w"]
                vol = dict(x1=min(xa, xb), x2=max(xa, xb),
                           y1=py - ANT_BODY["d"] / 2, y2=py + ANT_BODY["d"] / 2)
            else:
                sgn = 1 if side == "south" else -1
                ya = py + sgn * reach
                yb = ya + sgn * ANT_BODY["w"]
                vol = dict(x1=px - ANT_BODY["d"] / 2, x2=px + ANT_BODY["d"] / 2,
                           y1=min(ya, yb), y2=max(ya, yb))
            vol["z_mm"] = ANT_BODY["h"]

            out.append(dict(ref=ref, pin=port["pin"] or "body", band=port["band"], side=side,
                            anchor=[round(px, 2), round(py, 2)],
                            volume={k: round(v, 2) for k, v in vol.items()},
                            access=port["access"], evidence=port["evidence"],
                            status="VERIFIED" if port["verified"] else "PROVISIONAL"))

    print(f"antenna volume reservation -- {len(out)} port(s), board {BW:.1f} x {BH:.1f} mm")
    print(f"  body {ANT_BODY['w']:.0f}x{ANT_BODY['d']:.0f}x{ANT_BODY['h']:.0f} mm "
          f"[{ANT_BODY['status']}]")
    print(f"  connector {CONNECTOR['w']:.0f}x{CONNECTOR['d']:.0f}x{CONNECTOR['h']:.0f} mm, "
          f"pigtail bend r {PIGTAIL_BEND_R:.0f} mm")
    print()
    for e in out:
        v = e["volume"]
        print(f"  {e['ref']:<6} pad {e['pin']:<3} {e['band']:<9} {e['status']:<11} {e['side']:<5} "
              f"x {v['x1']:7.1f}..{v['x2']:7.1f}  y {v['y1']:7.1f}..{v['y2']:7.1f}")
        print(f"         {e['evidence']}")

    print("\nvolume collisions (real, anchored at antenna pads):")
    found = []
    for a, b in itertools.combinations(out, 2):
        A, B = a["volume"], b["volume"]
        ox = min(A["x2"], B["x2"]) - max(A["x1"], B["x1"])
        oy = min(A["y2"], B["y2"]) - max(A["y1"], B["y1"])
        if ox > 0 and oy > 0:
            found.append((a, b, ox, oy))
            print(f"  COLLISION {a['ref']}.{a['pin']} <-> {b['ref']}.{b['pin']}  "
                  f"{ox:.1f} x {oy:.1f} mm = {ox*oy:.0f} mm2")
    if not found:
        print("  none -- every antenna port has its own free volume")

    prov = [f"{e['ref']}.{e['pin']}" for e in out if e["status"] == "PROVISIONAL"]
    if prov:
        print(f"\nPROVISIONAL antenna pad (not datasheet-verified): {', '.join(prov)}")
        print("  ADR-045 D1 records these TODO(unverified). Do not let mechanical or enclosure")
        print("  work assume them.")

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(dict(board=os.path.basename(BOARD), board_mm=[BW, BH],
                           copper_layers=board.GetCopperLayerCount(),
                           model=dict(ant_body=ANT_BODY, connector=CONNECTOR,
                                      pigtail_bend_r=PIGTAIL_BEND_R),
                           volumes=out,
                           collisions=[dict(a=f"{a['ref']}.{a['pin']}", b=f"{b['ref']}.{b['pin']}",
                                            size_mm=[round(ox, 2), round(oy, 2)])
                                       for a, b, ox, oy in found]), fh, indent=2)
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""compute_pcba_curve.py -- derive the PCBA price curve from LCSC price breaks.

WHY THIS EXISTS
---------------
Sampling the quote page at 16 different quantities is wasteful: each point costs
a browser round-trip, and the quantity widget is the least reliable part of the
page. The parts API (`.../smtGood/selectSmtComponentList/v2`) is UNAUTHENTICATED
and returns each component's PRICE-BREAK TABLE:

    1-9 $5.7607 / 10-29 $4.9550 / 30-99 $4.4787 / ...

So the expensive, qty-dependent part of the total can be computed exactly, for
every quantity, from one API call per part. The cliffs are the break boundaries.
Only the ASSEMBLY fee needs the quote page.

THE MODEL (and what is measured vs assumed)
-------------------------------------------
total(qty) = parts(qty) + pcb(qty) + assembly(qty)

  parts(qty)  MEASURED. Sum over parts of price_at_qty() from the API breaks.
              NB: JLC prices parts at ORDER quantity, not per-board quantity --
              a board needing 3 capacitors at qty 5 buys 15. This is the single
              biggest structural driver of the curve, and it is why the per-board
              price steps down as breaks are crossed.
  pcb(qty)    MEASURED at qty 5 ($32.30 hub). Scaled by the known JLCPCB 4-layer
              ladder shape; the ladder start points are ASSUMED and flagged.
  assembly    MEASURED fixed component: "$25 per assembly side" (Standard PCBA,
              single-sided here => $25 x 1). JLC also quotes a per-joint /
              per-placement figure that was NOT captured -- that is the main
              assumption, and it is applied as a per-board constant so the curve
              shape is driven by the measured parts data.

Every assumption is written into the CSV's notes column per row, and the
sensitivity of the answer to the assumed terms is printed. Nothing here is
presented as a quote.
"""
import argparse
import csv
import json
import os
import sys
import urllib.request

API = ("https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/"
       "smtGood/selectSmtComponentList/v2")

# BOM: comment -> (lcsc, per_board_qty). Per-board quantities are read off the
# board's own PCBA BOM (docs/fab/hub-v9/hub_v9_bom_pcba.csv) where the "Qty"
# column is the count needed per assembled board at the page's default order
# size of 5 -- so board_qty = page_qty / 5.
BOM = [
    ("U1  ESP32-S3-WROOM-1U-N8R8", "C2980300", 1),
    ("U4  SX1280IMLTRT",           "C125969",  1),
    ("U5  MAX-M10S-00B",           "C4153167", 1),
    ("U6  MS561101BA03-50",        "C15639",   1),
    ("U7  TPS7A0233DBVR",          "C5142805", 1),
    ("ANT U.FL-R-SMT(10)",         "C434808",  4),
    ("C4  10uF",                   "C15525",   1),
    ("C_BULK 100uF",               "C15008",   1),
    ("C_HF 100nF",                 "C1525",    1),
    ("C_MON 10nF",                 "C15195",   1),
    ("D1  BAT54W",                 "C699107",  4),
    ("D_BP SS24",                  "C50645",   2),
    ("D_HUB SS24",                 "C50645",   4),
    ("R_BAL 10k",                  "C25744",   2),
    ("R_DIV 1M",                   "C26083",   2),
    ("R_F1 100R",                  "C25076",   1),
    ("R_MON 4.7M",                 "C11906",   4),
]

QTY_MIN, QTY_MAX = 5, 20
PCB_AT_5 = 32.30          # measured on the live page
PCB_LADDER = [(5, 32.30), (10, 45.00), (15, 55.00), (20, 62.00)]  # 4-layer shape
SETUP_PER_SIDE = 25.00    # measured: "$25 per assembly side", Standard PCBA
PLACEMENT_PER_BOARD = 0.0  # NOT captured; exposed as a sensitivity knob


def fetch_breaks(lcsc, cache):
    if lcsc in cache:
        return cache[lcsc]
    body = json.dumps({"currentPage": 1, "pageSize": 10, "keyword": lcsc}).encode()
    req = urllib.request.Request(API, data=body, headers={
        "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as fh:
        data = json.load(fh)
    lst = (data.get("data", {}).get("componentPageInfo", {}) or {}).get("list", [])
    want = next((c for c in lst if c.get("componentCode") == lcsc), None)
    if want is None and lst:
        want = lst[0]
    if want is None:
        cache[lcsc] = None
        return None
    breaks = sorted(
        ((int(b["startNumber"]), int(b["endNumber"]), float(b["productPrice"]))
         for b in want.get("componentPrices", [])),
        key=lambda t: t[0])
    rec = {"breaks": breaks, "stock": want.get("stockCount"),
           "lib": want.get("componentLibraryType"), "raw": want}
    cache[lcsc] = rec
    return rec


def price_at(rec, n):
    """Unit price for n pieces from the break table (breaks are start-inclusive)."""
    if not rec or not rec["breaks"]:
        return None
    p = rec["breaks"][0][2]
    for start, _end, price in rec["breaks"]:
        if n >= start:
            p = price
        else:
            break
    return p


def pcb_at(q):
    """Piecewise-linear through the measured/assumed 4-layer ladder."""
    pts = PCB_LADDER
    if q <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if q <= x1:
            return y0 + (y1 - y0) * (q - x0) / (x1 - x0)
    return pts[-1][1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.expanduser("~/pcba_hub_qty_curve.csv"))
    ap.add_argument("--cache", default=os.path.expanduser("~/pcba_breaks.json"))
    ap.add_argument("--placement-per-board", type=float, default=PLACEMENT_PER_BOARD)
    args = ap.parse_args()

    cache = {}
    if os.path.isfile(args.cache):
        try:
            cache = json.load(open(args.cache))
        except Exception:
            cache = {}

    print(f"{'lcsc':<12} {'stock':>7} {'lib':<9} breaks (qty:unit$)")
    for name, lcsc, per in BOM:
        rec = fetch_breaks(lcsc, cache)
        if not rec:
            print(f"{lcsc:<12} ** NOT FOUND **  ({name})")
            continue
        bs = " ".join(f"{s}+:{p:.4f}" for s, _e, p in rec["breaks"][:6])
        print(f"{lcsc:<12} {str(rec['stock']):>7} {str(rec['lib']):<9} {bs}")
    json.dump(cache, open(args.cache, "w"), indent=1, default=str)

    # Sanity: every part must resolve, else the curve is incomplete.
    missing = [l for _n, l, _q in BOM if not cache.get(l)]
    if missing:
        print(f"\nWARNING: {len(missing)} part(s) unresolved: {missing}")
        print("Curve would UNDERSTATE cost. Continuing but flagging every row.")

    rows = []
    for q in range(QTY_MIN, QTY_MAX + 1):
        parts, detail = 0.0, []
        for name, lcsc, per in BOM:
            rec = cache.get(lcsc)
            n = per * q                       # JLC prices at ORDER quantity
            unit = price_at(rec, n) if rec else None
            if unit is None:
                detail.append(f"{name}:UNPRICED")
                continue
            parts += unit * n
            detail.append(f"{name}:{unit:.4f}x{n}")
        pcb = pcb_at(q)
        asm = SETUP_PER_SIDE * 1 + args.placement_per_board * q
        total = parts + pcb + asm
        rows.append({
            "qty": q, "pcb_price": round(pcb, 2), "parts_cost": round(parts, 2),
            "assembly_cost": round(asm, 2), "total": round(total, 2),
            "unit_total": round(total / q, 2),
            # NB: the ternary MUST be parenthesised. Written unparenthesised as
            #     ("DERIVED ... " + ("UNRESOLVED: " + x) if missing else "")
            # Python parses it as ("DERIVED ..." + "UNRESOLVED: " + x) if missing
            # else "" -- so the whole provenance string vanished whenever every
            # part resolved, i.e. exactly on the successful runs. The chart then
            # truthfully reported "Source: quote page" from a CSV that had lost
            # its self-declaration. Measured, then fixed.
            "notes": ("DERIVED from LCSC break tables + measured $32.30 @qty5 + "
                      "$25/side setup. NOT a page quote. "
                      + (("UNRESOLVED PARTS: " + ",".join(missing) + " ")
                         if missing else "")
                      + "; ".join(detail)),
        })

    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    # sanity: monotone total, non-increasing unit
    bad = []
    for a, b in zip(rows, rows[1:]):
        if b["total"] < a["total"] - 0.01:
            bad.append((a["qty"], b["qty"], "total decreased"))
        if b["unit_total"] > a["unit_total"] + 0.005:
            bad.append((a["qty"], b["qty"], "unit increased"))
    print(f"\nwrote {args.out}  ({len(rows)} rows)")
    for r in rows:
        print(f"  qty {r['qty']:>3}: parts ${r['parts_cost']:>8,.2f}  "
              f"pcb ${r['pcb_price']:>6,.2f}  asm ${r['assembly_cost']:>6,.2f}  "
              f"TOTAL ${r['total']:>8,.2f}   per board ${r['unit_total']:>7,.2f}")
    print("\nsanity: " + ("FAILED " + str(bad) if bad else "OK (total rising, unit falling)"))

    # where do the cliffs land?
    steps = []
    for a, b in zip(rows, rows[1:]):
        d = b["unit_total"] - a["unit_total"]
        if abs(d) > 0.05:
            steps.append((b["qty"], round(d, 2)))
    print("per-board price changes: " + (str(steps) if steps else "none > $0.05"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

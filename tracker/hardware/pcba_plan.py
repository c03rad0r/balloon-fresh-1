#!/usr/bin/env python3
"""pcba_plan.py — deterministic board cost planning for ANY board.

WHAT THIS IS FOR
----------------
Every board-planning session needs the same answer: what does this order cost at
quantity N, which parts dominate, where are the cliffs, and what does it cost to
populate the expensive parts on only SOME of the boards? This script answers all
of it from published LCSC price-break tables — no browser, no LLM, no sampling.

REUSE FOR A NEW BOARD
---------------------
    pcba_plan.py --bom docs/fab/<board>/<board>_bom_pcba.csv \
                 --pcb "5:32.30,10:45.0,20:62.0" \
                 --qtys 5-20 --outdir docs/fab/<board>/plan

The only board-specific inputs are the BOM (with LCSC codes) and the MEASURED
PCB prices. Everything else is derived.

DESIGN DECISIONS THAT MATTER
----------------------------
* LOG Y AXIS + DECOMPOSITION: a stacked AREA chart is mathematically wrong on a
  log axis (stacking is additive, logs are multiplicative). So decomposition is
  drawn as CUMULATIVE LINES (PCB, +cheap, +each costly part). The vertical gap
  between consecutive lines is that component's contribution — readable on a log
  scale, and it keeps the small parts visible next to the $10 ICs.
* COSTLY vs CHEAP is a documented threshold, not a hand-picked list.
* An unpriced part is never guessed: the point is dropped and reported.
"""
import argparse
import csv
import json
import os
import re
import sys
import urllib.request

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

API = ("https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/"
       "smtGood/selectSmtComponentList/v2")

# A part is COSTLY when its extended per-board cost at the smallest quantity
# exceeds this. Documented + tunable; pass --costly-threshold to override.
COSTLY_USD_PER_BOARD = 0.50


# --------------------------------------------------------------------------
# data acquisition
# --------------------------------------------------------------------------
def fetch_breaks(codes, cache_path):
    """Return {code: {"breaks": [[s,e,p],...], "stock": n}}. Cached to disk."""
    cache = {}
    if cache_path and os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)
    todo = [c for c in codes if c not in cache or not cache[c].get("breaks")]
    for code in todo:
        body = json.dumps({
            "currentPage": 1, "pageSize": 25, "keyword": code,
        }).encode()
        req = urllib.request.Request(
            API, data=body,
            headers={"Content-Type": "application/json;charset=UTF-8",
                     "User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                payload = json.loads(r.read().decode())
        except Exception as e:  # noqa: BLE001
            print(f"  ! {code}: fetch failed ({e}) — leaving unpriced", file=sys.stderr)
            cache[code] = {"breaks": [], "stock": 0}
            continue
        rows = (payload.get("data") or {}).get("componentList") or []
        hit = next((c for c in rows
                    if (c.get("componentCode") or "").upper() == code.upper()), None)
        if not hit:
            cache[code] = {"breaks": [], "stock": 0}
            continue
        bands = [[p["startNumber"], p["endNumber"], p["productPrice"]]
                 for p in (hit.get("componentPrices") or [])]
        bands.sort(key=lambda b: b[0])
        cache[code] = {"breaks": bands, "stock": hit.get("stockCount", 0)}
    if todo and cache_path:
        os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=1, sort_keys=True)
    return cache


def load_bom(path):
    """BOM -> [(lcsc, per_board, comment)]. per_board = designator count."""
    out = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        # Accept both header conventions: "LCSC Part #" and JLC's "JLCPCB Part #".
        key = next((k for k in rd.fieldnames
                    if "LCSC" in k.upper() or "JLCPCB" in k.upper()
                    or "PART" in k.upper()), None)
        di = next((k for k in rd.fieldnames if "esignator" in k), None)
        mi = next((k for k in rd.fieldnames if "omment" in k), None)
        if not key or not di:
            sys.exit(f"BOM {path}: need a LCSC column and a Designator column; "
                     f"got {rd.fieldnames}")
        for r in rd:
            code = (r.get(key) or "").strip()
            des = [d for d in (r.get(di) or "").replace(" ", "").split(",") if d]
            if not code or not des:
                continue  # DNP / fiducials / mounting holes have no part
            out.append((code.upper(), len(des), (r.get(mi) or "").strip()))
    return out


# --------------------------------------------------------------------------
# arithmetic
# --------------------------------------------------------------------------
def unit_price(breaks, qty):
    """Exact band price, or None when NO band covers qty. Never guessed."""
    for s, e, p in breaks:
        if qty >= s and (e == -1 or qty <= e):
            return p
    return None


def part_break_qty(breaks, per_board):
    """Board quantities where this part's price steps."""
    qs = []
    for i in range(1, len(breaks)):
        qs.append(int(-(-breaks[i][0] // max(1, per_board))))  # ceil
    return qs


def decompose(bom, cache, qtys):
    """Per-qty {qty: {"total": x, "lines": {lcsc: cost}, "unpriced": [...]}}."""
    res = {}
    for q in qtys:
        lines, unpriced = {}, []
        for code, per_board, _ in bom:
            breaks = (cache.get(code) or {}).get("breaks") or []
            up = unit_price(breaks, q * per_board)
            if up is None:
                unpriced.append(code)
                continue
            lines[code] = lines.get(code, 0.0) + per_board * up * q
        res[q] = {"total": sum(lines.values()), "lines": lines, "unpriced": unpriced}
    return res


def classify(bom, cache, qtys, threshold):
    """Split into costly / cheap by extended per-board cost at the smallest qty."""
    q0 = min(qtys)
    costly, cheap = [], []
    for code, per_board, comment in bom:
        breaks = (cache.get(code) or {}).get("breaks") or []
        up = unit_price(breaks, q0 * per_board)
        if up is None:
            continue
        per_board_usd = per_board * up
        (costly if per_board_usd >= threshold else cheap).append(
            (code, per_board, comment, per_board_usd))
    costly.sort(key=lambda x: -x[3])
    return costly, cheap


def selective(bom, cache, q_boards, ks, pcb_by_qty, fixed_fees, costly_codes):
    """Cost of populating the COSTLY parts on only K of Q boards.

    Cheap parts + PCB are soldered on all Q. Costly parts are bought and placed
    on K only; the other Q-K boards get them hand-soldered later. Part unit
    prices follow the PURCHASE quantity, so buying fewer can lose a price break.
    """
    cheap_lines = [(c, pb) for c, pb, _ in bom if c not in costly_codes]
    costly_lines = [(c, pb) for c, pb, _ in bom if c in costly_codes]
    out = []
    for k in ks:
        cheap = sum(pb * (unit_price((cache[c])["breaks"], q_boards * pb) or 0) * q_boards
                    for c, pb in cheap_lines)
        cost_parts = sum(pb * (unit_price((cache[c])["breaks"], max(k, 1) * pb) or 0) * k
                         for c, pb in costly_lines) if k > 0 else 0.0
        pcb = pcb_by_qty.get(q_boards)
        total = None if pcb is None else cheap + cost_parts + pcb + fixed_fees
        out.append({"q_boards": q_boards, "k_populated": k,
                    "pcb_usd": pcb, "cheap_usd": cheap, "costly_usd": cost_parts,
                    "total_usd": total,
                    "per_board_usd": None if total is None else total / q_boards})
    return out


# --------------------------------------------------------------------------
# plots
# --------------------------------------------------------------------------
# Green is RESERVED for the cheap-parts band; no costly part may use it, or two
# different series read as one.
CHEAP_COLOR = "#2ca02c"
PALETTE = ["#d62728", "#1f77b4", "#9467bd", "#ff7f0e",
           "#8c564b", "#17becf", "#e377c2", "#bcbd22"]


def money(v, _pos=None):
    return f"${v:,.0f}" if v >= 100 else (f"${v:,.2f}" if v >= 1 else f"${v:.3f}")


def plot_decomposition(qtys, rows, costly, cheap, out):
    """Cumulative-line decomposition on a LOG y axis (stacked areas would lie)."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 12), sharex=True)
    # Only qtys with a PCB term: a None here would be an unlabelled guess.
    q = [x for x in qtys if rows[x]["pcb"] is not None]
    pcb = [rows[x]["pcb"] for x in q]
    cheap_c = [rows[x]["cheap"] for x in q]

    for ax, scale, title in ((ax1, 1.0, "Order total"),
                             (ax2, None, "Per board")):
        cum = []
        if scale:
            col = pcb
            lab = "PCB fab"
            c = "#7f7f7f"
        else:
            col = [v / n for v, n in zip(pcb, q)]
            lab = "PCB fab / board"
            c = "#7f7f7f"
        for name, series, color in [("PCB fab", col, c)]:
            ax.plot(q, series, color=color, lw=2.2, marker="o", ms=4, label=name)
            cum.append(series)
        # + cheap band
        if scale:
            cheap_s = cheap_c
        else:
            cheap_s = [v / n for v, n in zip(cheap_c, q)]
        cur = [a + b for a, b in zip(cum[-1], cheap_s)]
        ax.plot(q, cur, color=CHEAP_COLOR, lw=1.8, marker="o", ms=3.5,
                label="+ cheap parts (< ${:.2f}/bd)".format(COSTLY_USD_PER_BOARD))
        cum.append(cur)
        # + each costly part, own colour
        for i, (code, pb, comment, _) in enumerate(costly):
            series = []
            for x in q:
                v = rows[x]["lines"].get(code, 0.0)
                series.append(v if scale else v / x)
            cur = [a + b for a, b in zip(cum[-1], series)]
            color = PALETTE[i % len(PALETTE)]
            ax.plot(q, cur, color=color, lw=1.8, marker="o", ms=3.5,
                    label=f"+ {comment or code} ({code})")
            cum.append(cur)
        # total marker
        ax.plot(q, cum[-1], color="black", lw=2.6, marker="s", ms=5,
                label="TOTAL (assembled)", zorder=5)
        if cliff_rows:
            txt = "CLIFFS in range (real price breaks):\n" + "\n".join(
                f"qty {c['qty']}: {c['label']}" for c in cliff_rows)
            ax.text(0.985, 0.02, txt, transform=ax.transAxes, fontsize=7.2,
                    va="bottom", ha="right",
                    bbox=dict(boxstyle="round,pad=0.35", fc="white",
                              ec="#999999", alpha=0.9))
        # Cliffs: dotted lines coloured by the part that causes them, plus ONE
        # legible summary block. Rotated per-line labels collided at qty 10 where
        # five ICs break together, so the list carries the detail instead.
        for i, (code, pb, comment, _) in enumerate(costly):
            breaks = (cache_breaks.get(code) or {}).get("breaks") or []
            color = PALETTE[i % len(PALETTE)]
            for idx in range(1, len(breaks)):
                if breaks[idx][2] == breaks[idx - 1][2]:
                    continue  # unchanged price: not a cliff
                bq = int(-(-breaks[idx][0] // max(1, pb)))
                if min(q) < bq <= max(q):
                    ax.axvline(bq, color=color, ls=":", lw=1.3, alpha=0.75)
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(FuncFormatter(money))
        ax.set_ylabel(f"{title} (USD, log scale)")
        ax.set_title(f"Hub v9 — {title}: PCB vs cheap vs each costly part")
        ax.grid(alpha=0.3, which="both")
        ax.legend(fontsize=8, loc="upper left")
    ax2.set_xlabel("Boards ordered")
    ax2.set_xticks(q)

    fig.text(0.5, 0.035,
             "MODEL from LCSC break tables (page cross-check 0.7% @qty5) — NOT a page quote.\n"
             "Cumulative LINES, not stacked areas: on a log axis stacked areas misrepresent size.\n"
             "PARTS exact at every qty; PCB fab MEASURED at quoted qtys, INTERPOLATED between.\n"
             "EXCLUDES per-placement assembly fee (unmeasured) and shipping.",
             ha="center", va="center", fontsize=8.0, color="#444444")
    fig.tight_layout(rect=(0, 0.085, 1, 1))
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"wrote {out}")


def plot_costly_detail(qtys, costly, rows, out):
    """Per-costly-part unit cost vs qty (log y) — the 'which to leave out' view."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6.5))
    for i, (code, pb, comment, _) in enumerate(costly):
        breaks = (cache_breaks.get(code) or {}).get("breaks") or []
        color = PALETTE[i % len(PALETTE)]
        series = []
        for x in qtys:
            up = unit_price(breaks, x * pb)
            series.append(None if up is None else up * pb)
        ax1.plot(qtys, series, color=color, lw=2, marker="o", ms=4,
                 label=f"{comment or code} ×{pb} ({code})")
        for idx in range(1, len(breaks)):
            if breaks[idx][2] == breaks[idx - 1][2]:
                continue  # unchanged price: not a cliff
            bq = int(-(-breaks[idx][0] // max(1, pb)))
            if min(qtys) < bq <= max(qtys):
                ax1.axvline(bq, color=color, ls=":", lw=1.2, alpha=0.7)
    ax1.set_yscale("log")
    ax1.yaxis.set_major_formatter(FuncFormatter(money))
    ax1.set_xlabel("Boards ordered")
    ax1.set_ylabel("Cost per board (USD, log scale)")
    ax1.set_title("Costly parts: per-board cost vs quantity\n(dotted = that part's price break = a cliff)")
    ax1.grid(alpha=0.3, which="both")
    ax1.legend(fontsize=8)
    ax1.set_xticks(qtys)

    # selective population: cost vs how many boards get the costly parts
    for q_boards, style in ((10, "-"), (20, "--")):
        ks = list(range(0, q_boards + 1))
        srows = selective(bom_global, cache_breaks, q_boards, ks,
                          pcb_global, FIXED_FEES, costly_codes)
        tot = [r["total_usd"] for r in srows]
        ax2.plot(ks, tot, style, color="#1f77b4", lw=2, marker="o", ms=3.5,
                 label=f"order {q_boards} boards: total")
        ax2.plot(ks, [r["per_board_usd"] for r in srows], style, color="#d62728",
                 lw=2, marker="s", ms=3.5, label=f"order {q_boards} boards: per board")
    ax2.set_yscale("log")
    ax2.yaxis.set_major_formatter(FuncFormatter(money))
    ax2.set_xlabel("Boards that GET the costly parts (rest = bare, hand-solder later)")
    ax2.set_ylabel("USD (log scale)")
    ax2.set_title("Selective population: leave the costly parts out of some boards")
    ax2.grid(alpha=0.3, which="both")
    ax2.legend(fontsize=8)

    fig.text(0.5, 0.01,
             "MODEL from LCSC break tables — NOT a page quote. Cheap parts + PCB on every board; "
             "costly parts bought/placed on K only. Part unit price follows the PURCHASE quantity, "
             "so populating fewer boards can lose a break (the curve is not a straight line).",
             ha="center", fontsize=8.2, color="#444444")
    fig.tight_layout(rect=(0, 0.045, 1, 1))
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"wrote {out}")


# --------------------------------------------------------------------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bom", required=True)
    ap.add_argument("--pcb", required=True,
                    help='"qty:usd,qty:usd" MEASURED pcb prices only')
    ap.add_argument("--qtys", default="5-20")
    ap.add_argument("--fixed-fees", type=float, default=25.0)
    ap.add_argument("--costly-threshold", type=float, default=COSTLY_USD_PER_BOARD)
    ap.add_argument("--cache", default="pcba_breaks_cache.json")
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    COSTLY_USD_PER_BOARD = args.costly_threshold
    FIXED_FEES = args.fixed_fees
    m = re.match(r"(\d+)-(\d+)$", args.qtys)
    qtys = list(range(int(m.group(1)), int(m.group(2)) + 1)) if m else \
        [int(x) for x in args.qtys.split(",")]

    pcb_by_qty = {}
    for tok in args.pcb.split(","):
        k, v = tok.split(":")
        pcb_by_qty[int(k)] = float(v)
    pcb_global = pcb_by_qty
    bom_global = load_bom(args.bom)
    codes = sorted({c for c, _, _ in bom_global})
    print(f"BOM: {len(bom_global)} lines, {len(codes)} distinct parts")

    cache_breaks = fetch_breaks(codes, args.cache)
    missing = [c for c in codes if not (cache_breaks.get(c) or {}).get("breaks")]
    if missing:
        print(f"  WARNING unpriced parts (never guessed): {missing}", file=sys.stderr)

    costly, cheap = classify(bom_global, cache_breaks, qtys, COSTLY_USD_PER_BOARD)
    costly_codes = {c for c, _, _, _ in costly}
    print(f"COSTLY (>= ${COSTLY_USD_PER_BOARD:.2f}/bd): "
          f"{[(c, n) for c, n, _, _ in costly]}")
    print(f"cheap: {len(cheap)} lines")

    # PCB term: exact at measured qtys; INTERPOLATED between them for the rest,
    # and the figure says so. Never extrapolated past the measured range -- out
    # there the total is simply not reported. A total that silently mixed an
    # exact term with an unlabelled guess is the failure this tooling prevents.
    measured_qs = sorted(pcb_by_qty)

    def pcb_at(q):
        if q in pcb_by_qty:
            return pcb_by_qty[q]
        lo = [m for m in measured_qs if m < q]
        hi = [m for m in measured_qs if m > q]
        if not lo or not hi:
            return None
        a, b = lo[-1], hi[0]
        f = (q - a) / (b - a)
        return round(pcb_by_qty[a] + f * (pcb_by_qty[b] - pcb_by_qty[a]), 4)

    # Cliff list: every real band boundary inside the requested range, with the
    # per-board price delta. This is data (cliffs.csv), not just ink on a chart.
    cliff_rows = []
    for code, pb, comment, _ in costly:
        breaks = (cache_breaks.get(code) or {}).get("breaks") or []
        for idx in range(1, len(breaks)):
            bq = int(-(-breaks[idx][0] // max(1, pb)))
            # A band boundary with an UNCHANGED price is not a cliff: the MAX-M10S
            # publishes bands at 12/14/16/18 all at the same price, and calling
            # those cliffs would invent four price drops that do not exist.
            if breaks[idx][2] == breaks[idx - 1][2]:
                continue
            if min(qtys) < bq <= max(qtys):
                from_u = breaks[idx - 1][2] * pb
                to_u = breaks[idx][2] * pb
                cliff_rows.append({
                    "qty": bq, "lcsc": code, "comment": comment, "per_board": pb,
                    "from_usd_per_board": round(from_u, 4),
                    "to_usd_per_board": round(to_u, 4),
                    "delta_usd_per_board": round(to_u - from_u, 4),
                    "label": f"{comment or code} ({code}) ×{pb}  "
                             f"{to_u - from_u:+.3f}/bd",
                })
    cliff_rows.sort(key=lambda r: (r["qty"], -abs(r["delta_usd_per_board"])))
    grouped = {}
    for r in cliff_rows:
        grouped.setdefault(r["qty"], []).append(r["comment"] or r["lcsc"])
    for r in cliff_rows:
        r["label"] = f"{r['comment'] or r['lcsc']} ({r['lcsc']}) " \
                     f"{r['delta_usd_per_board']:+.3f}/bd"

    dec = decompose(bom_global, cache_breaks, qtys)
    rows = {}
    for q in qtys:
        entry = dec[q]
        rows[q] = {
            "pcb": pcb_at(q),
            "cheap": sum(v for c, v in entry["lines"].items() if c not in costly_codes),
            "lines": entry["lines"],
            "unpriced": entry["unpriced"],
        }
        rows[q]["total"] = (None if rows[q]["pcb"] is None
                            else rows[q]["pcb"] + rows[q]["cheap"] + FIXED_FEES)
        if rows[q]["total"] is None:
            print(f"  qty {q}: outside the measured PCB range -> total not reported")

    os.makedirs(args.outdir, exist_ok=True)
    # CSV: physical decomposition
    csv_path = os.path.join(args.outdir, "cost_decomposition.csv")
    hdr = ["qty", "pcb_usd", "cheap_usd"] + [f"costly_{c}" for c, _, _, _ in costly] + \
          ["parts_total_usd", "order_total_usd", "per_board_usd"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(hdr)
        for q in qtys:
            r = rows[q]
            w.writerow([q, r["pcb"], round(r["cheap"], 4)]
                       + [round(r["lines"].get(c, 0.0), 4) for c, _, _, _ in costly]
                       + [round(sum(r["lines"].values()), 4), r["total"],
                          None if r["total"] is None else round(r["total"] / q, 4)])
    print(f"wrote {csv_path}")

    sel_csv = os.path.join(args.outdir, "selective_population.csv")
    with open(sel_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["q_boards", "k_populated", "pcb_usd",
                                          "cheap_usd", "costly_usd", "total_usd",
                                          "per_board_usd"])
        w.writeheader()
        for q_boards in (k for k in pcb_by_qty if k >= 5):
            for r in selective(bom_global, cache_breaks, q_boards,
                               list(range(0, q_boards + 1)), pcb_by_qty,
                               FIXED_FEES, costly_codes):
                w.writerow(r)
    print(f"wrote {sel_csv}")

    cliffs_csv = os.path.join(args.outdir, "cliffs.csv")
    with open(cliffs_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["qty", "lcsc", "comment", "per_board",
                                          "from_usd_per_board", "to_usd_per_board",
                                          "delta_usd_per_board"])
        w.writeheader()
        for r in cliff_rows:
            w.writerow({k: r[k] for k in w.fieldnames})
    print(f"wrote {cliffs_csv} ({len(cliff_rows)} real break(s) in range)")
    for bq in sorted(grouped):
        print(f"   cliff @qty {bq}: {', '.join(grouped[bq])}")

    plot_decomposition(qtys, rows, costly, cheap,
                       os.path.join(args.outdir, "cost_decomposition_log.png"))
    plot_costly_detail(qtys, costly, rows,
                       os.path.join(args.outdir, "costly_components_log.png"))

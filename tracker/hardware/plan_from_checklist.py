#!/usr/bin/env python3
"""plan_from_checklist.py — deterministic cost planning for MODULE boards.

WHY A SECOND INPUT MODE
-----------------------
The hub board is a dense SMD board: cost = BOM x LCSC break tables (pcba_plan.py).
The base-station board is the opposite: a handful of bought MODULES and connectors
(Yagi, BPF, LNA, DSA, log detector, MCU) priced in EUR from vendor pages. Same
planning question, different input shape.

This reads the LIVING CHECKLIST MARKDOWN directly rather than a transcribed copy,
so the plot cannot drift from the document of record. Any row it cannot parse is
REPORTED, never silently dropped.

USAGE
    plan_from_checklist.py --checklist docs/BASE-STATION-BOARD-CHECKLIST.md \
                           --outdir docs/base-station/plan --currency EUR

Answers, with the same honesty rules as pcba_plan.py:
  * what does the board cost, by block?
  * which items are COSTLY (colour-coded) so the operator can decide to omit them?
  * what does it cost with the bench instruments excluded (they are not board parts)?
  * which required rows have NO price (real gaps, counted as 0)?
"""
import argparse
import csv
import os
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# Green is reserved for the "board parts" band so no single item can be confused
# with it (the same rule as pcba_plan.py).
BASECOLOR = "#2ca02c"
PALETTE = ["#d62728", "#1f77b4", "#9467bd", "#ff7f0e",
           "#8c564b", "#17becf", "#e377c2", "#bcbd22"]

# An item is COSTLY when its line total exceeds this. Documented + tunable.
COSTLY_ABS = 20.0
COSTLY_SHARE = 0.05  # or >= 5% of the grand total


def parse_checklist(path):
    """Rows from the checklist markdown table. Unparsed rows are reported."""
    rows, skipped = [], []
    cur_block = None
    for line in open(path, encoding="utf-8"):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 7:
            continue
        if cells[0] in ("#", "---:") or set(cells[0]) <= set("-: "):
            continue
        if not re.fullmatch(r"\d+", cells[0]):
            continue
        idx, block, function, part, status, qty, price = cells[:7]
        # strip markdown emphasis and links from the part name
        part_clean = re.sub(r"[*`]", "", part)
        part_clean = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", part_clean).strip()
        # STATUS: strip markdown emphasis so it prints as TO-BUY, not **TO-BUY**.
        status_clean = re.sub(r"[*`]", "", status).strip().upper()

        # PRICE: a cell may carry SEVERAL bolded prices (row 12 is 15 m of coax
        # PLUS 4 crimps PLUS 1 adapter). Those are a SET, not unit x qty. Taking
        # the first price and multiplying it by a digit-scraped qty produced
        # EUR 99,394 for a EUR 73.73 line. So:
        #   - 2+ bolded prices  -> line total = their SUM, qty = 1
        #   - exactly 1 price   -> unit x qty
        # A price inside parentheses is an ALTERNATIVE ("cheap alt 9.29"), not an
        # additional item: row 2 is "**24.19** (cheap alt **9.29**)" and summing
        # both inflated that row by EUR 9.29. Strip parenthesised groups first.
        price_additive = re.sub(r"\([^)]*\)", " ", price)
        bold_prices = [float(x.replace(",", ""))
                       for x in re.findall(r"\*\*([\d,]+(?:\.\d+)?)\*\*",
                                           price_additive)]
        has_price = bool(bold_prices) and "TODO" not in price.upper()
        if not bold_prices:  # fall back to the first bare number
            m0 = re.search(r"([\d,]+(?:\.\d+)?)", price)
            if m0 and "TODO" not in price.upper():
                bold_prices = [float(m0.group(1).replace(",", ""))]
                has_price = True

        # qty: take the FIRST integer only. "15 m / 4 / 1" -> 15, never "1541".
        mq = re.search(r"\d+", qty)
        qty_n = int(mq.group(0)) if mq else 0
        if qty_n == 0:
            qty_n = 1

        if not has_price or not bold_prices:
            unit_price = line_price = None
        elif len(bold_prices) > 1:
            unit_price = sum(bold_prices)   # the row IS a set of priced items
            line_price = sum(bold_prices)
            qty_n = 1
        else:
            unit_price = bold_prices[0]
            line_price = bold_prices[0] * qty_n

        rec = {
            "row": int(idx), "block": block, "function": function,
            "part": part_clean, "status": status_clean,
            "qty": qty_n,
            "unit_price": unit_price,
            "line_price": line_price,
            "note": cells[7] if len(cells) > 7 else "",
        }
        if rec["unit_price"] is None:
            skipped.append(rec)
        rows.append(rec)
    return rows, skipped


def classify(rows, grand_total):
    costly = []
    for r in rows:
        if r["line_price"] is None:
            continue
        if r["line_price"] >= COSTLY_ABS or (
                grand_total and r["line_price"] / grand_total >= COSTLY_SHARE):
            costly.append(r)
    costly.sort(key=lambda r: -r["line_price"])
    return costly


def money(v, _p=None):
    return f"€{v:,.0f}" if v >= 100 else (f"€{v:,.2f}" if v >= 1 else f"€{v:.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checklist", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--currency", default="EUR")
    ap.add_argument("--exclude-bench", action="store_true", default=True,
                    help="also compute the total without bench instruments")
    args = ap.parse_args()

    rows, unpriced = parse_checklist(args.checklist)
    if not rows:
        sys.exit("no checklist rows parsed — check the table shape")

    priced = [r for r in rows if r["line_price"] is not None]
    grand = sum(r["line_price"] for r in priced)
    print(f"rows: {len(rows)}  priced: {len(priced)}  unpriced: {len(unpriced)}")
    print(f"GRAND TOTAL (priced rows only): {money(grand)}")

    # Bench instruments are TOOLS, not board parts: the single biggest lever.
    BENCH_HINTS = ("bench", "vna", "pitaya", "divider", "mixer", "analy")
    bench = [r for r in priced
             if any(h in (r["block"] + " " + r["function"] + " " + r["status"]).lower()
                    for h in BENCH_HINTS)]
    bench_total = sum(r["line_price"] for r in bench)
    board_total = grand - bench_total
    print(f"  of which BENCH instruments (not board parts): {money(bench_total)}"
          f"  ({bench_total/grand*100:.0f}%)")
    print(f"  BOARD PARTS total: {money(board_total)}")

    costly = classify(rows, grand)
    print(f"\nCOSTLY items (>= {money(COSTLY_ABS)} or >= {COSTLY_SHARE:.0%} of total):")
    for r in costly:
        print(f"  {money(r['line_price']):>10s}  {r['part'][:46]:46s} [{r['status']}]")

    # VALIDATION: the checklist states its own to-buy total. Reproduce it, or say
    # plainly that the parse disagrees with the document.
    to_buy = [r for r in priced if "TO-BUY" in r["status"]]
    tb = sum(r["line_price"] for r in to_buy)
    print(f"\nVALIDATION vs the document's own stated total:")
    print(f"  TO-BUY parsed:            {money(tb)}")
    print(f"  document states ~EUR 274.58 (441.57 incl. the LiteVNA)")
    # Documented: EUR 274.58 to-buy excluding the LiteVNA; EUR 441.57 including it.
    if abs(tb - 274.58) < 1.0:
        print("  MATCH: equals the documented 274.58 (LiteVNA excluded)")
    elif abs(tb - 441.57) < 1.0:
        print("  MATCH: equals the documented 441.57 (LiteVNA included)")
    else:
        print(f"  DISAGREES by {money(abs(tb-441.57))} vs 441.57 -- parser suspect")

    print(f"\nUNPRICED required rows (real gaps, counted as 0):")
    for r in unpriced:
        print(f"  row {r['row']:>2d}  {r['part'][:46]:46s} [{r['status']}]")

    os.makedirs(args.outdir, exist_ok=True)

    # ---- CSV ---------------------------------------------------------------
    csv_path = os.path.join(args.outdir, "checklist_cost.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["row", "block", "function", "part",
                                          "status", "qty", "unit_price",
                                          "line_price", "is_bench", "is_costly"])
        w.writeheader()
        costly_rows = {r["row"] for r in costly}
        bench_rows = {r["row"] for r in bench}
        for r in rows:
            w.writerow({**{k: r[k] for k in w.fieldnames if k in r},
                        "is_bench": r["row"] in bench_rows,
                        "is_costly": r["row"] in costly_rows})
    print(f"\nwrote {csv_path}")

    # ---- plot: block totals, log axis, costly items individually -----------
    blocks = {}
    for r in priced:
        blocks.setdefault(r["block"], 0.0)
        blocks[r["block"]] += r["line_price"]
    order = sorted(blocks, key=lambda b: -blocks[b])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.5, 7))
    # left: cost by block, log
    ypos = range(len(order))
    vals = [blocks[b] for b in order]
    ax1.barh(list(ypos), vals, color="#1f77b4", alpha=0.85)
    ax1.set_yticks(list(ypos))
    ax1.set_yticklabels([b[:26] for b in order], fontsize=9)
    ax1.set_xscale("log")
    ax1.xaxis.set_major_formatter(FuncFormatter(money))
    ax1.set_xlabel(f"{args.currency} (log scale)")
    ax1.set_title("Base-station cost by block (log)")
    for y, v in zip(ypos, vals):
        ax1.annotate(money(v), (v, y), xytext=(4, 0), textcoords="offset points",
                     va="center", fontsize=8.5)
    ax1.grid(alpha=0.3, axis="x", which="both")

    # right: every priced row, costly ones in their own colour, log
    priced_sorted = sorted(priced, key=lambda r: -r["line_price"])
    costly_set = {r["row"] for r in costly}
    names = [f"{r['part'][:30]} [{r['status'][:4]}]" for r in priced_sorted]
    v = [r["line_price"] for r in priced_sorted]
    colors = []
    ci = 0
    for r in priced_sorted:
        if r["row"] in costly_set:
            colors.append(PALETTE[ci % len(PALETTE)])
            ci += 1
        else:
            colors.append(BASECOLOR)
    ax2.barh(range(len(names)), v, color=colors, alpha=0.9)
    ax2.set_yticks(range(len(names)))
    ax2.set_yticklabels(names, fontsize=8)
    ax2.invert_yaxis()
    ax2.set_xscale("log")
    ax2.xaxis.set_major_formatter(FuncFormatter(money))
    ax2.set_xlabel(f"{args.currency} (log scale)")
    ax2.set_title("Every priced line — costly items in their own colour\n"
                  "(green = below the costly threshold)")
    for y, val, r in zip(range(len(names)), v, priced_sorted):
        ax2.annotate(money(val), (val, y), xytext=(4, 0),
                     textcoords="offset points", va="center", fontsize=7.5)
    ax2.grid(alpha=0.3, axis="x", which="both")

    fig.suptitle(f"Base-station board — cost plan "
                 f"(board parts {money(board_total)} + bench {money(bench_total)} "
                 f"= {money(grand)})", fontsize=12)
    fig.text(0.5, 0.015,
             f"Parsed from {os.path.basename(args.checklist)} — vendor-list prices, "
             f"NOT a JLCPCB quote. {len(unpriced)} required row(s) have NO verified price "
             f"and are counted as 0 (real gaps).\n"
             f"BENCH instruments ({money(bench_total)}, {bench_total/grand*100:.0f}% of total) "
             f"are test equipment, not board parts — the single biggest thing to defer.",
             ha="center", fontsize=8.2, color="#444444")
    fig.tight_layout(rect=(0, 0.075, 1, 0.94))
    out_png = os.path.join(args.outdir, "base_station_cost_log.png")
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    print(f"wrote {out_png}")


if __name__ == "__main__":
    main()

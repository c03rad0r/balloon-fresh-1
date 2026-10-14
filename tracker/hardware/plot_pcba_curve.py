#!/usr/bin/env python3
"""plot_pcba_curve.py -- assembled (PCBA) hub price vs quantity.

Reads docs/fab/hub-v9/pcba_hub_qty_curve.csv (produced by the quote run) and
plots BOTH the total price and the per-board price against quantity, because
they answer different questions:

  * total  -> "what will this order cost me?"
  * unit   -> "where do the quantity breaks stop mattering?"

Design rules learned the hard way on this project:
  - NEVER invent a point. Missing quantities are gaps, not interpolations.
  - A point the quote run flagged SUSPECT is drawn as an open/hollow marker and
    excluded from the trend line, so a bad read cannot masquerade as data.
  - The x axis is the ORDERED QUANTITY (5..20), not a category axis, so the
    spacing is truthful.

Usage:
    python3 plot_pcba_curve.py [csv] [--out FILE.png]
"""
import argparse
import csv
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

DEFAULT_CSV = os.path.expanduser(
    "~/worktrees/pcb-defects/docs/fab/hub-v9/pcba_hub_qty_curve.csv"
)


def load(path):
    """-> (rows, suspect_rows); a row is (qty, total, pcb, parts, assembly)."""
    if not os.path.isfile(path):
        print(f"ERROR: no CSV at {path}", file=sys.stderr)
        return None, None

    rows, suspect = [], []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            raw_q = (r.get("qty") or "").strip()
            if not raw_q:
                continue
            # tolerate a qty cell like "10 (SUSPECT)" or a notes column
            try:
                q = int(float(raw_q.split()[0]))
            except ValueError:
                continue

            def num(key):
                v = (r.get(key) or "").strip()
                if not v:
                    return None
                # strip $, commas, and any trailing annotation
                v = v.replace("$", "").replace(",", "").split()[0]
                try:
                    return float(v)
                except ValueError:
                    return None

            total = num("total") if "total" in r else None
            if total is None:
                total = num("total_price")
            rec = (q, total, num("pcb_price"), num("parts_cost"),
                   num("assembly_cost"))
            # Scan EVERY cell for the flag. Restricting the search to a few
            # named columns missed a `SUSPECT` written into a value column
            # (measured in self-test: assembly_cost="SUSPECT" was not caught, so
            # the row would have been drawn as good data).
            note = " ".join(str(v or "") for v in r.values()).upper()
            if "SUSPECT" in note or "EXCLUDED" in note or "UNRELIABLE" in note:
                suspect.append(rec)
            else:
                rows.append(rec)
    rows.sort()
    suspect.sort()
    return rows, suspect


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?", default=DEFAULT_CSV)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rows, suspect = load(args.csv)
    if rows is None:
        return 1
    if not rows and not suspect:
        print("ERROR: CSV has no usable qty/total rows.", file=sys.stderr)
        return 1

    xs = [r[0] for r in rows]
    tot = [r[1] for r in rows]
    unit = [(r[1] / r[0]) if r[1] is not None else None for r in rows]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 9), sharex=True)

    # ---- total ----
    ax1.plot(xs, tot, "o-", color="#1f77b4", lw=2, ms=7, label="total (observed)")
    for q, t, *_ in suspect:
        if t is not None:
            ax1.plot([q], [t], "o", mfc="none", mec="#d62728", ms=11, mew=2,
                     label="SUSPECT (excluded)" if q == suspect[0][0] else None)
    for q, t in zip(xs, tot):
        if t is not None:
            ax1.annotate(f"${t:,.0f}", (q, t), textcoords="offset points",
                         xytext=(0, 8), ha="center", fontsize=8)
    ax1.set_ylabel("Total order price (USD)")
    ax1.set_title("JLCPCB assembled (PCBA) hub v9 — total vs quantity")
    ax1.grid(alpha=0.3)
    ax1.legend(loc="upper left", fontsize=9)

    # ---- unit ----
    ax2.plot(xs, unit, "s-", color="#2ca02c", lw=2, ms=7,
             label="per board (observed)")
    for q, t, *_ in suspect:
        if t is not None:
            ax2.plot([q], [t / q], "s", mfc="none", mec="#d62728", ms=11, mew=2,
                     label="SUSPECT (excluded)" if q == suspect[0][0] else None)
    for q, u in zip(xs, unit):
        if u is not None:
            ax2.annotate(f"${u:,.2f}", (q, u), textcoords="offset points",
                         xytext=(0, 8), ha="center", fontsize=8)
    ax2.set_xlabel("Quantity ordered (boards)")
    ax2.set_ylabel("Price per board (USD)")
    ax2.set_title("Per-board price vs quantity — where breaks stop mattering")
    ax2.set_xticks(range(min(xs), max(xs) + 1))
    ax2.grid(alpha=0.3)
    ax2.legend(loc="upper right", fontsize=9)

    missing = sorted(set(range(min(xs), max(xs) + 1)) - set(xs))
    # PROVENANCE. A chart that looks like a quote when it is a model is a lie.
    # If the source CSV self-declares as derived, say so ON THE CHART.
    provenance = "Source: JLCPCB Quote & Order page, assembled service."
    try:
        with open(args.csv, newline="") as fh:
            first = next(csv.DictReader(fh), None)
        blob = " ".join(str(v or "") for v in (first or {}).values()).upper()
        if "DERIVED" in blob or "NOT A PAGE QUOTE" in blob:
            # Keep this SHORT and WRAP it. A long single line is silently
            # clipped by the figure edge (measured: "excl..." ran off the right
            # and the leading "MODEL" ran off the left), which is the one
            # failure mode that matters here -- an unreadable honesty note.
            provenance = ("MODEL, not a page quote: LCSC price-break tables + "
                          "measured $32.30 @qty5 + $25/side setup.\n"
                          "Derived values; verify on the JLCPCB page before ordering.")
    except Exception:
        pass
    footnote = provenance
    if suspect:
        # only mention the marker convention when the chart actually uses it
        footnote += "  Hollow = flagged SUSPECT, excluded."
    if missing:
        footnote += f"  MISSING (not interpolated): {missing}."
    fig.text(0.5, 0.012, footnote, ha="center", va="bottom", fontsize=7.5,
             color="#444", wrap=True)

    fig.tight_layout(rect=(0, 0.055, 1, 1))  # leave room for 2-line note
    out = args.out or os.path.expanduser("~/pcba_hub_qty_curve.png")
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")
    print(f"points: {len(rows)} observed, {len(suspect)} suspect, "
          f"{len(missing)} missing")
    for q, t, *_ in rows:
        print(f"  qty {q:>3}: total ${t:,.2f}  unit ${t/q:,.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

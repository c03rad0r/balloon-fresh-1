#!/usr/bin/env python3
"""plot_pcba_breakdown.py -- bare-board vs assembled-with-parts price decomposition.

Answers: "do these prices include the parts?" -- the curve already did, but this
makes the decomposition visible: PCB fab vs parts vs setup, total AND per board.

Data: the validated derived curve (LCSC break tables, 0.7% agreement with the
measured page at qty 5). Same honesty rules: MODEL label on the figure, cliffs
drawn only where break boundaries actually are (10, 13), no interpolation of
unmeasured terms -- the per-placement assembly fee is EXCLUDED and said so.
"""
import argparse
import csv
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---- CLI -----------------------------------------------------------------
ap = argparse.ArgumentParser()
ap.add_argument("csv_path")
ap.add_argument("--out", required=True)
args = ap.parse_args()

# ---- load ----------------------------------------------------------------
rows = []
with open(args.csv_path, newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        blob = " ".join(str(v) for v in r.values()).upper()
        if "SUSPECT" in blob:
            continue  # flagged reads never render as good data
        try:
            rows.append({
                "qty": int(r["qty"]),
                "pcb": float(r["pcb_price"]),
                "parts": float(r["parts_cost"]),
                "setup": float(r["assembly_cost"]),
                "total": float(r["total"]),
            })
        except (KeyError, ValueError):
            continue
rows.sort(key=lambda x: x["qty"])
if not rows:
    sys.exit("no usable rows")

q = [x["qty"] for x in rows]
pcb = [x["pcb"] for x in rows]
parts = [x["parts"] for x in rows]
setup = [x["setup"] for x in rows]
total = [x["total"] for x in rows]
u_pcb = [p / n for p, n in zip(pcb, q)]
u_parts = [p / n for p, n in zip(parts, q)]
u_setup = [p / n for p, n in zip(setup, q)]
u_total = [t / n for t, n in zip(total, q)]
bare = [p for p in pcb]  # fab-only curve = the bare-board order

# ---- figure ----------------------------------------------------------------
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 11), sharex=True)
SETUPC, PARTSC, PCBC = "#9e9e9e", "#1f77b4", "#ff7f0e"
for ax in (ax1, ax2):
    for c in (10, 13):
        ax.axvline(c, color="#d62728", ls="--", lw=1, alpha=0.55)

# Panel 1: totals, stacked
ax1.stackplot(q, pcb, parts, setup,
              labels=["PCB fab (bare board)", "Parts (LCSC)", "Setup $25/side"],
              colors=[PCBC, PARTSC, SETUPC], alpha=0.85)
ax1.plot(q, bare, color=PCBC, lw=2.4, marker="o", ms=4,
         label="Bare-board order (fab only)")
ax1.plot(q, total, color="black", lw=2.2, marker="s", ms=4,
         label="Assembled total (PCB+parts+setup)")
ax1.set_ylabel("Order total (USD)")
ax1.set_title("Hub v9 — bare boards vs assembled (parts included)")
ax1.legend(loc="upper left", fontsize=9)
ax1.grid(alpha=0.3)
for n, t in zip(q, total):
    ax1.annotate(f"${t:,.0f}", (n, t), textcoords="offset points",
                 xytext=(0, 7), ha="center", fontsize=7.5)

# Panel 2: per board, stacked
ax2.stackplot(q, u_pcb, u_parts, u_setup,
              labels=["PCB fab / board", "Parts / board", "Setup / board"],
              colors=[PCBC, PARTSC, SETUPC], alpha=0.85)
ax2.plot(q, u_total, color="black", lw=2.2, marker="s", ms=4,
         label="Assembled $/board")
ax2.plot(q, u_pcb, color=PCBC, lw=1.8, marker="o", ms=3.5,
         label="Bare fab $/board")
ax2.set_ylabel("USD per board")
ax2.set_xlabel("Boards ordered")
ax2.set_title("Per-board price — parts are 72–86% of the total")
ax2.legend(loc="upper right", fontsize=9)
ax2.grid(alpha=0.3)
for n, v in zip(q, u_total):
    ax2.annotate(f"${v:,.2f}", (n, v), textcoords="offset points",
                 xytext=(0, 7), ha="center", fontsize=7.5)
ax2.set_xticks(q)

fig.text(0.5, 0.005,
         "MODEL derived from LCSC break tables (page cross-check 0.7% @qty5) — NOT a page quote.\n"
         "Includes: PCB fab + LCSC parts + $25/side setup. EXCLUDES: per-placement assembly "
         "fee (unmeasured) and shipping ($23.36/parcel).\n"
         "Dashed red = real price cliffs (qty 10: five ICs break; qty 13: U.FL). "
         "Intermediate PCB steps 6-9,11-12,14-19 are interpolated, not measured.",
         ha="center", fontsize=8.2, color="#444444", wrap=True)
fig.tight_layout(rect=(0, 0.055, 1, 1))
fig.savefig(args.out, dpi=150)
print(f"wrote {args.out}: {len(q)} qty points, qty {q[0]}..{q[-1]}")

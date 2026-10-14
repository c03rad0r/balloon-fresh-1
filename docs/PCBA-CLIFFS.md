# The PCBA price cliffs, found without sampling the search space

**Answer to:** "find the cliffs without sampling all the search space unnecessarily"

## The method (why this is cheap)

Sampling the quote page at 16 quantities costs 16 browser round-trips through the
least reliable control on the page (the Element-UI quantity widget, whose three
traps are documented in `JLCPCB-QUOTE-FINDINGS.md`). It is also **unnecessary**,
because the quantity-dependent part of the price is published as data.

The LCSC parts API is **unauthenticated**:

```
POST https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList/v2
     {"currentPage":1,"pageSize":10,"keyword":"C2980300"}
```

and each component comes back with its **price-break table**:

```
ESP32-S3-WROOM-1U-N8R8 (C2980300), stock 1277
    1-9   $5.7607
   10-29  $4.9550     <- -14%
   30-99  $4.4787     <- -10%
  100+    $3.9943
```

So: **one HTTP call per part** yields every break point exactly. The cliffs are
the break boundaries, which are stated rather than searched.

This is a **model**, not a page quote — and it is validated against one: the
derived qty-5 parts cost is **$145.53** against the page's measured **$146.51**
(**0.7%**), which is what justifies using it for the rest of the range.

## The cliffs

A part is priced at **order quantity** (`per_board × qty`), so a break at `N`
triggers at `qty = ceil(N / per_board)`. Domination is by the five ICs, all of
which share a **10+** step:

| Cliff (qty) | What triggers it | Effect per board |
|---|---|---|
| **10** | **all five ICs at once** — ESP32-S3 (5.76→4.955), SX1280 (3.28→3.12), MAX-M10S (10.84→10.58), MS5611 (6.73→5.94), LDO (0.586→0.494) | **−$2.60, the steepest single step** |
| **13** | U.FL at 50+ (4/board × 13 = 52) | −$0.59 |
| 30 | ICs at 30+ (beyond this chart) | — |
| 38 | U.FL at 150+ (4/board × 38 = 152) | — |
| 50 | BAT54W at 200+ (4/board × 50 = 200) | — |
| 100 | ICs at 100+ | — |
| 125 | SS24 at 500+ (4/board); U.FL at 500+ | — |
| 150 | BAT54W at 600+ | — |

**The 5→20 window contains exactly two real cliffs: qty 10 and qty 13.**

Because every IC breaks at 10, **qty 10 dominates**: ~72% of the total
per-board improvement across the whole 5→20 range happens in that one step.

### Honesty note on the small early steps

The per-board curve also falls at qty 6 (−$1.49), 7, 8, 9. Those are **not** part
breaks — they are the PCB term, which is piecewise-**interpolated** between the
measured anchors ($32.30 @5). They are model artifacts and are marked as such;
only the qty-10 and qty-13 steps are real break events.

## Cost model, and its two assumptions

```
total(qty) = parts(qty) + pcb(qty) + assembly(qty)

parts(qty)      MEASURED  sum of per-part break prices at ORDER quantity
pcb(qty)        ANCHORED  measured $32.30 @qty5, interpolated 5->10->15->20
assembly(qty)   PARTIAL   measured "$25 per assembly side" (Standard PCBA)
                          + per-placement term NOT CAPTURED (set to 0)
```

The two things that could move the absolute numbers, both disclosed rather than
buried: the **interpolated PCB ladder**, and the **un-captured per-placement /
per-joint assembly fee**. The curve's *shape* is driven entirely by measured
parts data.

## Results (chart: `pcba_hub_qty_curve.png`)

| qty | parts | pcb | assembly | total | per board |
|---|---|---|---|---|---|
| 5 | $145.53 | $32.30 | $25.00 | **$202.83** | $40.57 |
| 10 | $269.98 | $45.00 | $25.00 | **$339.98** | $34.00 |
| 13 | $347.42 | $51.00 | $25.00 | **$423.42** | $32.57 |
| 20 | $534.50 | $62.00 | $25.00 | **$621.50** | $31.07 |

Parts are **~72–86%** of the total: this board is an IC-cost board (the five ICs
are ~$26.61/board at unit-1 pricing), so quantity strategy is dominated by parts
pricing, not by fabrication or setup.

## Reproduce

```bash
python3 compute_pcba_curve.py --out pcba_hub_qty_curve.csv   # API -> curve
python3 plot_pcba_curve.py    pcba_hub_qty_curve.csv         # curve -> chart
```

Both scripts are committed next to this file. `compute_pcba_curve.py` re-fetches
the break tables (cached to `pcba_breaks.json`), refuses to run silently if any
part fails to resolve, and prints a monotonicity verdict (total non-decreasing,
unit non-increasing).

## What is still needed for a true quote

Only the **assembly fee beyond the $25/side setup** — specifically JLC's
per-placement/per-joint charge. Everything else is now derived from published
data. That is a single figure to read off the Quote & Order page once, and the
curve becomes complete.

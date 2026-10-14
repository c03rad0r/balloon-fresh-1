# Cross-validation: the derived model vs JLCPCB's real page costs

**Date:** 2026-10-14
**Verdict:** the model is validated on 10 of 13 comparable lines to the cent
($0.0000 delta), and the remaining three reveal a real cost factor the model
does not yet carry.

## What was compared

JLCPCB's **Component Placements** table carries a real per-line `Total Cost`
column. A timed-out browser worker captured that table at qty 5
(`~/jlc-pcba-work/p3_matched_body.txt`). That is ground truth, and it is the
strongest test the derived model has had — much stronger than the earlier
aggregate cross-check, because it compares **line by line**.

## Line-by-line result

| LCSC | page qty | page $ | placed | model $ | delta |
|---|---|---|---|---|---|
| C434808 U.FL ×4 | 20 | 7.2100 | 20 | 7.2100 | **0.0000** |
| C15525 10uF | 5 | 0.1285 | 5 | 0.1285 | **0.0000** |
| C15008 100uF | 5 | 0.6535 | 5 | 0.6535 | **0.0000** |
| C15195 10nF | 5 | 0.0245 | 5 | 0.0245 | **0.0000** |
| C25744 10k ×2 | 10 | 0.0330 | 10 | 0.0330 | **0.0000** |
| C26083 1M ×2 | 10 | 0.0240 | 10 | 0.0240 | **0.0000** |
| C25076 100R | 5 | 0.0060 | 5 | 0.0060 | **0.0000** |
| C2980300 ESP32-S3 | 5 | 28.8035 | 5 | 28.8035 | **0.0000** |
| C125969 SX1280 | 5 | 16.4240 | 5 | 16.4240 | **0.0000** |
| C4153167 MAX-M10S | 5 | 54.1975 | 5 | 54.1975 | **0.0000** |
| C699107 BAT54W | **20** | 0.6380 | 5 | 0.1595 | **+0.4785** |
| C11906 4.7M ×2 | **20** | 0.0300 | 10 | 0.0150 | **+0.0150** |
| C5142805 LDO | **9** | 5.2704 | 5 | 2.9280 | **+2.3424** |

Ten lines agree **to the cent**. The three that do not are all
**Extended-library** parts, and in each case the page's quantity is HIGHER than
the number of placements.

## The reconciliation (exact, not approximate)

```
model total (covered lines)      $110.6070
+ BAT54W purchase-qty delta      + 0.4785
+ 4.7M   purchase-qty delta      + 0.0150
+ LDO    purchase-qty delta      + 2.3424
                                 ─────────
page total (covered lines)       $113.4429   ✓ matches the page exactly
```

The page's table covers 13 of the 16 BOM lines; it does **not** show C15639
(MS5611) or C50645 (SS24). Adding those back to the model
($145.03 − $33.63 − $0.77 ≈ $110.6) reproduces the same covered-lines figure, so
the two sides are consistent once coverage is equalised.

## What this means — and a correction to my own earlier claim

**Earlier I "corrected" BAT54W from ×4 to ×1 and called the ×4 a mistake. That
was half right and half wrong, and the half-wrong part mattered:**

- For **placement**, the BOM designator list is right: one BAT54W (`D1`) is
  populated per board. The CPL agrees.
- For **purchase**, JLC buys an Extended part in a **minimum quantity**, and you
  pay for what it buys. At qty 5 boards, C699107 is bought in 20s and C11906 in
  20s — 4× the placements.

So the ×4 was not a fabrication; it was the *purchase* quantity read as a
*placement* quantity. Both numbers are real, and they answer different questions.

**Model limitation to carry forward:** `pcba_plan.py` computes parts cost as
`placements × unit price`. For **Extended** parts at small order quantities that
understates cost, because the MOQ dominates. The direction is known
(understatement) and the magnitude is measurable per line; it is NOT yet
modelled.

**Hypothesis, explicitly unverified:** the page's qty column is a
minimum-purchase quantity for Extended parts. The evidence is consistent (all
three mismatches are Extended; all three are rounded up; C434808 is Extended but
already at 20 placements so no gap appears) but the mechanism has not been
confirmed against JLCPCB's documentation. Treat it as a lead, not a fact.

## Action taken

- The BOM keeps C50645 for SS24 (C78573 has stock 0 and no price bands — it
  cannot be ordered). Unchanged by this analysis.
- BAT54W placement stays ×1 (BOM and CPL agree).
- The purchase-quantity effect is recorded here rather than baked into the model,
  because the mechanism is unverified. A model that quietly absorbed an
  unverified multiplier would be exactly the kind of fabricated number this
  tooling exists to prevent.

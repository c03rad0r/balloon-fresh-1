# Envelope material — gap analysis against the pasted AI advice

**Date:** 2026-10-15 · **Feeds:** the envelope decision (`docs/analysis/pico-balloon-envelope-mass.md`)
**Reproduce:** `python3 docs/analysis/envelope_material_gap.py`
**Tests:** `tests/test_envelope_material_gap.py` (11 cases)

Answers the operator's ask: *"research this with your consultants, do a gap analysis to see how it
fits in with what we are building in terms of cost and reliability, make a recommendation."*

The pasted conversation recommended **metallized BoPET / Mylar / "Cymylar"** envelopes, compared
them to Yokohama 32-inch nylon/PE spheres on cost and durability, and argued that a third layer
makes cheap film **less** reliable.

---

## 0. The answer, up front

> **No action on the envelope. Our design is already the paste's own top recommendation.**

The paste's recommendation reduces to *"use a high-grade low-permeability envelope (Yokohama /
SBS-13 class), not cheap film, and do not stack layers."* That is what this repo already flies.

| Paste recommendation | Our current design | Action |
|---|---|---|
| Use a high-grade low-permeability envelope | **Yokohama 32″ nylon/PE, 48.6 g** (measured) | none — already done |
| Don't use cheap film (high pinhole risk) | not on cheap film | none |
| Don't stack three layers | single envelope | none — already done |
| Floats 40–45 k ft vs 35–38 k ft for cheap film | Yokohama is the high-altitude option | none |

## 1. The gap is in the DECISION FRAME, not the technology

The paste argues on the axis **cost-per-balloon**. Our problem is not that axis.

| | paste's frame | our frame |
|---|---|---|
| flights | "blowing through five budget balloons" | **one flight, one envelope** |
| deciding variables | unit price, replacement rate | **dry mass** and **leak rate** |
| cost delta | $25 vs ~$2 = "Yokohama hurts" | $23 total, i.e. **$0.47 per gram of envelope** |

The envelope is **88 %** of our non-payload mass:

| envelope | mass | non-payload total | envelope share |
|---|---|---|---|
| **Yokohama 32″ new (ours)** | **48.6 g** | **54.97 g** | **88 %** |
| Yokohama 32″ old | 41.0 g | 47.37 g | 87 % |
| Qualatex Silver 36″ | 37.0 g | 43.37 g | 85 % |
| Chinese Clear 36″ | 38.0 g | 44.37 g | 86 % |

*(non-payload = envelope + 4.17 g helium + 2.20 g attachments, for a 20 g payload at 6 g free lift.)*

**So a $23 delta buys the single largest term in the budget.** At `$25 / 48.6 g` the Yokohama costs
**$0.51 per gram of envelope** — and the alternative saves **$0.47 per gram**. That is not a
trade-off; it is rounding error against the risk of losing the entire flight.

## 2. The paste's own rationale contradicts its own recommendation

This is the sharpest defect in the paste, and it is internal:

1. It asserts the envelope **"must be roughly 1/1000th of an inch thick and inelastic"**, and that
   a **"zero-stretch superpressure envelope"** is required.
2. It then recommends **Yokohama** — whose own manufacturer describes the material as
   **"Nylon, Polyethylene"**, a laminate **designed to stretch** (repo read of the MFR catalogue,
   `pico-balloon-envelope-mass.md` §1).

BoPET/Mylar is metallized polyester (effectively inelastic). Yokohama 32″ is a stretchable
nylon/PE sphere. **These are opposite mechanical regimes**, and the paste recommends the
stretchable one while arguing for the inelastic one. Its stated mechanism does not support its
stated pick.

It also lists **"SBS-13 / Yokohama Film" as a single row**, implying one material class. They are
not: SBS-13 is a superpressure film, the Yokohama 32″ is a party/scientific sphere.

## 3. Claim-by-claim verdict

Every "our" figure is already sourced in this repo. Every "unverified" is a paste figure we did
not need, and say so rather than absorbing it.

| paste claim | verdict |
|---|---|
| Material should be metallized BoPET / Mylar / Cymylar | structural — holds for a *superpressure* design, not for ours |
| Film must be inelastic, ~1/1000 in | structural — **contradicts** its own Yokohama pick |
| Yokohama dry weight ~48.6 g | **REAL** — matches our measured community value |
| Yokohama costs ~$25 / $250 per 10-pack | UNVERIFIED |
| Yokohama volume ~0.27–0.50 m³ | **INFLATED** — ours is 240–270 L = **0.24–0.27 m³** |
| Yokohama floats 40,000–45,000 ft | UNVERIFIED |
| Clear Cymylar floats 35,000–38,000 ft | UNVERIFIED |
| Clear Cymylar costs $1.50–2.00 | UNVERIFIED |
| Clear Cymylar weighs 15–25 g | UNVERIFIED |
| Yokohama leak ~1/6 of cheap film, "SBS-13 class" | UNVERIFIED |
| SBS-13 costs ~$165 | UNVERIFIED |
| "36-inch to 60-inch" Yokohama-class foil envelopes exist | **FABRICATED** — the manufacturer's range is **7/10/14/20/24/32 inch**; **there is no 36″ Yokohama** |
| Three layers make cheap film less reliable | modelling claim — see §4 |

**The one claim it got right is the measured mass** (48.6 g). Everything numeric it adds is either
unverified or wrong, and the one structural error (a 36″ Yokohama) is the kind that would mis-size
a design.

## 4. "Three layers" — the paste is right, and we already comply

The paste's substantive contribution: **a second/third envelope does not behave as parallel
redundancy, because a failed envelope keeps its dry mass** rather than shedding it.

**Our arithmetic agrees, and quantifies it:**

| n | envelope dry | non-payload | extra lift needed | verdict |
|---|---|---|---|---|
| 1 | 48.6 g | 54.97 g | 0 g | **FEASIBLE** |
| 2 | 97.2 g | 103.57 g | 48.6 g | exceeds the 85 g community ceiling |
| 3 | 145.8 g | 152.17 g | 97.2 g | exceeds it further |

A second envelope costs **48.6 g against a 6 g free-lift allowance** — **8.1× the allowance
itself**. In the usual parallel-reliability formula redundancy is cheap because a failed unit drops
out; here it cannot, because the plastic stays attached. So the paste is correct on the
mathematics — and we fly a **single** envelope, so the conclusion changes nothing.

Note this is also consistent with our own measurement: the community's free-lift band is 5–7 g and
a Yokohama gives ~8 g max free lift. There is no margin to carry a spare skin.

*(The formalism behind this — whether "number of sealed envelopes" is a Markov state, and the
correct model — is treated in the consultant pass; see §6.)*

## 5. What the paste CANNOT see: our legal constraint

`docs/analysis/free-balloon-mass-threshold-DE.md` establishes the German position. Under a
**total-mass** reading of a 20 g threshold, our non-payload subtotal is **54.97 g** — the design is
**~35 g over budget before any payload is added**, and the envelope alone is **2.43×** the entire
allowance.

**This makes lightweight film MORE attractive, not less** — and it is the one place the paste
accidentally points somewhere useful. But the trade is: a lighter envelope (Chinese Clear 36″,
38 g) saves **10.6 g** while taking the leak-rate and pinhole risk the paste itself warns about.
That is a real trade with real numbers, and it belongs on the mass-threshold card, not in an
envelope-material decision made from a cost comparison.

**Recorded as an open question, not a recommendation** — it depends on which threshold reading
applies, which is the sibling task's subject.

## 6. Consultant passes

Two independent passes were dispatched, each with pinned toolsets (`terminal`, `web`) and the
requirement to cite a fetched URL per load-bearing claim:

1. **Claim verification** — the cost / altitude / volume / leak-rate figures above.
2. **Reliability mathematics** — whether the paste's Markov-chain framing is statistically sound
   (is "number of sealed envelopes" even a Markov state?), whether the bathtub/Weibull reasoning
   is correct, and whether the dead-weight conclusion follows from a correct model.

Their verdicts are folded in below when they land. **Where they disagree with this document, the
consultant verdict wins and this document is corrected** — the point of the pass is to catch our
own error, not to confirm it.

## 7. Recommendation

> **Keep the Yokohama 32″ nylon/PE envelope. Do not switch to BoPET/Mylar. Do not add layers.
> Take no action from this paste.**

Reasons, in order of weight:

1. **The decision does not depend on any number the paste supplies.** Our envelope choice is
   already the paste's top recommendation; the paste's numeric additions are unverified or wrong.
2. **Its cost framing is off-axis for us.** We fly one envelope once; the envelope is 88 % of
   non-payload mass, and $23 is $0.47/g.
3. **Its own rationale contradicts its own pick** (inelastic foil vs a stretchable laminate).
4. **Its redundancy conclusion is correct and we already comply** (single envelope; the
   dead-weight arithmetic is quantified in §4).
5. **The one real opening it exposes is a MASS question, not a material question** — a lighter
   envelope buys 10.6 g under a total-mass threshold, at a leak-rate cost. That belongs on the
   mass-threshold card.

### What would change this

- A **measured** leak rate for the Yokohama that is materially worse than the community's
  ~1/6-of-cheap-film claim, at our altitude and temperature profile.
- A **measured** pinhole/infant-mortality rate on the Yokohama lot we own.
- A resolution of the German threshold reading that makes total mass binding — then the 10.6 g
  envelope-mass saving becomes worth pricing against the leak risk.

## 8. Open items

1. Every paste cost/altitude figure is `TODO(unverified)` — deliberately not absorbed, because
   the decision does not turn on them.
2. "Cymylar" is not resolved as a product or brand name; it may be a misspelling of Mylar/Cymer.
   Only matters if this ever becomes a live option.
3. The German threshold reading (payload vs total mass) decides whether a lighter envelope is worth
   the leak risk — sibling task `docs/analysis/free-balloon-mass-threshold-DE.md`.

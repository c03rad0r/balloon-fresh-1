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
| cost delta | $25 vs ~$2 = "Yokohama hurts" | **$10 total** — and the paste's $25 is ~2× too high (see §3) |

The envelope is **88 %** of our non-payload mass:

| envelope | mass | non-payload total | envelope share |
|---|---|---|---|
| **Yokohama 32″ new (ours)** | **48.6 g** | **54.97 g** | **88 %** |
| Yokohama 32″ old | 41.0 g | 47.37 g | 87 % |
| Qualatex Silver 36″ | 37.0 g | 43.37 g | 85 % |
| Chinese Clear 36″ | 38.0 g | 44.37 g | 86 % |

*(non-payload = envelope + 4.17 g helium + 2.20 g attachments, for a 20 g payload at 6 g free lift.)*

**So a ~$10 delta buys the single largest term in the budget.** At the manufacturer's live price of
**$12.00 per balloon** (see §3) the Yokohama costs **$0.25 per gram of envelope**. That is not a
trade-off; it is rounding error against the risk of losing the entire flight — and the paste's
$25 figure overstated the price by roughly **2×**, in the direction that made our already-correct
choice look expensive.

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

Every row below was checked against a **source that was actually fetched** (manufacturer
`products.json`, product JSON-LD, Amazon brand store, EOSSP-2 flight logs, QRP Labs PDFs,
Wayback CDX). Search engines were bot-walled; Marginalia + direct fetches were used instead.

| paste claim | verdict | the fetched figure |
|---|---|---|
| Material should be metallized BoPET / Mylar / Cymylar | structural — holds for a *superpressure* design, **not ours** | — |
| Film must be inelastic, ~1/1000 in | structural — **contradicts** its own Yokohama pick | Yokohama page: "Made from film that has superior **stretchability**" |
| Yokohama dry weight ~48.6 g | **REAL** — matches our measured community value | KevWal/Balloon-Info |
| Yokohama costs ~$25 ea / ~$250 per 10-pack | **FABRICATED, ~2× high** | live `products.json`, JSON-LD: `"price":120.0` per **10-pack** → **$12.00/balloon** (with valve $130) |
| Yokohama volume ~0.27–0.50 m³ | **INFLATED** | ours: 240–270 L = **0.24–0.27 m³** |
| Yokohama floats 40,000–45,000 ft, "44,000+" | REAL, **community report only — not a spec** | KevWal: 7 g payload → 13.5 km (≈44,300 ft) |
| Clear Cymylar floats 35,000–38,000 ft, "days to weeks" | **REFUTED BY A REAL FLIGHT** | EOSSP-2: 60″ Cymylar → **45,000 ft**, last report 46,522 ft **after 299 days aloft**, 19 circumnavigations |
| Clear Cymylar costs $1.50–2.00 | UNVERIFIABLE-WITHOUT-PROBE | no source ties that price to a pico-size envelope |
| Clear Cymylar weighs 15–25 g | **FABRICATED** | EOSS: 60″ = **70.75 g**; Chinese-clear 36″ = **38 g** |
| Yokohama leak ~1/6 of cheap film, "SBS-13 class" | UNVERIFIABLE — no leak datum exists | Yokohama claims only generic "high-barrier materials" for a *different* line |
| SBS-13 costs ~$165 | **FABRICATED — and SBS-13 is not a film** | it is **Scientific Balloon Solutions' finished super-pressure balloon** ("machine seamed … 43k–45k ft … 1mil"). Wayback: **$139** (2016) → **$189** (2017-02) → **$129** (2017-11/2018); today quote-only. **$165 in no snapshot.** |
| "Cymylar" is a misspelling | **WRONG — it is a live brand** | Amazon brand store `CYMYLAR` (175 results); sells metallized party foil |
| "36-inch to 60-inch" Yokohama envelopes | **FABRICATED** | manufacturer range is **7/10/14/20/24/32 inch**; there is **no 36″ Yokohama** |
| "38,000–43,000 ft" (its own 1st answer) | internally inconsistent | matches neither EOSS (45 k) nor KevWal (13.5 km) |
| Three layers make cheap film less reliable | **FALSE for its own stated hardware** | see §4 — it is a *sizing* or *common-mode* effect, not cheapness |

**What survives contact:** the measured mass (48.6 g) and the stretched volume (~0.17 m³, QRP
Labs' own measuring rig). **Everything else numeric is wrong, unverifiable, or a category error**
— and two of them (the 36″ Yokohama, "SBS-13 film") would mis-size a design or send a purchase
to a product that does not exist in that class.

## 4. "Three layers" — the paste got the mechanism wrong, and the conclusion wrong

The paste's substantive claim: **a second/third envelope does not behave as parallel redundancy,
because a failed envelope keeps its dry mass**, so "adding a third layer makes cheap film *less*
reliable".

A consultant pass modelled this rigorously (NIST/SEMATECH e-Handbook §8.1 + Monte-Carlo to
<0.2 %). The verdict is that the paste **reaches a real effect by a wrong route, then states it
for hardware where it does not hold**.

### 4a. Its formalism is mislabelled

- **The state space is fine.** `{n … 0}` *is* a legitimate absorbing chain. Nothing about counting
  envelopes is illegitimate.
- **The Markov *property* lives in the holding times, not the state labels.** With non-exponential
  per-envelope life the process is **not a CTMC** — the correct name is a **semi-Markov process**
  (Markovian only at the failure epochs). Fix: **phase-type / Coxian expansion**, folding age into
  extra pseudo-states, which recovers an honest CTMC on an expanded state space.
- **"Markov chains assume exponential failure rates" is right for continuous-time, false for
  discrete-time chains**, and misapplied here: the objection is about holding-time distributions.
- **The dead-weight point is a REWARD/drift claim** (`Λ(k) = k·B − W_tot`), a separate layer from
  the Markov property. The paste stacks the two as if one followed from the other. It does not.

### 4b. The correct deciding condition

With a failed envelope **retaining** its mass (the paste's premise), the lift needed to buy
redundancy grows **quadratically**, and a third envelope is net-harmful past

> **`m* = (2B − P) / 3`**  — equivalently, required total lift `n²m + nP` (retained) vs `n(m+P)` (shed).

With a **shedding** mechanism the cost is linear and **redundancy never backfires**.

### 4c. Applied to OUR hardware — and it confirms our decision

| | envelope dry `m` | gross lift `B` | boundary `m*` | in backfire regime? |
|---|---|---|---|---|
| **us (Yokohama 32″)** | **48.6 g** | **56.6 g** | **31.1 g** | **YES — m > m\*** |
| the paste's hypothetical | 18 g | 110 g | 65 g | no — m ≪ m* |

**Our hardware genuinely IS in the backfire regime**, so a third envelope is net-harmful — and the
consultant's formula arrives at that **independently of the mass-allowance argument in §4/§1**.
Two different calculations, same conclusion.

**But note why:** our envelope is a heavy high-barrier sphere giving only **8 g of maximum free
lift**. There is almost no margin for a second skin. The paste's hypothetical was *light film with
huge lift headroom* — the opposite situation. **The paste's own numbers are NOT in the backfire
regime**, so its headline claim ("triple makes cheap film less reliable") is **false for the
hardware it was describing**. Where a third layer genuinely fails there, the cause is
**sizing** (`(B − m) ≤ m + P`) or **common mode** — neither of which is the mechanism it named.

Its sign is also backwards on its own argument: for **infant-mortality** film (Weibull β < 1) the
redundancy payoff is **higher**, not lower (×2.09 at β = 0.7 vs ×1.83 at β = 1.0). A single
2-parameter Weibull **cannot** produce a bathtub at all — that needs a mixture of a weak (β<sub>1</sub> < 1)
and a healthy (β<sub>2</sub> > 1) subpopulation.

### 4d. The caveat the paste MISSED — and it is the strong one

**Common mode.** Three layers sharing one **neck, weld, valve or tether** have **one point of
failure**. Marshall–Olkin / beta-factor: `R_sys = (1−q)·[1 − (1−p)^N]`. Even at `q = 0.9` the
ordering S1 < S2 < S3 holds but the **absolute gain collapses**.

> **Redundancy cannot fix a shared cause — and for a pico balloon the neck and weld ARE shared
> causes.** That is the legitimate reason not to stack envelopes. It is not the reason the paste
> gave.

Our arithmetic agrees and is simpler: each extra envelope adds **48.6 g of dry mass** against a
**6 g free-lift allowance** — **8.1× the allowance itself**.

| n | envelope dry | non-payload | extra lift needed | verdict |
|---|---|---|---|---|
| 1 | 48.6 g | 54.97 g | 0 g | **FEASIBLE** |
| 2 | 97.2 g | 103.57 g | 48.6 g | exceeds the 85 g community ceiling |
| 3 | 145.8 g | 152.17 g | 97.2 g | exceeds it further |

**Bottom line on redundancy:** the paste's *conclusion* (do not stack) is right for us, its
*mechanism* is mislabelled, and its *stated reason* is false for its own numbers. Ours is right on
both the conclusion and the grounds.

## 5. What the paste CANNOT see: our legal constraint

`docs/analysis/free-balloon-mass-threshold-DE.md` establishes the German position. Under a
**total-mass** reading of a 20 g threshold, our non-payload subtotal is **54.97 g** — the design is
**~35 g over budget before any payload is added**, and the envelope alone is **2.43×** the entire
allowance.

**This makes lightweight film MORE attractive, not less** — but only under a reading that does
not exist in our jurisdiction. A second paste (see §5b) answered this question directly, and the
answer is a **trap**: it applies US law to a German launch.

### 5b. The second paste — the "20 g excludes the envelope" answer is about the wrong country

A follow-up paste asked whether the 20 g figure includes the envelope, and answered: **no, the
20 g rule excludes the balloon envelope and applies only to the suspended electronics package**,
citing **FAA Part 101** (6 lb single-package / 12 lb total limits) and stating those "explicitly
exclude the balloon structure".

**That is US law.** `docs/analysis/free-balloon-mass-threshold-DE.md` establishes, from primary
sources (`gesetze-im-internet.de`, EUR-Lex), that for a launch **from Germany**:

| | the paste's frame | our law |
|---|---|---|
| instrument | FAA Part 101 / 14 CFR 101 | **LuftVO § 20** + **SERA Anlage 2 Nr. 2.1** |
| is there a 20 g de-minimis? | implied yes | **no de-minimis at all** |
| the real mass figure | 6 lb / 12 lb | **500 g**, LuftVO § 21 Abs. 1 Nr. 4 lit. b |
| which quantity does it count? | payload, envelope **excluded** | **"Gesamtmasse (Ballonhülle und Ballast)"** — envelope and ballast **included** |

**Two things make this dangerous rather than merely irrelevant:**

1. **It answers in the direction that makes a builder feel safe.** "Your envelope doesn't count"
   is exactly the reassurance that leads to launching without the required permission. There is
   **no** mass below which an unmanned free balloon needs no permission in German law.
2. **Where a mass threshold does bite in our law, it bites on the OPPOSITE quantity.** The 500 g
   de-minimis counts *Ballonhülle und Ballast* — envelope and ballast — the exact inverse of the
   paste's framing. The envelope is the **dominant** term there, not an excluded one.

Our design passes that figure easily (48.6 g envelope + ~2.2 g attachments ≪ 500 g) — **but for a
different reason than the paste gives, under a different instrument, counting a different
quantity.** A correct conclusion reached by a wrong argument is not a safe thing to fly on.

**Consequence for the envelope decision: none.** The lighter-film trade in §5 evaporates here,
because it only looked attractive under a threshold reading that does not apply to us. The
envelope stays the Yokohama 32″.

### 5c. The statutes verified against primary sources

A third consultant pass re-verified every claim above against the **primary instruments** — the
consolidated statute text on `gesetze-im-internet.de` (full-act HTML for LuftVG, LuftVO 2015,
LuftVZO), the EU instrument on EUR-Lex (base act `CELEX:32012R0923` + German consolidated
`CELEX:02012R0923-20220127`), and GPO CFR XML via govinfo for the US side. **No blogs, no forums,
no secondary summaries.**

**Verdict: our analysis is CONFIRMED on every point, not refuted.** The verbatim texts:

| instrument | § | wording (verbatim) | what it means |
|---|---|---|---|
| LuftVG | § 1 Abs. 2 Nr. 6 | „Luftfahrzeuge sind … **6. Frei- und Fesselballone**" | free balloons **are** aircraft; no mass qualifier |
| LuftVO | § 20 Abs. 1 Nr. 6 | „… der Betrieb von **unbemannten Freiballonen** nach Anlage 2 der Durchführungsverordnung (EU) Nr. 923/2012 im Hoheitsgebiet der Bundesrepublik Deutschland" | permission required — **no mass threshold, no de-minimis carve-out** |
| LuftVO | § 21 Abs. 1 Nr. 4 lit. b | „b) **leicht, sofern der Aufstiegsort innerhalb von Flugplatzkontrollzonen liegt und die Gesamtmasse (Ballonhülle und Ballast) mehr als 500 Gramm beträgt**" | the 500 g figure counts **envelope AND ballast**; it triggers an **ATC clearance** for light balloons inside a control zone — **not** a permission exemption |
| LuftVO | § 21f Abs. 3 Nr. 2 | „… mit Raketenantrieb, sofern **die Masse des Treibsatzes mehr als 20 Gramm** beträgt" | the **only** „20 Gramm" in the LuftVO — **model-aircraft rocket propellant** |
| SERA Anlage 2 Nr. 2.1 | — | „**Ein unbemannter Freiballon darf nur mit der Genehmigung des Staates betrieben werden, in dem der Aufstieg erfolgt.**" | unconditional; no mass qualifier |
| SERA Anlage 2 Nr. 1.1 | — | class *leicht* = payload „**weniger als 4 kg**" | the lowest category boundary is **4 kg**, not 20 g — and this is a *classification* rule, not a de-minimis |
| LuftVZO | § 19 Abs. 3 | „… **Startmasse von mehr als 5 Kilogramm** … Namen und Anschrift … anzubringen" | a separate **marking** duty; not a permission threshold |

**Corpus-wide negative checks** (regex over the complete fetched texts): „20 Gramm" occurs **once**
in the whole LuftVO (the model-rocket rule) and **zero** times in LuftVG, LuftVZO and the
consolidated German SERA. The string „130" — the paste's unsourced "overall mass often exceeding
130 grams" — **never appears** in LuftVO, LuftVG or LuftVZO.

**The paste is wrong on the US side too.** Its 6 lb / 12 lb figures are substantively right
(14 CFR § 101.1(a)(4)(ii),(iii)), but they are **applicability** thresholds — which balloons the
part regulates at all — not limits, and **no envelope-exclusion clause exists**: the envelope is
regulated *directly*, by § 101.35(a)(2)–(3) ("terminating the flight of the **balloon envelope**";
"the **balloon envelope** is equipped with a radar reflective device"). **There is no 20 g figure
anywhere in part 101** — its only gram figures (125 g / 1,500 g) sit in Subpart C, **amateur
rockets**. And § 101.1(a) scopes the whole part to operations "**in the United States**".

**A correction to our own record, found by the pass:** the marking duty is LuftVZO **§ 19 Abs. 3**;
**§ 18 LuftVZO reads only „(weggefallen)"** (repealed). Where the sibling analysis cites § 18, it is
wrong and § 19 Abs. 3 is the provision that applies.

> **Status:** verified — the `TODO(unverified)` on this section is cleared. The remaining
> `TODO(unverified)` is narrow: **no German state aviation authority detail page was reachable**
> (LBA/BMV URLs 404). That was marked rather than substituted with a secondary source, and **no
> finding here depends on it** — every load-bearing statement comes from the statutes themselves.

## 6. Consultant passes — delivered

Two independent passes, each with pinned toolsets (`terminal`, `web`) and a requirement to cite a
**fetched** URL per load-bearing claim. Both completed and both **corrected this document**:

| pass | covered | outcome |
|---|---|---|
| claim verification | cost / altitude / volume / leak / material identity | **corrected us** on the Yokohama price (we carried the paste's $25; the live manufacturer figure is **$12**) and on "Cymylar" (a **real brand**, not a misspelling). **Refuted the paste** on budget-film altitude (EOSSP-2: 299 days to 46,522 ft), on SBS-13 (not a film; $165 in no snapshot), and on the 15–25 g weight. |
| reliability mathematics | is the Markov framing sound; does the dead-weight conclusion follow | **Corrected our framing** (semi-Markov, not "the chain is wrong") and **refuted the paste's conclusion** for its own hardware, while **independently confirming ours** (§4c). Supplied the strongest caveat — **common mode** (§4d). |

Provenance note: the claim pass fetched the manufacturer's live `products.json` and product
JSON-LD directly (IPv4 forced — several hosts resolved IPv6-only), used **Marginalia** plus direct
vendor/PDF fetches because every major search engine was bot-walled, and used **Wayback CDX** for
the SBS-13 price history. The reliability pass used the **NIST/SEMATECH e-Handbook §8.1** for the
bathtub/Weibull/semi-Markov formalism, with every number reproduced by Monte-Carlo against closed
forms.

**Where they disagreed with this document, they won and the document was corrected** — which is
the point of the pass. The one place we held our ground: the mass-allowance argument in §1/§4,
which the reliability pass did not cover and which reaches the same conclusion independently.

## 7. Recommendation

> **Keep the Yokohama 32″ nylon/PE envelope. Do not switch to BoPET/Mylar. Do not add layers.
> Take no action from this paste.**

Reasons, in order of weight:

1. **The decision does not depend on any number the paste supplies.** Our envelope choice is
   already the paste's top recommendation, and of its numeric additions only the measured mass and
   the stretched volume survive verification — the rest are wrong or category errors (§3).
2. **Its cost framing is off-axis for us, and its price was wrong.** We fly one envelope once; the
   envelope is 88 % of non-payload mass, and at the manufacturer's real price the Yokohama is
   **$12, i.e. $0.25 per gram** — the paste's $25 overstated it ~2× (§1, §3).
3. **Its own rationale contradicts its own pick** (inelastic foil vs a stretchable laminate).
4. **Its redundancy conclusion is correct and we already comply** (single envelope; the
   dead-weight arithmetic is quantified in §4).
5. **The one real opening it exposes is closed by the second paste (§5b)** — the lighter-envelope
   case rested on a threshold reading that does not exist in German law.

### What would change this

- A **measured** leak rate for the Yokohama that is materially worse than the community's
  ~1/6-of-cheap-film claim, at our altitude and temperature profile.
- A **measured** pinhole/infant-mortality rate on the Yokohama lot we own.
- A resolution of the German threshold reading that makes total mass binding — then the 10.6 g
  envelope-mass saving becomes worth pricing against the leak risk.
- Evidence that the **neck/weld** is *not* the dominant failure mode. If it is (and it is the
  standard pico-balloon failure), then stacking cannot help by construction (§4d), and effort
  belongs on the single envelope's seal, not on its count.

## 8. Open items

1. Every paste cost/altitude figure is `TODO(unverified)` — deliberately not absorbed, because
   the decision does not turn on them.
2. ~~"Cymylar" is not resolved as a product or brand name.~~ **Resolved: it is a live brand**
   (Amazon brand store `CYMYLAR`, 175 results, metallized party foil). And a 60″ Cymylar flew
   **299 days / 19 circumnavigations to 46,522 ft** (EOSSP-2) — a *better* documented record than
   the paste credited it with. Worth pricing only if the mass-threshold question ever reopens.
3. ~~The German threshold reading decides whether a lighter envelope is worth the leak risk.~~
   **Resolved as a non-question**: the paste's answer applies US law to a German launch (§5b). A
   consultant pass re-verifies the German statutes.
4. The §5b finding is a **safety-relevant** error mode in this paste series: both pastes answer
   confidently in a jurisdiction that is not ours. Future pastes on this topic should be checked
   for which country's rules they are actually describing before any number in them is used.

# Foam sourcing — real DE products, with densities where published

**Date:** 2026-10-15 · **Feeds:** `docs/adr/117-wing-airframe-foam-selection.md`
**Scope:** purchasable sheet foam in Germany for the wing backing plate (167.1 × 86.8 mm × 4 wings).

**Every price and spec below was fetched from the vendor page.** Products with the density
**stated on the page** are marked; ones without are flagged, because density is the number the
mass budget needs.

---

## What was actually wanted

ADR-117 selected **XPS / "Depron"-class sheet, 3 mm for the first build**, ideally from a vendor
that stocks **both 3 and 6 mm** so the stiffness fallback is one purchase. The wing needs
**581.3 cm² total** (4 × 145.3 cm²) — a single A4 sheet is enough for one wing, a 700 × 1000 mm
sheet covers all four wings **~9 times over**.

Areal mass = `0.1 × ρ[kg/m³] × t[mm]` mg/cm².

## 1. The recommendation

**architekturbedarf.de — Modellbauschaum weiß ca. 3 mm, 70 × 100 cm, 4.85 EUR/sheet**

- <https://www.architekturbedarf.de/pappe-+-papier/depron-+-modellbauschaum/modellbauschaum-weiss-ca-3-mm>
- **Density stated on the page: 40 kg/m³** (Raumgewicht) — the only DE source found that publishes one
- Self-described as a Styrodur/Depron equivalent; cuttable with a knife or hot wire
- Areal mass **12.0 mg/cm²** → **1.74 g per wing**, 6.97 g for four
- One sheet covers all four wings ~9× with spares

### And buy the thickness ladder from the SAME shop, in one order

The whole ADR-117 finding is that **thickness is the dial**. This vendor stocks the family at a
stated 40 kg/m³, so ordering two thicknesses lets the first build A/B the trade on the same
material for a few euros:

| thickness | price | sheet | areal mass | per wing |
|---|---|---|---|---|
| 2 mm (B-Ware) | 3.95 EUR | 70 × 100 cm | 8.0 mg/cm² | 1.16 g |
| **3 mm** | **4.85 EUR** | 70 × 100 cm | **12.0 mg/cm²** | **1.74 g** |
| 3.5 mm | 3.65 EUR | 50 × 70 cm | 14.0 mg/cm² | 2.03 g |
| 4 mm | 4.95 EUR | 70 × 100 cm | 16.0 mg/cm² | 2.32 g |
| 5 mm | 5.90 EUR | 70 × 100 cm | 20.0 mg/cm² | 2.91 g |

*All incl. 19 % VAT, excl. shipping.*

## 2. The lightest credible option

**Himmlischer Höllein — EPP Platte weiß 900 × 600 × 3 mm, 8.95 EUR**

- <https://www.hoelleinshop.com/products/epp-platte-weiss-900-x-600-x-3mm-pichler-c3139>
- **Density stated: 30 kg/m³** (Raumgewicht 30 g/L)
- Areal mass **9.0 mg/cm²** → **1.31 g per wing**
- **EPP is far tougher than XPS/Depron and does not shatter** — relevant at −60 °C and during
  launch/ascent handling

**This is the one to reconsider if the vacuum/handling risk bites.** It is the lightest option
with a *published* density, and toughness is the property XPS is weakest on.

## 3. Kitted A4 sets — one sheet per wing

**Amazon.de, seller ZIEMER — Styrodur 3035 CS (XPS), density STATED 30 kg/m³**

| pack | thickness | price | per sheet | ASIN |
|---|---|---|---|---|
| 10-pack | 4 mm | 19.90 EUR | 1.99 EUR | B0HG5SQLXH |
| 7-pack | 6 mm | 16.40 EUR | 2.34 EUR | B0GDTGHB5L |
| 8-pack (4× 2 mm + 4× 3 mm) | 2 & 3 mm | 16.40 EUR | 2.05 EUR | B0DPR416SP |

A4 (210 × 297 mm) is the closest off-the-shelf size to one 167 × 87 mm wing — **one sheet per
wing, minimal waste**. 30 kg/m³ × 4 mm = 12.0 mg/cm². Prices are marketplace-live; **re-read the
buy-box before ordering**.

## 4. True Depron brand (if brand fidelity matters)

**Höllein / Aeronaut** — genuine Depron sheets, in stock, per-sheet pricing:

| product | price | density |
|---|---|---|
| Depronplatte 1000 × 500 × 6 mm (#785925) | 5.95 EUR | **not stated** |
| Depronplatte 1000 × 500 × 3 mm (#785925) | 4.20 EUR | **not stated** |
| Depronplatte 620 × 800 × 3 mm (#785923) | 3.90 EUR | **not stated** |

⚠️ **The 3 mm page shows "Gewicht 100 g"** for a 1000 × 500 × 3 mm sheet. If that were pure foam
it implies **~67 kg/m³**, far above real Depron's ~33–40 kg/m³ — so it is almost certainly
gross/shipping weight. **Do not use it as a density.** Ranked below the products with published
densities because the mass budget cannot be closed from these pages.

## 5. What NOT to buy

- **OBI Qboard / Duschparadies 4–6 mm** (14.03 / 15.83 / 25.99 EUR) — XPS core but
  **cement-and-mesh faced**, not bare foam, no density published, and the mineral facing adds
  parasitic mass.
- **OBI "Styropor EPS 040"** — "040" is a **thermal-conductivity class (WLG 040), not a
  density.** No kg/m³ published. Typical EPS 040 is ~15 kg/m³ but the page does not say so.
- **Modulor Polystyrol Hartschaum** (3 mm 4.90 EUR, 5 mm 5.90 EUR) — price-confirmed but
  **density is not published**, and the linked technical datasheet PDF has corrupt flate streams
  (`pdftotext` returns 3 bytes). Usable only if the density is obtained another way.
- **Amazon Depron bulk** (3 mm, 20-sheet pack, 144 EUR) — no density, and 20 sheets is ~90× what
  the four wings need.

## 6. Open items

1. **No DE product is marketed as "high-altitude balloon airframe foam."** The practical
   equivalent is the 30–40 kg/m³ XPS/EPP/Depron families above.
2. **Modulor's datasheet PDF** needs OCR (render to PNG → vision) or an email to the vendor to
   recover its density.
3. **Genuine Depron's ~33 kg/m³** is widely-cited but needs an Aeronaut/Depron datasheet
   citation — not an inference from a shipping weight.
4. **Lindinger (lindinger.at)** stocks Depron 1250 × 800 × 3 and 6 mm and EPP, but serves a
   17 MB JS-rendered page; no parseable price. Manual browser or fallback only.
5. **Blocked vendors** (confirmed, do not retry with curl — need a real browser): ebay.de (403),
   hobbyking.com (403), der-schweighofer.de (000), rc-toy.de, conrad.de search, hornbach.de,
   toom.de, hagebau.de, modellbau-bichler.com, and ~15 more.
6. **Amazon prices are live-at-fetch** and marketplace-driven.

## 7. Method

Vendor category pages and product pages were fetched directly with a browser User-Agent and
`curl --compressed` (search engines are bot-blocked for scripted access). Product URLs were
enumerated via vendor site-search and `/sitemap.xml` where category pages were JS-rendered.
Prices are the per-product page figure, not a marketplace "from" price. **Density is quoted only
where the vendor page states it**; every other figure is marked as unpublished rather than
inferred.

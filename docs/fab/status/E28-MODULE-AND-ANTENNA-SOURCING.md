# Antenna + module sourcing decision (E28-2G4M27SX)

Status: **module OK to buy; antenna still OPEN.**
Written 2026-10-26 after the operator asked whether the Amazon listing (earliest delivery) is the
right part, and offered to measure the NiceRF coil antennas he already owns.

## 1. The Amazon listing — yes, right part, but read the caveats

`https://amzn.eu/d/0ddRmj0W` → `amazon.de/dp/B0CJJTTBVB`

```
title     CROIRE SX1280 Wireless RF Module CDSENET E28-2G4M27SX
          27DBm 8Km ... SMD IPEX PA+LNA GFSK FLRC
seller    CROIRE
brand     CDSENET
```

**It is the module, not an antenna.** The listing is `E28-2G4M27SX` with `IPEX` and `PA+LNA` —
exactly the part the footprint and `ADR-137` were built around. Correct variant, correct connector.

Package contents, verbatim from the listing:

> `Package contents: 1 x Wireless RF Module`
> `Only the above package content, other products are not included.`

So: **no antenna, no U.FL pigtail.** Budget one or the other separately.

Two caveats, neither blocking:

1. **Not Ebyte direct.** Seller is `CROIRE`, the item is branded `CDSENET`. Same model number,
   almost certainly OEM/re-badge of the same design — but the datasheet this repo holds is
   **Ebyte's**. If the enable-default behaviour (Q2/Q4) is silicon- or vendor-firmware-dependent,
   a re-badge is the one place it could differ. Acceptable for a bring-up part; for flight
   hardware, prefer an Ebyte-branded unit from a distributor.
2. **Title says `SX1280`, model says `E28-2G4M27SX`** which Ebyte documents as SX1281-based. Ebyte's
   own material is inconsistent the same way. Same family, driver-compatible — already recorded in
   `docs/modules/e28-2g4m27sx/PROVENANCE.md`. Not a wrong part.

## 2. ⚠ Do not power this module with PA enabled and no antenna

At 27 dBm (500 mW) an open or mismatched IPEX port reflects power back into the PA. Bring-up
sequence: fit the antenna **first**, then enable `TX_EN`. Any firmware that asserts `TX_EN` at
boot (which is the unresolved Q4) is a real hazard on a bare module.

## 3. What the flight actually needs from an antenna

| requirement | value | why |
|---|---|---|
| band | 2.400–2.500 GHz | E28 is 2.4 GHz only |
| connector | **U.FL / IPEX-1 / MHF1** | mates the module's IPEX; measured land ≈ 2.9 mm ⇒ IPEX-1, **not** MHF4 (≈1.2 mm) |
| pattern | **omni** | the balloon rotates and drifts; a directional antenna loses the link at attitude |
| gain | ~2 dBi is plenty | module already emits 27 dBm; gain is not the constraint |
| ground plane | board GND counts | 72 × 80 mm ≈ 0.57 λ × 0.64 λ at 2.4 GHz — adequate for a monopole |
| mass | tens of grams available | not a real constraint at this scale |

A high-gain or directional antenna is **not** wanted here. Link margin is set by the 500 mW PA,
not by aperture.

## 4. Yes, please measure the NiceRF coil antennas — length alone identifies the band

This is the cheapest possible win: if one of them is 2.4 GHz with a U.FL plug, we fly it and buy
nothing.

**Measure in this order:**

| # | measurement | how it decides |
|---|---|---|
| 1 | **overall length** of the coil, mm | **this alone identifies the band** — see table below |
| 2 | coil outer diameter, mm | with #1 and turns, gives the resonant length |
| 3 | number of turns | same |
| 4 | connector | U.FL/IPEX-1 = usable as-is; SMA = needs a U.FL→SMA pigtail; bare wire = solder only |
| 5 | mass, g | affects the mass budget |
| 6 | which NiceRF board it shipped with, and any silkscreen band marking | corroboration |

**Band from length — quarter-wave reference:**

```
433 MHz   λ 692 mm   λ/4 173 mm
868 MHz   λ 345 mm   λ/4  86 mm
915 MHz   λ 328 mm   λ/4  82 mm
2.4 GHz   λ 125 mm   λ/4  31 mm  -> helical coils compress this to ~8-15 mm overall
```

So: **≈ 8–15 mm overall ⇒ 2.4 GHz, usable. ≈ 80–175 mm ⇒ sub-GHz, wrong band for the E28.**

A 2.4 GHz helical monopole is a quarter-wave radiator wound into 6–8 turns, which is why it looks
almost identical to a sub-GHz coil while being an order of magnitude shorter. Measure length
first — do not judge by appearance.

## 5. What not to bother measuring

- Anything on the LR2021's **sub-GHz** port as a candidate for the E28 — different band.
- The antenna's "gain" as a number printed by the seller. Unverifiable without a chamber; the
  band + connector + omni pattern is what matters.
- The E28 body dimensions — settled in `E28-DIMENSIONS-RESOLVED.md` from published sources.

## 6. Open items this closes / leaves open

- **Closes:** which module to buy (yes, `B0CJJTTBVB`), and that an antenna is a separate line item.
- **Open:** the antenna itself, pending the coil measurements. If none is 2.4 GHz + U.FL, the
  fallback is a 2.4 GHz FPC with a U.FL plug — same class Ebyte recommends for this module.
- **Still open, electrical:** simultaneous `TX_EN`/`RX_EN`, float behaviour, sequencing. See
  `EBYTE-QUESTION-e28-enables.md`.

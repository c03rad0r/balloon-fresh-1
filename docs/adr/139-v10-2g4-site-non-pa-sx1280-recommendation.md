# ADR-139 — v10's 2.4 GHz site should be a NON-PA SX1280 module; the 27 dBm class is where ranging dies

> Numbered **139** on 2026-10-26. Next free after 138.

**Status:** **Proposed** — a recommendation with one open question (§8). Not applied to the board.
**Relates:** ADR-138 (ranging unproven on the E28 — this record answers it),
ADR-118/119 (v10 radio sites — would be amended), ADR-035 (ranging slot),
ADR-137 (no RF on the carrier), `docs/analysis/radio-legal-power-limits.md` §2.4 GHz

---

## 1. The question

The operator asked, after ADR-138's gate: *"is there a different board that we could be planning
around in our PCB design instead to get more certainty that ranging will be supported?"*

**Yes.** And the finding is not "a different vendor" — it is **a different class of module**.

## 2. Two independent vendors say the same thing about 27 dBm parts

**NiceRF's own SX1280 selection table** (`nicerf.com/sx1280-lora-module.html`, updated 2024-03-22)
splits its four SX1280 modules into two groups:

| | LoRa1280 / -TCXO | LoRa1280F27 / -TCXO |
|---|---|---|
| **Ranging function** | **Yes** | **No** |
| Max output power | 12.5 dBm | 27 dBm |
| Built-in LNA | No | Yes |
| Power amplifier (PA) | No | Yes |
| TX current | 26–30 mA | <600 mA |
| Size (L×W×T) | **16 × 16 × 2.1 mm** | 31.54 × 15.8 × 2.9 mm |
| Working voltage | 1.8–3.7 V | 2–5.5 V |

NiceRF sells `LoRa1280F27` (SX1280) and `LoRa1281F27` (SX1281) as **separate 27 dBm products** — they
plainly distinguish the two chips — and *still* marks **ranging: No** on both F27 variants.

Meanwhile Ebyte did the same thing to us: its 27 dBm `E28-2G4M27SX` carried a ranging claim in
manual v1.0, and v1.1 "modified" it and v1.2 **deleted** it (ADR-138 §4).

**Two unrelated vendors, one conclusion: the 27 dBm PA+LNA modules do not do ranging.**

*Inference, not vendor statement:* the PA/LNA front end is the likely mechanism — an external T/R
stage with `TX_EN`/`RX_EN` switching sits between the radio and the antenna, adding path delay and
control dependence that a time-of-flight exchange cannot tolerate. Neither vendor states a reason.
What is **not** in doubt is that both refuse to claim ranging on those parts.

## 3. The second finding: 27 dBm is not legally usable here anyway

From this repo's own analysis, `docs/analysis/radio-legal-power-limits.md` §2.4 GHz:

> "The 100 mW EIRP tier (57c) carries a **power-density** condition: 10 mW/MHz EIRP for every
> modulation other than frequency hopping. A LoRa (chirp spread spectrum) or FLRC link with ≤ 1 MHz
> occupied bandwidth therefore **cannot** radiate 100 mW — its density cap is ≤ ~10 mW EIRP. The
> applicable entry is **57a / CEPT Annex 1 h = 10 mW EIRP** … The lawful ceiling for the 2.4 GHz
> LoRa uplink is **10 mW EIRP**."

**10 mW EIRP = 10 dBm EIRP.** A 27 dBm module must therefore be operated far below its rating.

So the PA is **not merely useless — it is a cost**:

```
                        E28-2G4M27SX (27 dBm PA+LNA)     LoRa1280 (12.5 dBm, no PA)
lawful ceiling          10 dBm EIRP  -> PA throttled     10 dBm EIRP -> ~at the ceiling
ranging                 NO                               YES (vendor-stated)
TX current              580 mA peak (at 27 dBm)          26-30 mA (at 12.5 dBm)
enables                 TX_EN + RX_EN -> 2 GPIOs         none
enable-default hazard   Q2/Q4/Q5 unresolved              does not exist
pins                    16                               16
size                    15 x 20 x 2.90 mm                16 x 16 x 2.10 mm
```

**The 27 dBm part pays for a power amplifier it cannot legally use, with the money going to two
GPIOs, 580 mA of peak current on a solar harvester, and the loss of the one feature it was chosen
for.**

## 4. Recommended part

**G-NiceRF `LoRa1280-TCXO`** — SX1280, 12.5 dBm, **ranging: Yes**, 0.5 ppm TCXO.

Why the TCXO variant over the plain one: a pico-balloon sees −40…+85 °C and the ranging accuracy is a
timing measurement — 0.5 ppm matters more here than it does for a bench link. The plain `LoRa1280`
(10 ppm) is the fallback.

Verified from the vendor's own pin table (`nicerf.com/lora-module/lora-module-lora128x.html`):

```
1 DIO2   2 DIO3   3 VCC   4 GND   5 MISO   6 MOSI   7 SCK   8 NSS
9 ANT   10/11/12 GND   13 NRESET   14 TCXOEN*   15 BUSY   16 DIO1
* pin 14 is GND on LoRa1280/LoRa1281, TCXOEN on the -TCXO
```

- **There is no `TX_EN` / `RX_EN`.** No PA, no LNA, nothing to enable — so **ADR-138's Q2, Q4 and Q5
  stop existing** rather than being answered. That is the single biggest simplification available.
- 1.8–3.7 V, < 10 mA RX, < 1 µA sleep, −132 dBm sensitivity, 2400–2500 MHz.
- TX current **26–30 mA** at 12.5 dBm versus 580 mA instantaneous on the E28 — the energy budget
  (ADR-036) and the `C_BULK` sizing both improve dramatically.
- TCXOEN sequence is specified: pull high, wait ≥3 ms, then release `NRESET`; keep high while
  running; `SetSleep()` → wait ≥1 ms → pull low.

## 5. What it costs — stated plainly

**This is a board change, not a BOM swap.** `U_E28` is 15 × 20 mm with 16 pads at 1.27 mm; the
NiceRF part is 16 × 16 mm with a **different 16-pin order** (ANT on pin 9, no enables, TCXOEN on
pin 14). Therefore:

1. New footprint, new courtyard, new antenna anchor.
2. **The radio link just routed at 4 layers must be re-routed** — pin order changed, so the
   9/9 net result does not transfer.
3. `docs/ssot/parameters.json` gains/updates the 2.4 GHz site parameters.
4. Two nets disappear (`TX_EN`/`RX_EN`), two GPIOs come free.

The 4-layer stackup (ADR-130 lineage) is unaffected and still buys the escape corridor.

## 6. Where the certainty actually comes from

The point of changing part is that certainty moves from **a marking read off a delivered unit** to
**a vendor document that states the feature**. ADR-138's chip-marking test is still worth doing as a
receipt check, but the design should not depend on it.

Prefer, in order:

1. vendor datasheet states **ranging: Yes** ← this is what we now have
2. datasheet states the chip is **SX1280** (Semtech Table 1-1 in `docs/sx1280/SX1280-81_Rev3.2` gives
   the chip's ranging engine)
3. chip marking on the delivered unit

A reseller's listing title is not in this list.

## 7. Alternatives considered and rejected

| option | why not |
|---|---|
| Keep the E28, test the marking | Leaves the flight gated on a coin flip; and even an SX1280 E28 is a 27 dBm PA part that NiceRF's analogue says cannot range. |
| NiceRF `LoRa1280F27` (SX1280, 27 dBm) | Vendor says ranging **No**. Same trap with a different logo. |
| Bare SX1280 QFN | ADR-118 already measured this as fatal — the 7-part matching network is exactly the RF design ADR-137 forbids. |
| Use the T3S3's on-board radio for ranging | It is a plain +13 dBm SX1280, so it *would* range — but it is on a different board and is not part of the flight stack. Recorded as a bench fallback only. |
| Drop ranging | Operator gate: not acceptable. |

## 8. The IPEX gate — RESOLVED, and it turns out to be an advantage

**Was open:** does the module have an IPEX/u.FL connector, or only a solder `ANT` pad? If only a pad,
attaching an antenna would mean routing 50 Ω on our carrier — the RF design ADR-137 forbids.

**Answer: there is no connector on the module.** Confirmed from the vendor datasheet
(`docs/modules/lora128x/LoRa128X_Series_Datasheet_Rev2.2.pdf`):

- Pin 9 is `ANT` — "connect with 50 ohm coaxial antenna".
- §8 "Communication Antenna" expects a **wire or spring antenna**, or a coax pigtail, attached
  directly at the module.
- The §9 mechanical drawing shows **no miniature coax connector** on the body; the SMA in the
  vendor's photo belongs to the *external* cable assembly, not to the module.

**This is not a problem — it is the cleanest ADR-137 outcome available.** A coil/spring antenna
soldered **directly to the `ANT` pad** has *no* controlled-impedance feed and *no* matching network
anywhere on our board: the antenna begins at the module's own antenna port. That is precisely what
ADR-137 asks for, and it is better than the E28's IPEX path, which still needed a U.FL pigtail.

The operator already owns NiceRF coil antennas, so this uses parts on hand.

### 8.1 Mechanical data — read from the vendor drawing, not guessed

`LoRa128X Series` datasheet Rev 2.2, §9 (an image, so rendered at 400 dpi):

| item | value |
|---|---|
| outline | **16.00 ± 0.2 × 16.00 ± 0.1 mm** |
| thickness | **2.10 ± 0.15 mm** (shield/body 1.10 ± 0.1 above the PCB) |
| pads | **16, 8 per side, castellated** (half-hole) with a Ø0.70 ± 0.1 plated hole in each land |
| **pad pitch** | **2.00 ± 0.1 mm** |
| pad land | 1.20 ± 0.1 along the edge × 1.70 ± 0.1 inward |
| first row offset | 1.00 ± 0.1 mm from the end edge |
| antenna | **`ANT` pad, no connector** |
| shield | **yes — the radio is shielded** |

### 8.2 Consequence the shield creates

Because the module is shielded, **ADR-138's chip-marking test cannot be performed on this part.**
There is nothing to read. That makes the **orderable part number the only lever** for ranging
certainty — which is why the vendor states the distinction in its own datasheet:

```
LoRa1280-TCXO   SX1280   ★ Supports ranging with more precision   CE & FCC
LoRa1281-TCXO   SX1281   Does not support ranging                  CE & FCC
```

Same package, same 0.5 ppm TCXO, same certifications — **ranging is the only difference.** Buying
`LoRa1281-TCXO` by mistake cannot be detected after the fact, so the part number must be pinned in
the BOM and on the assembly drawing.

### 8.3 Footprint impact versus the E28

```
                 E28-2G4M27SX        LoRa1280-TCXO
outline          15.0 x 20.0         16.0 x 16.0
thickness        2.90                2.10
pads             16                  16
pad pitch        1.27 mm             2.00 mm     <- 0.73 mm coarser
inter-pad gap    0.27 mm             ~0.80 mm    <- far more tolerant
enables          TX_EN, RX_EN        none
```

A 2.00 mm pitch with a ~0.80 mm gap is materially easier to hand-solder than the E28's 0.27 mm gap —
relevant because this board is hand-assembled by the operator.

## 9. Reproduce

```bash
# vendor's own ranging/PA split
# https://www.nicerf.com/sx1280-lora-module.html  -> "Differences between the four SX1280 LoRa modules"
# vendor's pin table and electricals (no TX_EN/RX_EN)
# https://www.nicerf.com/lora-module/lora-module-lora128x.html

# the legal ceiling that makes 27 dBm unusable
grep -n "10 mW EIRP" docs/analysis/radio-legal-power-limits.md

# the chip difference
pdftotext -layout docs/sx1280/SX1280-81_Rev3.2_Mar2020.pdf - | grep -A12 "Product Reference"
```

## 10. For future sessions

**The one-line rule:** *for 2.4 GHz ranging, pick a module whose datasheet says "ranging: Yes" and
whose output power is inside the 10 dBm EIRP legal ceiling; a 27 dBm PA+LNA module buys nothing
legal and loses ranging.*

**Do not** assume "SX1280-based module" implies ranging — two vendors sell SX1280 chips in 27 dBm
modules and explicitly do not support ranging on them.

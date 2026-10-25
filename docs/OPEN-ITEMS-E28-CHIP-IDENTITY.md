# E28-2G4M27S chip identity is contradicted by EBYTE's own documents

**Status: UNRESOLVED — do not rely on `E28-2G4M27S` for ranging until closed.**

## The problem

Six `balloon-fresh` documents state that the `E28-2G4M27S` module we own 3 of is
an **SX1281**. EBYTE's own user manual and one of its spec sheets state the same
part number is an **SX1280**.

Both cannot be true, and the difference is functional: Semtech's product pages
name ranging in the title — **"SX1280, 2.4 GHz With Ranging"** vs **"SX1281,
2.4 GHz Without Ranging"**.

## Evidence, per source

| Source | `E28-2G4M27S` chip | Ranging claimed |
|---|---|---|
| `cdebyte.com/products/E28-2G4M27S` (product page) | **SX1281** | no |
| `cdebyte.com/products/E28-2G4M20S` (series table) | **SX1281** for all `M*` | no |
| `E28-2G4M20S` spec sheet (中文, xonlink mirror) | **SX1281** | no |
| `E28-2G4M27SX` spec sheet (xonlink mirror) | **SX1280** | yes (ToF listed) |
| `E28-2G4M27S` user manual (`cdebyte.com/pdf-down.aspx?id=2128`) | **SX1280** | **yes — "With Time-of-flight function, good for ranging"** |
| `docs/inventory.md` (this repo) | **SX1281** | no |
| `docs/component-guide.md` (this repo) | **SX1281** | no |
| `docs/FLIGHT-TEST-READINESS-2026-07-29.md` | **SX1281** | no |
| `docs/HANDOVER-PROMPT.md` | **SX1281** | no |
| `docs/PCB-HANDOVER-FOR-JLCPCB.md` | **SX1281** | no |
| `docs/lr2021-dual-track-master-plan-2026-07-17.md` | **SX1281** | no |

### The internal contradiction, in EBYTE's own words

The `E28-2G4M20S` spec sheet lists the family:

> `E28-2G4M27S | SX1281 | 2.4G | 27 | 8 | 15*26.5 | 贴片 | SPI`

The `E28-2G4M27S` user manual, §1.1, describing the same module:

> "The IC **SX1280** from Semtech features multiple physical layers … the DC-DC
> and **Time-of-Flight on chip** make the chip much more capable for … wireless
> distance measuring"

And §2.2 of the same manual:

> "With **SX1280**+PA+LNA, its driving method is similar to SX1280, please refer
> to SX1280 datasheet for operation guidance"

**So the module's own manual says SX1280 three times, while the family table in
the sibling spec sheet says SX1281.** The `M27SX` variant sheet says SX1280.

## Why this is not a cosmetic documentation bug

1. **Ranging is a hardware feature.** If the chips differ as Semtech describes,
   the SX1281 cannot do RToF ranging at all — no firmware fixes that.
2. **The parts are indistinguishable by inspection.** Pin-compatible QFN-24,
   identical RF performance, no external marking convention documented.
3. **The repo has already misdiagnosed a chip this way.** ADR-017 concluded "the
   chip is not an SX1280" from an SPI probe (SX1280 opcodes `0xC0` sent to an
   LR2021 returned `0x21`, read as "it responds"). That ADR is **SUPERSEDED by
   ADR-020** and is explicitly marked as an incorrect diagnosis. **SPI probing
   alone has already produced one wrong chip-identity conclusion here.**

## What is NOT in dispute

- **SX1280** = ranging. **SX1281** = no ranging. (Semtech product page titles.)
- **LR2021 ≠ LR1121.** Confirmed independently: the module label reads
  `LORA2021-915`, FCC ID `2RAD6S-LORA2021-915` (ADR-017).
- The `E28-2G4M**` family mixes part numbers across at least two axes — output
  power (`12`/`20`/`27` dBm) and package/interface (`M*` SMD SPI, `T12S` TTL).

## How to close this

One of these, in order of preference:

1. **Read the chip marking off an owned module** under magnification after
   removing it from the reel — the QFN-24 laser mark carries the part number.
   **This is the decisive check and costs nothing.**
2. **Query the chip's own version register** over SPI and compare to
   `SX1280 V3B A9B7` (the string the bench firmware already reports for a known
   SX1280, per checklist V2.3). Note: a *mismatch* is informative; a match from a
   single read is still weaker than a physical marking.
3. **Ask EBYTE directly** which chip `M27S` ships with, and whether it changed
   between production batches. Worth doing regardless — if the chip changed,
   *both* documents are right and the inventory note needs a date range.

## What we do in the meantime

**Do not design ranging onto the E28.** Buy the **LilyGO T3S3 SX1280 variant**,
where the chip is named explicitly in the product variant selector. The E28 stays
a data-radio module; treat its ranging capability as **unknown** rather than
assumed-present or assumed-absent.

## Files to update when this closes

`docs/inventory.md`, `docs/component-guide.md`, `docs/FLIGHT-TEST-READINESS-2026-07-29.md`,
`docs/HANDOVER-PROMPT.md`, `docs/PCB-HANDOVER-FOR-JLCPCB.md`,
`docs/lr2021-dual-track-master-plan-2026-07-17.md` — all six carry the `SX1281`
claim. They must be corrected **together**, or the contradiction simply moves.

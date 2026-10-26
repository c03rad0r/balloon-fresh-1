# ADR-138 — The E28-2G4M27SX's ranging capability is UNPROVEN; the flight is gated on it

> Numbered **138** on 2026-10-26. Next free number after 137.

**Status:** Accepted — **this is a gate, not a part change.** The part decision stays open until
the module is measured.
**Supersedes:** nothing. **Corrects:** the unqualified premise in ADR-118 §3/§27 and ADR-119 §16/§20
that the E28-2G4M27SX **is** an SX1280.
**Relates:** ADR-035 (TDM schedule — ranging is a scheduled radio), ADR-118 (v10 directives),
ADR-119 (v10 radio sites), ADR-137 (no RF on the hub)

---

## 1. The operator's gate, verbatim

> "The board I ordered has an SX1280 according to Amazon. I won't fly it unless if it does ranging."

That is a hard flight gate. It is also **correct engineering**, because the part's ranging ability
is the single reason this module was chosen.

## 2. Why ranging matters here — the whole v10 2.4 GHz site rests on it

ADR-118 §3: *"The ranging radio is the whole E28-2G4M27SX board … the whole E28 board with the
matching network included so that we don't need to design that ourselves."*

ADR-118 §27: *"`U_D` — **E28-2G4M27SX** (ranging: **SX1280** + PA + LNA + matching + 52 MHz
crystal …) replacing the bare-chip SX1280."*

ADR-119 §16: *"| **D** | `E28-2G4M27SX` module | 2.4 GHz **ranging** | replaces the bare-chip
SX1280 |"*

ADR-035 §88 schedules it: *"| Ranging | `SX1280` | 2.4 GHz | yes — ranging slot (bidirectional) |"*.

And **hub v10 has no other 2.4 GHz part.** Verified from `hub_board_v10.kicad_pcb`: 49 footprints,
the only 2.4 GHz radio is `U_E28`. So if `U_E28` cannot range, **v10 cannot range**, and the
architecture that motivated choosing this module has no substitute on the board.

## 3. The silicon fact — SX1281 has no ranging engine

From **`docs/sx1280/SX1280-81_Rev3.2_Mar2020.pdf`, Table 1-1 "Product Portfolio and Modem
Functionality"** (already in this repository; extracted with `pdftotext -layout`):

```
Product Reference      SX1280      SX1281
LoRa                     yes         yes
FLRC                     yes         yes
GFSK                     yes         yes
Ranging Engine           yes          -
Advanced Ranging         yes          -
```

**SX1281 has neither the Ranging Engine nor Advanced Ranging.** The two parts are otherwise the same
radio. There is no firmware workaround: the ranging engine is silicon, not software.

## 4. What the vendor says about *this module* — and it changed

| source | chip | ranging claimed? |
|---|---|---|
| Ebyte manual **v1.0** (2021-11-15, in repo) | SX1280 | **yes** — "Ranging, with Time-of-flight function" |
| Ebyte manual **v1.1** (2024-02-23) | — | revision note: **"Modified ranging description"** |
| Ebyte manual **v1.2** (2024-04-18, in repo, canonical) | **SX1281** | **no** — bullet deleted, chip renamed throughout |
| Ebyte product page | SX1281 | no |
| Amazon listing `B0CJJTTBVB` (CROIRE/CDSENET) | **SX1280** | implied |

Ebyte renamed the chip from SX1280 to SX1281 **and deleted the ranging claim in the same revision.**
A vendor retiring a feature claim it cannot support is stronger evidence than a reseller's listing
title. The Amazon "SX1280" is the *least* reliable source in this table.

**Conclusion: on the vendor's current documentation, the E28-2G4M27SX does not range.**

## 5. Decision

1. **Ranging capability is UNPROVEN for any specific module** until measured. Documentation now
   points against it; a reseller title is not evidence.
2. **Flight gate stands:** the module is not flown as a ranging radio, and is not soldered onto a
   v10 board as one, until §6 passes.
3. **Do not weaken ADR-035.** Ranging remains a requirement. The question is *which part* delivers
   it, not whether it is wanted.
4. ADR-118/119's "SX1280" premise is **corrected to "SX1281, hence no ranging engine"** pending §6.
   Those records stay otherwise intact — the site, the footprint, the no-RF-on-carrier rule are all
   unaffected.

## 6. How to settle it — two independent tests, both cheap

### Test A — read the chip marking (decides it; no firmware, no peer)

The E28 module carries no RF shield, so the QFN is visible. Under magnification read the marking:
`SX1280IMLTRT` vs `SX1281IMLTRT`. **This is the authoritative answer** for the silicon actually
delivered, and it is independent of every document above.

### Test B — functional ranging probe (confirms it end-to-end)

Ranging is a **two-way** exchange (ADR-035 §68), so this needs two modules. Then:

- issue `SetRangingRole` (`0x0200`) and read the returned status;
- on SX1280 the ranging command set is accepted and a ranging exchange yields a distance + RSSI;
- on SX1281 the ranging engine is absent, so the commands are not supported and no valid ranging
  result is ever produced.

Test A is preferred: it needs one part, no peer, and no firmware.

### What does NOT settle it

- The Amazon listing title. It is a reseller's copy of the family name.
- A vendor manual. Our own documents have now been wrong in **both** directions on this part.
- "It transmits and receives fine." LoRa/FLRC/GFSK are in **both** parts; a working link proves
  nothing about ranging.

## 7. Consequences if Test A says SX1281

This is the branch that changes a board, so it must be decided **before** assembly:

1. **`U_E28` (15 × 20 mm, 16 pads @ 1.27 mm) is the wrong part for v10's purpose.** A replacement
   genuine-SX1280 module will almost certainly have a different outline and land pattern, so
   **the v10 board changes** — `docs/ssot/parameters.json` and the footprint must be re-derived.
2. Alternatives, in order of cost:
   - source a genuine **SX1280** module and accept a board revision;
   - use the **bare SX1280 already owned** (the LILYGO T3S3's radio is the plain +13 dBm SX1280 —
     it *has* the ranging engine, but only +13 dBm and no PA/LNA) for ranging only, on its own site;
   - drop ranging from this flight and accept the operator's gate blocks it;
   - keep the E28 for the 27 dBm link and add a separate ranging radio — two 2.4 GHz sites, which
     ADR-035's TDM schedule can already arbitrate but which needs a site (new board area).
3. **Do not** silently fly the E28 and discover it at the balloon. A ranging failure in flight is
   indistinguishable from a firmware bug, a timing bug or an RF problem — the worst kind of thing to
   debug in a flight campaign.

## 8. Reproduce

```bash
# the silicon fact, from the datasheet in this repo
pdftotext -layout docs/sx1280/SX1280-81_Rev3.2_Mar2020.pdf - | grep -A12 "Product Reference"

# the vendor's change of position
pdftotext -layout docs/modules/e28-2g4m27sx/E28-2G4M27SX_UserManual_v1.2.pdf - | grep -A6 -i "Revise History"
pdftotext -layout docs/modules/e28-2g4m27sx/E28-2G4M27SX_UserManual_v1.0.pdf - | grep -i "time of flight"

# v10 has no other 2.4 GHz part
/usr/bin/python3 -c "import pcbnew;b=pcbnew.LoadBoard('tracker/hardware/hub_board_v10.kicad_pcb');print([f.GetReference() for f in b.GetFootprints()])"
```

## 9. For future sessions

**The one-line rule:** *the E28-2G4M27SX is SX1281-based per Ebyte's rev 1.2 and therefore has no
ranging engine; ADR-035's ranging slot only becomes buildable once a module's chip marking reads SX1280.*

**Do not** cite an Amazon listing as part evidence. **Do** cite `docs/sx1280/SX1280-81_Rev3.2`
Table 1-1 for the SX1280/SX1281 difference.

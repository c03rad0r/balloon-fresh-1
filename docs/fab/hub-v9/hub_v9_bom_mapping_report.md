# Hub v9 — LCSC part-number mapping report (for JLCPCB PCBA)

Date: 2026-10-14. Method: every part looked up live via JLCPCB's own parts-search
API (`POST /api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList/v2`,
captured from authenticated session `jlc-browser9`, driven from the
`https://jlcpcb.com/parts` page context). Search URL form:
`https://jlcpcb.com/parts/componentSearch?searchTxt=<keyword>`.
Raw API dumps: `~/jlc-pcba-work/lcsc_map_raw{,2,3,4}.json` (host: cobrador).

## Resolved parts (with stock at time of lookup)

| BOM line | C-number | Mfr / model | Evidence | Stock | Unit $ |
|---|---|---|---|---|---|
| C4 10uF 0402 | C15525 | Samsung CL05A106MQ5NUNC | search "10uF 0402" (3108 hits, rank 1, base lib) | 10.75M | 0.0257 |
| C_BULK 100uF 1206 | C15008 | Samsung CL31A107MQHNNNE | search "100uF 1206" (3838 hits, rank 1, base lib) | 1.68M | 0.1307 |
| C_HF 100nF 0402 | C1525 | Samsung CL05B104KO5NNNC | search "100nF 0402" (2275 hits, rank 1, base lib) | 23.5M | 0.0046 |
| C_MON 10nF 0402 | C15195 | Samsung CL05B103KB5NNNC | search "10nF 0402" (1715 hits, rank 2, base lib) | 3.95M | 0.0049 |
| D1 BAT54 (SOD-123) | C699107 | Yangjie BAT54W | search "BAT54 SOD-123" — original BAT54 is SOT-23 only at LCSC; BAT54W is the SOD-123 package part. **SUBSTITUTION** | 22,960 | 0.0319 |
| D_BP*/D_HUB* SS24 (SMA) | C50645 | MDD SS24 SMA(DO-214AC) | search "SS24" (193 hits; picked exact "SS24" + SMA spec — C35501 is SMB, rejected) | 777,745 | 0.0257 |
| R_BAL* 10k 0402 | C25744 | UNI-ROYAL 0402WGF1002TCE | search "10k 0402" (rank 2, base lib, 1% — 5% C25531 rejected for divider duty) | 22.4M | 0.0033 |
| R_DIV* 1M 0402 | C26083 | UNI-ROYAL 0402WGF1004TCE | search "1M 0402" (rank 1, base lib) | 2.2M | 0.0024 |
| R_F1 100R 0402 | C25076 | UNI-ROYAL 0402WGF1000TCE | search "100R 0402" (rank 1, base lib) | 8.65M | 0.0012 |
| R_MON* 4.7M 0402 | C11906 | RALEC RTT02475JTH | search "4.7M 0402" (rank 1 by stock; UNI-ROYAL alt C26091 has stock 11) | 3,414 | 0.0015 |
| U1 ESP32-S3-WROOM-1U-N8R8 | C2980300 | Espressif ESP32-S3-WROOM-1U-N8R8 | search "ESP32-S3-WROOM-1U" → exact N8R8 variant; also verified by code-search C2980300 (1 hit) | 1,277 | 5.7607 |
| U4 SX1280 | C125969 | Semtech SX1280IMLTRT QFN-24-EP(4x4) | search "SX1280IMLTRT" (1 hit) + code-search verify | 726 | 3.2848 |
| U5 MAX-M10S | C4153167 | u-blox MAX-M10S-00B LCC-18 | search "MAX-M10S" (2 hits; -00B-01 C24834155 stock 157 rejected in favour of -00B stock 1157) | 1,157 | 10.8395 |
| U6 MS5611 | C15639 | TE Connectivity MS561101BA03-50 QFN-8(3x5) | search "MS5611" (1 hit) + code-search verify | 3,372 | 6.7262 |
| U7 TPS7A02 (3.3V) | C5142805 | TI TPS7A0233DBVR SOT-23-5 | schematic note "TPS7A02 3.3 V ultra-low-Iq LDO" (ADR-006 3.3V rail) → 33 = 3.3V variant; hub_board_diy.kicad_sch also carries TPS7A0233DBVR | 2,159 | 0.5856 |
| ANT* U.FL (73412-0110) | C434808 | Hirose U.FL-R-SMT(10) | searches "73412-0110", "MCRF", "Molex U.FL" → **Molex 73412-0110 NOT in JLC catalog** (0 hits). Hirose U.FL-R-SMT(10) is the standard U.FL SMD mate. **SUBSTITUTION**. NB: C2906862 (a hint from the dispatch brief) is actually a 10Ω 0402 resistor — verified by code-search, rejected. | 17,019 | 0.3605 |

## DNP rows (explicit, with reasons)

| Designators | Part | Reason |
|---|---|---|
| C_CAP1, C_CAP2 | AVX SCC 3.3F 2.7V supercap, THT radial D10 | Not in LCSC catalog ("AVX supercapacitor", "3.3F", "SCC", "2.7V supercapacitor" → 0 hits each). THT + not stocked → hand-install. |
| D_CLAMP | TVS clamp, SOD-323 | Schematic value "TVS clamp (set point TODO(unverified))" — no characterized part exists; OPEN item. Picking one would invent a design decision. |
| R_NTC1, TH_NTC1 | NTC 0402 | Schematic: "TODO(unverified) (NTC, R25/beta TODO)" + OPEN-31 note forbidding inventing NTC params. |
| U2 | LoRa2021F33-2G4 | Search "LoRa2021F33" → **0 hits**. G-NiceRF LoRa2021 modules stocked only as 433/470/868/915 MHz assembled modules (C53243919–22); the F33-2G4 2.4 GHz variant is not carried. |
| U3 | LoRa2021 2.4GHz bare castellated | Search "LoRa2021" → 4 hits, all assembled 433–915 MHz modules; "LR2021"/"LR2021IMLTRT" → 0 hits. Bare 2.4G chip not stocked. |
| J_VCC | Solder jumper 3-pad | Hand-soldered configuration selector, not an assembly part. |
| J_W1–J_W4 | Wing_Tab_4P | Board-edge castellated tab feature (mechanical, footprint graphics only), no purchasable part. |
| FID1, FID3 | Fiducials | Machine vision targets, no part. |
| TH1, TH2 | Mounting holes | No part. |

## Notes

- Skeleton listed `FID3` twice (FID1, FID3, FID3) — deduplicated; CPL has 39 rows total.
- Substitutions flagged above: BAT54→BAT54W (SOD-123 package pinout-compatible
  single Schottky; BAT54 itself only stocked in SOT-23) and Molex 73412-0110 →
  Hirose U.FL-R-SMT(10) (same U.FL mate standard). Both are U.FL/SOD-123
  standard-mate swaps; JLC's BOM tool will re-confirm at upload.
- Wing v9: all placements are solar cells (SC1–SC6, not in LCSC catalog),
  fiducials, NPTH holes, a board-edge tab connector (J1) and v2-only provision
  pads (FB1, RF1) → **no non-DNP parts; wing PCBA is not meaningful** (see quote
  report).

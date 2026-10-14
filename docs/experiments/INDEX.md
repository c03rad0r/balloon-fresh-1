# FLIGHT EXPERIMENT PROGRAMME — index

**Created:** 2026-10-14, on the operator's instruction: a tracked directory of
experiments worth doing on balloon flights, so the **software can be prepared
before the flights** (a flight that can't log the data is a wasted flight).

## Mission context (from the committed analyses)

- **Envelope:** Yokohama 32-inch sphere (chloroprene assumed); realistic float
  **6.4–9.5 km** (`docs/analysis/LIFT-AND-FLOAT-ANALYSIS-32IN.md`).
- **Board:** hub v9 @ 0.8 mm; ESP32-S3 + SX1280 FLRC + MAX-M10S (4 of 10 boards);
  supercaps DNP; only buffer = 100 µF bulk. All ICs −40 °C rated.
- **Links:** FLRC 2.4 GHz to the base station; **LoRa fallback** when out of
  FLRC range (the experiment channel — see E-00).

## Experiment register

| ID | Experiment | Status | Priority |
|---|---|---|---|
| E-00 | Range & speed, base↔balloon; LoRa fallback commissioning | **FIRST FLIGHT** (operator-set) | — |
| E-CS1..E-CS6 | Cold-start series (see `cold-start-plan.md`) | planned | HIGH |
| E-01 | Thermal environment characterisation (NTC log vs altitude/sun) | planned | HIGH |
| E-02 | FLRC link statistics vs altitude/attitude/rotation | planned | HIGH |
| E-03 | GPS at altitude: airborne<1g dynamic model validation | planned | MED |
| E-04 | Night survival: descent depth + morning cold-start | planned | HIGH |
| E-05 | Wing/tab mechanical survival (vibration, thermal cycles) | planned | MED |
| E-06 | Solar budget: irradiance vs sun angle, rotation | planned | MED |
| E-07 | Float stability via GPS rate-of-climb (superpressure proxy) | planned | LOW |
| E-08 | SEU / cosmic-ray effects on ESP32 over weeks | planned | LOW |
| E-09 | Envelope leak rate: in-flight vs bench | planned | LOW |

Files: `cold-start-plan.md` (the consultant's plan, E-CS1..6), one file per
experiment group as they are designed. **Each experiment page carries: what it
measures, why a flight (not bench), the telemetry fields it needs (so the
software team can build the loggers NOW), pass/fail criteria, and the board
decision it informs.**

## Software to prepare BEFORE the flights (from this register)

1. **Telemetry schema** covering every field below: NTC_SENSE, SCAP_ADC,
   F33_VSENSE, HUB_PV_MID1/P/N (the board's existing sense lines), plus GPS
   (fix, sats, alt, vdop), link stats (RSSI/SNR per RX), brownout/reset-cause
   counters, uptime, and experiment-mode flags.
2. **Store-and-forward**: cold-start/night data must survive reboots → littlefs
   ring buffer in flash, LoRa-downlink batches.
3. **Reset-cause + brownout logging** (E-CS3/E-CS4 hinge on it): esp_reset_reason()
   persisted across reboots.
4. **Airborne<1g GPS config** baked into the firmware (E-03).
5. **Duty-cycle scheduler**: experiments share a strict energy budget; the
   scheduler must prioritise telemetry > cold-start logging > link stats.

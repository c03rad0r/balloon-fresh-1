# Cold-start experiment plan (E-CS1..E-CS6)

**Prepared:** 2026-10-14. Consultant dispatch died on API exhaustion 3×; this
plan is written by the manager from the consultant's completed research trail
(ADR-043, ADR-042, board sense-line map, EN-pin finding) — noted for honesty.
**Context:** hub v9, supercaps DNP (only buffer = 100 µF bulk C_BULK), solar
wings, TPS7A02 LDO, ESP32-S3 (EN floats — no pull-up fitted!), SX1280 FLRC.
Bench access: freezer −18 °C (no −55 °C chamber). Float 6.4–9.5 km with the
32-inch envelope ⇒ real ambient ≈ −40…−50 °C.

## What we need to know about cold starts, and why

| # | Question | Why it matters for future boards/flights |
|---|---|---|
| E-CS1 | Minimum irradiance/PV voltage for a cold boot | If the LDO dropout rises when cold, dawn boot may fail for hours → sets the wing sizing on the next board |
| E-CS2 | Can 100 µF alone carry one SX1280 TX burst at low sun? | Decides supercap population vs bigger bulk C on rev-10 |
| E-CS3 | Cold-boot reliability with EN floating (50 cycles) | Decides the EN pull-up resistor on rev-10 — a 1-cent fix, needs evidence |
| E-CS4 | Brownout-mid-TX recovery; OTA/partition corruption rate | Sets watchdog + store-and-forward design; whether OTA is safe at all aloft |
| E-CS5 | Thermal time constants: self-heat to stability, duty-cycle floor | Whether the −40 °C rating is met by duty cycling alone |
| E-CS6 | Solar output vs temperature and sun angle (balloon rotates) | Wing geometry + MPPT-vs-LDO decision for rev-10 |

## Rigs and procedures (bench, freezer −18 °C, honest extrapolation)

**Instrumentation (all existing board sense lines, logged at ≥10 Hz by a bench
ESP32 or the DUT itself into flash):** `HUB_PV_MID1`, `HUB_PV_P/N` (wing
voltage/current via shunt), `SCAP_ADC` (bulk-rail sag), `NTC_SENSE` (board
temp), `F33_VSENSE` (3V3 rail), plus esp_reset_reason() persisted per boot.

- **E-CS1 rig:** desk lamp + dimmer or adjustable bench supply emulating PV
  (current-limited!), DUT freezer-soaked ≥2 h. Ramp irradiance 0→full in 5%
  steps, 10 min/step. **Pass:** boots and stays up 10 min at ≤ the worst
  December-dawn equivalent irradiance (compute from wing specs × 10% sun).
  **Fail →** rev-10 wing-size or LDO-swap decision.
- **E-CS2 rig:** DUT awake at minimum viable sun; command one 13 dBm FLRC TX
  (~130 mA, ~100 ms); log SCAP_ADC at 1 kHz (scope on the rail). **Pass:** rail
  sag stays above ESP32-S3 brown-out (2.55 V typ) with ≥100 mV margin. **Fail →**
  populate supercaps on rev-10 or add bulk C.
- **E-CS3 rig:** power relay cycles the DUT 50× at −18 °C and 50× at +20 °C,
  counting successful boots (GPIO toggle within 5 s = success). **Pass:**
  ≥98% boot at both temps. **Any cold-only failure → fit EN pull-up (10 kΩ)
  before flights** — this is the evidence gate for that resistor.
- **E-CS4 rig:** loop: start OTA-write → kill power mid-write (random 0–95%
  progress) ×30 at −18 °C; count boots that fall back to the other partition
  vs brick. **Pass:** 30/30 auto-rollback. **Fail →** no in-flight OTA; LoRa
  full-image fallback only.
- **E-CS5 rig:** NTC log while duty-cycling (1:9, 1:4, 1:1) inside the freezer
  vs ambient; measure the warm-up curve. Extrapolate to −50 °C ambient
  linearly (state the assumption!). **Pass:** some duty cycle keeps the die
  above −40 °C at −50 °C ambient. Output: the flight duty-cycle table.
- **E-CS6 rig:** wing on a gimbal in real sun (cold morning), sweep angle
  0–90°, log PV power vs angle × temperature. Output: expected daily energy
  envelope for the attitude-randomised balloon; feeds the duty scheduler.

**Freezer honesty:** −18 °C cannot prove −50 °C. Extrapolations are stated as
such; every E-CS result above is re-measured IN FLIGHT via the LoRa fallback
channel (that is the point of the experiment programme).

## Flight follow-ups (rides the E-00 LoRa fallback)

- F-CS1: log reset-cause + NTC + SCAP across every dawn for 14 days.
- F-CS2: count boots-to-first-TX minutes after terminator exit.
- F-CS3: correlate brownouts with TX duty and sun angle (needs E-06 data).

# Bands and regulatory notes

These are engineering starting points. They are **not** a certification or legal
opinion. Measure the real hardware and check the rules for the site before
transmitting.

## Profiles

| Profile | Frequency | FLRC | Power | Notes |
|---|---:|---:|---:|---|
| `eu868` | 868.100 MHz | 650 kbps | +14 dBm | EU 868.0–868.6, 1% duty cycle |
| `eu868-high` | 869.525 MHz | 650 kbps | +14 dBm | EU 869.4–869.65, 10% duty cycle |
| `us915` | 915.000 MHz | 1300 kbps | +22 dBm | US 902–928 DTS |
| `us915-robust` | 915.000 MHz | 650 kbps | +22 dBm | Narrower US fallback |
| `eu2400` | 2440.000 MHz | 2600 kbps | +12 dBm | 2.4 GHz ISM |
| `us2400` | 2440.000 MHz | 2600 kbps | +12 dBm | 2.4 GHz ISM |
| `custom` | operator | operator | operator | Validated only for range, not law |

## EU 868

- Keep the default at 868.1 MHz, +14 dBm.
- FLRC-650 occupies roughly 650 kHz; the 868.0–868.6 sub-band is only 600 kHz.
  Measure the actual 6 dB bandwidth before claiming compliance.
- The 1% duty cycle is a *time* budget, not a power budget. A continuous FIPS
  link can exceed it. The event plan must either respect it or use a band with a
  more suitable allowance.
- `eu868-high` at 869.525 MHz has a 10% duty cycle but is a different sub-band;
  do not mix it with 868.1 nodes.

## US 902–928

- 915.0 MHz, FLRC-1300 or FLRC-650.
- 47 CFR 15.247 DTS requires at least 500 kHz of 6 dB bandwidth. FLRC-260/325
  are not compliant as fixed-channel DTS modes.
- +22 dBm conducted is within the 1 W limit; EIRP depends on the antenna.
- Measure the E80 output filter and harmonics. The 3rd harmonic of 915 MHz lands
  at 2745 MHz, in a restricted band.

## 2.4 GHz

- 2440 MHz, FLRC-2600, +12 dBm.
- The LR2021 HF path max is +12 dBm; do not assume the sub-GHz PA numbers apply.
- The E80-900 module's 2.4 GHz path and antenna jack must be verified on the
  actual board. If it is not populated, use sub-GHz.

## Antenna and power

- The E80 LF PA is not the HF PA. The bridge configures the path explicitly.
- Start at lower power on the bench and raise only with an antenna connected.
- Never transmit into an open SMA without a load or antenna.

## What the code enforces

The host validates frequency range, bitrate, power and `sub_ghz` consistency.
It does **not** enforce duty cycle, 6 dB bandwidth or harmonic limits. Those are
operator responsibilities.

# RP2040 + E80/LR2021 bridge

- USB CDC: binary host protocol (`docs/BRIDGE-PROTOCOL.md`).
- UART1 GP12/GP13: human-readable log at 115200.
- Radio: E80 LR2021, SPI bypass pin map, one owner in `loop()`.
- Default: 915 MHz, FLRC-1300, +22 dBm, 255-byte packets, LF path.
- Host `CFG` overrides band/frequency/bitrate/power/sync/relay.

## Build

```bash
pio run -d reference/fips-lr2021/firmware/rp2040-bridge -e rp2040-bridge
```

## Flash

Put the RP2040 in BOOTSEL, then:

```bash
pio run -d reference/fips-lr2021/firmware/rp2040-bridge -e rp2040-bridge -t upload
```

or `scripts/flash-bridge.sh /dev/ttyACM0`.

## Check

```bash
fips-lr2021ctl --serial /dev/ttyACM0 hello
fips-lr2021ctl --serial /dev/ttyACM0 cfg --band us915
fips-lr2021ctl --serial /dev/ttyACM0 status
```

## Notes

- The radio is configured fixed-length 255. The bridge trims the padded packet
  to the link frame's declared length before sending `RX`.
- `radioApply` is the only re-init path. The watchdog uses the same path.
- Relay mode hashes the last 16 packets for 2 s to stop an immediate loop.
- 2.4 GHz uses the HF path and HF PA bytes; verify the E80 module actually has
  that path before enabling it.

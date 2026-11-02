# Results

**Status: hardware pending.** Do not fill this in from expectations.

## Host tests

Run:

```bash
cd <fips-fork>
cargo test -p fips-lr2021
cargo check -p fips-mesh
cargo test -p fips-mesh lr2021_transport_parses --lib
```

Record:

| Date | Commit | Command | Result |
|---|---|---|---|
| 2026-11-02 | `8aa2dd6` | `cargo test -p fips-lr2021` | 22 passed |
| 2026-11-02 | `8aa2dd6` | `cargo check -p fips-mesh` | clean |
| 2026-11-02 | `8aa2dd6` | config parse | pass |

## Hardware matrix

Fill only with measured numbers. Attach the raw CSV/log path.

| Date | Host A | Host B | Band | Bitrate | Distance | Payload | Sent | RX | PER | RSSI | SNR | Notes |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 2026-11-02 | mock PTY A | mock PTY B | us915 | 1300 | 0 m | 64 | 20 | 20 | 0% | -40 | 10 | host link/CLI E2E |
| 2026-11-02 | x280 E80 STM32 | — | us915 | 1300 | 0 m | — | — | — | — | — | — | HELLO/CFG/STATUS verified; RF peer blocked (second SWD dead) |

## FIPS checks

| Date | Band | Handshake | Ping | iperf3 UDP | Relay? | Notes |
|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |

## Soak

| Date | Band | Duration | Resets | Drops | Result |
|---|---|---:|---:|---:|---|
|  |  |  |  |  |  |

## Hardware bridge protocol

2026-11-02, `/dev/ttyUSB6`, probe `203584200D2D0D42`:

```text
OK BRIDGE 115200
protocol=1 firmware=0.1.0 chip=0x1801 capabilities=0x0007
configured band=us915 freq=915000000 Hz flrc=1300 kbps power=22 dBm payload=255B relay=false
pong
tx=0 rx=0 crc=0 drops=0 timeouts=0 resets=0
```

Blocked: second E80 SWD probe `148757200D2D1425` cannot read IDR; CH340 ROM
bootloader path fails as documented. Two-node RF needs the second board
re-seated or power-cycled.

## Native FIPS transport start

2026-11-02, patched FIPS rev `1559063`, config `transports.lr2021` on
`/dev/ttyUSB6` at 115200:

```text
Transports initialized count=1
Node started: state=running transports=1
Transport stopped transport_id=transport:1 transport_type="lr2021"
```

This proves the native fork path opens the E80 bridge, applies CFG, enters the
node dataplane, and shuts down cleanly. No peer was present, so this is not a
handshake result.

## Known issues observed

- 

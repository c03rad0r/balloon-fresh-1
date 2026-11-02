# Demo runbook — two machines, Exit & Build

## Pre-flight (before travel)

- [ ] Both RP2040/E80 boards flash the same bridge firmware.
- [ ] Both boards enumerate and answer `fips-lr2021ctl hello`.
- [ ] Antennas connected; power and ground checked.
- [ ] Laptops have the patched FIPS binary and the `lr2021` config.
- [ ] FIPS identities and TUN names are known.
- [ ] A fallback `fips-lr2021d` config exists.

## Bench bring-up (2.4 GHz first)

On machine A:

```bash
fips-lr2021ctl --serial /dev/ttyACM0 cfg --band us2400 --power-dbm 8
fips-lr2021ctl --serial /dev/ttyACM0 status
```

On machine B:

```bash
fips-lr2021ctl --serial /dev/ttyACM0 cfg --band us2400 --power-dbm 8
fips-lr2021ctl --serial /dev/ttyACM0 status
```

Start FIPS on both with the `transports.lr2021` block. Use the same `band`,
`radio_payload`, sync word and MTU. Give each node a distinct `local_id` (1 and
2).

Check:

```bash
fipsctl show peers
fipsctl show transports
```

## Ping and throughput

```bash
ping6 -I fips0 <peer-fips-address>
iperf3 -u -c <peer-fips-address> -b 100k -t 10
```

Expected first result: handshake in under 60 seconds, 0% ping loss at bench
distance, and at least 100 kbps at 2.4 GHz.

## Event band (US 915)

Repeat with:

```bash
fips-lr2021ctl --serial /dev/ttyACM0 cfg --band us915
fips-lr2021ctl --serial /dev/ttyACM1 cfg --band us915
```

`us915` is FLRC-1300 at +22 dBm. `us915-robust` is FLRC-650 if the channel is
dirty.

## Relay

Third bridge:

```bash
fips-lr2021ctl --serial /dev/ttyACM2 cfg --band us915 --relay
```

Place it between A and B. Run the same ping/iperf test. Compare direct vs relayed
at the same positions. The relay is transparent; FIPS sees a longer path.

## Fallback: stock FIPS + daemon

If the native transport build is blocked:

```bash
fips-lr2021d --serial /dev/ttyACM0 --band us915 --udp-bind 127.0.0.1:2122
```

Point stock FIPS `transports.udp` at `127.0.0.1:2122` and use the daemon as the
peer endpoint. The radio path is the same; only the FIPS integration differs.

## Failure playbook

| Symptom | Check |
|---|---|
| no HELLO_ACK | wrong port, bridge not flashed, USB cable |
| CFG_ACK status != 0 | band/frequency/bitrate rejected by firmware |
| CFG_ACK values differ | firmware and host profile mismatch |
| handshake never starts | both ends same band/sync/radio_payload? |
| handshake starts, no data | link IDs, MTU, ACK path, relay loop |
| link dies after minutes | radio watchdog, power/thermal, USB reconnect |
| relay duplicates | expected; check link dedup counters |

## Shutdown

- Stop FIPS first.
- Stop the daemon if used.
- Unplug antennas last; never transmit without a load.
- Record results in `docs/RESULTS.md`.

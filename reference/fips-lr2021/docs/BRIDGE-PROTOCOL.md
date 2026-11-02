# Host ↔ bridge protocol

## Framing

```
offset  size  field
0       2     magic A5 5A
2       1     type
3       2     payload length, little-endian
5       N     payload
5+N     2     CRC16/CCITT-FALSE over bytes [2 .. 5+N)
```

Maximum payload is 2048 bytes. The decoder skips leading garbage, resynchronizes
on the next `A5 5A`, and drops frames with a bad CRC. That matters after a USB
reconnect or a bridge reset.

## Types

| Value | Name | Direction |
|---:|---|---|
| 1 | HELLO | host → bridge |
| 2 | HELLO_ACK | bridge → host |
| 3 | CFG | host → bridge |
| 4 | CFG_ACK | bridge → host |
| 5 | TX | host → bridge |
| 6 | RX | bridge → host |
| 7 | STAT | bridge → host |
| 8 | EVT | bridge → host |
| 9 | PING | host → bridge |
| 10 | PONG | bridge → host |

## HELLO

Payload: one byte, protocol version (currently `1`).

## HELLO_ACK

8 bytes:

```
0   protocol u8
1   firmware major
2   firmware minor
3   firmware patch
4   chip id u16 LE
6   capabilities u16 LE
```

Capabilities:

| Bit | Meaning |
|---:|---|
| 0 | sub-GHz path |
| 1 | 2.4 GHz path |
| 2 | relay mode |
| 3 | variable packet length |

## CFG

15 bytes:

```
0   band u8
1   frequency_hz u32 LE
5   bitrate_kbps u16 LE
7   tx_power_dbm i8
8   sync_word[4]
12  radio_payload u16 LE
14  flags
```

Band values: 0 `eu868`, 1 `eu868-high`, 2 `us915`, 3 `us915-robust`,
4 `eu2400`, 5 `us2400`, 6 `custom`.

Flags: bit 0 relay, bit 1 sub-GHz path.

## CFG_ACK

10 bytes:

```
0   status u8 (0 = ok)
1   frequency_hz u32 LE
5   bitrate_kbps u16 LE
7   tx_power_dbm i8
8   radio_payload u16 LE
```

The host compares the applied values with the requested values. A mismatch is a
startup failure.

## TX

Payload: one raw radio packet, exactly as it should appear on air.

## RX

```
0   rssi_dbm i16 LE
2   snr_db i8
3   crc_ok u8
4   data_len u16 LE
6   data
```

## STAT

24 bytes, six little-endian `u32` counters:

```
tx_packets, rx_packets, crc_errors, drops, tx_timeouts, resets
```

## EVT

UTF-8 text, e.g. `watchdog reinit`, for the host log.

## PING/PONG

Empty payload. The bridge replies `PONG` followed by `STAT`.

## Timing

- Host read timeout: 50 ms.
- HELLO/CFG timeout: 2 s.
- Link ACK timeout: 40 ms.
- Link retry budget: 3.
- Reassembly timeout: 500 ms.
- Dedup window: 5 s.

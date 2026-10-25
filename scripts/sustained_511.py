#!/usr/bin/env python3
"""Sustained sweep at LEN 511 (and the 127 baseline) on E80 boards.

WHY THIS EXISTS
---------------
The repo has no sustained (no-gap) 511 B measurement. Every 511 B row on disk was
taken at a 40 ms inter-packet gap, which floors throughput at ~90 kbps and cannot
answer a throughput question. This script measures it properly.

WHAT THE SPEC ALLOWS (BENCH-CONSOLE-SPEC.md, read before changing anything)
--------------------------------------------------------------------------
§7 GAP rule: **for LEN > 256, hosts MUST set GAP >= 40000 us (40 ms).**
   Rationale given: at 115200 8N1 the console drains ~87 us/byte; a worst-case PKT
   line plus housekeeping needs headroom so RX line assembly never starves radio
   IRQ servicing. 40 ms was measured safe in the E80<->E80 511 B sweeps
   (651 pkts, zero drops).

CONSEQUENCE, STATED PLAINLY: **as specified, a 511 B sweep cannot exceed
~255*8/0.040 = 25.5 kbps.** The spec's own numbers make a 511 B sustained
throughput number impossible at 115200. So this script runs TWO things:

  MODE A  "spec"   -- LEN 511, GAP 40000. Legal today. Gives the *delivery*
                      result (PER, bit errors, drops) at 511 B. It will report a
                      tiny kbps, and that number is a property of the CONSOLE, not
                      of the radio. Expected, not a failure.

  MODE B  "fast"   -- LEN 511, GAP as tight as the console tolerates, and the
                      console moved to 2 Mbaud first if the firmware supports it.
                      This is the measurement that can answer the throughput
                      question. It CONTRADICTS spec §7 as written, so sample.py
                      refuses to run it without --ack-spec-conflict, and it
                      watches the `drops` counter to prove whether the gap was
                      actually safe.

The kbps ceiling being measured is a HOST SPI/CONSOLE wall, not the air interface.
See docs/THROUGHPUT-SETTLED-by-measurement.md in exit-and-build-balloon.

USAGE
-----
    ./sustained_511.py --tx /dev/ttyUSB1 --rx /dev/ttyUSB0 --mode spec
    ./sustained_511.py --tx /dev/ttyUSB1 --rx /dev/ttyUSB0 --mode fast \
        --baud 2000000 --ack-spec-conflict

Prints one CSV line per (len, br, gap) point so results are paste-able into the
repo. Nothing is written to disk unless --out is given.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("need pyserial:  pip install pyserial   (or apt install python3-serial)")


SPEC_GAP_US = 40000          # BENCH-CONSOLE-SPEC §7, mandatory for LEN > 256
SPEC_LEN_MAX = 511           # driver-documented maximum; 512 is NOT legal
SPEC_LEN_MAX_LORA = 255

STAT_RE = re.compile(r"STAT\b(?P<body>.*)$")
KV_RE = re.compile(r"(\w+)=([^\s]+)")


def parse_stat(line: str) -> dict:
    m = STAT_RE.search(line)
    if not m:
        return {}
    return {k: v for k, v in KV_RE.findall(m.group("body"))}


class Board:
    """One E80 console over USB serial."""

    def __init__(self, port: str, baud: int, label: str, timeout: float = 1.0):
        self.port, self.baud, self.label = port, baud, label
        self.ser = serial.Serial(port, baud, timeout=timeout)
        time.sleep(0.4)
        self.drain()

    def drain(self) -> str:
        out = b""
        while self.ser.in_waiting:
            out += self.ser.read(self.ser.in_waiting)
            time.sleep(0.01)
        return out.decode("utf-8", errors="replace")

    def cmd(self, text: str, wait: float = 0.35) -> str:
        self.ser.write((text + "\r\n").encode())
        time.sleep(wait)
        return self.drain()

    def stat(self, retries: int = 3) -> dict:
        for _ in range(retries):
            d = parse_stat(self.cmd("STAT?", wait=0.30))
            if d:
                return d
        return {}

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass


def configure_pair(tx: Board, rx: Board, br: int, dbm: int = 22):
    """Golden FLRC config per BENCH-CONSOLE-SPEC §8. Same on both boards."""
    for b in (tx, rx):
        b.cmd("STOP", 0.4)
        b.cmd("ROLE NONE", 0.2)
    tx.cmd("ROLE TX", 0.2)
    rx.cmd("ROLE RX", 0.2)
    # MOD flrc <br_kbps> <dbm> — cr 3/4, 32 b preamble, CRC on, per §8
    for b in (tx, rx):
        b.cmd(f"MOD flrc {br} {dbm}", 0.5)
    tx.cmd("PRBS ON", 0.2)
    rx.cmd("PRBS ON", 0.2)


def one_point(tx: Board, rx: Board, length: int, br: int, gap_us: int,
              duration_s: float, dbm: int) -> dict:
    """Run one (len, br, gap) sustained point. Returns a result dict."""
    configure_pair(tx, rx, br, dbm)

    # arm RX first so it is listening before TX starts
    rx.cmd(f"START N=1000000 LEN={length} GAP={gap_us}", 0.4)
    time.sleep(0.5)
    tx.cmd(f"START N=1000000 LEN={length} GAP={gap_us}", 0.4)

    time.sleep(duration_s)
    tx.cmd("STOP", 0.5)
    rx.cmd("STOP", 0.5)

    txs, rxs = tx.stat(), rx.stat()

    def num(d, k, default=None):
        try:
            return float(d.get(k))
        except (TypeError, ValueError):
            return default

    sent = num(txs, "sent_ok", num(txs, "sent"))
    recv = num(rxs, "rx")
    elapsed = num(txs, "elapsed_s") or num(rxs, "elapsed_s")
    kbps_rx = num(rxs, "kbps")
    per_x1e6 = num(rxs, "per_x1e6")
    drops = num(rxs, "drops")
    crc_err = num(rxs, "crc_err")

    # throughput the radio actually radiated, computed independently of the fw
    kbps_calc = None
    if sent and elapsed:
        kbps_calc = sent * length * 8 / elapsed / 1000.0

    return {
        "len": length, "br_kbps": br, "gap_us": gap_us, "dur_s": duration_s,
        "sent_ok": int(sent) if sent else None,
        "rx": int(recv) if recv else None,
        "elapsed_s": round(elapsed, 3) if elapsed else None,
        "kbps_fw_rx": kbps_rx,
        "kbps_calc_tx": round(kbps_calc, 1) if kbps_calc else None,
        "pct_of_air": round(100.0 * kbps_calc / br, 1) if (kbps_calc and br) else None,
        "per_x1e6": per_x1e6,
        "crc_err": int(crc_err) if crc_err is not None else None,
        "drops": int(drops) if drops is not None else None,
        "tx_stat_raw": " ".join(f"{k}={v}" for k, v in txs.items()),
        "rx_stat_raw": " ".join(f"{k}={v}" for k, v in rxs.items()),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tx", required=True, help="TX board serial port")
    ap.add_argument("--rx", required=True, help="RX board serial port")
    ap.add_argument("--baud", type=int, default=115200, help="console baud (default 115200)")
    ap.add_argument("--mode", choices=("spec", "fast"), default="spec")
    ap.add_argument("--lengths", default="127,511", help="comma list, <=511")
    ap.add_argument("--bitrates", default="2600", help="comma list of FLRC kbps")
    ap.add_argument("--gap", type=int, default=None,
                    help="override gap_us (spec mode forces >=40000 for len>256)")
    ap.add_argument("--duration", type=float, default=20.0, help="seconds per point")
    ap.add_argument("--dbm", type=int, default=22)
    ap.add_argument("--out", default=None, help="write CSV here")
    ap.add_argument("--ack-spec-conflict", action="store_true",
                    help="required for --mode fast with len>256 (contradicts spec §7)")
    args = ap.parse_args()

    lengths = [int(x) for x in args.lengths.split(",") if x.strip()]
    bitrates = [int(x) for x in args.bitrates.split(",") if x.strip()]

    for L in lengths:
        if L > SPEC_LEN_MAX:
            print(f"refuse: LEN {L} > {SPEC_LEN_MAX} (driver maximum; 512 is not legal)")
            return 2

    # ---- the conflict, made impossible to trip over silently ----
    needs_ack = args.mode == "fast" and any(L > 256 for L in lengths)
    if needs_ack and not args.ack_spec_conflict:
        print("REFUSING: --mode fast with LEN > 256 contradicts BENCH-CONSOLE-SPEC §7,")
        print("which says hosts MUST use GAP >= 40000 us for LEN > 256, and prices the")
        print("reason at 115200 8N1 console drain. As specified, a 511 B sweep cannot")
        print("exceed ~25.5 kbps -- the number would describe the console, not the radio.")
        print()
        print("If you intend to measure the real ceiling anyway, re-run with")
        print("  --ack-spec-conflict  (and ideally --baud 2000000)")
        print("and check the `drops` column: drops > 0 means the tighter gap starved")
        print("the console and the point is INVALID, not fast.")
        return 2

    gaps = {}
    for L in lengths:
        if args.gap is not None:
            if args.mode == "spec" and L > 256 and args.gap < SPEC_GAP_US:
                print(f"refuse: spec mode needs GAP >= {SPEC_GAP_US} for LEN {L}")
                return 2
            gaps[L] = args.gap
        else:
            # spec: 40 ms for big packets; fast: 2 ms floor and let drops judge it
            gaps[L] = SPEC_GAP_US if (args.mode == "spec" and L > 256) else (
                2000 if args.mode == "fast" else 10000)

    print(f"ports tx={args.tx} rx={args.rx} baud={args.baud} mode={args.mode}")
    print(f"points: {[(L, br, gaps[L]) for L in lengths for br in bitrates]}")
    if args.mode == "spec":
        print("NOTE: spec mode measures DELIVERY at 511 B. Its kbps is console-bound")
        print("      (~25 kbps max) BY DESIGN and is not a radio throughput result.")

    try:
        tx = Board(args.tx, args.baud, "TX")
        rx = Board(args.rx, args.baud, "RX")
    except serial.SerialException as e:
        print(f"\nERROR: cannot open a board console -- {e}")
        print("No hardware was touched. Plug both E80 boards in and check:")
        print("  lsusb | grep -i 1a86      # CH340 on-board bridge")
        print("  ls /dev/ttyUSB*           # then pass the right two ports")
        return 3
    rows = []
    try:
        for L in lengths:
            for br in bitrates:
                gap = gaps[L]
                print(f"\n--- LEN {L} BR {br} GAP {gap}us for {args.duration}s ---")
                row = one_point(tx, rx, L, br, gap, args.duration, args.dbm)
                rows.append(row)
                print(f"  sent_ok={row['sent_ok']} rx={row['rx']} "
                      f"kbps_calc={row['kbps_calc_tx']} ({row['pct_of_air']}% of air) "
                      f"PER={row['per_x1e6']} drops={row['drops']} crc_err={row['crc_err']}")
                if row["drops"] and row["drops"] > 0:
                    print("  ⚠ drops > 0 -- gap too tight for the console. Point INVALID.")
                time.sleep(1.0)
    finally:
        tx.close()
        rx.close()

    if args.out:
        with open(args.out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\nwrote {args.out}")

    print("\nSUMMARY")
    for r in rows:
        print(f"  LEN {r['len']} BR {r['br_kbps']} GAP {r['gap_us']}: "
              f"{r['kbps_calc_tx']} kbps ({r['pct_of_air']}%), "
              f"PER {r['per_x1e6']}, drops {r['drops']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Two virtual LR2021 bridges over PTYs, for host-side end-to-end tests.

Creates two PTY links (default /tmp/fips-lr2021-a and -b). Each side speaks the
host bridge protocol, and TX frames from one are delivered as RX frames to the
other, with a small fixed RSSI/SNR. This is not a radio model; it is a cheap
way to exercise the serial codec, link layer and CLI without hardware.
"""
import os
import pty
import select
import struct
import sys
import termios
import time
import tty

MAGIC = b"\xA5\x5A"
HELLO, HELLO_ACK, CFG, CFG_ACK, TX, RX, STAT, EVT, PING, PONG = range(1, 11)


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return crc


def encode(kind: int, payload: bytes) -> bytes:
    body = bytes([kind]) + struct.pack("<H", len(payload)) + payload
    return MAGIC + body + struct.pack("<H", crc16(body))


def decode(buf: bytearray):
    while True:
        i = buf.find(MAGIC)
        if i < 0:
            buf.clear()
            return None
        if i:
            del buf[:i]
        if len(buf) < 5:
            return None
        plen = struct.unpack_from("<H", buf, 3)[0]
        total = 7 + plen
        if len(buf) < total:
            return None
        body = bytes(buf[2 : total - 2])
        if crc16(body) != struct.unpack_from("<H", buf, total - 2)[0]:
            del buf[0]
            continue
        kind = buf[2]
        payload = bytes(buf[5 : total - 2])
        del buf[:total]
        return kind, payload


class Endpoint:
    def __init__(self, master_fd, path):
        self.master = master_fd
        self.path = path
        self.buf = bytearray()
        self.stats = [0, 0, 0, 0, 0, 0]

    def send(self, kind: int, payload: bytes = b""):
        os.write(self.master, encode(kind, payload))

    def handle(self, kind: int, payload: bytes, peer: "Endpoint"):
        print(f"{self.path}: kind={kind} len={len(payload)}", flush=True)
        if kind == HELLO:
            self.send(HELLO_ACK, bytes([1, 0, 1, 0, 0x21, 0x00, 0x07, 0x00]))
        elif kind == CFG:
            if len(payload) != 15:
                self.send(CFG_ACK, bytes([3]) + b"\x00" * 9)
                return
            ack = bytes([0]) + payload[1:8] + payload[12:14]
            self.send(CFG_ACK, ack)
        elif kind == PING:
            self.send(PONG)
            self.send(STAT, struct.pack("<6I", *self.stats))
        elif kind == TX:
            self.stats[0] += 1
            peer.stats[1] += 1
            print(f"  relay TX len={len(payload)} head={payload[:4].hex()}", flush=True)
            peer.send(RX, struct.pack("<hBBH", -40, 10, 1, len(payload)) + payload)


def open_pty(link_path: str):
    master, slave = pty.openpty()
    tty.setraw(master)
    tty.setraw(slave)
    name = os.ttyname(slave)
    if os.path.islink(link_path) or os.path.exists(link_path):
        os.unlink(link_path)
    os.symlink(name, link_path)
    return master, slave


def main():
    a_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/fips-lr2021-a"
    b_path = sys.argv[2] if len(sys.argv) > 2 else "/tmp/fips-lr2021-b"
    ma, sa = open_pty(a_path)
    mb, sb = open_pty(b_path)
    a = Endpoint(ma, a_path)
    b = Endpoint(mb, b_path)
    print(f"mock radio: {a_path} <-> {b_path}", flush=True)
    try:
        while True:
            ready, _, _ = select.select([ma, mb], [], [], 1.0)
            for fd in ready:
                data = os.read(fd, 4096)
                if not data:
                    continue
                ep = a if fd == ma else b
                peer = b if ep is a else a
                ep.buf.extend(data)
                while True:
                    frame = decode(ep.buf)
                    if frame is None:
                        break
                    ep.handle(frame[0], frame[1], peer)
    except KeyboardInterrupt:
        pass
    finally:
        for fd in (ma, sa, mb, sb):
            try:
                os.close(fd)
            except OSError:
                pass


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Route the compact SX1280 match with controlled-impedance widths, then verify.

TOPOLOGY, read from the pads rather than assumed:
    C0 : pad1 = /SX1280_RF , pad2 = GND          -> SHUNT capacitor to ground
    L1 : pad1 = /SX1280_RF , pad2 = /SX1280_RF_MATCH -> SERIES inductor onward
    U4 : pad22 = /SX1280_RF                      -> the radio's RFIO

So the electrical node is: pad22 --+-- C0.pad1 (shunt to GND)
                                   |
                                   +-- L1.pad1 (series, continues to L2/C1/C2/C3/C7)

WIDTHS, measured not guessed (rf_impedance.py, rf_escape_width.py):
    0.364 mm = 50.0 ohm on this stackup, BUT pad22's 0.50 mm pitch land set caps the escaping trace
               at 0.300 mm (0.200 mm clearance to U4.pad21/pad23 GND, exactly at the floor).
    0.300 mm = 56.3 ohm -- the widest legal neck out of the pad.
So: neck out of pad22 at 0.300 mm, then widen to 0.364 mm once clear of the pad row. That is standard
RF practice: a short controlled neck is better than a long wrong impedance.

Usage: route_rf_match2.py <in.kicad_pcb> <out.kicad_pcb>
"""
import math
import sys

import pcbnew

RF_NET = "/SX1280_RF"
NECK_MM = 0.300
WIDE_MM = 0.364
CLEAR = 0.20


def mm(v):
    return pcbnew.ToMM(v)


def find_net(b, name):
    for c in range(1, b.GetNetCount()):
        n = b.FindNet(c)
        if n and n.GetNetname() == name:
            return n
    return None


def pad_bbox(b):
    out = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            r = p.GetBoundingBox()
            out.append((fp.GetReference(), str(p.GetNumber()), p.GetNetname(),
                        mm(r.GetLeft()), mm(r.GetTop()), mm(r.GetRight()), mm(r.GetBottom())))
    return out


def seg_clear(seg, width, own_net, obs, clearance):
    """Return the tightest penetration found, or None if clear."""
    half = width / 2.0
    ax, ay = seg[0]
    bx, by = seg[1]
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    worst = None
    for ref, num, net, x0, y0, x1, y1 in obs:
        if net == own_net:
            continue
        for i in range(41):
            t = i / 40.0
            px, py = ax + t * vx, ay + t * vy
            dx = max(0.0, max(x0 - px, px - x1))
            dy = max(0.0, max(y0 - py, py - y1))
            d = math.hypot(dx, dy)
            need = clearance + half
            if d < need:
                pen = need - d
                if worst is None or pen > worst[0]:
                    worst = (pen, f"{ref}.{num} {net}", round(d, 3))
    return worst


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    b = pcbnew.LoadBoard(src)
    net = find_net(b, RF_NET)
    if net is None:
        print(f"{RF_NET} absent")
        return 1

    def pad(ref, num):
        fp = b.FindFootprintByReference(ref)
        for p in fp.Pads():
            if str(p.GetNumber()) == num:
                return p
        return None

    p22 = pad("U4", "22")
    c0 = pad("C0", "1")
    l1 = pad("L1", "1")
    for nm, p in (("U4.22", p22), ("C0.1", c0), ("L1.1", l1)):
        if p is None:
            print(f"{nm} missing")
            return 1
    a = (mm(p22.GetPosition().x), mm(p22.GetPosition().y))
    c = (mm(c0.GetPosition().x), mm(c0.GetPosition().y))
    l = (mm(l1.GetPosition().x), mm(l1.GetPosition().y))
    print(f"board: {src}")
    print(f"  U4.pad22 {a}\n  C0.pad1  {c}  (shunt to GND)\n  L1.pad1  {l}  (series onward)")
    print(f"  neck {NECK_MM} mm (56.3 ohm, max legal escape), then {WIDE_MM} mm (50 ohm)\n")

    # clear pre-existing tracks on this net
    for t in [t for t in b.GetTracks() if t.GetNetname() == RF_NET]:
        b.Remove(t)

    obs = pad_bbox(b)
    # Junction below the pad row: pad row ends at y=29.55, so clear it and stay above D_HUB1 (y=32.00).
    jy = 30.15
    j = (a[0], jy)
    print(f"junction at {j}  (below the pad row y<29.55, above D_HUB1 y>32.00)")

    legs = [
        ("neck pad22->junction", a, j, NECK_MM),
        ("junction->C0.pad1", j, c, WIDE_MM),
        ("junction->L1.pad1", j, l, WIDE_MM),
    ]
    all_ok = True
    for name, s, e, w in legs:
        worst = seg_clear((s, e), w, RF_NET, obs, CLEAR)
        if worst:
            print(f"  [BLOCKED] {name:22} w={w:.3f}  {worst[1]} d={worst[2]} pen={worst[0]:.3f}")
            all_ok = False
        else:
            print(f"  [CLEAR]   {name:22} w={w:.3f}")

    if not all_ok:
        print("\nNOT ROUTING -- at least one leg is blocked. Report as-is rather than forcing a trace.")
        return 1

    made = []
    for name, s, e, w in legs:
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(int(round(s[0] * 1e6)), int(round(s[1] * 1e6))))
        t.SetEnd(pcbnew.VECTOR2I(int(round(e[0] * 1e6)), int(round(e[1] * 1e6))))
        t.SetWidth(int(round(w * 1e6)))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(net)
        b.Add(t)
        made.append(t)

    rbt = [t for t in b.GetTracks() if t.GetNetname() == RF_NET]
    print(f"\ntracks laid: {len(rbt)}")
    for t in rbt:
        s, e = t.GetStart(), t.GetEnd()
        print(f"  ({mm(s.x):6.2f},{mm(s.y):6.2f})->({mm(e.x):6.2f},{mm(e.y):6.2f}) "
              f"w={mm(t.GetWidth()):.3f} L={math.hypot(mm(e.x)-mm(s.x), mm(e.y)-mm(s.y)):.2f}mm")
    zs = sorted({round(mm(t.GetWidth()), 3) for t in rbt})
    tot = sum(math.hypot(mm(t.GetEnd().x) - mm(t.GetStart().x),
                         mm(t.GetEnd().y) - mm(t.GetStart().y)) for t in rbt)
    print(f"\ntotal length {tot:.2f} mm, widths {zs}, vias {sum(1 for t in rbt if t.Type() == pcbnew.PCB_VIA_T)}")
    pcbnew.SaveBoard(dst, b)
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

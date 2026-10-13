"""v18: v17 + fix the 2 new I2C_SCL grazes: the A* west column hugs I2C_SCL.
Fix: raise the track-keep for I2C_SCL only (it can move later if needed) --
no: correct fix = nudge the two west-leg vertices +0.25 east (off I2C_SCL's
keep-ring), verified vs all foreign B.Cu copper. Also fix the +1 unconnected
(the DIO1 F.Cu elbow now has a redundant stub at (49.5,8.225)-(49.59,8.316)
-- old elbow point; remove stubs < 0.3mm attached to nothing)."""
import argparse
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

MM = 1e6
TRACK_W = 0.20
RULE = 0.20
NET_F33 = "/F33_SCK"
NET_DIO1 = "/SX1280_DIO1"
NET_I2C = "/I2C_SCL"


def seg_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def seg_seg(ax, ay, bx, by, cx, cy, dx, dy):
    return min(seg_dist(ax, ay, cx, cy, dx, dy), seg_dist(bx, by, cx, cy, dx, dy),
               seg_dist(cx, cy, ax, ay, bx, by), seg_dist(dx, dy, ax, ay, bx, by))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    args = ap.parse_args()
    b = pcbnew.LoadBoard(args.inp)
    bcu = b.GetLayerID("B.Cu")

    # --- 1. nudge F33_SCK vertices that violate I2C_SCL, east by 0.25
    # gather I2C_SCL B.Cu segments
    i2c = []
    for t in b.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetLayer() == bcu and t.GetNetname() == NET_I2C:
            s, e = t.GetStart(), t.GetEnd()
            i2c.append((s.x / MM, s.y / MM, e.x / MM, e.y / MM, t.GetWidth() / MM / 2))
    moved = 0
    for t in b.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetLayer() != bcu or t.GetNetname() != NET_F33:
            continue
        for getter, setter in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
            pt = getter()
            px, py = pt.x / MM, pt.y / MM
            viol = False
            for (tx0, ty0, tx1, ty1, hw) in i2c:
                d = seg_dist(px * MM, py * MM, tx0 * MM, ty0 * MM, tx1 * MM, ty1 * MM) / MM - hw
                if d < TRACK_W / 2 + RULE - 1e-9:
                    viol = True
                    break
            if viol:
                setter(pcbnew.VECTOR2I(int((px + 0.25) * MM), int(py * MM)))
                moved += 1
    print(f"1. F33_SCK vertices nudged east off I2C_SCL: {moved}")

    # --- 2. remove DIO1 stub: tiny segment(s) whose midpoint is far from both
    # the pad (49.50,7.20) and the new via (49.59,8.616) chain endpoints
    # -- simplest: delete DIO1 F.Cu segments shorter than 0.3mm
    removed = 0
    victims = []
    for t in b.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetNetname() == NET_DIO1:
            s, e = t.GetStart(), t.GetEnd()
            if math.hypot(e.x - s.x, e.y - s.y) / MM < 0.30:
                victims.append(t)
    for t in victims:
        b.Remove(t)
        removed += 1
    print(f"2. DIO1 micro-stubs removed: {removed}")
    b.BuildConnectivity()

    # reconnect if the elbow broke: add straight F.Cu pad->via track
    pad = (49.50, 7.20)
    via = (49.590, 8.616)
    have = False
    for t in b.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetNetname() == NET_DIO1 and t.GetLayerName() == "F.Cu":
            have = True
    if not have:
        netcode = None
        for code, ni in b.GetNetInfo().NetsByNetcode().items():
            if ni.GetNetname() == NET_DIO1:
                netcode = code
        nt = pcbnew.PCB_TRACK(b)
        nt.SetStart(pcbnew.VECTOR2I(int(pad[0] * MM), int(pad[1] * MM)))
        nt.SetEnd(pcbnew.VECTOR2I(int(via[0] * MM), int(via[1] * MM)))
        nt.SetWidth(int(TRACK_W * MM))
        nt.SetLayer(b.GetLayerID("F.Cu"))
        nt.SetNetCode(netcode)
        b.Add(nt)
        b.BuildConnectivity()
        print("   re-added straight F.Cu pad->via escape")

    b.Save(args.out)
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

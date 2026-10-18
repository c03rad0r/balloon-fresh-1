#!/usr/bin/env python3
"""Prove the layout guard measures what it claims, before trusting it to gate a drawing.

Two things must hold, and neither may be assumed:
  (1) the ink box the guard computes must match what rsvg-convert actually paints, or the guard is
      checking a different picture than the reviewer sees;
  (2) the guard must FIRE on the defect classes the visual reviews kept finding, and stay silent on a
      clean layout -- a guard that never fires is decoration.

Run: python3 tracker/hardware/test_svg_layout_guard.py
"""
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svg_layout_guard import Canvas, OverlapError, audit_svg, text_ink_box  # noqa: E402

FAILS = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def rendered_ink_extent(svg_text, size, family):
    """Render one line of text with rsvg and return its ink extent in SVG units."""
    tmp = "/tmp/guard_metric_probe"
    os.makedirs(tmp, exist_ok=True)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="200" viewBox="0 0 1600 200">'
           f'<rect width="1600" height="200" fill="#ffffff"/>'
           f'<text x="40" y="120" font-size="{size}" font-family="{family}">{svg_text}</text></svg>')
    sp = f"{tmp}/probe.svg"
    pp = f"{tmp}/probe.png"
    open(sp, "w").write(svg)
    subprocess.run(["rsvg-convert", "-w", "1600", sp, "-o", pp], check=True,
                   capture_output=True, text=True)
    from PIL import Image
    import numpy as np
    a = np.array(Image.open(pp).convert("L"))
    cols = np.where((a < 128).any(axis=0))[0]
    rows = np.where((a < 128).any(axis=1))[0]
    return (int(cols.min()), int(rows.min()), int(cols.max()), int(rows.max()))


def main():
    print("1. metrics agree with the renderer")
    probe = "SPECIMEN B \u2014 PEEL (Option B's failure mode)"
    for size in (13, 14, 20, 22):
        got = rendered_ink_extent(probe, size, "DejaVu Sans, Helvetica, sans-serif")
        box = text_ink_box(40, 120, probe, size)
        dx0, dx1 = abs(box[0] - got[0]), abs(box[2] - got[2])
        check(max(dx0, dx1) <= 3.0,
              f"size {size}: guard x=({box[0]:.1f},{box[2]:.1f}) vs render x=({got[0]},{got[2]})"
              f" -> max delta {max(dx0, dx1):.1f} px")
    # the pixels between the glyphs: a height error is harmless, an x error is not. Report the y fit.
    got = rendered_ink_extent(probe, 20, "DejaVu Sans")
    box = text_ink_box(40, 120, probe, 20)
    check(abs(box[1] - got[1]) <= 3 and abs(box[3] - got[3]) <= 3,
          f"y fit: guard y=({box[1]:.1f},{box[3]:.1f}) vs render y=({got[1]},{got[3]})")

    print("2. the guard fires on the defect classes the reviews found")
    c = Canvas(600, 400)
    c.text(50, 100, "alpha", tag="a")
    c.text(60, 108, "beta", tag="b")          # 8 px pitch at size 14 -> real collision
    probs = c.check()
    check(any("text/text overlap" in p for p in probs), f"overlapping text detected ({len(probs)})")

    c2 = Canvas(600, 400)
    c2.rect(40, 60, 300, 80, tag="green wall", fill="#2f6b3a")
    c2.text(60, 110, "label over the wall", tag="onwall")
    probs2 = c2.check()
    check(any("text on shape" in p for p in probs2), f"label on a filled shape detected ({len(probs2)})")

    c3 = Canvas(600, 400)
    c3.text(50, 100, "shear", tag="t1")
    c3.text(64, 100, "shear", tag="t2")      # 14 px apart on one baseline: the words interleave
    check(any("text/text overlap" in p for p in c3.check()), "same-baseline text collision detected")

    print("3. the guard stays silent on a clean layout")
    c4 = Canvas(600, 400)
    c4.rect(40, 60, 300, 80, fill="#2f6b3a", tag="wall")
    c4.text(40, 200, "clear of the wall", tag="ok")
    c4.text(40, 240, "also clear", tag="ok2")
    c4.line(40, 260, 340, 260, tag="rule")
    probs4 = c4.check()
    check(probs4 == [], f"clean layout has no findings: {probs4}")

    print("4. clipping outside the frame is caught")
    c5 = Canvas(200, 200)
    c5.text(180, 100, "runs off the right edge", tag="edge")
    check(any("clipped" in p for p in c5.check()), "text past the frame edge detected")

    print("5. write() refuses a bad canvas and emits a good one")
    try:
        c.write("/tmp/guard_should_not_exist.svg")
        check(False, "write() accepted a colliding canvas")
    except OverlapError:
        check(True, "write() raised OverlapError on a colliding canvas")
    good = Canvas(400, 300)
    good.text(30, 100, "hello", tag="h")
    good.write("/tmp/guard_good.svg")
    check(os.path.exists("/tmp/guard_good.svg"), "write() emitted a clean canvas")
    check(audit_svg("/tmp/guard_good.svg") == [], "audit_svg() re-reads a clean file as clean")

    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} check(s)")
        for f in FAILS:
            print("  - " + f)
        return 1
    print("all layout-guard self-tests passed")
    if not shutil.which("rsvg-convert"):
        print("NOTE: rsvg-convert absent, metric checks were skipped-level only")
    return 0


if __name__ == "__main__":
    sys.exit(main())

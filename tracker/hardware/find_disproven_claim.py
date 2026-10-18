#!/usr/bin/env python3
"""Find every doc that still asserts the DISPROVEN U1.41 claim.

WHY. The claim "U1.41 has no net -- an electrical defect in the radio's ground return" was disproven on
2026-10-17 by measurement (docs/fab/U1-FOOTPRINT-DIAGNOSIS.md):

  - the thirteen pads numbered '41' are a THERMAL-VIA ARRAY, all on ONE net (GND) -- the stock KiCad idiom
    for several physical pads, one net; the official RF_Module:ESP32-S3-WROOM-1U footprint ships exactly
    that structure, so this project did not author it
  - the nine unnamed pads carry NO COPPER AT ALL (layers=['F.Paste'] only) -- stencil apertures, so they
    cannot be "floating copper"
  - 'U1' is the ESP32-S3-WROOM-1U; the SX1280 is 'U4'
  - DRC's own unconnected list does not involve U1 at all

GATE-RESULTS.md was corrected. But a claim like this lives in MANY documents, and the one that matters most
is the entry point a fabricator reads first -- docs/fab/README.md, which still carried it when this script
was written.

This script finds every remaining instance so they can be corrected TOGETHER. It deliberately does NOT
auto-edit: each hit needs a human-readable correction, and a blind replace would corrupt the ones that are
quoting the claim in order to correct it.

Run: python3 tracker/hardware/find_disproven_claim.py [root]
Exit: 0 = no live assertions remain (quoted corrections are fine), 1 = live assertions found
"""
from __future__ import annotations

import os
import re
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "docs"

# Phrases that assert the claim. Matched case-insensitively.
CLAIM_PATTERNS = [
    r"U1\.41[^\n]{0,120}(no net|not connected|has no net)",
    r"(exposed|radio'?s?)[^\n]{0,40}(RF )?(ground )?pad[^\n]{0,60}no net",
    r"U1\.41[^\n]{0,80}electrical defect",
    r"pad-number mismatch",
    r"floating copper",
    # NOT a bare r"U1...is the SX1280": that matched the CORRECT sentence "U1 is the ESP32 module and
    # U4 is the SX1280 radio" and reported it as a live assertion. A detector that cries wolf on correct
    # text is the failure mode this whole session has been about. Require the claim to appear WITHOUT U4
    # being named as the SX1280 in the same line.
    # REMOVED: a pattern for "U1 is the SX1280". It could not be made to distinguish the CLAIM from the
    # CORRECT sentence "`U1` is the ESP32 module and `U4` is the SX1280 radio" -- both contain those words
    # in that order -- and it reported the correct sentence as a live assertion twice. A detector that
    # cries wolf on correct text is the failure mode this session has been about, so it is dropped rather
    # than made cleverer. The claim it targeted is caught by the U1.41-specific patterns above, which name
    # the pad and cannot match a correct sentence.
]

# A hit is a CORRECTION, not a live assertion, when it sits near a correction marker.
CORRECTION_MARKERS = (
    "disproven", "disproved", "corrected", "correction", "was wrong", "old claim",
    "no longer", "superseded", "retracted", "false alarm", "WRONG",
)


def main() -> int:
    if not os.path.isdir(ROOT):
        print(f"ABSENT: {ROOT}")
        return 2

    live, quoted = [], []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in (".git", "archive")]
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            p = os.path.join(dirpath, fn)
            try:
                lines = open(p, encoding="utf-8", errors="replace").read().splitlines()
            except Exception as e:
                print(f"  WARN unreadable {p}: {e}")
                continue
            for i, line in enumerate(lines):
                for pat in CLAIM_PATTERNS:
                    if re.search(pat, line, re.I):
                        # look at a window around the hit for a correction marker
                        # Widen forward as well as back: a correction block can sit several lines BELOW
                        # the claim it corrects (struck-through claim, then a quoted correction beneath).
                        lo, hi = max(0, i - 25), min(len(lines), i + 14)
                        window = " ".join(lines[lo:hi])
                        entry = (p, i + 1, line.strip()[:130])
                        if any(m.lower() in window.lower() for m in CORRECTION_MARKERS):
                            quoted.append(entry)
                        else:
                            live.append(entry)
                        break

    print(f"scanned: {ROOT}")
    print(f"\n=== LIVE ASSERTIONS of the disproven claim: {len(live)} ===")
    for p, ln, text in live:
        print(f"  {p}:{ln}")
        print(f"      {text}")
    if not live:
        print("  (none)")

    print(f"\n=== hits that sit near a correction marker (fine): {len(quoted)} ===")
    for p, ln, text in quoted[:8]:
        print(f"  {p}:{ln}")
    if len(quoted) > 8:
        print(f"  ... and {len(quoted) - 8} more")

    if live:
        print(f"\nRESULT: {len(live)} document(s) still assert a claim that measurement disproved.")
        print("  Correct them TOGETHER, and keep the record of what was corrected -- do not delete the")
        print("  history of the error, and do not blind-replace: some hits quote the claim to correct it.")
        return 1
    print("\nRESULT: no live assertions remain.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

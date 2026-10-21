# v10 placement GATE LOG (ADR-120 R3 — verdicts recorded, never skipped)

| date (UTC) | board | outline | renders shown | checks run | verdict |
|---|---|---|---|---|---|
| 2026-10-21 | v10 placement concept (front+back rectangles from measured v9 courtyards + E28 datasheet dims) | 52 × 62 mm | Signal: front.png + back.png (overlap-free, in-bounds, wing-seat clearance — programmatic) | `/tmp/v10_render2.py` local geometric check: FRONT OK, BACK OK | **APPROVED — operator: "looks better. Yes please go with this placing"** |

Routing is authorised to begin only after the TRUE-FOOTPRINT placement render is also shown
(same gate, second round: concept → real footprints → routing). This log line authorises the
real-board build, not routing.

| 2026-10-21 | v10 REAL placement, solver + both gates (front+back renders in Signal) | **72 × 80 mm** | front+back, 3D+technical (28 footprints, 4 seats, 8 holes) | geometry 0 violations · holes 0 violations · poison test still fails gate | **PENDING OPERATOR SIGN-OFF — amendment: 72×80 replaces the approved ~53×62.** Reasons + trade-offs in PR body. |

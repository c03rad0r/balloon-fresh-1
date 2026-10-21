# v10 placement GATE LOG (ADR-120 R3 — verdicts recorded, never skipped)

| date (UTC) | board | outline | renders shown | checks run | verdict |
|---|---|---|---|---|---|
| 2026-10-21 | v10 placement concept (front+back rectangles from measured v9 courtyards + E28 datasheet dims) | 52 × 62 mm | Signal: front.png + back.png (overlap-free, in-bounds, wing-seat clearance — programmatic) | `/tmp/v10_render2.py` local geometric check: FRONT OK, BACK OK | **APPROVED — operator: "looks better. Yes please go with this placing"** |

Routing is authorised to begin only after the TRUE-FOOTPRINT placement render is also shown
(same gate, second round: concept → real footprints → routing). This log line authorises the
real-board build, not routing.

| 2026-10-21 | v10 REAL placement, solver + both gates (front+back renders in Signal) | **72 × 80 mm** | front+back, 3D+technical (28 footprints, 4 seats, 8 holes) | geometry 0 violations · holes 0 violations · poison test still fails gate | **PENDING OPERATOR SIGN-OFF — amendment: 72×80 replaces the approved ~53×62.** Reasons + trade-offs in PR body. |

| 2026-10-21 | Operator sign-off (Signal): "looks good, please continue" on the 72×80 renders | 72 × 80 mm | front+back 3D + technical | both gates 0/0 | **APPROVED — routing phase begins** |

| 2026-10-21 | Operator caught 3 lane defects by eye (U_C.9 short at 0.000mm, 2 dead-end stubs, copper through the F33 body) | 72 × 80 mm | progress map + zoom crop | 4 gates; my own audit REFUTED (it tested contact, not validity) | **REJECTED the copper — board returned to zero tracks** |
| 2026-10-21 | Operator directive: "(a) a real grid/A* router with via support ... make sure this approach is taken in all future attempts" | 72 × 80 mm | — | ADR-126 written; AGENTS.md items 6–10; `tests/test_routing_method_binding.py` (13 assertions) + `tests/test_v10_connectivity.py` (8 gate tests) in CI Suites 10–11 | **BINDING — straight/L routing banned; A* with vias is the only permitted method; no copper ships unless all 4 gates pass** |

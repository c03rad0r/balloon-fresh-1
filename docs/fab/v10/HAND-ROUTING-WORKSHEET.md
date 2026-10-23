# v10 HAND-ROUTING WORKSHEET — the three stubborn nets (2026-10-22)

**Purpose.** The router refuses `/EN`, `/SPI2_SCK` and `/F33_RESET_N` with plain *no-path*
failures, and five automated levers failed to add them. This worksheet gives you everything
needed to try ONE hop by hand in the KiCad GUI.

**Why this test matters.** If you can place even one of these on two layers, then **capacity is
not the limit** and the router's search is the problem — which means the fix is code, not
~2x fab cost. If you cannot either, that is real evidence for four layers.

**Read this first — what the measurement does and does not say.** The numbers below come from
`hand_route_test.py`, which walks a **STRAIGHT LINE** between the two pads and reports where it
is first blocked. A straight line can only *under*-report feasibility: a human detours and this
tool cannot. So a "blocked" result here is **not** proof that no route exists. It is a statement
that the direct corridor is occupied.

---

## Per-layer clearance before the first block (measured)

| net | pads | length | clear on F.Cu | clear on B.Cu |
|---|---|---|---|---|
| `/EN` | U1.3 → J_PROG.3 | 30.71 mm | **0.70 mm** | 3.85 mm |
| `/SPI2_SCK` | U1.4 → U2.12 | 23.76 mm | **0.85 mm** | 14.16 mm |
| `/F33_RESET_N` | U1.18 → U2.17 | 21.20 mm | **0.95 mm** | 7.65 mm |

**The pattern that matters: on F.Cu all three die within 1 mm of the pad.** That is the pin
field — U1 is a 1.27 mm-pitch module and each pad is fenced by its neighbours. So the first
thing to solve is not the long run, it is **getting out of the pin row**.

`/SPI2_SCK` is the best candidate: **14.16 mm of clear B.Cu** before anything is in the way,
out of 23.76 mm total. It almost completes on the back layer.

---

## HOP 1 — recommendation: `/SPI2_SCK` (U1.4 → U2.12)

Why this one first: most clear B.Cu (14.16 mm), and its destination U2.12 is nearby, so the
detour only has to solve the **last ~9.5 mm**.

### Coordinates (mm, board origin top-left; board is 72.10 x 80.10)

| item | ref.pad | centre (x, y) | side |
|---|---|---|---|
| start | **U1.4** | (11.05, 37.70) | F.Cu only |
| end | **U2.12** | (33.73, 30.60) | F.Cu only |

Both pads are **F.Cu only** (SMD). Any B.Cu run therefore needs **a via near each end** — and
that is the crux, because a via needs 0.50 mm diameter with 0.200 mm clearance to neighbouring
pad copper.

### What blocks it, and where

```
F.Cu  blocked at 0.85 mm out   by track /SPI2_MISO
B.Cu  blocked at 14.16 mm out  by track /U3_CS_N
```

- The **F.Cu** block is `/SPI2_MISO` immediately beside the pad — so F.Cu is not usable for the
  escape.
- The **B.Cu** run is clear for 14.16 mm. Then `/U3_CS_N` crosses. `/U3_CS_N` is *itself* a
  routed net, so in the GUI you can see exactly where it runs and judge whether hopping over it
  (another via pair) or stepping around it is possible.

### What to try, concretely

1. Open `tracker/hardware/hub_board_v10.kicad_pcb` in KiCad.
2. Zoom to **U1.4** at (11.05, 37.70).
3. Try to place a **via** beside U1.4 and route on **B.Cu**. This is the expected sticking point:
   U1.4's neighbours U1.3 and U1.5 are **0.67 mm** away edge-to-edge (pad 1.50 x 0.90 mm at
   1.27 mm pitch), and a 0.50 mm via needs 0.200 mm clearance, so the geometry is tight but the
   earlier pad-widening experiment showed a via *does* fit once the gap is 0.67 mm.
   **Watch this**: if KiCad refuses the via here, note the exact message — that is a result.
4. If the via lands, route B.Cu east toward (33.73, 30.60).
5. At the far end you need a second via beside **U2.12** to come back to F.Cu.
6. **Do not save over the file.** Save As `hub_board_v10_handtest.kicad_pcb` and tell me — I will
   run the full gate battery plus kicad-cli DRC on it and report whether it is clean.

### What I need from you

- Did the **first via beside U1.4** place? (yes / no + the message if no)
- Did the route reach the far end? (yes / no + how far)
- A screenshot at whatever point it stopped is ideal.

---

## HOP 2 — `/EN` (U1.3 → J_PROG.3), 30.71 mm — hardest

| item | ref.pad | centre (x, y) | side |
|---|---|---|---|
| start | **U1.3** | (11.05, 36.43) | F.Cu only |
| end | **J_PROG.3** | (31.00, 59.78) | **both layers** |

```
F.Cu  blocked at 0.70 mm out  by PAD U1.4  (its OWN NEIGHBOUR — not a track)
B.Cu  blocked at 3.85 mm out  by track /GNSS_TX
```

**The F.Cu block is a neighbouring pad, which is why reordering never helped**: no ordering
change creates space between U1.3 and U1.4.

Good news: **J_PROG.3 is on both layers**, so only the **start** end needs a via.

## HOP 3 — `/F33_RESET_N` (U1.18 → U2.17), 21.20 mm

| item | ref.pad | centre (x, y) | side |
|---|---|---|---|
| start | **U1.18** | (16.62, 51.65) | F.Cu only |
| end | **U2.17** | (14.08, 30.60) | F.Cu only |

```
F.Cu  blocked at 0.95 mm out  by track /GNSS_PPS
B.Cu  blocked at 7.65 mm out  by track /GNSS_RX
```

Shortest of the three and both ends are F.Cu, so two vias needed. Second-best candidate.

---

## Reference — what is ALREADY routed, so you can see what is in the way

26 nets routed, 753 tracks, 22 vias. The blocker nets you will meet:

- `/SPI2_MISO`, `/SPI2_MOSI` — the SPI2 pair, routed in the U1/U2 region
- `/GNSS_TX`, `/GNSS_RX`, `/GNSS_PPS` — the GNSS group
- `/U3_CS_N` — the LoRa2021 control link

These are all **signal nets, not planes**, so none is immovable in principle. If you find that
moving one of them by a few millimetres frees a corridor, that is a legitimate hand fix and a
**router finding** (the search cannot do rip-up).

## If it goes badly

Stop and report, do not force it. A failed hand attempt with a screenshot is a valid and useful
result: combined with the five failed automated levers it would be the honest basis for four
layers. **No fab order either way without the operator's word.**

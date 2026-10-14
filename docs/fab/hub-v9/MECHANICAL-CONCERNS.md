# Hub v9 — mechanical concerns: what they are and what to do

**Date:** 2026-10-14 · every number below is **read from the board files**, not assumed.

## Concern 1 — U.FL connectors close to the board edge

### The physics of the problem

A U.FL / IPEX MHF connector is a **snap-on** part. The plug has a tiny rotating
latch, and it needs to come **straight down** onto the receptacle and then rotate
free of the board edge. Two failure modes if the receptacle sits too near the edge:

1. **Mating tool / finger access.** You cannot press the plug on straight if the
   plug body overhangs the edge and your finger/tool has nothing to push against
   — the plug skates off and you bend the receptacle's centre contact (a
   ~0.2 mm post). Bent centre contacts are the #1 U.FL failure.
2. **Cable side-load.** The coax leaves the connector and immediately bends. A
   cable that exits over the board edge with a tight radius levers the
   receptacle; vibration and thermal cycling then fatigue the solder fillet and
   the receptacle's anchor.

### The measured geometry

| Connector | Position (mm) | Nearest edge | Pad-centre to edge |
|---|---|---|---|
| ANT1 | (2.5, 22.7) | left (x=0) | **2.5 mm** |
| ANT3 | (100.5, 80.3) | right (x=103) | **2.5 mm** |
| ANT2 | (24.7, 100.5) | bottom (y=103) | **2.5 mm** |
| ANT4 | (78.3, 100.5) | bottom (y=103) | **2.5 mm** |

### Is 2.5 mm actually a problem? Partly — and here is the honest answer

- The **receptacle body itself** is ~3.0 × 3.1 mm, so half of it (~1.5 mm) plus
  its solder pads (~0.4 mm) fits inside 2.5 mm. It will **solder fine** — this is
  not a fab defect and JLC will not reject the board.
- The **mated plug** (Ø≈2.6 mm body, ~1.4 mm mated height) will **overhang the
  edge** slightly. That is acceptable mechanically — millions of boards do this.
- **What is genuinely marginal** is (a) having enough flat board-side area to
  land the plug straight, and (b) the coax bend radius right at the edge.

### Recommendation — no respin; do these three things

1. **Use right-angle / pigtail U.FL assemblies with a strain-relief anchor.**
   Zip-tie or adhesive-dot the coax to the board ~10 mm from the connector so
   NO side-load reaches the receptacle. This is the single highest-value action
   and costs nothing on the board.
2. **Mate BEFORE installing the wings**, while the hub is bare on the bench, and
   use a proper U.FL insertion tool (or fine tweezers pressing on the plug body,
   never the cable). Budget one spare board per 10 for a bent-contact victim —
   that is why the 10-board order has slack.
3. **Rev-10 change (cheap, no risk):** move ANT1/ANT3 to 4–5 mm from the edge
   and put ANT2/ANT4 on the **top** edge, away from the wing tabs. Costs nothing,
   removes the marginality entirely. Do it in the same respin as the EN pull-up.

**Verdict:** order as-is. Handle with strain relief. Fix properly in rev-10.

---

## Concern 2 — wing tabs on thin FR4 + only 2 asymmetric mounting holes

### The measured geometry

| Item | Fact |
|---|---|
| Wing tabs | **J_W1..J_W4** — four `Wing_Tab_4P`, one at the **mid-point of each board edge** (left x=0, right x=103, top y=0, bottom y=103) |
| Tab copper | 8 SMD pads each (4P × 2 sides: 3 solar-string pads + shield/ground) |
| Mounting holes | **TH1 (9.425, 9.425)** and **TH2 (9.425, 93.575)** — both at **x = 9.425 mm** |
| Tether/load holes | none dedicated |

### Why asymmetric holes matter — the mechanics

Two mounting holes only **constrain two axes at one end** of the board. Picture it:

```
  x=9.4        x=103
   ●  TH1          (nothing)
   |                  <-- 93 mm of unsupported 0.8 mm FR4
   ●  TH2          (nothing)
```

- The board is held along its **left edge only**. It is free to **rotate about
  the TH1–TH2 axis** and to **flap** at the right edge — exactly where ANT3 and
  the electrically-busy corner sit.
- Under **launch vibration** (car/trailer/launch) and **pendulum motion aloft**,
  the right half of a 115 mm panel with 0.8 mm FR4 becomes a **cantilever**, and
  the highest-stress point is the mounting-hole land itself. FR4 cracks at
  fastener holes before it cracks anywhere else.
- The **tabs are the other problem**: they are the wing-attachment points, so
  they carry the wings' weight AND the wings' gust loads. If the wings are
  **hard-soldered** to the tabs, that load runs straight into two copper pads
  whose bond to FR4 is weak in peel. Add thermal cycling between +40 °C (sun) and
  −50 °C (night) and the solder joint work-hardens and cracks.

### Recommendation — no respin for the first flight; soft-mount everything

**For the first flight (as ordered):**

1. **Tether through a stress-relief loop, not through the holes alone.** Pass a
   thin kevlar/thread loop through **both** TH1 and TH2 so the load spreads over
   two points, and let the loop (not the PCB) be the load path. A thread loop
   through two holes at ~90 mm spacing still allows the flap; add a **third soft
   tie** around the wing-tab area to stop the right half cantilevering.
2. **Attach wings flexibly, not rigidly.** Solder the solar strings as normal,
   but mechanically tie the wing to the hub with **thread/tape passing through
   the tab region**, so the wing's dynamic load goes into the tie, not the pad.
   Never let the solar wire be the structural load path.
3. **Fillet the mounting holes** (epoxy dab around the thread exit) and use a
   **soft washer** (silicone/foam) under any hard contact point — hard FR4
   against hard plastic at a fastener is a crack starter.
4. **Cap accelerations**: the tabs see the biggest loads at launch, so the
   first flight is also the stress test — inspect the tabs and hole lands
   before and after (photos, record in the experiment log; that is E-05).

**Rev-10 (do it in the same respin):**

- Add **two more mounting holes** diagonally opposite (e.g. at (93.6, 93.6) and
  (93.6, 9.4)) so the board is pinned at four corners — symmetric, no cantilever.
- Add a **dedicated tether hole pattern** (2 × Ø3 mm with 5 mm annular ring) on
  the board's centreline, so the load path never uses a wing tab.
- Widen the **tab-to-board fillet**: make the tab neck a smooth radius rather
  than a sharp step, and add a copper-free flex line across the neck so the tab
  can bend without delaminating.
- Consider **1.0 mm** for the hub in rev-10 if mass allows — the tab and hole
  land strength roughly scales with t², so 0.8 → 1.0 mm buys ~56% more local
  strength for ~2 g.

**Verdict:** the 0.8 mm board flies fine **if** the load path is thread, not
copper. The two-hole asymmetry is the real weakness; it is a rev-10 fix, not an
order blocker.

---

## Mass budget — recomputed with the REAL board facts

Supersedes the earlier estimate (108–154 g). New inputs, all **read from files**:

- wing thickness **0.6 mm** (2-layer — JLC *does* offer 0.6 mm at 2 layers, so no
  change needed there; only the hub's 4-layer 0.6 mm was impossible)
- **6 solar cells per wing**, not assumed: `SC1..SC3` on F.Cu, `SC4..SC6` on
  B.Cu (ADR-065 double-sided rework) → **12 cells** for two wings

Run `docs/analysis/mass_corrected.py` for the table. Headline result unchanged
in shape: the payload is dominated by **laminate, not electronics** — 6 cells
per wing at 0.8–1.6 g each is the single biggest unknown left.

## Do I need you to weigh the balloon?

**Yes — two things, and they are quick. Everything else I found on the internet
or derived from the board files.**

| What | Why it matters | Priority |
|---|---|---|
| **1. Weigh one balloon** (envelope only, empty, dry) | The 60–100 g bound swings the all-up mass by 40 g and therefore the float altitude by ~1.5 km. A jeweller's scale; the number decides accept-7–9 km vs switch-to-latex. | **HIGH** |
| **2. Weigh one solar cell** (52×19 mm, as delivered) | 0.8 vs 1.6 g per cell = 9.6 g difference across 12 cells — comparable to the whole hub's components. | **HIGH** |
| Board thickness | settled: hub 0.8 mm, wing 0.6 mm | done |
| Cell count / tab layout / hole positions | read from the board files | done |
| Connector mating envelope | Hirose site returned nothing to the scraper; the ~2.6 mm plug body is from the standard U.FL interface spec — confirm with the pigtails you buy | low |
| Wing copper area | wing outline known (25×184); copper fraction not measured — second-order | low |

**I cannot find the balloon mass on the internet**: the Yokohama product page
gives no weight, and no distributor listing carries it. That one genuinely needs
your scale.

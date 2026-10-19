# FAB REVIEW DISCLOSURE — hub v9, state as of 2026-10-18

**Purpose:** this board is **fit to SHOW a fabricator for review. It is NOT orderable.** This document
says exactly what is wrong, what has been measured, and what must change before an order is placed.

**Consultant:** `gpt-6-astra` (served id recorded). Its ruling on this question:
*"Submit the current design as NOT ORDERABLE, with the island measurements, single-via connection,
current DRC report, and proposed In1 reroute explicitly identified. These are useful review inputs…
an honest review can—and often should—happen first."*

---

## 1. Status: NOT ORDERABLE

| gate | result |
|---|---|
| netlist integrity | **PASS** — 14 pass / 0 FAIL / 2 WAIVED, fail-closed |
| ERC | **19 errors / 36 warnings — WAIVED with a printed waiver** (`docs/fab/ERC-DISPOSITION.md`) |
| DRC | **168 violations, 4 unconnected items** |
| fab grade | **NOT ORDERABLE** (exit 1, verdict-driven) |

**The two signal defects that were the original blocker are now diagnosed to the millimetre** — see §3.

---

## 2. 🔴 The most important finding: the In1.Cu reference plane is split

**This outranks everything else in this document.** Astra: *"It compromises the designated reference
layer beside an RF module… I rank this above the five F.Cu fragments."*

```
In1.Cu island 0:  4021.364 mm²   centroid (37.81, 29.15)   ← MAIN reference plane
In1.Cu island 1:    29.206 mm²   bbox x 32.70..36.70  y 40.09..50.10
gap between them:   0.572 mm     from (36.549, 40.087) to (36.558, 39.515)
```

**The island's ONLY connection to GND is one via:**

```
GND connection points inside the 29.2 mm² island: 2, and they are the SAME POINT
   via at (33.81, 42.995)
   pad U3.18 at (33.81, 42.995)      ← U3 = LoRa2021_Castellated, the 433 MHz radio
GND tracks on In1.Cu touching that island: 0
```

**So 29.2 mm² of the reference plane feeds through a single 0.60/0.30 mm via at one pad.** Astra's
scale for why that matters: **1 nH ≈ 2.7 Ω at 433 MHz and 15 Ω at 2.4 GHz** — illustrative, not an
extraction of this via, but it is the reason "DC-connected" is not the same as "adequate reference".

**What blocks the merge — BOTH must move, not one:**

```
In1.Cu track  +3V3           at +0.353 mm from the gap midpoint
In1.Cu track  /CUT_SENSE_W4  at +0.347 mm
```

Astra: *"Moving only one could leave the clearance barrier intact… Aim for a broad copper connection,
not merely a barely legal neck."*

**This is NOT required to make DRC green. It is required for the board to be electrically sound.**

---

## 3. The two signal nets — diagnosed, with the escape geometry proven

Both were unrouted at the start of this work. Their escape constraints are now measured to the
millimetre and confirmed by DRC:

```
MOSI:  exactly ONE legal via site exists on all four layers:
       (55.850, 25.250), dx = +0.700 from the pad edge
       0.50 mm dia / 0.25 mm drill  ==  m_ViasMinSize, so NO rule waiver is needed
       worst clearance 0.211 mm to U4.16
       then route on B.Cu to U1.8 — 16 segments, DRC-legal in run 6

SCK:   escapes U4.18 on F.Cu at y = 24.700
       NOTE: y = 24.700 is INSIDE that pad's own y-span (24.600..24.900).
       A 0.200 mm track may offset within the pad's own height and slide out sideways.
       This is why a centreline-only analysis wrongly concluded U4.18 was blocked.

MISO:  its long run is already on B.Cu; only a 1.5 mm F.Cu stub needs restoring.
       Routable at a 0.025 mm grid. A 0.100 mm grid cannot see it: the corridor between
       U4's thermal pad edge (54.100) and the pad column edge (54.750) leaves only
       0.650 - 0.200 - 2x0.200 = 0.050 mm usable, and grid phase decides whether a cell lands in it.

CONSTRAINT THAT BROKE SEVEN ATTEMPTS: two 0.60 mm vias need 0.800 mm centre-to-centre.
       One candidate pair came out 0.155 mm apart. Check this explicitly, by eye it is invisible.
```

**Why the automated router was abandoned** after seven runs: sequential A* has no backtracking, so the
first net routed wins the contested cells and the loser reports `no path`. Changing the order only
changes *which* net fails. **The fix is one GUI session, not another router iteration.**

---

## 4. F.Cu pour fragments — real, but secondary

```
F.Cu GND: 6 islands
  3543.334 mm²  ← main plane = 70.3 % of the 70.2 × 71.7 mm board footprint
    15.734 mm²  orphan, centroid (51.07, 26.64)
     8.615 mm²  orphan, centroid (53.70, 31.23)
     1.428 mm²  orphan, centroid (53.35, 29.84)
     0.445 mm²  sliver
     0.278 mm²  sliver, centroid (55.21, 27.26)
```

**A corrected metric, recorded so it is not repeated:** earlier in this work the board was described
as "15.9 % copper-utilised". **That figure was wrong for this question** — it is total routed copper
*length* divided by total copper *area*, i.e. a **routing-density metric** (how much of the board's
copper budget is spent on tracks), and it says nothing about plane coverage. The correct figure for
pour coverage is **main-plane area ÷ board footprint = 3543.3 / 5040 = 70.3 %**. The error came from
using a routing metric to reason about plane continuity; the consultant (`gpt-6-astra`) caught it:
*"your utilization numbers use different denominators… it should not drive this decision."*

Orphans total **26.5 mm² = 0.74 % of the plane = 0.53 % of the board footprint.** Each is cut off from
the main plane by exactly one non-GND feature:

| orphan | blocker |
|---|---|
| 15.734 mm² | `/SX1280_XTB` track |
| 8.615 mm² | `/SX1280_VBAT_IO` track |
| 1.428 mm² | `U4.11` pad (`/SX1280_VBAT_IO`) |
| 0.445 mm² | `U_HUB_CVT.1` pad (`/HUB_PV_P`) |
| 0.278 mm² | `/SX1280_VDD` track |

**Astra's caution on the biggest one:** *"The `/SX1280_XTB` blocker deserves particular restraint:
rerouting a crystal-related net… can alter parasitic capacitance and coupling. Do not perturb it solely
to improve a polygon count."*

**Two remedies were tried and REFUTED (numbers in `docs/fab/DECISIONS-UNROUTED-NETS.md` D11):**
- **stitching vias** — island count 6 before, 6 after; DRC unconnected 4 → 4. A via is vertical; the
  DRC item is same-layer continuity. Wrong tool.
- **stale fill** — a full refill reproduces the identical 6 islands and areas. Island removal mode is
  `ALWAYS`, but each fragment *is* tied down to `In1.Cu`, so KiCad correctly keeps them. **Fill is not
  stale** (RALPH rule 1 applied and cleared it).

---

## 5. What this document CANNOT establish

- **RF performance.** Astra: *"Do not claim RF performance has been validated unless it has been
  tested or otherwise substantiated."* No S-parameters, no VNA, no anechoic data exist.
- **Whether the `In1.Cu` split actually costs measurable range.** The mechanism is established; the
  magnitude is not.
- **Which specific F.Cu fragment produces which DRC item.** Astra: *"Five fragments and two errors do
  not provide a one-to-one mapping."* The two DRC items are zone-level and are **not** individually
  attributed.
- **Impedance, copper thickness, finish** — these need tooling, not vision.

---

## 6. Minimum change set before ORDERING (execution order, per Astra)

1. **Capture the DRC report including every unconnected endpoint.** Do not assume the F.Cu fragments
   account for them.
2. **Restore In1.Cu GND continuity at ≈ (36.55, 39.80)** — reroute the local `+3V3` **and**
   `/CUT_SENSE_W4` In1 segments away from the intended GND bridge. Refill. **Acceptance:** the former
   29.206 mm² island is part of the main polygon through a *useful-width* connection.
3. **Route MOSI and SCK** (GUI session) using the proven numbers in §3.
4. **Resolve the F.Cu orphans by function** — delete genuinely unused copper; connect needed copper via
   a same-layer bridge or GND vias; **if a pad depends on a fragment, connect the pad, do not just
   delete the fragment.**
5. **Refill all zones, rerun full DRC with the fab rule set.** Verify **zero** violations and **zero**
   unconnected items — not exclusions, not suppressed checks, not a stale report.

**Step 2 is the electrical repair. It is not required merely to make DRC green, and doing it does not
by itself make DRC clean.**

---

## 7. What IS ready for a reviewer right now

- **Complete fab package** — 59/59 footprints (verified; the previous package had 39, missing the whole
  SX1280 RF match/filter).
- **Schematics, netlist, ERC with printed waiver** — 14 pass / 0 FAIL / 2 WAIVED fail-closed.
- **Escape analysis** to the millimetre for all four unrouted pads, DRC-confirmed.
- **Edge-launch cross-section drawing** — 3 mechanical defects fixed; **2 out-of-scope items moved into
  the JLCPCB query** (slot-face copper construction; mating-fit spec).
- **This disclosure** — every defect named with a number, including the one that outranks the rest.

**No order has been placed, and none should be until §6 is complete.**

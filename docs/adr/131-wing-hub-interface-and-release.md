# ADR-131 — Wing↔hub interface redesigned for a FOAM wing: the 4-pin row stays, the insertion feature changes, and the release is designed with it

> Numbered **131** on 2026-10-25. Verified free with the repo's own allocator:
> `python3 scripts/adr_next_number.py --number 131` → `131` (exit 0);
> `--path docs/adr/131-wing-hub-interface-and-release.md` → `131` (exit 0); and
> `git log --all --name-only --pretty=format: -- 'docs/adr/131*'` returns nothing.
> (`grep -c` exits 1 on zero matches — that is the empty result, not a failure.)

- **Status:** **Proposed** — design direction is worker-derivable; the operator
  corrects pass 2 (AGENTS.md §"STANDING AUTHORITY").
- **Date:** 2026-10-25
- **Author:** balloon-hermes (manager CW), branch `feat/foam-wing-3d`.
- **Closes:** ADR-130 **D5** (the interface re-opened by the foam airframe) — **to the
  extent it can be closed without the two blocking measurements.**
- **Amends:** ADR-046 §2.2/§4 (tab + slot) and `WING-TO-HUB-SOCKET-SPEC.md` §2.1
  (the milled slot) for the **foam** variant.
- **Reads with:** ADR-117 (foam airframe), ADR-052 (end-only mount), ADR-054 §2.2
  (hub-side bypass), ADR-051 §2.5.1 (latched one-shot cut), ADR-129 D5 (`U_CUT1–4`),
  `docs/HANDOVER-WING-RELEASE-AND-BYPASS-DIODE.md` §3/§4,
  `docs/analysis/wing-release-electrical-contacts.md` §3 option 4.
- **No hardware ordered, no board edited, no BOM changed.** Design work only.

---

## 0. The decision, in one paragraph

**Keep the 4-pin electrical interface exactly as it is; change what provides the
mechanical normal force, because a foam wing cannot supply a rigid tab.** The
`SOLAR_P / GND / RF_FEED / SOLAR_N` land row, its 4.0 × 1.2 mm size, its 1.8 mm
pitch, its order and its 6.0 mm insertion depth are **retained unchanged** — the hub
is routed against them and `wing-jettison.md` §0 finding 3 forbids replacing them
with flying leads. What changes: the wing side of the joint is a **carried insert**
(a small rigid strip bonded into the foam, or a separate thin carrier) that presents
the tab, because **0.21 mm cells and 3 mm foam cannot be inserted into a 0.9 mm slot
and soldered reliably**. The **keeper + slip-fit release is designed in the same
record**, because ADR-117 consequence §1 and ADR-130 D5 require them to be one
problem.

---

## 1. Why the interface re-opens — the two things a foam wing cannot do

ADR-046 §2.2 and `WING-TO-HUB-SOCKET-SPEC.md` §2.1 assume the wing is a **0.6 mm
FR4 board** that:
1. **can be milled into a 9.0 mm-wide tab** with 4 lands at 1.8 mm pitch, and
2. **can be inserted into a 0.9 mm × 6.0 mm slot** and soldered, using the board's
   own stiffness to carry both the shear and the electrical lands.

**A foam wing can do neither.** A 3 mm sheet with cells end-mounted has no rigid
tab, and foam does not hold a solder land. So the *electrical* geometry survives and
the *mechanical* provider must change. This is the whole of D5.

**Also recorded here (already a known defect, not new):** ADR-049 clause 4 says
**ADR-046's 0.9 mm hub slot is below JLCPCB's 1.0 mm minimum non-plated slot**, and
its worst-case clearance against a 0.6 mm tab is **0.00 mm**. Any slot-based design
must fix the slot to **≥ 1.0 mm or drop it for plain pads** — this is a **hub-side
blocker** and is inherited, not created, by this record.

---

## 2. Decision

### D1 — The 4-pin electrical interface is RETAINED unchanged

| Parameter | Value | Source |
|---|---|---|
| Lands per interface | 4 per face (**8** total) | ADR-046 §2.2 / socket spec §2 |
| Land size | **4.0 × 1.2 mm** | same |
| Land pitch | **1.8 mm** | same |
| Land order 1→4 | `W<n>_SOLAR_P`, `GND`, `W<n>_RF` (no net on v9), `W<n>_SOLAR_N` | socket spec §3 |
| Insertion depth | **6.0 mm** | socket spec §2.1 |
| Tab width | **9.0 mm** | ADR-046 §2.1 (wins over the spec's 8 mm, ADR-048 §3 D-2) |
| Component keep-out | no body/courtyard within **1.5 mm** of the land row, either face | socket spec |
| Copper-to-edge | **≥ 0.5 mm** to the hub perimeter | socket spec §2 |

**Rationale:** the hub is routed against these; changing them is a hub respin for no
gain. `wing-jettison.md` §0 finding 3 explicitly forbids replacing the row with
flying leads. **The row is the invariant of this redesign.**

### D2 — The wing presents the tab via a CARRIED INSERT, not the foam itself

The foam sheet cannot be the tab. The joint is carried by a **rigid insert**:

- **Option I-a — bonded strip (recommended).** A thin strip (FR4 or a rigid
  plastic) milled to the 9.0 mm tab with the 4 lands, **bonded into the foam's root
  edge**. The foam body is the arm; the strip is the joint. Local, small, and it
  keeps the batting surface identical to the current socket.
- **Option I-b — separate carrier plate.** A small rigid plate carrying both the tab
  and the cell-end lands, epoxied to the foam root. Rejected as the *first* choice
  because it adds a part ADR-117 removed.

**Either way the cells remain END-MOUNTED (ADR-052)** — the insert carries the
*joint*, never a cell face. **Bonding a cell face is forbidden** (ADR-052 §2.1) and
the insert must not become an accidental substrate.

> **`TODO(unverified)`:** the insert's bond to foam under thermal cycling: foam CTE
> 80e-6/K vs FR4 12–18e-6/K (`foam_airframe_selection.py` §6). The insert is small,
> so the differential strain is bounded by its own length rather than the arm's —
> **but the bond length is a design number this record does not freeze.**

### D3 — The slot is FIXED to ≥ 1.0 mm or replaced by plain pads

Inherited from ADR-049 clause 4 (JLCPCB minimum 1.0 mm). **The slot cannot stay at
0.9 mm.** Two acceptable resolutions, the operator's call at layout time:
- widen to **≥ 1.0 mm** with a stated supplier tolerance, **or**
- drop the slot and use **plain pads on both faces** (socket spec §2.2 Option B),
  with alignment by a fixture.

**This record does not pick between them** — it picks the *bound*: **no 0.9 mm slot
may be ordered.**

### D4 — The release is designed WITH the interface, not after it

The electrical path is a **slip-fit held closed by a mechanical keeper**; releasing
the keeper parts the contacts passively and **no copper is ever cut**
(`wing-release-electrical-contacts.md` §3 option 4). Decisions, with their
constraints, carried from the handover §4.2 **and given the foam-specific values
this record adds**:

| # | Decision | Constraint | Foam-specific value added here |
|---|---|---|---|
| 1 | Contact geometry | must fit the retained 4.0×1.2 mm row at 1.8 mm pitch, 6.0 mm insertion, 9.0 mm tab | **the insert of D2 provides it**, not the foam |
| 2 | Normal force | ≥ ascent vibration + **10 g burst shock** margin | **mass is now measured, not estimated**: see §3 |
| 3 | Contact resistance spec | **not in the repo**; at 400 mA a 100 mΩ contact costs **16 mW** vs the 100 µW night budget | unchanged — still `TODO(unverified)` |
| 4 | Keeper retention | release force > slip-fit opening force + margin | scales with the same mass as #2 |
| 5 | Keeper actuation | nichrome on nylon is the only in-repo precedent (**~0.5 g/channel, 2.59 J/cut**); `U_CUT1–4` already exist | **the actuator channel exists; the 3-pin `U_CUT` symbol must grow first** (handover blocker #4) |
| 6 | Where the bypass lives | **HUB side** (ADR-054 §2.2) — must not leave with the wing | unchanged and now more important: the foam wing carries no diode at all |
| 7 | Release verification | `wing-jettison.md` failure mode #2 is *"partially cut loop"* with **no telemetry** | **the slip-fit's new best feature** — a continuity sense across the keeper is available and should be specified |

### D5 — Arming is DESCENT-ONLY, and the cut is a LATCHED ONE-SHOT

Per ADR-051 §2.5.1: cutting is irreversible, so the driver **must** be latched. A
level-sensitive driver can re-fire on reset/brown-out/retry, each fire costing
**~2.59 J of the bank's 16.63 J**. Firmware must **serialise cuts** — 4 simultaneous
fires = **9.9 A = 2.4× the IRLML2502 class rating**. Premature fire is
`wing-jettison.md` failure mode #1, **severity 5**.

---

## 3. The foam change moves the numbers the release is sized against

This is the reason the interface and the release are one record. The whole force
window scales with **wing mass**, and ADR-117 + ADR-130 changed the mass from an
estimate to a **measured arithmet**ic:

| wing build | mass/wing | 10 g shock | ×1.5 design lower bound |
|---|---:|---:|---:|
| *estimate used by `wing-jettison.md` §7 (FR4 spine+ribs)* | *3.20 g* | *314 mN* | **471 mN** |
| **EPS 3 mm, single-sided (ADR-130)** | **5.249 g** | **515 mN** | **772 mN** |
| **XPS 3 mm, single-sided (ADR-117 pick)** | **5.988 g** | **587 mN** | **881 mN** |
| XPS 6 mm, single-sided | 7.381 g | 724 mN | 1086 mN |
| EPS 3 mm, double-sided (ADR-065) | 9.845 g | 966 mN | 1449 mN |

**The keeper's release-force requirement rises ~64–87 % versus the estimate the
current handover assumes** (471 mN → 772–881 mN), because the foam+cell wing is
heavier than the FR4 spine it replaced *as a complete assembly* (the carrier got 24×
lighter but the mass was never carrier-dominated). **A keeper sized to 471 mN is
undersized for the build ADR-117 selected.** This is the single most actionable
finding of this record.

**Double-siding makes it worse** (~1449 mN) and simultaneously eats most of the
payload (§ ADR-130), so **a double-sided cutter flight is the worst case for both**.

---

## 4. What blocks the layout — the two measurements, unchanged

Both are `TODO(unverified)` and **must be measured before any layout**, per handover
§4.3. This record does not invent them:

1. **Slip-fit pull-out force window.** Lower bound = ascent vibration + 10 g shock
   (must not open in flight); upper bound = the keeper actuator must be able to open
   it. **§3 now supplies the lower bound from measured mass (772–881 mN for the
   single-sided builds); the upper bound is still unmeasured.**
2. **Contact resistance** of the chosen slip-fit at 400 mA, cold (−55 °C). Not in the
   repo; circular until a connector class is chosen (MEASUREMENT-REQUEST §0 splits it
   into C1 class / C2 measured part).

**Bench plan** (handover §4.3, still valid): pull rig + spring scale for (1);
4-wire measurement at 400 mA in a freezer for (2). Cheap, no flight needed.

---

## 5. What this record does NOT do

- **No layout, no board edit, no schematic change.** The hub keeps its routed lands.
- **No connector part selected.** D4 item 3 remains circular until a class is chosen.
- **No slot resolution chosen** beyond the bound (≥ 1.0 mm or plain pads, D3).
- **No bond length frozen** for the D2 insert.
- **No order, no BOM, no fab authorisation.**
- **It does not re-derive** the bypass diode (ADR-054) or the cut topology (ADR-129).

## 6. For future sessions

- **The invariant is the 4-pin row.** Change it only with a hub respin, and only if
  the operator asks. Everything else here is negotiable.
- **Size the keeper to the MEASURED wing mass**, not to the retired 3.2 g estimate:
  **772–881 mN** for the ADR-117 single-sided builds (§3).
- **The 0.9 mm slot may not be ordered** (D3) — inherited JLCPCB limit.
- **Release verification is the win available** (D4 item 7): a continuity sense across
  the keeper removes `wing-jettison.md` failure mode #2's blindness. Specify it.
- **Next: the two measurements (§4)**, then the insert bond length (D2), then layout.

---

*Proposed. Design only. No order, no board, no BOM, no fab authorisation.*

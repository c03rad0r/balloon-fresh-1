# Wing interfaces — ROOT CAUSE: the rotations are 180° inconsistent, and a 2026-10-14 offset masked it

**Board:** `tracker/hardware/hub_board_v9.kicad_pcb`, sha256 `e55a294628fd38a73e5006fa7fa91389…`
**Reproduce:** `~/venvs/kicad/bin/python tracker/hardware/verify_wing_interfaces.py`
**Rule under test:** `build_hub_board_v9.py` → `EDGE_SEATS` + `apply_floorplan()` + `wing_socket_inboard_offset()`

## The measurement

```
tab    edge    rot     origin            slot union (absolute mm)        slot vs edge
J_W1   west      0.0   ( 5.20, 35.00)    x  5.17 … 11.22   y 34.52…35.48  WHOLLY INSIDE, 5.25 mm
J_W2   north   270.0   (35.00, 64.80)    x 34.52 … 35.48   y 64.78…70.83  crosses bottom, +0.75 mm
J_W3   east    180.0   (64.80, 35.00)    x 58.77 … 64.83   y 34.52…35.48  WHOLLY INSIDE, 5.25 mm
J_W4   south    90.0   (35.00,  5.20)    x 34.52 … 35.48   y -0.82… 5.22  crosses top,    +0.75 mm
```

**All four footprints have IDENTICAL local geometry** (slot local `x ∈ [-0.03, +6.02]`, width 0.96 mm;
lands at local `x = +3.0`) **and the SAME 5.20 mm origin offset.** The only thing that differs is the
rotation — and the rotation sends the slot in **opposite directions**:

```
J_W1 west   rot   0   local +x → absolute +x   slot goes INBOARD  → buried
J_W3 east   rot 180   local +x → absolute -x   slot goes INBOARD  → buried
J_W4 south  rot  90   local +x → absolute -y   slot goes OUTBOARD → crosses the edge
J_W2 north  rot 270   local +x → absolute +y   slot goes OUTBOARD → crosses the edge
```

**So the rotation set is 180° inconsistent between the {west,east} pair and the {north,south} pair.**
`ADR-048 §2.2` requires *"Identical geometry, differing only in assembly tilt | yes"*. It is not met.

**The pads, separately, ARE equivalent** — every tab's pad set is identical to `J_W4`'s after a 90°
multiple (`J_W1` 270°, `J_W2` 180°, `J_W3` 90°). The electrical interface is symmetric; the **milled slot**
is not.

## The 2026-10-14 "fix" treated the symptom, and that is why this survived

`build_hub_board_v9.py` carries a documented repair in `wing_socket_inboard_offset()`:

> *"MEASURED DEFECT this repairs (2026-10-14): `apply_floorplan` seated each J_W footprint with
> `offset=0.0` — 'the datum IS the interface edge'. […] **16 of 32 wing-socket pads landed OUTSIDE the board
> outline** — J_W2 pads at y = 63.0 on a 60 mm board and J_W4 pads at y = -3.0. […] **A router cannot route
> to a pad that is not on the board.**"*

**Why did the pads land outside? Because the rotations were ALREADY inconsistent.** With local `+x` pointing
**outboard** on the north and south edges, the lands (local `x = +3.0`) landed 3 mm *off* the board. On the
west and east edges, where `+x` pointed inboard, they did not.

**The repair added a 5.20 mm inboard offset for all four**, computed from pad reach + edge clearance:

```
land reach = |land local x| + land length/2 = 3.0 + 2.0 = 5.0 mm
edge clear = max pad-y extent              = 2.7 + 0.6 = 3.3 mm
+ 0.2 mm fab edge clearance                => 5.4 mm, rounded up
```

**That pulled every pad onto the board — and pushed the west/east slots 5.25 mm inboard.** The offset is a
**compensation for a rotation error**, applied uniformly, so it hides the error on two edges and creates a
new defect on the other two.

**This is why fixing one without the other cannot work:**
- **offset → 0** (the "datum is the edge" reading) puts the slot on the edge ✓ and the pads off the board ✗
- **offset = 5.2** (today) puts the pads on the board ✓ and the slots inboard ✗
- **rotations made consistent + offset re-derived** is the only combination that satisfies both.

## What the fix must therefore be

1. **Make the rotation set consistent** so all four slots sit on the **same side of the origin**, per the
   footprint's own stated datum convention (*"the intersection of the hub's INTERFACE (outer) edge with the
   SLOT CENTRE LINE, +x INBOARD"*). Concretely, the {north,south} rotations are the ones that send `+x`
   outboard and must be corrected — but **derive the correct set from the convention, do not just swap two
   numbers**, and state which edge inboard means for each.
2. **Then re-derive the inboard offset from the corrected rotations.** With `+x` inboard everywhere, the
   lands at local `x = +3.0` are automatically inboard, and the offset need only satisfy edge clearance —
   which should be a **small** number, not 5.4 mm. **Show the before/after for all four tabs.**
3. **The slot must reach the edge.** `ADR-048`/`WING-TO-HUB-SOCKET-SPEC` §2.1 require a **milled edge
   slot**; a slot wholly inside the board is not one. Assert this as a **check**: each `J_W*` slot's union
   bbox must intersect its own board edge within a stated tolerance.
4. **An ADR stating the rule**, because `ADR-048 §2.1` still records the outline as **22 × 22 mm** while the
   board is **70 × 70** (`ADR-068`). The placement rule was written for a board a third the size.
5. **A gate.** `verify_wing_interfaces.py` is the detector; make its edge-reach assertion an exit code so
   the four interfaces cannot silently diverge again. Nothing electrical sees this class of defect.

## Acceptance

- the corrected `EDGE_SEATS` rotations, **derived from the datum convention**, with the reasoning recorded
- the re-derived offset, with before/after slot geometry for all four tabs
- **all four slots reach their own edge** within a stated tolerance, asserted by a check
- an ADR (new or amended) for the slot-placement rule on a 70 × 70 outline
- `ADR-048 §2.1`'s stale `22 × 22 mm` corrected or marked superseded, with the correction recorded
- a freshly regenerated 3D render re-reviewed with `ask_astra.py`, no longer reporting the defect
- gates re-run: a footprint move changes clearance and routing, and the 16 `copper_edge_clearance`
  findings may change (moving the west/east slots to the edge ADDS edge-located copper, which is the
  intentional interface)

## Related

- `docs/fab/WING-INTERFACE-VERIFICATION.md` — the independent measurement
- `docs/boards/reviews/hub-v9-render-r1.md` — the render review that found it (commit `14e8e9410`)
- `docs/adr/048-v9-hub-wing-interfaces.md` §2.1, §2.2 · `docs/adr/068-hub-v9-outline-60x60.md`
- `docs/WING-TO-HUB-SOCKET-SPEC.md` §2.1 · `docs/fab/hub-v9/PEEL-COUPON.md`
- `tracker/hardware/verify_wing_interfaces.py` — the detector

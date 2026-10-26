# Hub v10 — ADR-136 options A/B, ADR-137 applied, antenna volumes

Status: **A applied · B BLOCKED by measured geometry · antenna volumes reserved (4 of 5 provisional)**
Board: `tracker/hardware/hub_board_v10.kicad_pcb` — **72.1 × 80.1 mm, 2 copper layers**
Date: 2026-10-25

---

## 1. What was actually done

| item | result | evidence |
|---|---|---|
| ADR-137 applied to the board | **90 RF segments removed, 121.9 mm of `ANT*` copper, 4 × U.FL (`ANT1..4`)** | `apply_adr137_remove_rf.py`, dry-run then `--write` |
| Orientation A (move `U_E28` up) | **applied: y 69.00 → 66.60 (+2.4 mm)** | `move_u_e28_up.py --write`, destination clear (0 foreign-net items) |
| Routing the radio nets | **still 0 routed of 9 attempted** | `route_v10_astar.py` on `SPI1_*`/`E28_*` |
| Antenna volumes | **5 reserved, 1 confirmed side, 4 provisional** | `reserve_antenna_volume.py` → `antenna-volumes.json` |
| DRC after all changes | **35 violations, all pre-existing classes; 0 shorts** | `kicad-cli pcb drc` |
| Unrouted | **104 → 98** | KiCad connectivity engine |

### DRC detail after the changes (35 total)

```
copper_edge_clearance  16   pre-existing (J_W2 wing-seat slot, B43 area)
lib_footprint_mismatch 11   pre-existing
lib_footprint_issues    8   pre-existing
```

**No new violation class was introduced.** Two transient regressions were created *and fixed* during
the work, both by the same cause: a stale zone fill.

- After deleting the RF copper: 6 × `isolated_copper` ("Zone GND_BCu") because a now-empty GND
  island floated. Fixed by refilling zones.
- After moving `U_E28`: 16 × `clearance` + 16 × `solder_mask_bridge` because the moved pads landed
  inside the `/VSCAP` pour with stale antipads. Fixed by refilling zones. **Lesson: any footprint
  move or net deletion invalidates the zone fill; refill before judging a DRC result.**

---

## 2. Option A — applied, and it did not unblock the radio link (measured)

The move was legal (destination clear), so it was applied. It did **not** help: routing 9 radio
nets afterwards still returned `routed 0, failed 9`.

That was predicted in ADR-136 §5 and is now confirmed by execution: A buys the vertical leg, not the
escape from U1's bottom pads.

---

## 3. Option B — BLOCKED, and the cause is arithmetic, not search

Option B ("re-assign the radio nets to U1's top/right pads") fails for three measured reasons.

### 3.1 The escape gap is physically too small for any legal track

Adjacent U1 pads are on a uniform **1.27 mm pitch** with **0.370 mm of copper-to-copper gap**,
on both the bottom row and the right column. Board rules are **0.2 mm clearance, 0.2 mm track**
(`hub_board_v10.kicad_pro`, Default net class).

A track squeezed between two pads needs:

```
0.2 (clearance) + 0.2 (track) + 0.2 (clearance) = 0.600 mm
available                                         0.370 mm
deficit                                           0.230 mm
```

**No track of any legal width can pass between adjacent U1 pads.** Escape must therefore go around
the module, not between pads — and "around" is what is saturated.

### 3.2 The side corridors are occupied

Measured occupancy, x 29.0–33.0 over y 52–58:

```
x=29.0  F.Cu CLEAR      B.Cu /USB_DN
x=29.5  F.Cu /I2C_SCL   B.Cu /USB_DN
x=30.0+ F.Cu /I2C_SCL   B.Cu /USB_DN   + J_PROG pads 1,2
```

There is a single 0.5 mm-wide clean F.Cu sliver at x≈29.0. A 0.2 mm track with 0.2 mm clearance
needs 0.6 mm. **The sliver is narrower than the track needs.**

### 3.3 The board is 2-LAYER — there is no inner plane to escape through

```
copper layers enabled: 2   ->  F.Cu, B.Cu
```

Every escape must happen on one of two layers, and both are occupied at every column between U1 and
the destinations. This is the structural reason a bigger expansion budget changed nothing
(ADR-136: 29 nets / 2 M expansions → 0 routed; 2 nets / 20 M → 0 routed).

### 3.4 Option B also breaks the pin plan

ADR-108 §R1 records, after the four free GPIOs were spent:

> "after R1 **no free ESP32-S3 GPIO remains** — every other pin is an assignment, a strap, an
> octal-PSRAM pin or the USB console."

And `-N8R8` (the fitted part) reserves **IO35/36/37 for octal PSRAM**, so pads 35/36/37 are not
spare IO. The board's U1 footprint carries **no pin-function data** (`GetPinFunction()` returns
empty), so pad→GPIO cannot even be read off the board — a reassignment would need the symbol map
before it could be checked.

**Conclusion: Option B is not a pin change plus a route. It is a 4-layer board or a component
re-placement.** That is a design decision for the operator, not a routing task.

---

## 4. SOLVED: 4-layer conversion routes the radio link at the board's OWN rules

Operator decision 2026-10-25: *"yes please make it a 4 layer board. Try to avoid moving the
components."* Applied.

### 4.1 What the extra layers actually buy (stated precisely)

Adding copper layers does **not** let a track squeeze between pads — that gap is 0.370 mm in the pad
ROW, not in the stack, and no layer changes it. What the layers buy is somewhere for the nets that
currently own the corridors to move aside. That is the entire mechanism.

### 4.2 Stackup, as built

| layer | role, as built |
|---|---|
| `F.Cu` | signal (existing routing preserved) |
| `In1.Cu` | **GND plane + the radio escape corridor** — see the honesty note below |
| `In2.Cu` | signal escape layer |
| `B.Cu` | signal (existing routing preserved) |

**Honesty note:** the original plan declared `In1` a *solid* GND plane with no routing. The routed
result puts `/SPI1_SCK`, `/SPI1_MOSI`, `/SPI1_MISO`, `/E28_CS_N`, `/E28_BUSY`, `/E28_DIO1` and
`/E28_DIO2` partly on `In1`. So `In1` is a **GND plane carrying a route corridor**, not a solid
plane. DRC reports **no isolated copper** after refill, so the plane remains connected, but the
reference plane is locally slotted. That trade is recorded here rather than left as a surprise.

### 4.3 Result, measured under the board's ORIGINAL rules (not KRT's relaxed ones)

KRT's first pass reported "clean" while having **silently relaxed** the rules
(`clearance 0.2 → 0.175`, `via 0.5 → 0.45`, `hole clearance 0.25 → 0.175`) and shipped **21
via-in-pad** sites. Re-graded against the original project file that pass showed **234 violations**
(115 clearance, 83 hole_clearance, 1 via_diameter). **That pass was rejected.**

The accepted pass was re-run with the floors pinned explicitly:

```
--clearance 0.2 --via-size 0.5 --via-drill 0.25
--same-net-pad-clearance 0.2 --hole-to-hole-clearance 0.25
```

| metric | result |
|---|---|
| radio nets routed | **9 / 9** |
| multi-point pads connected | **12 / 12** |
| via-in-pad | **0** |
| fab-floor escalations | **0** |
| vias | 52, **all 0.5 / 0.25** (uniform, no margin violation) |
| **DRC under original rules** | **35 — all pre-existing** (`copper_edge_clearance` 16, `lib_footprint_mismatch` 11, `lib_footprint_issues` 8) |
| clearance / shorts / hole_clearance | **0 / 0 / 0** |
| unconnected | **98 → 82** (the 12 radio pads plus 3) |
| footprints moved | **none** (49 before and after) |

Layer usage of the routed nets (measured):

```
/SPI1_SCK   22 segs  B.Cu F.Cu In1.Cu In2.Cu
/SPI1_MOSI  25 segs  B.Cu F.Cu In1.Cu In2.Cu
/SPI1_MISO  24 segs  B.Cu F.Cu In1.Cu In2.Cu
/E28_CS_N   14 segs  B.Cu F.Cu In1.Cu In2.Cu
/E28_BUSY    7 segs  B.Cu F.Cu In1.Cu
/E28_RESET_N 7 segs  B.Cu F.Cu In2.Cu
/E28_DIO1    7 segs  B.Cu F.Cu In1.Cu
/E28_DIO2    9 segs  B.Cu F.Cu In1.Cu
/E28_DIO3    8 segs  B.Cu F.Cu In2.Cu
```

### 4.4 The lesson worth keeping

**A router that edits the design rules is grading its own homework.** KRT wrote
`rules.min_hole_clearance: 0.25 -> 0.175` and `net_class[Default].clearance: 0.2 -> 0.175` into the
output project, and every checker downstream then reads the relaxed value. Always restore the
original `.kicad_pro` and re-run `kicad-cli pcb drc` before believing a routing result. The repo
already warns about this ("self-grading"); this session produced a second live instance.



## 5. Antenna volumes (the operator's standing directive)

`reserve_antenna_volume.py` reserves a **3D volume** per radio — connector + pigtail bend + antenna
body — not a blanket copper keep-out (a keep-out in the wrong place forbids routing where the
antenna is not while leaving the real antenna unprotected).

Volume model: body **32 × 8 × 3 mm** `PLACEHOLDER` + connector **4 × 4 × 3 mm** + pigtail bend
**r 8 mm**.

| ref | side | status | access | basis |
|---|---|---|---|---|
| `U2` | west | **CONFIRMED** | module pin (50 Ω) | project plan: `docs/F33-MODULE-PLAN.md` pins 9/10 (ANT, ANT-2G4) — **not vendor-verified** |
| `U5` | west | PROVISIONAL | unknown | no evidence in repo |
| `U3` | west | PROVISIONAL | unknown | no evidence in repo |
| `U_C` | north | PROVISIONAL | unknown | no evidence in repo |
| `U_E28` | south | PROVISIONAL | unknown | no evidence in repo |

### 4.1 A real collision was found

```
U2 <-> U3   overlap 28.6 x 4.6 mm = 131 mm2
```

**Two antennas cannot occupy the same space.** This is a physical conflict the volume reservation
surfaced that no copper-level check would have. It must be resolved before enclosure or mechanical
work: either a module's antenna is re-aimed, or the pigtail routes to a different exit.

### 4.2 What is NOT claimed

- The antenna **body size is a placeholder**, sized to a 433 MHz quarter-wave whip's mechanical
  envelope. It is not a datasheet part and must not be quoted as a requirement.
- Four of five **sides are guesses** (nearest board edge). The volume *size* is usable as a
  reservation; the *side* is not verified.
- Nothing in this repo establishes the antenna access of `U_E28`, `U3`, `U_C` or `U5`.

---

## 5. Why the RFC821 datasheet point matters

`docs/LR2021_LR2022_LR2012_Datasheet_Rev2.1.pdf` confirms ADR-137 was the right call, and that it
is not merely a preference:

- lines 1615–1621: PA output on `RFO_LF1`/`RFO_LF2`, which **"must be connected together at PCB
  level"**, and **"off-chip impedance matching and harmonic filtering are carried out using external
  components"**.
- lines 1792–1800: the reference design contains an **"Antenna match"** block and a
  **"PA matching & filtering"** block.
- lines 2950–2952: impedances matched using the vendor **reference design**; output power defined in
  a **50 Ω load**.

So a bare LR2021 **cannot** be connected without exactly the RF design ADR-137 forbids. The module
does it for us, which is why the antenna attaches at the module.

---

## 6. Reproduction

```bash
cd ~/worktrees/foam-wing-3d
/usr/bin/python3 tracker/hardware/apply_adr137_remove_rf.py            # dry run
/usr/bin/python3 tracker/hardware/apply_adr137_remove_rf.py --write
/usr/bin/python3 tracker/hardware/move_u_e28_up.py --write
/usr/bin/python3 -c "import pcbnew; b=pcbnew.LoadBoard('tracker/hardware/hub_board_v10.kicad_pcb'); \
  pcbnew.ZONE_FILLER(b).Fill(b.Zones()); pcbnew.SaveBoard('tracker/hardware/hub_board_v10.kicad_pcb', b)"
kicad-cli pcb drc --severity-all --format json --output /tmp/d.json tracker/hardware/hub_board_v10.kicad_pcb
/usr/bin/python3 tracker/hardware/reserve_antenna_volume.py --json docs/fab/status/antenna-volumes.json
python3 tracker/hardware/render_antenna_volumes.py
```

**Refill zones after every move or net deletion** — see §1.

---

## 7. What is still required

1. **Confirm the antenna access of `U_E28`, `U3`, `U_C`, `U5`** from datasheets/mechanical drawings,
   then set `side=` in `reserve_antenna_volume.py` and re-run.
2. **Resolve the U2↔U3 volume collision** (131 mm²) before mechanical/enclosure work.
3. **Replace the antenna body placeholder** with a real part's envelope.
4. **Decide whether `In1` may carry signal.** The routed result uses it (§4.2). If `In1` must be a
   solid reference plane, the radio link needs a different escape and this becomes a 6-layer
   question — measure before assuming.
5. **Remaining 82 unrouted items** are the rest of the board's signal nets (not the radio link). The
   radio link — the first-flight requirement — is done.

# Hub v9 board — 3D render review, round 1 (`hub-v9-render-r1`)

**Scope:** a *milestone* board review. The hub v9 board was rendered in 3D (top + bottom) and the
**render** was put in front of the visual consultant. This is the programme requirement to review the
**boards**, not just the drawings, at each milestone.

- **Board:** `tracker/hardware/hub_board_v9.kicad_pcb` (unmodified by this task)
- **Worktree / branch:** `/home/c08r4d0r/worktrees/hub-milestone` on `pr/hub-milestone`
- **Renderer:** `kicad-cli 9.0.9` via `tracker/hardware/renders/render_pcb.sh`
- **Consultant tool:** `tracker/hardware/ask_astra.py` — **not** `test_astra_vision.py`
- **Date:** 2026-10-17

---

## 1. The renders (documented path + sizes)

Both produced in one run of the documented pipeline; **both stat'ed non-zero** (a render step that
produces no file must fail loudly — checked explicitly, both passed):

```
WIDTH=3600 HEIGHT=2700 QUALITY=high tracker/hardware/renders/render_pcb.sh hub_board_v9
# exit 0; "Successfully created 3D render image" for both sides; Rendering time 152.555 s
# coverage report: tracker/hardware/hub_board_v9.kicad_pcb: 59/59 footprints have a (model ...) block
```

| File (path relative to repo root) | Size (bytes) | Size (human) | Pixels |
|---|---:|---:|---|
| `tracker/hardware/renders/hub_board_v9_top.png` | 2 426 080 | 2.31 MiB | 3584 × 2688 |
| `tracker/hardware/renders/hub_board_v9_bottom.png` | 1 022 917 | 0.98 MiB | 3584 × 2688 |

`kicad-cli` snaps `--width/--height` to a multiple of 256, hence 3584 × 2688 for a requested
3600 × 2700.

**Not a copper-only render.** Per `EVIDENCE-render-probe.txt` the discriminators are render time
(~60–121 s real vs ~1.9 s copper-only) and PNG size (~157 KB real vs ~22 KB copper-only). This run:
**152.6 s** and **2.43 MB** — component bodies are present. The static coverage check independently
reports **59/59** footprints carrying a `(model …)` block.

**The renderer is not bit-reproducible.** A previously produced top render of the same board sat at
the same path (2 427 983 B, `sha256 71a2060141b016474a4698a2e390a4ff522316d7092401431c557154e0c828e5`); the re-render is 2 426 080 B
(`sha256 86b723d0365b…9d962a`). Same board, same command, different bytes — so a **sha256 identifies the
exact artefact reviewed**, and is the right thing to record, but two renders of one board are not
interchangeable as evidence.

### PNG sha256 (the exact artefacts reviewed)

```
86b723d0365b8f2f010662eadfe35f910c13e41bb461f22d4219f983719d962a  tracker/hardware/renders/hub_board_v9_top.png
2ea87eee59ae4d37b42d25506182258c4485a8a890e7e8a36e34d3488fee6480  tracker/hardware/renders/hub_board_v9_bottom.png
```

---

## 2. Served model id

The request alias is not the answer. `ask_astra.py` prints the id the router actually served:

```
SERVED MODEL: gpt-6-astra
```

**No silent substitution** — the served model is the intended consultant (`gpt-6-astra`), not a
different family. Recorded because a served model that is not the one intended is a silent
substitution and would invalidate the review.

Lane note: the consult lane routinely returns HTTP 503 ("all candidate lanes busy or capped"); the call
was wrapped in a 12-attempt retry loop and landed on **attempt 1**. Only one round was needed — the
answer below is the first and only verdict for these two PNGs.

---

## 3. The question asked

A **specific, answerable** question (not "does this look good?"), asking about **placement, presence/
absence and geometry** — the properties a render can actually show — and explicitly inviting
"cannot establish from this render" instead of a guess. Nine numbered items (3 radio modules present;
4 U.FL connectors near edges; 4 wing-connector edge features on each edge, on-edge vs inset; outline a
single rectangle; anything overhanging the outline; missing/mirrored/rotated/colliding parts; the same
for the bottom view) plus two required headed lists: **A. what the render CAN establish** and
**B. what it CANNOT** (with at least four distinct items, naming impedance / copper weight / dielectric /
clearances / layer count / internal structure).

Full prompt: reproduced in `docs/boards/reviews/hub-v9-render-r1-question.txt`.

---

## 4. Verdict — verbatim

> VERDICT: DEFECTS_PRESENT 7

(Exit code 3 from `ask_astra.py`, which is its "defects present" code.)

### Full consultant answer, verbatim

```
## TOP VIEW — hub_board_v9_top.png

1. **Three radio modules as visible component bodies**
   - **(a) Large castellated LoRa module:** A large, translucent rectangular representation labelled **U2** occupies the **upper-centre/centre-left** and is the largest component-shaped region. Its pads and underlying traces remain visible. A populated LoRa module body, rather than a placeholder representation: **cannot establish from this render**.
   - **(b) SX1280, QFN24:** A small exposed-pad IC footprint/representation is visible at **centre-right, labelled U4**. Its identity as an SX1280 and the presence of an actual QFN24 body: **cannot establish from this render**.
   - **(c) ESP32-S3-WROOM-1U:** A large module footprint/translucent representation labelled **U1** is at the **upper-right**. I do **not** see the specified metal shield and U.FL pigtail. Presence of the populated ESP32 module: **cannot establish from this render**.

2. **Four coaxial antenna connectors**

   Four similar small connector-like bodies are visible:

   | Position | Near a board edge? |
   |---|---|
   | Left edge, above the vertical midpoint, near ANT1 | Yes—left edge |
   | Lower-left, along the bottom edge | Yes—bottom edge |
   | Lower-right, along the bottom edge | Yes—bottom edge |
   | Right edge, below the midpoint, labelled ANT3 | Yes—right edge |

   Their round centre contacts are not resolved in this rendering. Whether all four are specifically U.FL/MHF coaxial connectors: **cannot establish from this render**.

3. **Four wing-connector features**
   - **Top:** Yes, approximately centred; its contact feature reaches the edge.
   - **Bottom:** Yes, approximately centred; its contact feature reaches the edge.
   - **Left:** Yes, approximately centred vertically, but the contact/slot feature is **inset inside the board**, not on the left edge.
   - **Right:** Yes, approximately centred vertically, but the contact/slot feature is **inset inside the board**, not on the right edge.

4. **Single closed rectangular outline**

   **No—not an uninterrupted rectangle as rendered.** Narrow black interruptions extend inward at the **top-centre and bottom-centre**, between the wing-connector contacts. These read as slots/notches. The remaining outer edges appear straight; no other perimeter step or missing segment is evident. Exact CAD outline closure cannot be established from a raster render.

5. **Overhang or unsupported features**
   - **Silkscreen is visibly clipped at the perimeter**, including text along the top, left and right edges.
   - No unambiguous component-body overhang beyond the outer square is visible.
   - The top and bottom connector features coincide with the black perimeter interruptions.
   - Whether any component has **no copper beneath it: cannot establish from this render**. Copper coverage and physical board support are different properties.

6. **Missing, mirrored, rotated or colliding parts**
   - **Missing-looking bodies:** Several major footprints, including U1, U2, U3 and U4, show translucent regions and visible pad patterns rather than clearly populated, opaque bodies. This is a rendering/presence ambiguity, not proof that the assembly omits those parts.
   - **Mirrored:** **cannot establish from this render**.
   - **Rotated relative to its own outline:** No unequivocal example is visible.
   - **Collision:** The top-centre wing-connector representation overlaps the upper boundary of U2 in plan view. A physical three-dimensional collision **cannot establish from this render**, but the apparent overlap needs checking.
   - **Silkscreen collisions:** Several labels overlap other labels or component regions, notably around the left-side small ICs and the centre-right component cluster.

## BOTTOM VIEW — hub_board_v9_bottom.png

7. **Single closed rectangular outline**

   **No—not an uninterrupted rectangle as rendered.** The narrow **top-centre and bottom-centre perimeter interruptions** are visible again. The left and right edges appear continuous.

8. **Wing-connector features at the edges**
   - **Top:** Visible and at the edge.
   - **Bottom:** Visible and at the edge.
   - **Left:** Visible, but inset well inside the outline.
   - **Right:** Visible, but inset well inside the outline.

   Thus, all four features are visible, but **not all four sit at their respective edges**.

9. **Bottom free of large component bodies**

   **Yes, visually.** No large component bodies are visible on the bottom; the view mainly shows routing, vias, pads and connector-related features. All clearly visible large populated bodies are on the top side. Complete assembly population **cannot establish from this render**.

## A. WHAT THIS RENDER CAN ESTABLISH

- **Top view:** Approximate placement and relative size of visible bodies, footprints and translucent component representations.
- **Top view:** Four small antenna-connector-like bodies near the perimeter.
- **Both views:** Four wing-connector feature locations, with the left and right features inset rather than reaching their edges.
- **Both views:** Visible interruptions at the top-centre and bottom-centre perimeter.
- **Top view:** Clipped and overlapping silkscreen, and an apparent plan-view overlap between U2 and the top connector.
- **Bottom view:** Absence of visible large bottom-side component bodies.

## B. WHAT THIS RENDER CANNOT ESTABLISH

- **Electrical correctness:** Net connectivity, shorts, opens, pin assignments, power integrity or functional operation.
- **RF properties:** Controlled impedance, matching, insertion loss, antenna performance or radio isolation.
- **Exact dimensions:** The claimed 70 mm × 70 mm size, board thickness, connector pitch or precise component-to-edge distances.
- **Fabrication stack-up:** Layer count, internal routing, internal planes or reference-plane continuity.
- **Materials:** Copper weight, copper thickness, dielectric material, dielectric thickness or dielectric constant.
- **Manufacturing compliance:** Numerical clearances, creepage, annular-ring dimensions, solder-mask tolerances or fabrication-rule compliance.
- **Actual population:** Whether translucent representations correspond to fitted parts, omitted parts or missing/simplified 3D models.
- **Mechanical fit:** Connector mating access, component heights or actual three-dimensional interference.

## Defects found — actionable items

1. **Left wing feature is inset.** Move or revise it so the mating feature reaches the left board edge.
2. **Right wing feature is inset.** Move or revise it so the mating feature reaches the right board edge.
3. **Top and bottom perimeter interruptions conflict with a plain rectangular outline.** Inspect the associated slots/cuts and remove or revise them if an uninterrupted rectangle is required.
4. **Major component bodies are not clearly represented.** Supply and correctly place populated 3D models for the radio/module footprints so presence and geometry can be reviewed.
5. **Top connector and U2 overlap in plan view.** Check their actual mechanical envelopes and separate them if the overlap is physical.
6. **Silkscreen is clipped at board edges.** Move perimeter labels fully inside the printable board area.
7. **Silkscreen labels overlap each other and component regions.** Reposition the crowded labels, especially in the left-side and centre-right clusters.

VERDICT: DEFECTS_PRESENT 7
```

---

## 5. Reconciliation — each defect checked against measured geometry

A consult verdict is a **hypothesis list**, not a measurement: the lane grades the picture, it does not
measure it. Every numbered defect was therefore re-checked against the board itself
(`pcbnew` via `~/venvs/kicad/bin/python`, plus the `.kicad_pcb` text). One defect **did not reproduce**.

### D-1 / D-2 — left and right wing features inset — **CONFIRMED, and root-caused**

Measured with `pcbnew` (absolute board coordinates, mm; outline is `0..70` on both axes):

| Tab | Edge | Footprint origin | Milled-slot `Edge.Cuts` rect (board mm) | Slot vs edge | Land row (board mm) |
|---|---|---|---|---|---|
| `J_W4` | top | (35.00, 5.20) rot 90 | y **−0.80 … 5.20** | **crosses** the edge by 0.80 mm | y 0.20 … 4.20 |
| `J_W2` | bottom | (35.00, 64.80) rot −90 | y 64.80 … **70.80** | **crosses** the edge by 0.80 mm | y 65.80 … 69.80 |
| `J_W1` | left | (5.20, 35.00) rot 0 | x **5.20 … 11.20** | **wholly inside** (5.20 mm in) | x 6.20 … 10.20 |
| `J_W3` | right | (64.80, 35.00) rot 180 | x 58.80 … **64.80** | **wholly inside** (5.20 mm in) | x 59.80 … 63.80 |

**The four wing-tab footprints are not geometrically equivalent.** `J_W1` and `J_W3` are **rotated 180°
relative to `J_W2`/`J_W4`**: rotating `J_W1` 180° about its origin (5.20, 35) reproduces `J_W4`'s
geometry exactly (slot → −0.80 … 5.20, lands → 0.20 … 4.20). Consequences:

- the milled **edge** slot of the left and right interfaces is buried **5.20 mm inside** the board
  instead of opening onto its edge (top/bottom slots cross their edges; left/right do not);
- the left/right land rows sit **5.20 mm further inboard** than the top/bottom rows.

This violates the requirement that the interfaces be identical: `docs/adr/048-v9-hub-wing-interfaces.md`
§2.2 — *"Identical geometry, differing only in assembly tilt | yes"* — and
`docs/WING-TO-HUB-SOCKET-SPEC.md` §2.1, which defines Option A as a **"milled edge slot"**, *"Routed slot
in the hub edge"*.

**Contributing cause (cited, not guessed):** ADR-048 §2.1 still records the hub outline the slots sit on
as **22 × 22 mm** (*"Hub outline the slots sit on | 22 × 22 mm"*). The board is now **70 × 70 mm**
(`docs/adr/068-hub-v9-outline-60x60.md`, revised 2026-10-14 by measurement). The wing-tab placements
appear never to have been re-derived for the larger outline.

**Fixing this is a board-geometry change** (rule R2 — no hand-typed geometry) and is **out of scope**
here. Reported, not touched.

### D-3 — "not an uninterrupted rectangle" — **CONFIRMED as a visible feature; NOT a broken outline**

The board-level outline **is** a single closed rectangle: exactly one board-level `Edge.Cuts` primitive,
a `gr_rect (0,0)→(70,70)`; `pcbnew`'s board-edge bounding box is **70.15 × 71.65 mm**. The "narrow black
interruptions at top-centre and bottom-centre" the consultant saw are the **designed milled edge slots**
of `J_W4`/`J_W2` crossing the outline (table above) — i.e. the render is showing a real, intended
feature, not a damaged outline. Note the asymmetry: a notch appears on **two** edges only, because only
`J_W2`/`J_W4`'s slots reach their edges — which is D-1/D-2 seen from the other side.

### D-4 — "major component bodies are not clearly represented" — **CONFIRMED as a render characteristic, NOT a missing model**

All 22 `(model …)` references resolve (with `${KIPRJMOD}` expanded to the `.kicad_pcb` directory —
the nine hand-authored hub envelopes at `tracker/hardware/3dmodels/hub/*.wrl` all exist, 2 878–3 843 B,
and are tracked). They are **solid** `IndexedFaceSet` boxes, but with **`transparency 0.35`** — so the
modules render as deliberately semi-transparent envelopes (the generator marks them
*"ENVELOPE, height unverified"*, Z *"a flagged placeholder"*). The consultant's "translucent
rectangular representations" are that transparency, and its abstention on *"populated vs placeholder"*
is the correct call: the render genuinely cannot distinguish a fitted part from a placeholder envelope.
**This is a property of the render configuration, not a board defect.** (Zero models are missing — an
earlier automated check of mine reported 15 "missing" models because it did not expand `${KIPRJMOD}`;
that was my tool's bug and is retracted here.)

### D-5 — "top connector and U2 overlap in plan view" — **NOT REPRODUCED** (consultant false positive)

Measured courtyard (F.CrtYd/B.CrtYd) bounding boxes:

- `U2` (`LoRa2021F33-2G4`): x[7.02, 46.67] y[7.33, 28.98]
- `J_W4` (top wing tab): x[30.18, 39.83] y[−1.32, 5.72]

**Separation 1.60 mm in y — no overlap.** The pad rows are further apart still (`U2` pads end at
y = 28.65; `J_W4` pads span y 0.20 … 4.20). The apparent overlap is the two **transparent envelope
boxes** (D-4) seen through each other in plan view. Not a real collision.

### D-6 — "silkscreen clipped at board edges" — **PARTIALLY CONFIRMED**

Measured: only `J_W4` (silk y −3.88 … −1.12, i.e. **3.88 mm outside** the top edge) and `J_W2` (silk
y 71.12 … 73.88, **3.88 mm outside** the bottom edge) put silkscreen outside the outline — the wing-tab
marks (`W`, `1`, `4`, `90`). Silkscreen outside the board outline cannot be printed (there is no
substrate there). Same root cause as D-1/D-2: those are the two tabs whose footprint orientation points
**outward**; `J_W1`/`J_W3` point inward and put no silk outside. Not independently fixed here.

### D-7 — "silkscreen labels overlap each other / component regions" — **NOT INDEPENDENTLY VERIFIED**

The render does show dense silkscreen with some apparent crowding. This was **not** measured: label
collision needs the vector/geometry source, and the consultant's specific claims (left-side ICs,
centre-right cluster) are unquantified. Recorded as an **open item**, not a confirmed defect.
`docs/fab/hub-v9/DRC-CLASSIFICATION.md` is the right place to settle it.

---

## 6. What this render can and cannot establish

**The cannot-list is the useful half.** A 3D render is a picture of the **outside** of the board.

### CAN establish (and did)

- **Presence / absence** of component bodies and their **approximate placement** on the board — this is
  how D-1/D-2 surfaced (four wing features present, but two of them not at their edges).
- **Gross geometry of the outline and of milled features** — the outline is one rectangle; the
  top/bottom edge slots are visible as notches, and their absence on the left/right edges is visible.
- **Relative size and layout** of the large bodies, and that the four antenna connectors sit near the
  perimeter.
- **That the bottom side carries no large component bodies.**
- **Silkscreen that falls outside the outline** (D-6) — visible as clipped marks at the perimeter.

### CANNOT establish (do not ask the render for these)

- **Characteristic impedance / RF properties.** The board is **4-layer, 0.60 mm total** (F.Cu / In1.Cu /
  In2.Cu / B.Cu; stackup thicknesses `0.04` mm copper, `0.15` mm dielectric layers). As an earlier
  review of a different board said correctly, *"the total 0.6 mm board thickness alone is insufficient"*
  to judge characteristic impedance. Impedance depends on trace width, dielectric constant and
  reference-plane spacing — **none of which a render shows**. Matching, insertion loss, antenna
  performance and radio isolation are likewise invisible.
- **Copper weight / copper thickness / dielectric material and thickness / dielectric constant** — the
  visible surface is solder mask over copper; the interior is not shown at all.
- **Layer count and internal structure** — planes, internal routing and reference-plane continuity are
  hidden behind the outer copper. (The 4-layer stack here was read from the board **file**, not the
  render.)
- **Numerical clearances, creepage, annular rings, solder-mask tolerances, DRC compliance** — a render
  has no dimension scale and cannot be measured against a rule.
- **Electrical correctness** — net connectivity, shorts, opens, pin assignments, power integrity,
  function. (A render cannot even confirm that a visible pad is connected to anything.)
- **Exact dimensions** — the 70 × 70 mm outline, board thickness, connector pitch, precise
  component-to-edge distances. The render carries no scale bar; every distance in §5 was measured from
  the board file with `pcbnew`, **not** from the PNG.
- **Whether translucent envelopes correspond to fitted parts or placeholders** (D-4) — which is why the
  consultant's abstentions there are correct.
- **Mechanical fit** — connector mating access, component heights, true 3D interference.

---

## 7. Outcome

- **Verdict:** `DEFECTS_PRESENT 7` (served model `gpt-6-astra`).
- **1 consultant false positive** (D-5, no collision — measured 1.60 mm clearance).
- **1 confirmed-and-root-caused real board defect** (D-1/D-2: `J_W1`/`J_W3` rotated 180° relative to
  `J_W2`/`J_W4`, burying the left/right milled edge slots 5.20 mm inside the board; with D-3 and D-6 as
  its visible consequences).
- **1 confirmed render-configuration characteristic** (D-4: envelope `transparency 0.35`, not a missing
  model).
- **1 partially confirmed** (D-6: 3.88 mm of silkscreen outside the outline on the two outward-pointing
  tabs) and **1 open item** (D-7: silkscreen crowding, unmeasured).

**No board geometry was modified.** The D-1/D-2 fix is a board change under rule R2 (no hand-typed
geometry) and belongs to a separate task.

---

## 8. Reproduce

```bash
cd /home/c08r4d0r/worktrees/hub-milestone

# renders (documented path + sizes)
WIDTH=3600 HEIGHT=2700 QUALITY=high tracker/hardware/renders/render_pcb.sh hub_board_v9
stat -c '%n %s' tracker/hardware/renders/hub_board_v9_top.png tracker/hardware/renders/hub_board_v9_bottom.png
sha256sum tracker/hardware/renders/hub_board_v9_top.png tracker/hardware/renders/hub_board_v9_bottom.png

# the consult (records the SERVED model id; NOT test_astra_vision.py)
python3 tracker/hardware/ask_astra.py --prompt-file docs/boards/reviews/hub-v9-render-r1-question.txt \
    --max-tokens 6000 tracker/hardware/renders/hub_board_v9_top.png \
                          tracker/hardware/renders/hub_board_v9_bottom.png

# the measurements in §5 (needs the KiCad 9 bindings venv; plain python3 segfaults on pcbnew)
~/venvs/kicad/bin/python tracker/hardware/renders/wing_tab_geometry_probe.py
```

`wing_tab_geometry_probe.py` prints, from the board file: the board-level outline primitive, each wing
tab's footprint-embedded milled-slot `Edge.Cuts` rectangle and its distance from the nearest outline
edge, each land row, the U2/J_W4 courtyard clearance, and 3D-model coverage. It is read-only.

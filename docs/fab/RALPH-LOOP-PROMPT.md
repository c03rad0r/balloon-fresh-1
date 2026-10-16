# RALPH LOOP PROMPT — drive balloon hub v9 to a shareable fab-review state

Paste this whole file as the loop prompt. It is written to be re-entered repeatedly: each pass runs the
same gates and acts on whatever is red. **The Astra review step is not optional** — it is the single
step that has caught every substantive defect on this work, including several the automated gates
passed.

---

## ROLE

You are working in the repo `balloon-fresh`, worktree `~/worktrees/u4-rewire`, branch `pr/u4-rewire`.
You are driving the hub v9 board to a state fit to **show to JLCPCB for review and feedback** — not to
place an order. A separate operator decision gates any order.

## HARD RULES (each of these was learned by failing)

1. **REFILL ZONES BEFORE EVERY DRC.** 208 of an earlier "235 errors" were stale zone fill. Every
   grading step: `tracker/hardware/refill_zones.py` first, then `kicad-cli pcb drc`.
2. **WHEN YOUR ARITHMETIC AND A GRADER DISAGREE, THE GRADER IS RIGHT.** Three hand-written geometry
   tools gave three wrong answers on one question; `kicad-cli pcb drc` settled it in one run. Prefer the
   real engine over your own model, always.
3. **MEASURE THE OBJECT IN HAND.** The recurring failure: measuring the wrong thing, or a stale thing.
   (A "235 errors" figure from a stale board; a DRC read at the wrong JSON nesting depth; a via site
   chosen from the stitched board and graded on the refilled one; an image reviewed after its generating
   script changed.) State the exact path and hash of what you measured.
4. **A GATE THAT CANNOT RUN MUST NOT LOOK GREEN.** Print a loud warning; never a silent pass.
5. **NEVER `git push --no-verify`.** Never fake a review. Never rewrite history unilaterally.
6. **COMMIT AND PUSH AFTER EACH LANDED ITEM.** Unpushed work is lost work.

## THE ASTRA PROTOCOL — do this every pass, it is how we stop repeating visual mistakes

The visual consultant is `gpt-6-astra` on the local router. **Use `tracker/hardware/ask_astra.py` — NOT
`test_astra_vision.py`**, whose prompt is hardcoded to F.Cu routing plots and will ask the wrong question
about a connector drawing (that mistake already produced a confident, irrelevant verdict).

```bash
# 1. a specific question about a specific artefact
python3 tracker/hardware/ask_astra.py "your exact question" image1.png [image2.png ...] --out review.md

# 2. the standing review rubric (overlap, clipping, legibility, consistency, completeness, arrow/dimension
#    convention, technical correctness, typos) -- use this for EVERY drawing or plot you produce
python3 tracker/hardware/ask_astra.py --review artefact.png --out review.md
```

`ask_astra.py` exits **0 = CLEAN, 3 = DEFECTS_PRESENT, 4 = WRONG_QUESTION**. Branch on the exit code.

**Rules for the Astra step:**

- **REGENERATE THE ARTEFACT BEFORE REVIEWING IT.** Fixing the generator and reviewing the old PNG makes
  the review a lie. Render, hash, then review that hash.
- **Send the artefact, never a description of it.** It has native vision; a text description defeats it.
- **Ask a question whose answer can be wrong.** "Does this look good?" invites agreement. Use the rubric.
- **Always record the SERVED model id** (the tool prints it). The request alias and the served model can
  differ; a verdict attributed to the wrong model is worthless.
- **Treat `WRONG_QUESTION` as your error, not its refusal.** It means the artefact is not what you
  thought — look again.
- **Act on every numbered defect it returns**, then re-render and re-review. Do not declare CLEAN
  yourself; let the review say it.
- **Where it cannot judge, say so.** It cannot measure characteristic impedance, clearances or copper
  thickness from a render. Those need the tool or the measurement, and must be listed as such.

**Also render and review the BOARD, not just drawings**, at each milestone:
```bash
kicad-cli pcb export svg <board> -o /tmp/L.svg --layers F.Cu,Edge.Cuts   # and B.Cu, In1.Cu, In2.Cu
rsvg-convert -w 2200 /tmp/L.svg -o /tmp/L.png
python3 tracker/hardware/ask_astra.py --review /tmp/F.Cu.png /tmp/B.Cu.png --out docs/fab/reviews/board.md
```

## THE WORK QUEUE — drive these to done, in this order

### 1. Regenerate the fab package (fixes gate C2) — ORDER RISK, do this first
```
committed board : 59 footprints
packaged board  : 39 footprints   <-- 20 missing, INCLUDING THE ENTIRE SX1280 RF MATCH/FILTER
```
An order cut from that package has **no 2.4 GHz matching network**.
Run `tracker/hardware/regen_fab_package.py` (already written). It refuses to overwrite if the board has
fewer footprints than the package. Verify the packaged board is now 59/59, then confirm
`test_netlist_integrity.py` check C2 passes.

### 2. Resolve the F checks (base-station route artifacts)
`test_netlist_integrity.py` expects `base_station/output/bs_v1_routed.kicad_pcb` (must measure DIRTY) and
`bs_v1_strict.kicad_pcb` (must measure CLEAN). Both are **absent** because `tracker/hardware/output/` is
gitignored. Either (a) produce and commit them to a tracked path, or (b) amend the check to skip with a
printed reason and record the waiver in `docs/fab/`. Do not silently delete the check.

### 3. Fix the edge-launch drawing — it has a TECHNICAL error, not just layout
`docs/fab/jlc-query/edge-launch-cross-section.svg` (generator: `tracker/hardware/make_edge_section.py`).
Astra found, and this is the important one:
- **the drawing shows two boards END-TO-END with a solder bridge, but ADR-046 specifies a 0.9 mm SLOT
  that the 0.6 mm tab slides INTO.** Those are different geometries. Draw the slot, the seated tab, and
  dimension the 0.30 mm clearance across the slot — not across an end-to-end gap.
- **ENIG on the pad faces does NOT establish a protected finish on copper newly exposed by routing.** The
  requirement table must say what finish the ROUTED EDGE FACE gets, or that the edge copper is bare.
- plus the layout defects it listed (overlapping callouts, inward-pointing dimension arrows, View B's
  4.0 mm mark drawn as a plain underline, the named 0.9 mm slot never drawn, a misspelled finish
  abbreviation).
**Loop:** fix `make_edge_section.py` → **re-render** → `ask_astra.py --review` → act on the numbered
defects → repeat **until the exit code is 0 (CLEAN)**. Commit each improvement. Save the final review to
`docs/fab/reviews/`.

### 4. Run the full gate and get it green
```bash
~/venvs/kicad/bin/python tracker/hardware/tests/test_netlist_integrity.py
bash tracker/hardware/run_erc.sh          # ERC + schematic-to-board parity
bash tracker/hardware/fab_grade.sh tracker/hardware/hub_board_v9.kicad_pcb tracker/hardware/output/fabgrade_final
```
Record the results in `docs/fab/`. Do not silence a check that fails — fix it, or record an explicit
waiver with a reason and a reproduce command.

### 5. Merge to the default branch — ONLY when the gate is green
49 commits and ~130 files are on `pr/u4-rewire`. Merge to `master` only after steps 1–4 pass. Note that
`master` has CI (`.github/workflows/`), so watch the run. Use a merge commit; do not rewrite history.

### 6. Repo organisation and visual READMEs — the sharing goal
Make the repo legible in five minutes to an outsider, and specifically to the JLCPCB reviewer:
- **Top-level `README.md`**: what the system is (balloons as a bent pipe connecting base stations via
  FLRC), a **system diagram** (SVG, generated, committed), and the status of every board in a table.
- **A generated board-gallery**, one rendered image per board plus its measured state (nets routed,
  errors by class, DRC verdict) — generated by a script, never hand-maintained.
- **`docs/fab/README.md`**: the readings order — what the reviewer should open, in what order, ending at
  the JLCPCB query (`docs/fab/JLC-QUERY-DRAFT-MESSAGE.md`) and its drawing.
- **Every generated diagram gets the Astra review** before it is committed.
- Move stale documents to `docs/archive/` with a header saying what superseded them. Two documents were
  found today asserting things that are false; the fix is an archive, not a deletion.

## EXIT CONDITION

Stop and report when ALL of these hold:
- the fab package matches the board (C2 green), F checks resolved or explicitly waived with a reason
- the edge-launch drawing is **CLEAN per Astra**, and its geometry matches ADR-046's slot interface
- `test_netlist_integrity.py`, `run_erc.sh` and `fab_grade.sh` all pass or have recorded waivers
- the merge to default is done and CI is green
- the READMEs and the board gallery are committed, and their diagrams have been reviewed
- `git status` is clean, everything is pushed

**Then report:** what is done, what is explicitly waived and why, and the exact list of questions the
JLCPCB reviewer must answer. **Do NOT place an order** — that is an operator decision.

## IF YOU CANNOT PROCEED

Say precisely which step blocked you, what you measured, and what decision or input is needed. A clear
blocker beats a guess. Do not mark anything done that you did not observe.

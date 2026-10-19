# TOOL DEFECT — `fab_grade.sh` grades a re-routed copy, not the committed board

**Found:** 2026-10-19, while refreshing the DFM snapshot after PR #240.

## The symptom

```
bash tracker/hardware/fab_grade.sh <board> <out>
  → violations 154, holes_co_located 2, via_dangling 8      ← fab_grade's report
kicad-cli pcb drc <board> (direct, fresh refill)
  → violations 164, holes_co_located 0, via_dangling 7       ← the committed board
```

Two grader runs disagreed. RALPH rule 2: the grader is right — but here **two different objects** were
graded, so the rule's resolution step is: identify the object in hand.

## The root cause — measured

`fab_grade.sh` step [1] does **not grade the board you pass it**. It runs the KRT router
(`$KRT/py_router/route.py --escalation off`) to produce `${STEM}_strict.kicad_pcb`, stitches, refills,
and DRCs **that**. The chain:

```
board → [1] KRT re-route → strict → [2] stitch → [3] refill → [4] DRC
```

The comparison that proves it:

```
committed board:   835 tracks, 288 vias, sha256 71bd675f74a0…
fab_grade's copy:  835 tracks, 289 vias, sha256 01ee8ba444…
```

One via different — and it is **exactly the `C_CAP2` phantom via** that PR #240 removed:

```
KRT-routed copy: phantom C_CAP2 via present:    1   ← re-introduced by the router
KRT-routed copy: my C_CAP2 GND track present:   1   ← my fix WAS carried through
KRT-routed copy: my 3 In1 stitching vias:       3/3 ← PR #239's fix WAS carried through
```

**The KRT router sees `C_CAP2.2` — a GND pad whose pour clearance leaves it unconnected in ITS routing —
and stitches it with a via at the pad centre. That reproduces the exact drill conflict PR #240 removed.**
`fab_grade` then grades its own re-introduced defect and reports it as the board's state.

## Why this matters

1. **The gate's verdict can lag the board.** Any fix whose rationale the router doesn't share gets
   silently undone in the graded copy. `holes_co_located 2` in the fab report is not the board's state.
2. **`NOT ORDERABLE` is still correct** — the direct DRC also reports 4 unconnected and plenty of
   violations — but the *number* the gate prints is not the board's number.
3. **It explains a historical oddity**: PR #240's `fab-guard` pre-commit hook said "2 unrouted nets"
   while the direct DRC says the same — but the *fab_grade* numbers never matched my direct runs.
   Now we know why: they were never the same board.

## What must change (not done in this record)

`fab_grade.sh` needs a mode that grades **the committed board as-is** (refill + DRC only, no re-route),
for the "is the artefact in hand clean" question — while keeping the KRT chain for the
"can this board be routed at the frozen floor" question. Those are two different questions and today
one tool conflates them.

**Until that split exists: quote the direct DRC for board state, and quote `fab_grade` only as the
router-capability signal it actually is.**

## Reproduce

```
bash tracker/hardware/fab_grade.sh tracker/hardware/hub_board_v9.kicad_pcb /tmp/fabgrade
sha256sum /tmp/fabgrade/hub_board_v9_filled.kicad_pcb    # != the committed board's hash
kicad-cli pcb drc --format json --output /tmp/d.json tracker/hardware/hub_board_v9.kicad_pcb
```

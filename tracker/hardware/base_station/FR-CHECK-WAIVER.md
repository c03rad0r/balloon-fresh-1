# Base-station F-class check waivers — MACHINE-READABLE RECORD

This file is the **single source of the reason text that `test_netlist_integrity.py` PRINTS when the
suite runs**. The gate reads it at run time (`_waiver_blocks()`) instead of carrying an inlined copy, so
the reason a reader sees in the suite output and the reason committed here can never drift apart. A
waiver whose printed reason and committed reason differ is just a quieter kind of silent skip.

The gate fails closed on this file: if an F-check's artifact is absent and there is **no `WAIVER:`
entry for it here** (record missing, empty, or the entry deleted), the check is reported as **FAIL** —
not as a docile `PENDING`. Deleting this record must not be able to turn a gap green.

Rules this file obeys (see `docs/fab/BASE-STATION-F-CHECKS.md` for the full reasoning):

- A waiver states **which** check, **why** it cannot run today (measured, with the reproduce command),
  and **what would make it runnable**.
- A waiver is **never** a pass. It prints, it stays countable, and it is not deleted.
- Nothing here asserts an unearned floor. No board is invented and no route is manufactured to satisfy
  a file-existence check.

---

WAIVER: bs_v1_routed.kicad_pcb
CHECK: F. base station (first route -- REJECTED, must FAIL): board present
EXPECTED: bs_v1_routed.kicad_pcb at a path the gate resolves; must measure DIRTY (min track < 0.10 mm, min via diameter < 0.45 mm, min via drill < 0.20 mm)
VERDICT: WAIVED — the artifact is ABSENT and is NOT produced by this change
WHY (measured, not assumed):
  1. The artifact has never existed in version control, in ANY ref. This is not "not yet measured" and
     not "generated then deleted" — it was never committed once:
         git log --all --oneline -- '*bs_v1_routed.kicad_pcb'      # -> no output
         git log --all --diff-filter=D -- '*bs_v1_routed*'         # -> no output
     It is absent today because the base-station route/DRC intermediates are gitignored
     (`tracker/hardware/base_station/output/`, .gitignore line 91), so the route lived only in a
     worker's scratch tree that no longer exists:
         git check-ignore -v tracker/hardware/base_station/output/bs_v1_routed.kicad_pcb
         find / -name 'bs_v1_routed*.kicad_pcb'    # -> no hits anywhere on this host
     Only the DRC REPORT survives, and it is committed as evidence that a board once existed:
         docs/fab/hub-v9/gerbers/bs_v1_routed_strict-drc.json        ("source": "bs_v1_routed_strict.kicad_pcb", kicad 9.0.9, 2026-10-14)
         docs/fab/hub-v9/gerbers/bs_v1_routed_strict_filled-drc.json
  2. The base station has a NETLIST and a PLACED board but NO EDITABLE SCHEMATIC, and the placed board
     has 44 nets and ZERO tracks — nothing is routed at all:
         find . -name '*.kicad_sch' | grep base_station      # -> no output (no base-station schematic)
         ~/venvs/kicad/bin/python -c "import pcbnew; b=pcbnew.LoadBoard('tracker/hardware/base_station/base_station_v1_placed.kicad_pcb'); print(len(list(b.GetFootprints())), len(list(b.GetTracks())), b.GetNetCount())"
             # -> 44 footprints, 0 tracks, 45 nets
  3. Fabricating this board to satisfy the file-existence branch would MANUFACTURE an artifact whose
     only purpose is to assert a floor the design has not earned — and the floor it "proves" is a floor
     of a 44-net board with no schematic behind it. `docs/fab/ASTRA-GAP-ANALYSIS.md` places the
     base-station work at items B2-B9 (B2 = "reconstruct the schematic") and states "a netlist is a
     useful baseline, not proof of a correct circuit"; §5 ranks the zero-routed base station as the
     single HIGHEST-RISK item on the programme: "JLCPCB may successfully manufacture an electrically
     incomplete design."
     Stated precisely: this artifact IS mechanically re-routable (the two historical attempts were
     re-run with `--escalation fab` and `/board`; their measured minima — 0.0889 / 0.25 / 0.15 mm — are
     recorded in docs/fab/BASE-STATION-ROUTE-REJECTED.md and would satisfy this check's DIRTY
     expectation). It is NOT produced here because doing so requires routing a design whose schematic
     does not exist, committing a non-deterministic throwaway as if it were a design artifact, and
     would exercise only the grader — asserting nothing about the board's manufacturability. The
     reason is therefore "not earned at this stage of the design", not "impossible".
CLEARED_BY: complete B2 (reconstruct the Kicad schematic from the netlist) and B5-B6 (re-place, route),
  then commit a deliberately-loose route as bs_v1_routed.kicad_pcb (must violate 0.10/0.45/0.20) to a
  path the gate resolves — i.e. a tracked path, or make the gate build it on demand. See
  docs/fab/RALPH-LOOP-PROMPT.md §2 and docs/fab/BASE-STATION-F-CHECKS.md.

---

WAIVER: bs_v1_routed_strict.kicad_pcb
CHECK: F. base station (strict, --escalation off, must PASS): board present
EXPECTED: bs_v1_routed_strict.kicad_pcb at a path the gate resolves; must measure CLEAN (min track >= 0.10 mm, min via diameter >= 0.45 mm, min via drill >= 0.20 mm)
VERDICT: WAIVED — the artifact is ABSENT and is NOT produced by this change
WHY (measured, not assumed):
  1. Same absence, same root cause, same measurement as the entry above: never committed in any ref
     (`git log --all` finds nothing), gitignored output directory, and no such file anywhere on this
     host (`find / -name 'bs_v1_routed*.kicad_pcb'` -> no hits but the two committed DRC reports).
  2. Same missing schematic and same zero-routed starting board (44 footprints, 0 tracks, 45 nets).
     A CLEAN route cannot be graded into existence from a placed-only board with no schematic.
  3. The historical strict attempt did run and was honestly reported as INCOMPLETE — it is not a
     shipped artifact: `docs/fab/BASE-STATION-ROUTING-HONEST-STATE.md` records 17/35 nets routed with
     18 open, and `docs/fab/BASE-STATION-REFILL-RESULT.md` records 19 unconnected items after refill.
     Producing a file here would therefore have to hide 18-19 open nets behind a "CLEAN" assertion.
     Refusing to do that is the point of this waiver.
CLEARED_BY: same as the entry above (B2 -> B5-B6), and the route must actually complete so that the
  CLEAN assertion is earned: refill zones, then grade from the BOARD (not the router's project), with
  0 unconnected items and minima >= 0.10/0.45/0.20. See docs/fab/BASE-STATION-F-CHECKS.md.

---

## Note on the second site of the same check

`tracker/hardware/tests/test_v9_board_invariants.py` §5 guards the SAME property for the same board and
is left as-is: it already prints a loud, non-silent failure naming the same cause and the same
clear-path ("no output/bs_v1_routed_strict.kicad_pcb -- re-route with --escalation off"), so it is not a
silent skip. It is deliberately NOT converted to PENDING here, because that file is the hub-invariant
suite and this change does not touch it. Its exit code stays non-zero, which is honest: the artifact
genuinely does not exist. Recorded in `docs/fab/BASE-STATION-F-CHECKS.md` so the two representations
cannot look like a contradiction to the next reader.

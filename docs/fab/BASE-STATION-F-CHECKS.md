# BASE-STATION F-CLASS CHECKS — state and reasoning (both WAIVED, loudly)

**Date:** 2026-10-17 · **Checks:** `bs_v1_routed`, `bs_v1_strict` (the two `F.` items in
`tracker/hardware/tests/test_netlist_integrity.py`) · **Outcome: both WAIVED, with the reason PRINTED
when the suite runs. No board was produced. No check was deleted or silently skipped.**

## Why this doc exists

The brief's acceptance is "for each of the two checks: either the committed artefact, or a committed +
PRINTED waiver with a measured reason". This is the committed record of which of the two happened and
why — so the next reader does not have to re-derive it, and so the decision can be argued with.

## The two checks, and what they asked for

| check | artifact it resolves | expected measurement |
|---|---|---|
| `F. base station (first route -- REJECTED, must FAIL): board present` | `tracker/hardware/base_station/output/bs_v1_routed.kicad_pcb` | must measure **DIRTY** — min track < 0.10 mm, min via < 0.45 mm, min drill < 0.20 mm |
| `F. base station (strict, --escalation off, must PASS): board present` | `tracker/hardware/base_station/output/bs_v1_routed_strict.kicad_pcb` | must measure **CLEAN** — meets all three JLC floors |

They guard a real property: **that a rejected route measures dirty and a shipped one measures clean,
graded from the BOARD rather than from a project file the router may have rewritten.** The check is
worth keeping — the self-grading hazard it encodes (the router lowered four floor values in its own
output project so its own checkers would read clean) is a measured, documented failure on this project.

## What the state actually is (measured in this session, not assumed)

Not produced. The artifacts are absent, and they are **not** absent because someone forgot to commit
them:

```
$ git log --all --oneline -- '*bs_v1_routed.kicad_pcb'      # -> no output
$ git log --all --diff-filter=D -- '*bs_v1_routed*'         # -> no output
```

They have **never existed in version control, in any ref.** They are absent from the working tree
because the base-station route/DRC intermediates are gitignored, and the route lived only in a worker's
scratch tree that no longer exists:

```
$ git check-ignore -v tracker/hardware/base_station/output/bs_v1_routed.kicad_pcb
  .gitignore:91:tracker/hardware/base_station/output/   tracker/hardware/base_station/output/bs_v1_routed.kicad_pcb
$ find / -name 'bs_v1_routed*.kicad_pcb'     # -> no hits anywhere on this host (only DRC *reports*)
$ ls tracker/hardware/base_station/output/   # -> .bs_v1_scaffold.kicad_pcb  (a scaffold, no copper)
```

What the base station actually has:

```
$ ~/venvs/kicad/bin/python -c "import pcbnew; b=pcbnew.LoadBoard('tracker/hardware/base_station/base_station_v1_placed.kicad_pcb'); \
    print(len(list(b.GetFootprints())), len(list(b.GetTracks())), b.GetNetCount())"
  44 footprints, 0 tracks, 45 nets

$ find . -name '*.kicad_sch' | grep base_station     # -> no output
```

So: **44 placed footprints, ZERO tracks, 45 nets, a netlist, and NO editable schematic.** Only DRC
reports survive as evidence a route once existed — `docs/fab/hub-v9/gerbers/bs_v1_routed_strict-drc.json`
(names `"source": "bs_v1_routed_strict.kicad_pcb"`, kicad 9.0.9, 2026-10-14) and its `_filled`
counterpart.

## The decision, stated plainly

**Both checks are WAIVED. No board was produced.** Producing them to satisfy the file-existence branch
would manufacture an artifact whose only purpose is to assert a floor the design has not earned: to make
`bs_v1_routed` resolve, a board must be routed from a netlist with no schematic behind it, and the
"floor" it would then be graded against is the floor of that unverified board.

The repo already says this, and pre-dates this task:

- `docs/fab/ASTRA-GAP-ANALYSIS.md` places the base-station work at **B2–B9**, with **B2 = reconstruct the
  schematic**, and states *"a netlist is a useful baseline, not proof of a correct circuit."*
- Its §5 names **"Incomplete routing—most starkly, the base station's zero-routed PCB"** as the single
  **highest-risk item** on the programme: *"JLCPCB may successfully manufacture an electrically
  incomplete design."*
- `docs/fab/BASE-STATION-SCHEMATIC-CAPTURE.md` closes with: *"no schematic, placement, route, DRC or
  gerber exists for the base station."*

### The honest counter-argument, recorded rather than hidden

**Both boards ARE mechanically re-routeable**, and that must be stated plainly or the waiver overstates
itself. The historical runs exist and their measurements are on file:

- The rejected route was produced at `--escalation fab`/`board` and measured **0.0889 / 0.25 / 0.15 mm**
  (`BASE-STATION-ROUTE-REJECTED.md`). That satisfies `bs_v1_routed`'s **DIRTY** expectation exactly.
- `KiCadRoutingTools` is present at `/data/repos/KiCadRoutingTools`.

So the reason this is a waiver is **not** "impossible". It is **"not earned at this stage of the
design"**: the artifact would be a non-deterministic throwaway driving an unverified netlist, its
committed presence would assert a design floor nobody has established, and no reader could tell it apart
from a real route artifact. A gate is supposed to measure the design; this would only measure the
grader. That distinction is written into the printed waiver text itself.

For `bs_v1_strict` the argument is stronger still: the strict attempt **did** complete and was
**incomplete** — 17/35 nets routed, 18 open (`BASE-STATION-ROUTING-HONEST-STATE.md`), 19 unconnected
after refill (`BASE-STATION-REFILL-RESULT.md`). A committed file could only satisfy the **CLEAN**
assertion by hiding 18–19 open nets. Refusing that is the whole point.

## How the waiver satisfies the rule

The governing rule is **"a gate that cannot run must not look green, and a check must never be silently
deleted."** The implementation:

1. **The reason PRINTS when the suite runs**, and it is not a copy — the gate **reads** it at run time
   from a committed record, so the printed reason and the committed reason cannot drift:
   ```
   $ ~/venvs/kicad/bin/python tracker/hardware/tests/test_netlist_integrity.py
   === F. DRC FLOOR: no relaxed project may be the graded authority ===
       waiver record: tracker/hardware/base_station/FR-CHECK-WAIVER.md (present, 2 entries)
     WAIVED   F. base station (first route -- REJECTED, must FAIL): board present
             the artifact is ABSENT and NOT produced. Reason, from tracker/hardware/base_station/FR-CHECK-WAIVER.md:
             CHECK: F. base station (first route -- REJECTED, must FAIL): board present
             EXPECTED: bs_v1_routed.kicad_pcb at a path the gate resolves; must measure DIRTY (...)
             VERDICT: WAIVED — the artifact is ABSENT and is NOT produced by this change
             WHY (measured, not assumed): ...
             CLEARED_BY: complete B2 ... and B5-B6 ...
             A WAIVER IS NOT A PASS. It is a stated gap that stays countable and is never deleted.
     WAIVED   F. base station (strict, --escalation off, must PASS): board present
             ...
   RESULT: 14 pass, 0 FAIL, 2 WAIVED, 0 PENDING
   ```
   The summary **counts waivers separately from passes**, so the suite line cannot be read as "all
   green". The record — `tracker/hardware/base_station/FR-CHECK-WAIVER.md` — is the single source of the
   printed text and carries, per check: which check, WHY (with the exact reproduce commands), and
   CLEARED_BY.
2. **Deleting the record cannot make the gap go green.** This is the load-bearing property. If an
   artifact is absent **and** the record has no `WAIVER:` entry for it, the check is reported **FAIL**:
   ```
   $ mv tracker/hardware/base_station/FR-CHECK-WAIVER.md /tmp/ && python3 .../test_netlist_integrity.py
       waiver record: tracker/hardware/base_station/FR-CHECK-WAIVER.md (ABSENT -- an absent artifact will FAIL, not be waived)
     FAIL  F. base station (first route -- REJECTED, must FAIL): board present
             ... does not exist AND there is no WAIVER entry for bs_v1_routed.kicad_pcb ...
   RESULT: 14 pass, 2 FAIL, 0 WAIVED, 0 PENDING      # exit 1
   ```
   So the old `ck_pending` fallback — which would have turned two real gaps into a green run after one
   `rm` — is gone for these two checks.
3. **A waiver can be made blocking when it matters.** `--strict-waivers` turns every waiver into a
   failure, so a release gate can demand the artifacts actually exist (`RAISED_EXIT=1`, `RESULT: 14
   pass, 0 FAIL, 2 WAIVED` → `STRICT MODE: 2 waiver(s) present -- failing the run by request`). The
   default stays non-failing so a normal run reports the gap loudly without blocking unrelated work.
4. **No check was deleted.** All three `F.` items and their `ROUTED` table are intact; the only edit to
   the check bodies is the absent-artifact branch. See the diff of
   `tracker/hardware/tests/test_netlist_integrity.py`.

### The grading branch is LIVE, proven with controls

Exercised with two throwaway probes built from the real placed board, written to a `/tmp` path
(`~/venvs/kicad/bin/python /tmp/mkprobe.py <track> <via> <drill> <out>`), never committed:

| control | artifacts | result |
|---|---|---|
| DIRTY probe (0.0889 / 0.25 / 0.15) as `bs_v1_routed` + CLEAN probe (0.20 / 0.60 / 0.30) as `bs_v1_routed_strict` | correct | **16 pass, 0 FAIL** — both F checks PASS with their measured minima printed |
| same two probes **swapped** | wrong polarity | **14 pass, 2 FAIL** — `meets JLC floors: True (expected False)` etc. |

So the checks are neither permanently red nor permanently green: they can pass, and they can fail, on
the right input. The probes were then deleted and `tracker/hardware/base_station/output/` re-checked to
contain only `.bs_v1_scaffold.kicad_pcb` — **no fabricated board was committed, and none was left on
disk at a path a future run could resolve.**

## One more site of the same check — deliberately left failing

`tracker/hardware/tests/test_v9_board_invariants.py` §5 guards the **same** property for the **same**
board and prints `FAIL base-station strict route exists / no output/bs_v1_routed_strict.kicad_pcb --
re-route with --escalation off`. That is a **loud** failure naming the same cause and the same clear
path, not a silent skip, so it complies with the rule as written. It is **not** converted to a waiver
here for two reasons: that file is the hub-invariant suite (out of this task's scope, and the brief says
not to modify hub-related files), and its non-zero exit is **honest** — the artifact genuinely does not
exist. It is recorded here so the next reader can reconcile the two representations (WAIVED in the
netlist gate, FAIL in the invariant gate) instead of reading them as a contradiction. If a future change
wants one voice, the right fix is to make that file's §5 read the **same** waiver record, not to
constant-fold the string.

## Reproduce

```bash
cd /home/c08r4d0r/worktrees/hub-fchecks        # or the pr/hub-milestone worktree

# the two checks, waived loudly
~/venvs/kicad/bin/python tracker/hardware/tests/test_netlist_integrity.py
~/venvs/kicad/bin/python tracker/hardware/tests/test_netlist_integrity.py --strict-waivers   # exit 1

# the absence itself
git log --all --oneline -- '*bs_v1_routed.kicad_pcb'        # -> no output
git check-ignore -v tracker/hardware/base_station/output/bs_v1_routed.kicad_pcb
find / -name 'bs_v1_routed*.kicad_pcb' 2>/dev/null          # -> no hits

# the state that makes the waiver honest
~/venvs/kicad/bin/python -c "import pcbnew; b=pcbnew.LoadBoard('tracker/hardware/base_station/base_station_v1_placed.kicad_pcb'); print(len(list(b.GetFootprints())), len(list(b.GetTracks())), b.GetNetCount())"
find . -name '*.kicad_sch' | grep base_station              # -> no output
```

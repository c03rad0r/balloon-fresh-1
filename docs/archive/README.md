# `docs/archive/` — superseded documents

**Purpose:** keep a superseded document's *address and history* without letting stale prose read as
current. Nothing here is authoritative; nothing here may be cited as a live decision.

This directory uses the repo's existing archive convention (`archive/README.md` at the repo root, and
`docs/hardware-reference/`-style pointer stubs): a superseded file is **moved, never deleted**, and the
move is recorded in a header block on the file itself.

## The rule for this directory

| | |
|---|---|
| **What goes here** | A doc that says about **itself** that it is superseded / obsolete / withdrawn / retracted / historical, **and** for which a successor can be named from evidence in the repo. |
| **What does NOT go here** | A doc that merely *discusses* supersession (a triage of other branches, a "do not use this register value" note, a row marked superseded inside an otherwise live table). A marker inside body prose is not a document-level status. |
| **How to move something** | `git mv` the file here, then prepend the header block below. Update every referrer in the **same commit** (relative links and `docs/<name>` tokens in `docs/`, `tests/`, `tools/`, `scripts/`, `firmware/`, `AGENTS.md`, `README.md`). |
| **Where the record lands** | A retired doc that has a source-of-truth owner is indexed in `docs/`; this directory is storage. ADRs are **never** moved here — a superseded ADR is superseded by a newer ADR and stays in `docs/adr/`. |

## Header convention (required on every file moved here)

```markdown
> ## ARCHIVED — YYYY-MM-DD · <superseded | superseded in part | superseded generation>
>
> **Superseded by `<path/to/successor>`** — <the evidence: the successor's own supersedes line, or the
> sentence naming this file, quoted>. Where this file's own status line marks its content: <quote it>.
> Moved to `docs/archive/` on YYYY-MM-DD. Kept for provenance — do not cite as current.
```

Where **no successor exists**, the header must say so explicitly rather than invent one:

```markdown
> **Superseded by nothing on record — archived for provenance.**
```

A citation that resolves to nothing is the worst outcome of a reorganisation (`archive/README.md`,
"Why pointers instead of deletion"). The header states the supersession so the address and the reason
both survive.

## Files archived on 2026-10-17

| file | superseded by | evidence |
|---|---|---|
| `HANDOFF-SWD-NEXT-STEPS.md` | `docs/E80-SWD-DIAGNOSIS-2026-08-18.md` | successor's status line: *"ACTIVE (supersedes the SWD-disable theory in `HANDOFF-SWD-NEXT-STEPS.md`)"* |
| `PLAN-speed-optimization.md` | `docs/FLRC-512B-THROUGHPUT-AUDIT-2026-10-06.md` §1.1 (+ `sustained-throughput-results-2026-07-23.md`) | its own status: *"SUPERSEDED IN PART — the 1391 kbps baseline below is history"* |
| `PAYLOAD-WEIGHT-ESTIMATES.md` | `docs/analysis/MEASURED-MASSES.md`, `docs/analysis/CELL-MASS-MEASUREMENTS-2026-10-14.md` | its own *"⚠ SUPERSEDED 2026-10-14: the cells ARE 0.440 g each when measured"* |
| `flrc-optimization-comprehensive-plan-2026-07-16.md` | `docs/archive/PLAN-speed-optimization.md` + `docs/PLAN-range-tests.md` | its own UPDATE block: *"superseded by two focused, actionable plans"* |
| `handover-data-collaborator-2026-08-21.md` | `docs/handover-adaptive-sweep-2026-08-22.md` | successor names it *"Prior handover (2026-08-21, for reference)"* |
| `HANDOVER-speed-tests-2026-07-23.md` | `docs/HANDOVER-COMPLETE-2026-07-24.md` | successor names it the *"Original handover"* |
| `HANDOVER-sustained-throughput-2026-07-23.md` | `docs/HANDOVER-COMPLETE-2026-07-24.md` (via `HANDOVER-speed-tests-2026-07-23.md`) | named there as the *"Earlier handover"* |

Seven of the 40 loose docs the triage index flagged as self-marked were archived here. **The other 33 were
screened out**, each for a stated reason, because their marker sits in body prose or on one row of a live
table rather than in a document-level status. The screening decision — verdict and reason per doc — is in
the Stage 1 commit message and in `docs/REPO-TRIAGE-INDEX.md` (regenerate with
`python3 scripts/repo_triage.py`).

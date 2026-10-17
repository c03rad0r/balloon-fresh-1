# `docs/` — layout

`docs/` was reorganised in three separately-committed stages (branch `pr/repo-cleanup`):
1. **archive** — docs that mark themselves superseded moved to [`archive/`](archive/README.md), each with a header naming its successor.
2. **clusters** — the loose docs at the `docs/` root were filed into the directories below; every referrer was rewritten in the same commit as its move.
3. **contradictions** — see the dated notes in the affected records.

The measurement that made this cheap: of the 277 loose docs, 259 were linked from nowhere, so only ~18 moves needed referrer care.
The per-file inbound count is in [REPO-TRIAGE-INDEX.md](REPO-TRIAGE-INDEX.md) (regenerate with `python3 scripts/repo_triage.py --root docs --out docs`).

## Cluster directories

| directory | what belongs in it | docs moved in |
|---|---|---|
| `docs/balloon/` | pico-balloon scope and test results | 2 |
| `docs/base-station/` | base station, telco backhaul, tollgate decode | 3 |
| `docs/bench/` | bench console, task-chain specs, sweep/throughput results | 17 |
| `docs/design/` | design proposals | 2 |
| `docs/discovery/` | discovery-sync and adoption-roadmap records | 9 |
| `docs/e80-900mbl-02-eval/` | E80 STM32 + 900MBL-02 evaluation (existing home) | 4 |
| `docs/flight/` | flight checklists, bootsel/flashing, firmware prepare lists | 5 |
| `docs/flrc/` | FLRC (SX1280) radio: characterisation, throughput, sweeps, test results | 34 |
| `docs/handovers/` | session / track handover prompts and summaries | 18 |
| `docs/hardware-reference/` | component guides, inventory, wiring, soldering (existing home) | 6 |
| `docs/harmonized/` | harmonised bench runs and results | 4 |
| `docs/link/` | link budget, frequency plan, antenna, regulatory/licence notes | 7 |
| `docs/lr2021/` | LR2021 dual-radio research, SPI/protocol references, bandwidth codes | 15 |
| `docs/nostr/` | Nostr / relay / blossom / meshcore integration notes | 5 |
| `docs/pcb/` | PCB-level design and review (existing home) | 2 |
| `docs/plans/` | plans and proposals (existing home) | 20 |
| `docs/power/` | powerbank and dummy-load work | 2 |
| `docs/prestretch/` | pre-stretching and pressure protocols | 4 |
| `docs/range/` | range / outdoor link tests | 5 |
| `docs/recon/` | reconnaissance / security findings (existing home) | 4 |
| `docs/repo/` | repo-process records: changelog, branch triage, consolidation | 2 |
| `docs/rfa/` | RFA1 / RFA1b / RFA1c modules | 2 |
| `docs/rp2040/` | RP2040 vs ESP32 MCU assessment and bring-up | 8 |
| `docs/sdr/` | SDR tooling and captures | 2 |
| `docs/speed/` | speed-test plans and results | 2 |
| `docs/spi/` | SPI timing and protocol notes | 6 |
| `docs/status/` | point-in-time status reports and audits | 4 |
| `docs/sx1280/` | SX1280 datasheets and references (existing home) | 3 |
| `docs/walk-tests/` | walk-around / walk test procedures and QA | 5 |
| `docs/wing/` | wing structural / electrical / release work | 1 |

## Deliberately left at the `docs/` root

A doc stays at the root when a *machine* reads its path, because moving it would need an edit to the
reader (out of scope for a layout commit). Two kinds:

**Read by code** (tests, tools, generators, firmware config, `.kicad_sch`/`.net`/`.wrl` artifacts):

`2G4-LINK-BUDGET-ANALYSIS.md`, `3d-model-coverage-wing.md`, `ADR-range-sync-cvm.md`, `BALLOON-SWEEP-TOOL.md`, `BASE-STATION-PCBA-D14-FREEZE.md`, `BENCH-CONSOLE-SPEC.md`, `BRANCH-TRIAGE-2026-10-06.md`, `BUILD-SIZE-REPORT.md`, `CHANGELOG.md`, `COEXISTENCE-V9.md`, `DESIGN-contextvm-adaptive.md`, `DUAL-VARIANT-DESIGN.md`, `E80-FLASH-ACCESS-FINDINGS.md`, `E80-PRBS-VERIFY-2026-08-20.md`, `F33-MODULE-PLAN.md`, `FLIGHT-BOARD-AUTO-BOOTSEL.md`, `FLRC-512B-THROUGHPUT-AUDIT-2026-10-06.md`, `FRIDAY-DEMO-CHEATSHEET.md`, `FRIDAY-DEMO-HANDOVER-2026-08-29.md`, `HANDOVER-WING-RELEASE-AND-BYPASS-DIODE.md`, `INTEGRATION-ASSESSMENT.md`, `LINK-BUDGET-LICENCE-EXEMPT.md`, `LR2021-LESSONS-2026-09.md`, `MEASUREMENT-REQUEST-WING-RELEASE.md`, `P4.1-DMA-CHAINING-ZERO-COPY.md`, `PCB-HANDOVER-FOR-JLCPCB.md`, `PLAN-adaptive-sweep-firmware.md`, `PLAN-esp32-vs-rp2040-benchmark.md`, `PLAN-host-driven-bench.md`, `POWER-BUDGET-V9-D2BE.md`, `PRESTRETCH-OVERPRESSURE-INTERLOCK.md`, `RANGE-TEST-PLAN.md`, `RANGE-THROUGHPUT-PLAN.md`, `RF-EXPERIMENT-DESIGN-ANALYSIS.md`, `RFA1-ELRS-LR2021-DIFF-2026-10-12.md`, `RFA1b-FOLLOWUP-650KBPS-ZEROS-2026-10-14.md`, `RFA1b-PRAM-PATCH-VERDICT-2026-10-14.md`, `SECURITY-FINDINGS.md`, `SOFTWARE-PREPARE-LIST.md`, `STATUS-balloon-circuit-design.md`, `STATUS-balloon-nostr.md`, `STATUS-balloon-pow.md`, `STATUS-balloon-pre-stretching.md`, `STATUS-balloon-range-tests.md`, `STATUS-balloon-speed-tests.md`, `STATUS-balloon-tollgate.md`, `balloon-flight-lessons.md`, `balloon-options-analysis.md`, `balloon-pressure-test.md`, `balloon-test-results.md`, `blossom-design.md`, `bw-code-table.md`, `flrc-rx-verified-results-2026-07-16.md`, `guard-time-config-cvm-optimization-plan.md`, `inventory.md`, `lr2021-flrc-24ghz-datasheet-audit-2026-07-26.md`, `lr2021-spi-command-reference.md`, `lr2021-spi-protocol-reference.md`, `plan.md`, `power-sweep-results-2026-07-24.md`, `rca-fix-plan-20260821.md`, `uart-bridge-pin-verification.md`, `uart-telemetry-protocol.md`

**Read by the SSOT registry / generated** (edit `docs/ssot/parameters.json` first if these ever move):

- `v9-BOM.md` — generated by `scripts/gen_v9_bom.py` (fixed output path).
- `V9-RADIO-SITE-MATRIX.md`, `WING-TO-HUB-SOCKET-SPEC.md`, `hardware-design.md` — `scan[]`/`anchor` paths in `docs/ssot/parameters.json`.
- `REPO-TRIAGE-INDEX.md` / `.json` — generated by `scripts/repo_triage.py`.

Nothing was deleted: the `.md` count is preserved (base 683 + the generated index + the READMEs added here).

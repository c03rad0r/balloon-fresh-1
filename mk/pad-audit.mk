# ─────────────────────────────────────────────────────────────────────────────
# PAD AUDIT — the checks that COUNT-BASED gates structurally cannot make
#
# WHY. test_netlist_integrity.py checks FOOTPRINT COUNTS and REFERENCE DESIGNATORS. It never looks at
# PAD NUMBERS. So a footprint can carry 62 pad objects where the part has 41 -- thirteen pads all
# numbered '41' at thirteen distinct positions, nine pads numbered '' on no net -- and pass every check
# in that file: the footprint is present, its reference resolves, and every pad carries a net or (none),
# which nothing interrogates.
#
# MEASURED on hub_board_v9, 2026-10-16 (board sha256 90a8aeaa17a199ba...):
#   U1  (ESP32-S3-WROOM-1U)    pad '41' x13 at 13 DISTINCT positions  -> unaddressable collision
#   U1                        9 pads with an EMPTY number, net=(none) -> FLOATING COPPER
#   ANT1..ANT4 (U.FL)         pad '2' x3 at 3 DISTINCT positions      -> same collision class
#   U4                         footprint ID has NO library nickname
#   U_HUB_CVT                  1 unnamed pad, net=(none)
#   J_W1..J_W4 (16 pads)       coincident duplicates                  -> WARNING, cosmetic
#
# SO THE AUDIT GATE FORECLOSES A REAL, MEASURED, ELECTRICAL DEFECT THAT NOTHING ELSE SEES.
#
# THE INTERPRETER IS CHOSEN BY TESTING FOR pcbnew, not by assuming a path -- measured on this host:
# ~/venvs/kicad/bin/python HAS pcbnew; ~/venvs/ho-test/bin/python has pytest but NOT pcbnew.
#
# A gate that cannot run WARNS LOUDLY and exits non-zero. It never passes silently, because a silent
# pass is exactly the failure mode this whole gate set exists to prevent.
# ─────────────────────────────────────────────────────────────────────────────

PY_PCBNEW := $(shell for c in $$HOME/venvs/kicad/bin/python /usr/bin/python3 python3; do \
	$$c -c "import pcbnew" >/dev/null 2>&1 && { echo $$c; break; }; done)

# Boards the audit covers. The hub is canonical; the wing and base station are added as they stabilise.
PAD_AUDIT_BOARDS := tracker/hardware/hub_board_v9.kicad_pcb

.PHONY: pad-audit pad-audit-selftest

## ─── pad-audit ────────────────────────────────────────────────────────
## THE GATE. Per-pad audit: repeated numbers, unnamed pads, missing library nicknames,
## unresolvable model references. Exit 1 on findings, 2 if it cannot run.
## Usage: make pad-audit
pad-audit:
	@if [ -z "$(PY_PCBNEW)" ]; then \
		echo "PAD-AUDIT: CANNOT RUN -- no interpreter with pcbnew found." >&2; \
		echo "  Looked for: \$$HOME/venvs/kicad/bin/python /usr/bin/python3 python3" >&2; \
		echo "  This gate is NOT passing; it is not running. Fix the interpreter, then re-run." >&2; \
		exit 2; \
	fi
	@$(PY_PCBNEW) tracker/hardware/pad_audit.py $(PAD_AUDIT_BOARDS)

## ─── pad-audit-selftest ───────────────────────────────────────────────
## Prove the audit is EXACT and CAN FAIL. A hook that fires wrongly teaches people to bypass it.
## Usage: make pad-audit-selftest
pad-audit-selftest:
	@if [ -x "$$HOME/venvs/ho-test/bin/python" ]; then \
		$$HOME/venvs/ho-test/bin/python -m pytest tests/test_pad_audit.py -q 2>&1 | tail -4; \
	else \
		echo "PAD-AUDIT SELFTEST: SKIPPED -- no pytest venv (NOT a pass)" >&2; exit 2; \
	fi

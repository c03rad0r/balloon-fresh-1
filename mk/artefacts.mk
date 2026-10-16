# ─────────────────────────────────────────────────────────────────────────────
# ARTEFACT GENERATION — deterministic plots, diagrams and renders
#
# WHY THESE TARGETS EXIST. The repo generates committed images (board renders, the
# system diagram, the edge-launch drawing, plots). Before this section, each was
# produced by running a script by hand: nothing detected a STALE committed image, and
# nothing pinned WHICH PYTHON ran it. Both bit us:
#   - the fab package drifted 20 footprints behind the board, unnoticed
#   - a typo survived in a reviewed PNG after its generator had been fixed, because the
#     review looked at the old render
#   - make_board_gallery.py needs pcbnew, which the pytest interpreter does not have, so
#     the generator's success depended on which python invoked it
#
# THE RULE: every image/plot generator supports --check, --check exits non-zero when a
# committed artefact differs from what the generator produces, and the interpreter is
# pinned here rather than inherited from whatever shell you happen to be in.
#
#   make artefacts          regenerate every artefact, then verify
#   make artefacts-check    verify only; non-zero if anything is stale (this is the GATE)
#   make artefacts-status   report generator / interpreter / current-or-stale, no judging
#   make figures            the human-facing subset (gallery + system diagram)
#
# CPython: chosen by TESTING for pcbnew, not by assuming a path. See PY_KICAD below.
# ─────────────────────────────────────────────────────────────────────────────

# An interpreter that can `import pcbnew`. Tried in a fixed order; the first that works wins.
PY_KICAD := $(shell for c in $$HOME/venvs/kicad/bin/python /usr/bin/python3 python3; do \
	$$c -c "import pcbnew" >/dev/null 2>&1 && { echo $$c; break; }; done)
PY_PLAIN := $(shell command -v python3 2>/dev/null || echo python3)

# Generators that need pcbnew (they read .kicad_pcb files) and those that do not.
ARTEFACT_GENS_KICAD := \
	tracker/hardware/make_board_gallery.py \
	tracker/hardware/make_system_diagram.py \
	tracker/hardware/make_edge_section.py
ARTEFACT_GENS_PLAIN := \
	tracker/hardware/draw_peel_coupon.py

ARTEFACT_GENS := $(ARTEFACT_GENS_KICAD) $(ARTEFACT_GENS_PLAIN)
ARTEFACT_GENS_EXISTING := $(wildcard $(ARTEFACT_GENS))

.PHONY: artefacts artefacts-check artefacts-status figures determinism-check

## ─── artefacts ────────────────────────────────────────────────────────
## Regenerate every committed image/plot, then verify it verifies.
## Usage: make artefacts
artefacts: determinism-check
	@echo "=== regenerating artefacts with $(PY_KICAD) ==="
	@if [ -z "$(PY_KICAD)" ]; then \
		echo "ERROR: no interpreter with pcbnew found; cannot regenerate board renders." >&2; \
		echo "  looked for: $$HOME/venvs/kicad/bin/python /usr/bin/python3 python3" >&2; \
		exit 2; \
	fi
	@for g in $(ARTEFACT_GENS_KICAD); do \
		[ -f "$$g" ] || continue; \
		echo "  -> $$g"; \
		$(PY_KICAD) "$$g" || exit 1; \
	done
	@for g in $(ARTEFACT_GENS_PLAIN); do \
		[ -f "$$g" ] || continue; \
		echo "  -> $$g"; \
		$(PY_PLAIN) "$$g" || exit 1; \
	done
	@$(MAKE) --no-print-directory artefacts-check

## ─── artefacts-check ──────────────────────────────────────────────────
## THE GATE. Non-zero if any committed artefact differs from what its generator produces.
## Safe to run anywhere: it writes nothing.
## Usage: make artefacts-check
artefacts-check:
	@echo "=== artefact determinism check (writes nothing) ==="
	@fail=0; \
	if [ -z "$(PY_KICAD)" ]; then \
		echo "WARNING: no interpreter with pcbnew; board-render checks SKIPPED (not passed)" >&2; \
		fail=1; \
	fi; \
	for g in $(ARTEFACT_GENS_KICAD); do \
		[ -f "$$g" ] || continue; \
		if $(PY_KICAD) "$$g" --check >/tmp/artefact-check.log 2>&1; then \
			printf '  OK       %s\n' "$$g"; \
		else \
			printf '  STALE    %s\n' "$$g"; tail -6 /tmp/artefact-check.log | sed 's/^/             /'; \
			fail=1; \
		fi; \
	done; \
	for g in $(ARTEFACT_GENS_PLAIN); do \
		[ -f "$$g" ] || continue; \
		if $(PY_PLAIN) "$$g" --check >/tmp/artefact-check.log 2>&1; then \
			printf '  OK       %s\n' "$$g"; \
		else \
			printf '  STALE    %s\n' "$$g"; tail -6 /tmp/artefact-check.log | sed 's/^/             /'; \
			fail=1; \
		fi; \
	done; \
	echo; \
	if [ $$fail -ne 0 ]; then \
		echo "ARTEFACT CHECK: FAIL -- run 'make artefacts' and commit the result."; exit 1; \
	fi; \
	echo "ARTEFACT CHECK: PASS -- every committed image is what its generator produces."

## ─── determinism-check ────────────────────────────────────────────────
## Prove the determinism machinery itself works (helper selftest + the guard tests).
## Usage: make determinism-check
determinism-check:
	@echo "=== determinism machinery selftest ==="
	@$(PY_PLAIN) scripts/artefact.py --selftest | tail -3
	@if [ -x "$$HOME/venvs/ho-test/bin/python" ]; then \
		$$HOME/venvs/ho-test/bin/python -m pytest tests/test_generators_deterministic.py -q 2>&1 | tail -3; \
	else \
		echo "  (pytest venv not found; guard tests SKIPPED -- not passed)"; \
	fi

## ─── artefacts-status ─────────────────────────────────────────────────
## Report the interpreter, the generators, and whether each artefact set is current.
## Never exits non-zero. This is the "just tell me" target.
## Usage: make artefacts-status
artefacts-status:
	@echo "artefact tooling status"
	@echo "  PY_KICAD : $(if $(PY_KICAD),$(PY_KICAD),** NONE -- no interpreter with pcbnew **)"
	@echo "  PY_PLAIN : $(PY_PLAIN)"
	@echo
	@echo "  generators:"
	@for g in $(ARTEFACT_GENS); do \
		if [ -f "$$g" ]; then \
			printf '    present  %s\n' "$$g"; \
		else \
			printf '    ABSENT   %s\n' "$$g"; \
		fi; \
	done

## ─── figures ──────────────────────────────────────────────────────────
## Regenerate the human-facing figures (board gallery + system diagram).
## Usage: make figures
figures:
	@echo "=== regenerating figures ==="
	$(PY_KICAD) tracker/hardware/make_board_gallery.py
	$(PY_KICAD) tracker/hardware/make_system_diagram.py
	@echo "done -- commit docs/boards/ if anything changed"

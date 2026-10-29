# ---------------------------------------------------------------------------
# Interactive-routing support for the LoRa1280 site on hub v10.
#
# The hand-written router reached 7/9 and then hit two nets that need a human
# router: E28_DIO3 (congestion) and SPI1_SCK (geometry -- it cannot leave the
# pad without a fan-out). This file is the tooling half of the runbook at
# docs/runbooks/INTERACTIVE-ROUTING-LORA1280.md.
#
# Targets:
#   kicad-setup        install KiCad 9 + libraries + bindings (ansible, needs sudo)
#   kicad-verify       prove the install actually works before trusting it
#   lora1280-board     regenerate the 7/9 board deterministically
#   lora1280-open      open that board in the KiCad GUI
#   lora1280-status    nets routed / still unrouted
#   lora1280-drc       DRC with per-class counts against the baseline
#   lora1280-render    3D top/bottom renders
#   lora1280-verify    status + drc + render, and FAIL if any rule count is non-zero
# ---------------------------------------------------------------------------

KICAD_CLI   ?= kicad-cli
DISTRO_PY   ?= /usr/bin/python3
VENV_PY     ?= python3

LORA_BOARD  ?= tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb
# The UN-ROUTED swapped board. The router must start here: feeding it the already-routed board
# makes it re-route on top of existing copper and it scores 5/9 instead of 7/9 (measured).
LORA_SWAP   ?= tracker/hardware/hub_board_v10_lora1280_swap.kicad_pcb
LORA_E28    ?= tracker/hardware/hub_board_v10.kicad_pcb
LORA_OUT    ?= /tmp/lora1280

.PHONY: kicad-setup kicad-verify lora1280-swap lora1280-board lora1280-open \
        lora1280-status lora1280-drc lora1280-render lora1280-verify

kicad-setup: ## Install KiCad 9 + libraries + python bindings (ansible, needs sudo).
	ansible-playbook ansible/pcb-workstation.yml -K

kicad-verify: ## Prove the KiCad install works: version, pcbnew, 3D models, suite.
	@echo "== kicad-cli =="
	@$(KICAD_CLI) --version || { echo "FAIL: kicad-cli missing"; exit 1; }
	@v=$$($(KICAD_CLI) --version | head -1); case "$$v" in \
	  9.*) echo "ok: $$v";; \
	  *) echo "FAIL: need KiCad 9.x, got $$v"; \
	     echo "      Ubuntu 24.04 ships 7.x unless the KiCad PPA is added"; exit 1;; esac
	@echo "== pcbnew under distro python (NOT the venv) =="
	@$(DISTRO_PY) -c 'import pcbnew; print("ok:", pcbnew.Version())' \
	  || { echo "FAIL: pcbnew not importable under $(DISTRO_PY)"; exit 1; }
	@echo "== 3D model libraries =="
	@test -d /usr/share/kicad/3dmodels && echo "ok: /usr/share/kicad/3dmodels" \
	  || { echo "FAIL: no 3D library -- kicad-cli render is silently body-less"; exit 1; }
	@echo "== LoRa1280-specific tests (HARD gate) =="
	@mkdir -p $(LORA_OUT)
	@PYTHONPATH=/usr/lib/python3/dist-packages $(VENV_PY) -m pytest \
	  tests/test_lora1280_footprint.py tests/test_hub_lora1280_swap.py -q --no-header \
	  > $(LORA_OUT)/lora_tests.log 2>&1; rc=$$?; tail -2 $(LORA_OUT)/lora_tests.log; \
	  if [ $$rc -ne 0 ]; then \
	    echo "FAIL: LoRa1280 tests red (rc=$$rc) -- do not trust this board"; \
	    grep -E "^FAILED|Error" $(LORA_OUT)/lora_tests.log | head -5; exit 1; fi
	@echo "== full suite (INFORMATIONAL) =="
	@PYTHONPATH=/usr/lib/python3/dist-packages $(VENV_PY) -m pytest tests/ -q \
	  --continue-on-collection-errors 2>&1 | tail -2 || true
	@echo "   ^ 6 failures are PRE-EXISTING on origin/master (measured 2026-10-27, same list red"
	@echo "     on a pristine origin/master worktree before any of this branch's changes):"
	@echo "     test_c_host.py::TestFIPSTransport::test_fips_transport_host"
	@echo "     test_system_diagram_geometry.py::test_geometry_gate"
	@echo "     test_v10_connectivity.py::{test_registry_matches_board,"
	@echo "       test_lane_integrity_clean_board_passes, test_back_side_pads_are_checked}"
	@echo "     test_v10_hole_clearance.py::test_hole_clearance_clean_on_v10"
	@echo "     A NEW failure is still yours. Compare against this list, do not ignore it."

# --dy 1.5 is NOT cosmetic: at dy = 0 the 16x16 body overlaps U6's courtyard by 4.76 mm^2, which
# also produces 3 silk_overlap and an extra silk_over_copper (measured: 79 violations instead of 74).
# test_hub_lora1280_swap.py::test_placement_clears_the_neighbours fails without it.
lora1280-swap: ## Rebuild the un-routed swapped board from the E28 board.
	@mkdir -p $(LORA_OUT)
	cp $(LORA_E28) $(LORA_OUT)/swap_in.kicad_pcb
	$(DISTRO_PY) tracker/hardware/swap_u_e28_to_lora1280.py \
	    --board $(LORA_OUT)/swap_in.kicad_pcb --side F.Cu --rot 0 --dy 1.5 --apply
	cp $(LORA_OUT)/swap_in.kicad_pcb $(LORA_SWAP)
	@echo "wrote $(LORA_SWAP)"

lora1280-board: ## Regenerate the 7/9 board from the UN-ROUTED swap board (swap + router + rip-up).
	@mkdir -p $(LORA_OUT)
	@test -f $(LORA_SWAP) || { echo "FAIL: $(LORA_SWAP) missing -- run 'make lora1280-swap'"; exit 1; }
	$(DISTRO_PY) tracker/hardware/route_lora1280_ripup.py \
	    --board $(LORA_SWAP) --out $(LORA_OUT)/rebuilt.kicad_pcb --budget 300
	@echo "regenerated $(LORA_OUT)/rebuilt.kicad_pcb -- compare with $(LORA_BOARD)"
	@$(DISTRO_PY) tracker/hardware/tmp_probes/probe_net_alone.py || true

lora1280-open: ## Open the 7/9 board in the KiCad GUI (the interactive routing session).
	@test -f $(LORA_BOARD) || { echo "FAIL: $(LORA_BOARD) missing"; exit 1; }
	pcbnew $(LORA_BOARD) &
	@echo "Opened. Read docs/runbooks/INTERACTIVE-ROUTING-LORA1280.md section 3 first."

lora1280-status: ## Nets routed / still unrouted on the LoRa1280 interface.
	@$(DISTRO_PY) -c "import pcbnew; \
b=pcbnew.LoadBoard('$(LORA_BOARD)'); \
nets={'/SPI1_SCK','/SPI1_MOSI','/SPI1_MISO','/E28_CS_N','/E28_BUSY','/E28_RESET_N','/E28_DIO1','/E28_DIO2','/E28_DIO3'}; \
done={t.GetNetname() for t in b.GetTracks() if t.GetNetname() in nets}; \
print('routed  %d/9: %s' % (len(done), ', '.join(sorted(n[1:] for n in done)) or '-')); \
print('missing %d/9: %s' % (len(nets-done), ', '.join(sorted(n[1:] for n in nets-done)) or '-'))"

lora1280-drc: ## DRC with per-class counts; FAILS if clearance/shorting/mask-bridge is non-zero.
	@mkdir -p $(LORA_OUT)
	$(KICAD_CLI) pcb drc --format json --severity-all --output $(LORA_OUT)/drc.json $(LORA_BOARD) >/dev/null
	@$(VENV_PY) scripts/lora1280_drc_summary.py $(LORA_OUT)/drc.json

lora1280-render: ## 3D top + bottom renders into docs/fab/status/.
	@mkdir -p $(LORA_OUT) docs/fab/status
	$(KICAD_CLI) pcb render --side top --quality high --width 1800 --height 1500 \
	    --zoom 0.82 --background opaque \
	    --output docs/fab/status/lora1280-3d-top.png $(LORA_BOARD)
	$(KICAD_CLI) pcb render --side bottom --quality high --width 1800 --height 1500 \
	    --zoom 0.82 --background opaque \
	    --output docs/fab/status/lora1280-3d-bottom.png $(LORA_BOARD)

lora1280-verify: lora1280-status lora1280-drc lora1280-render ## Gate check before handing the board back.
	@echo "== hand-back checklist (runbook section 5) =="
	@echo "  [ ] 9/9 routed"
	@echo "  [ ] clearance / shorting / mask bridges = 0"
	@echo "  [ ] U_LORA1280 still at (53.000, 68.100), rot 0, F.Cu"
	@echo "  [ ] saved in place as $(LORA_BOARD)"

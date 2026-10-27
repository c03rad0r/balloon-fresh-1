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
LORA_SWAP   ?= tracker/hardware/hub_board_v10.kicad_pcb
LORA_OUT    ?= /tmp/lora1280

.PHONY: kicad-setup kicad-verify lora1280-board lora1280-open lora1280-status \
        lora1280-drc lora1280-render lora1280-verify

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
	@echo "== project suite =="
	@PYTHONPATH=/usr/lib/python3/dist-packages $(VENV_PY) -m pytest tests/ -q \
	  --continue-on-collection-errors 2>&1 | tail -3

lora1280-board: ## Regenerate the 7/9 LoRa1280 board (swap + independent router + rip-up).
	@mkdir -p $(LORA_OUT)
	@test -f $(LORA_SWAP) || { echo "FAIL: $(LORA_SWAP) missing"; exit 1; }
	$(DISTRO_PY) tracker/hardware/route_lora1280_ripup.py \
	    --board $(LORA_BOARD) --out $(LORA_OUT)/rebuilt.kicad_pcb --budget 300
	@echo "regenerated $(LORA_OUT)/rebuilt.kicad_pcb -- diff it against $(LORA_BOARD)"

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

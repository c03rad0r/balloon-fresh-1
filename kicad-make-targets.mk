# ============================================================================
#  KiCad inspection + ansible — Make targets
# ============================================================================
#  APPEND these to the root Makefile (they extend the existing hardware targets).
#
#  Everything here is INSPECTION. Nothing in this block writes to a board file.
#
#  Quick start:
#    make kicad-setup     # install KiCad 9 + tools the way this project needs
#    make inspect         # show every artifact you can open, with the command
#    make open-hub        # hub board in pcbnew
#    make open-hub-3d     # hub board in the 3D viewer (Alt+3 equivalent)
# ============================================================================

# ---- paths (override on the command line: make open-hub WT=~/other) ----
WT              ?= $(HOME)/worktrees/hub-v9-orderable
INSPECT_DIR     := $(WT)/tracker/hardware
HUB_PCB         := $(INSPECT_DIR)/hub_board_v9_d1c_routed.kicad_pcb
WING_PCB        := $(INSPECT_DIR)/wing_board/wing_board_v9.kicad_pcb
WING_NET        := $(INSPECT_DIR)/base_station/base_station_shack.net
MAST_NET        := $(INSPECT_DIR)/base_station/base_station_masthead.net
HUB_STEP        := $(WT)/docs/fab/hub-v9/hub_v9.step
WING_STEP       := $(WT)/docs/fab/wing-v9/wing_v9.step
HUB_GERBERS     := $(WT)/docs/fab/hub-v9
WING_GERBERS    := $(WT)/docs/fab/wing-v9/gerbers
# KiCad 9 gerber + drill extensions (NOT *.gbr — measured).
GERBER_GLOBS    := *.gtl *.gbl *.g1 *.g2 *.g3 *.g4 *.gts *.gbs *.gto *.gbo *.gm1 *.gbrjob
DRILL_GLOBS     := *.drl

ANSIBLE_INV     := $(WT)/ansible/inventory.ini
KICAD_PLAYBOOK  := $(WT)/ansible/kicad-workstation.yml
KICAD_VENV      ?= $(HOME)/venvs/kicad
TARGET          ?= localhost
BECOME_FLAGS    ?= -K

.PHONY: kicad-setup kicad-setup-remote kicad-check inspect \
        open-hub open-hub-3d open-wing open-wing-3d \
        open-hub-gerbers open-wing-gerbers open-hub-step open-wing-step \
        open-netlist kicad-drc-hub kicad-drc-wing kicad-libs kicad-help

# ---------------------------------------------------------------- ansible ----
kicad-setup: ## Install KiCad 9 + skidl + viewers on THIS machine (idempotent)
	ansible-playbook -i $(ANSIBLE_INV) $(KICAD_PLAYBOOK) $(BECOME_FLAGS)

kicad-setup-remote: ## Same, on TARGET=<host>. Usage: make kicad-setup-remote TARGET=cobrador
	ansible-playbook -i $(ANSIBLE_INV) $(KICAD_PLAYBOOK) $(BECOME_FLAGS) -e target=$(TARGET)

kicad-setup-dry: ## Dry run — show what the playbook WOULD change
	ansible-playbook -i $(ANSIBLE_INV) $(KICAD_PLAYBOOK) $(BECOME_FLAGS) --check --diff

kicad-check: ## Verify the workstation can actually do the work (no changes)
	@echo "=== capability check ==="
	@printf '%-24s' "kicad-cli";        kicad-cli version 2>/dev/null || echo "MISSING -> make kicad-setup"
	@printf '%-24s' "pcbnew (python)";  python3 -c 'import pcbnew; print(pcbnew.GetBuildVersion())' 2>/dev/null || echo "MISSING -> make kicad-setup"
	@printf '%-24s' "skidl (venv)";     $(KICAD_VENV)/bin/python -c 'import skidl; print(skidl.__version__)' 2>/dev/null || echo "MISSING -> make kicad-setup"
	@printf '%-24s' "eeschema (gui)";   command -v eeschema >/dev/null && echo present || echo MISSING
	@printf '%-24s' "gerbv";            command -v gerbv >/dev/null && echo present || echo "absent (optional)"
	@printf '%-24s' "freecad";          command -v freecad >/dev/null && echo present || echo "absent (optional)"
	@echo
	@echo "=== artifacts present in WT=$(WT) ==="
	@for f in "$(HUB_PCB)" "$(WING_PCB)" "$(WING_NET)" "$(HUB_STEP)"; do \
		if [ -f "$$f" ]; then echo "  OK      $$f"; else echo "  MISSING $$f"; fi; done

# --------------------------------------------------------------- inspect -----
inspect: ## List every artifact you can open, with its exact command
	@echo "================================================================================"
	@echo " INSPECTION MANIFEST"
	@echo " worktree: $(WT)"
	@echo "================================================================================"
	@echo
	@echo "-- PCB LAYOUT (pcbnew: routing, copper, DRC) --"
	@ls -la $(HUB_PCB) $(WING_PCB) 2>/dev/null || echo "  (missing — check WT=$(WT))"
	@echo "   make open-hub / make open-wing / make open-hub-3d / make open-wing-3d"
	@echo
	@echo "-- SCHEMATIC / NETLIST (eeschema) --"
	@ls -la $(WING_NET) $(MAST_NET) 2>/dev/null || echo "  (missing)"
	@echo "   make open-netlist"
	@echo
	@echo "-- 3D MODELS (STEP) --"
	@ls -la $(HUB_STEP) $(WING_STEP) 2>/dev/null || echo "  (missing)"
	@echo "   make open-hub-step / make open-wing-step"
	@echo
	@echo "-- FAB PACKETS (gerbers/drill/pos -> gerbv) --"
	@echo -n "   hub  gerber files: "; ls $(addprefix $(HUB_GERBERS)/,$(GERBER_GLOBS)) 2>/dev/null | wc -l
	@echo -n "   hub  drill files:  "; ls $(addprefix $(HUB_GERBERS)/,$(DRILL_GLOBS)) 2>/dev/null | wc -l
	@echo -n "   wing gerber files: "; ls $(addprefix $(WING_GERBERS)/,$(GERBER_GLOBS)) 2>/dev/null | wc -l
	@echo -n "   wing drill files:  "; ls $(addprefix $(WING_GERBERS)/,$(DRILL_GLOBS)) 2>/dev/null | wc -l
	@echo "   make open-hub-gerbers / make open-wing-gerbers"
	@echo
	@echo "-- REPORT OF RECORD --"
	@echo "   $(WT)/docs/BOARD-READINESS-REGISTER.md"
	@echo "   $(WT)/docs/CONTROLLED-EXCEPTION-TABLE-hub-v9.md"
	@echo "   $(WT)/docs/fab/hub-v9/PROVENANCE.txt   (board md5 + commit)"
	@echo "================================================================================"

# ------------------------------------------------------------- open files ----
open-hub: ## Open the hub board in pcbnew (routing/copper inspection)
	@test -f "$(HUB_PCB)" || { echo "missing: $(HUB_PCB)"; exit 1; }
	pcbnew "$(HUB_PCB)" &
	@echo "Opened hub in pcbnew.  Alt+3 inside pcbnew = 3D view."

open-wing: ## Open the wing board in pcbnew
	@test -f "$(WING_PCB)" || { echo "missing: $(WING_PCB)"; exit 1; }
	pcbnew "$(WING_PCB)" &

open-hub-3d: ## Open the hub board in the KiCad 3D viewer
	@test -f "$(HUB_PCB)" || { echo "missing: $(HUB_PCB)"; exit 1; }
	kicad "$(HUB_PCB)" --3dviewer 2>/dev/null || pcbnew "$(HUB_PCB)" &
	@echo "If the 3D viewer did not open: in pcbnew press Alt+3."

open-wing-3d: ## Open the wing board in the KiCad 3D viewer
	@test -f "$(WING_PCB)" || { echo "missing: $(WING_PCB)"; exit 1; }
	kicad "$(WING_PCB)" --3dviewer 2>/dev/null || pcbnew "$(WING_PCB)" &
	@echo "If the 3D viewer did not open: in pcbnew press Alt+3."

open-netlist: ## Open the base-station netlists (eeschema / text)
	@echo "SHACK netlist (orderable now):    $(WING_NET)"
	@echo "MASTHEAD netlist (post-LiteVNA):  $(MAST_NET)"
	@for f in "$(WING_NET)" "$(MAST_NET)"; do [ -f "$$f" ] && echo "--- $$f ---" && grep -c '(net ' "$$f" | sed 's/^/    nets: /'; done
	@eeschema "$(INSPECT_DIR)/base_station/base_station_schematic.kicad_sch" 2>/dev/null || \
	 echo "  (eeschema source not generated yet — the .net files are the netlists)"

open-hub-gerbers: ## Open the hub gerbers in gerbv
	@test -d "$(HUB_GERBERS)" || { echo "missing: $(HUB_GERBERS)"; exit 1; }
	gerbv $(addprefix $(HUB_GERBERS)/,$(GERBER_GLOBS)) $(addprefix $(HUB_GERBERS)/,$(DRILL_GLOBS)) &

open-wing-gerbers: ## Open the wing gerbers in gerbv
	@test -d "$(WING_GERBERS)" || { echo "missing: $(WING_GERBERS)"; exit 1; }
	gerbv $(addprefix $(WING_GERBERS)/,$(GERBER_GLOBS)) $(addprefix $(WING_GERBERS)/,$(DRILL_GLOBS)) &

open-hub-step: ## Open the hub STEP 3D model (freecad)
	@test -f "$(HUB_STEP)" || { echo "missing: $(HUB_STEP)"; exit 1; }
	freecad "$(HUB_STEP)" &

open-wing-step: ## Open the wing STEP 3D model (freecad)
	@test -f "$(WING_STEP)" || { echo "missing: $(WING_STEP)"; exit 1; }
	freecad "$(WING_STEP)" &

# ------------------------------------------------------------------ DRC ------
kicad-drc-hub: ## Re-run DRC on the hub (headless, JSON report)
	kicad-cli pcb drc --format json --output /tmp/drc_hub_make.json "$(HUB_PCB)" 2>&1 | tail -2
	@python3 -c "import json;d=json.load(open('/tmp/drc_hub_make.json'));print('unconnected:',len(d.get('unconnected_items',[])),'violations:',len(d.get('violations',[])))"

kicad-drc-wing: ## Re-run DRC on the wing (headless, JSON report)
	kicad-cli pcb drc --format json --output /tmp/drc_wing_make.json "$(WING_PCB)" 2>&1 | tail -2
	@python3 -c "import json;d=json.load(open('/tmp/drc_wing_make.json'));print('unconnected:',len(d.get('unconnected_items',[])),'violations:',len(d.get('violations',[])))"

kicad-libs: ## Show where the KiCad libraries live (for skidl explicit paths)
	@echo "symbols:    /usr/share/kicad/symbols  (($$$(ls /usr/share/kicad/symbols/*.kicad_sym 2>/dev/null | wc -l)) libs)"
	@echo "footprints: /usr/share/kicad/footprints"
	@echo "3dmodels:   /usr/share/kicad/3dmodels"
	@echo
	@echo "skidl note: pass FULL paths, e.g."
	@echo "  Part(\"/usr/share/kicad/symbols/Device.kicad_sym\", \"R\")"

kicad-help: ## List the kicad/inspection targets
	@grep -E '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | sed 's/:.*## /  -> /' | sort

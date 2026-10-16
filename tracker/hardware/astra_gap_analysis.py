#!/usr/bin/env python3
"""Astra gap analysis: what must be done before these boards can be ordered.

Inputs are MEASURED from the tree (gap_inventory.py) plus the visual state of the board that is closest
to orderable. The measured numbers below contradict the repo's own inventory document, which is stated
in the prompt so the reviewer can weigh which source to trust.

Writes the review to stdout AND to a file, so it can be committed.
"""
import base64
import json
import sys
import urllib.request

IMGS = ["/tmp/handoff_imgs/F.Cu.png", "/tmp/handoff_imgs/B.Cu.png", "/tmp/handoff_imgs/In1.Cu.png"]

PROMPT = """You are doing a GAP ANALYSIS for a hardware programme that wants to place a JLCPCB order.
Your job is to surface everything still required, in dependency order, and say HOW each item should be
done -- plus be explicit about what you cannot judge.

THE PROGRAMME: an end-to-end radio system where high-altitude balloons act as a "bent pipe" connecting
base stations via FLRC radio. The deliverable is 3D models, schematics, board designs and routed PCBs
for ALL boards, ready to order from JLCPCB.

WHAT IS MEASURED TODAY (from the tree, not from documentation):
  FLIGHT HUB v9    tracker/hardware/hub_board_v9.kicad_pcb
       59 nets total. The COMMITTED board has only 2 tracks on 1 net -- it is placed-only.
       A full route exists as a separate artifact: 834 tracks, 286 vias, 57 of 59 nets routed.
       The 2 unrouted nets (/SX1280_MOSI, /SX1280_SCK) are being hand-routed in a GUI.
       16 DRC errors, ALL `copper_edge_clearance`, all the J_W1..J_W4 wing-socket land sets meeting the
       board edge at 0.00 mm. These are edge-launched connectors by design (ADR-046/048): the pads must
       touch the edge to meet the wing tab. Zero involve any other net.
       Gerbers exist (56 files) and an assembled STEP model exists.
       Stackup: board is 0.6 mm 4-layer, chosen for balloon weight (ADR-028). NO stackup is declared,
       so the 50-ohm RF trace width is unknown by a factor of 3.7 across plausible builds.
  FLIGHT WING v9   tracker/hardware/wing_board/wing_board_v9.kicad_pcb
       6 nets total, 20 tracks, 8 vias, 4 of 6 nets routed. Assembled STEP exists.
  BASE STATION     tracker/hardware/base_station/base_station_v1_placed.kicad_pcb
       44 nets total. 0 tracks, 0 vias, 0 routed. A netlist exists
       (tracker/hardware/base_station/base_station_v1.net) but NO schematic file.
       This is the ground half of the bent pipe. It needs 4G/LTE (SIM7600E-H) and telco support.
  The repo's own inventory document (docs/fab/END-TO-END-BOARD-INVENTORY.md, dated 2026-10-14) claims
  there is no base-station board, no netlist and no assembled STEP for any board. ALL THREE CLAIMS ARE
  FALSE as measured above. Treat the measurements, not the document.

IMAGES: 1 = F.Cu, 2 = B.Cu, 3 = In1.Cu of the flight hub (the most advanced board).

ANSWER THESE, and say PLAINLY where you disagree with anything above:

1. GAP LIST. Every item still required before a JLCPCB order can be placed, for EACH of the three
   boards. Order them by dependency (what must precede what), not by difficulty.

2. FOR EACH GAP, HOW. What is the concrete method or decision needed? If a gap needs an operator
   decision rather than engineering work, say so.

3. THE 16 EDGE-CLEARANCE ITEMS. Are these genuinely non-blocking for an order, given they are an
   intentional edge-launched connector interface? If you think they still need action, what action?

4. THE UNDECLARED STACKUP. The RF route currently sits at the board's declared 0.20 mm. Is proceeding at
   0.20 mm acceptable for a first order, or is this a hard blocker? Give your reasoning.

5. THE BASE STATION. It has a netlist and 44 nets but no schematic file and no routing. What is the
   correct order of work to get it to the same state as the hub?

6. WHAT YOU CANNOT JUDGE from these images and this summary. Be specific -- list the checks that need a
   tool or a measurement rather than an opinion.

7. Finally: name the SINGLE item most likely to cause an order to be rejected or to produce a
   non-working board, and say why.

Finish with: VERDICT: <READY_TO_ORDER | NOT_READY | BLOCKED><one line of justification>
"""


def main():
    content = [{"type": "text", "text": PROMPT}]
    for p in IMGS:
        try:
            with open(p, "rb") as fh:
                content.append({"type": "image_url",
                                "image_url": {"url": "data:image/png;base64,"
                                                     + base64.b64encode(fh.read()).decode()}})
        except Exception as e:
            print(f"(skipping {p}: {e})")
    body = {"model": "gpt-6-astra",
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 3000}
    req = urllib.request.Request("http://localhost:9099/v1/chat/completions",
                                data=json.dumps(body).encode(),
                                headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=400) as r:
            d = json.loads(r.read())
    except Exception as e:
        print("FAILED:", type(e).__name__, str(e)[:400])
        return 1
    out = d["choices"][0]["message"]["content"]
    print("SERVED MODEL:", d.get("model"))
    print("=" * 78)
    print(out)
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w") as fh:
            fh.write(f"# Astra gap analysis\n\nServed model: {d.get('model')}\n\n{out}\n")
        print(f"\n(written to {sys.argv[1]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

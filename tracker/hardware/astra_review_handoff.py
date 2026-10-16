#!/usr/bin/env python3
"""Astra review of the GUI handoff board.

Sends three layer plots (F.Cu, B.Cu, In1.Cu) with the measured state, and asks for a spatial verdict on
whether the board is ready for the last two nets to be hand-routed. Reports the SERVED model id.

The questions are written to invite disagreement: the two wrong recommendations this session came from
me asserting a fix without asking the reviewer to falsify it, so this asks explicitly.
"""
import base64
import json
import sys
import urllib.request

IMGS = sys.argv[1:] or ["/tmp/handoff_imgs/F.Cu.png",
                        "/tmp/handoff_imgs/B.Cu.png",
                        "/tmp/handoff_imgs/In1.Cu.png"]

PROMPT = """You are reviewing a routed PCB before its last two nets are hand-routed in a GUI.

IMAGES: 1 = F.Cu, 2 = B.Cu, 3 = In1.Cu (internal ground plane). Green/red = copper, the thin outline = board edge.

BOARD: 70.15 x 71.65 mm, 4 copper layers, 0.6 mm FR4 (thin, for a high-altitude balloon weight budget).
Layer roles: F.Cu = signals + RF; In1.Cu = GND plane; In2.Cu = 3V3 plane; B.Cu = signals.

MEASURED STATE (from the board file, all independently verified):
- 834 tracks, 286 vias, 57 of 59 nets routed.
- ERRORS: 16, ALL of them `copper_edge_clearance`, and ALL of them the four wing-socket land sets
  J_W1..J_W4 meeting the board edge at 0.00 mm. These are edge-launched connectors by design
  (ADR-046/048) -- the pads must touch the edge to meet the wing tab. Zero involve any other net.
- starved_thermal: 0.
- NOT ROUTED: /SX1280_MOSI (U1.8 at (49.95,11.84) to U4.17 at (55.15,25.25), 14.38 mm) and
  /SX1280_SCK (U1.22 at (60.60,20.71) to U4.18 at (55.15,24.75), 6.79 mm).
  U1 = ESP32-S3 module, U4 = Semtech SX1280 2.4 GHz radio.
- A previous measurement found, at the U4 end of those nets: F.Cu allows only 1.05 mm of escape
  (blocked by a +3V3 track) while B.Cu allows 12 mm in 7 directions.

QUESTIONS -- answer each literally, and SAY SO PLAINLY if you disagree with any of it:

(A) Looking at the three plots, does the copper distribution look like a healthy routed board, or does
    something in the layout look WRONG to you?
(B) The plan is to route the last two nets on B.Cu because F.Cu is crowded near U4. Does image 2
    support that, or does B.Cu look crowded too?
(C) In1.Cu is the ground reference for the 2.4 GHz RF path. Does image 3 show a CONTINUOUS plane, or
    are there large gaps/splits that would break the RF return path?
(D) Is there anything visible that would change your mind about the board being ready for the last two
    nets to be routed by hand? Name a specific region or part if so.
(E) State ONE thing about this board that you CANNOT tell from these images, so the reader knows the
    limit of this review.

Finish with a line: VERDICT: <APPROVED | CHANGES_REQUESTED | PARTIAL>
"""


def main():
    content = [{"type": "text", "text": PROMPT}]
    for p in IMGS:
        with open(p, "rb") as fh:
            content.append({"type": "image_url",
                            "image_url": {"url": "data:image/png;base64,"
                                                 + base64.b64encode(fh.read()).decode()}})
    body = {"model": "gpt-6-astra",
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 1200}
    req = urllib.request.Request("http://localhost:9099/v1/chat/completions",
                                data=json.dumps(body).encode(),
                                headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            d = json.loads(r.read())
        print("SERVED MODEL:", d.get("model"))
        print("=" * 70)
        print(d["choices"][0]["message"]["content"])
    except Exception as e:
        print("FAILED:", type(e).__name__, str(e)[:400])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

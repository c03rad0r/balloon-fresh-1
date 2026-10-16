#!/usr/bin/env python3
"""Live vision test: does the gpt-6-astra lane actually read a PCB image, or only answer text?

Run as a FILE, not a heredoc, because heredoc quoting mangled the nested JSON on the first attempt.
Reports the SERVED model id (not the requested alias) and the literal answer.
"""
import base64
import json
import sys
import urllib.request

IMG = sys.argv[1] if len(sys.argv) > 1 else "/tmp/handoff_fcu.png"
MODEL = sys.argv[2] if len(sys.argv) > 2 else "gpt-6-astra"

with open(IMG, "rb") as fh:
    b64 = base64.b64encode(fh.read()).decode()

prompt = (
    "This is an F.Cu layer plot of a routed PCB. Answer literally in 2-3 sentences: "
    "(a) is there any visibly empty or unrouted region? "
    "(b) roughly what fraction of the board carries copper? "
    "(c) do you see any area where tracks appear to stop short?"
)

body = {
    "model": MODEL,
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}},
            ],
        }
    ],
    "max_tokens": 220,
}

req = urllib.request.Request(
    "http://localhost:9099/v1/chat/completions",
    data=json.dumps(body).encode(),
    headers={"Content-Type": "application/json"},
)
try:
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.loads(r.read())
    print("SERVED MODEL:", d.get("model"))
    print("ANSWER:")
    print(d["choices"][0]["message"]["content"][:1000])
except Exception as e:
    print("FAILED:", type(e).__name__, str(e)[:300])

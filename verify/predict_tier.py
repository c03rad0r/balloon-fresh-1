"""Predict the gate verdict for a candidate result text WITHOUT writing the DB.

Imports gate_engine read-only and calls classify_tier/board_tags against the
candidate text, so the tier claim is checked before any state change.
"""

import os
import sys

sys.path.insert(0, os.path.expanduser("~/.hermes/scripts"))
import gate_engine as ge  # noqa: E402

txt = open(os.path.expanduser("~/reports/.result-t_73c3244e.txt"), encoding="utf-8").read()

spec = ge.load_gates()
print("spec_error:", spec.get("__spec_error__", False))
print("known_tags:", sorted(ge.known_tags(spec)))

first = txt.splitlines()[0]
print("first_line:", repr(first))
tags = ge.tag_tokens(txt, ge.known_tags(spec))
print("tag_tokens:", tags)
print("tier:", ge.classify_tier("tollgate", tags, spec))

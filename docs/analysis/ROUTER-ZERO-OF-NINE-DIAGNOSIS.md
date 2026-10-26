# Router 0/9 — three hypotheses, two eliminated, one open question

Status: **UNRESOLVED.** Written 2026-10-26 after eliminating the two leading explanations for
`route_v10_astar.py` returning `routed 0 / failed 9` on the LoRa1280 interface.

## 1. Eliminated: the router treats the B.Cu pours as solid

`grep -i zone tracker/hardware/route_v10_astar.py` → **zero references.** The router has no zone
model at all. It cannot be blocked by a pour.

## 2. Eliminated: pad→net association is missing

The router discovers pads by scanning every footprint's pads and grouping by net code/name
(`build_world`, ~line 88). It then requires `len(uniq) >= 2` and routes `keys[0] → keys[1] → …`.

Its own failure message names the endpoints:

```
failed: ('/E28_DIO3', 'U1.34 -> U_LORA1280.2')
```

A net with no pads never reaches that message (`len(uniq) < 2` would `continue` silently). So the
pads **are** found, on the right nets, with the right designators. Hypothesis dead.

## 3. Open, and it is a question — not a bug claim

The router blocks a module's body only for references in a **hardcoded tuple**:

```python
KEEPOUT_REFS = ("U_E28",)
```

with the comment *"ONLY the E28 has a datasheet rule against routing beneath the module (E28
manual §4.1; ADR-118 line 22)"*.

The reference on this board is now `U_LORA1280`, so **the module keep-out no longer applies to
it.** Two readings, and I have not verified which is true:

- **(a) Correct as it stands** — if the LoRa128X datasheet has no §4.1-style rule, then copper
  under the module is legitimate and the new part should not be in that list. Nothing to fix.
- **(b) A silent regression** — if the rule does carry over, then the router may now route copper
  beneath a shielded radio module, and the DRC counts this session measured (`isolated_copper`,
  `clearance`) may be partly that.

**I have not verified which.** The LoRa128X Rev 2.2 sections read so far (pin definition §7,
communication antenna §8, mechanical §9) contain no under-module rule, but I have not read the
whole document for it. **Do not add `U_LORA1280` to `KEEPOUT_REFS` on a hunch** — that would block
a 16 × 16 mm slab in the middle of a congested board and could turn a 0/9 into a harder 0/9,
while looking like diligence.

This is the same defect shape the repo keeps recording: **a hardcoded identifier that silently
stops matching when the part changes.** Whether the consequence is benign here is exactly what
needs checking.

## 4. What is therefore still true

The A* fails between two cells whose coordinates map to real pads on real nets, with no zone
model and no body blocking on the new part. The cause is inside the search, not in the inputs —
most likely the start or goal cell is blocked, or the pad-centre is not landing in a free cell
after `unblock_own(..., reach=0.35)`.

Diagnosing it requires instrumenting the router, and any edit to `route_v10_astar.py` trips
`tests/test_router_grid_validator_agreement.py` — which is correct, and which is why this needs a
deliberate session rather than a tail-end guess.

## 5. Next, in order

1. **Instrument, don't guess.** A `--debug-net <name>` that prints, for one net: the start cell,
   the goal cell, whether each is `blocked`, and the number of blocked cells in the 5 × 5
   neighbourhood of each. That single print distinguishes "cell occupied" from "search exhausted".
2. **Read LoRa128X Rev 2.2 in full for an under-module rule.** Resolve §3 above with the document,
   not with intuition.
3. **Then** decide whether `KEEPOUT_REFS` needs the new reference.
4. Per ADR-140 D3, the placement gate stays **blocked** until a trial route completes 9/9 on a
   copy — and Astra's note stands: if this router stays suspect, use an independent router or
   hand-route the trial.

## 6. Reproduce

```bash
grep -c -i zone tracker/hardware/route_v10_astar.py      # 0
grep -n "KEEPOUT_REFS" tracker/hardware/route_v10_astar.py
/usr/bin/python3 tracker/hardware/route_v10_astar.py --append --order constrained \
  --nets "/SPI1_SCK,/SPI1_MOSI,/SPI1_MISO,/E28_CS_N,/E28_BUSY,/E28_RESET_N,/E28_DIO1,/E28_DIO2,/E28_DIO3"
```

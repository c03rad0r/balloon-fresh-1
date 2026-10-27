# Why the last two LoRa1280 nets will not route — and why more rip-up will not help

Status: **measured, negative result.** Written 2026-10-27 after the two-net rip-up pass returned
no improvement. This is the record of what was tried and what it proved, so the next session does
not repeat it.

Best achieved: **7 / 9** (`MOSI, MISO, BUSY, RESET, CS_N, DIO1, DIO2`), at the legal 0.30 mm
centre-to-foreign-copper margin, with **zero** new DRC violations versus the unrouted board.

## The control experiment that settles it

`tracker/hardware/tmp_probes/probe_net_alone.py` routes one net at a time on a board where **no
other new net has been routed** — only the pre-existing copper and every pad.

```
/SPI1_SCK    start free=True  goal free=True  alone-on-clean-board -> search exhausted
/E28_DIO3    start free=True  goal free=True  alone-on-clean-board -> ok 814 pts
/E28_DIO2    start free=True  goal free=True  alone-on-clean-board -> ok 625 pts
/SPI1_MOSI   start free=True  goal free=True  alone-on-clean-board -> ok 639 pts
```

Two different diseases, and only one of them is congestion:

- **`E28_DIO3` routes alone.** Its failure in the full set is congestion: other nets legitimately
  hold the corridor first. This is what rip-up is for.
- **`SPI1_SCK` cannot route even with the board empty.** Both endpoints test free, so the failure
  is not a blocked pad — it is that the two free regions are not connected for this net under the
  ownership model. **No amount of rip-up can fix that.** It needs a geometry change (an escape
  stub outside the pad, or a different pad row), not a scheduling change.

## What was tried, and the numbers

| attempt | result |
|---|---|
| easy-first ordering | 4 / 9 |
| hard-first ordering | 6 / 9 |
| one-net rip-up (`CS_N` out → `DIO2` in → `CS_N` back) | **7 / 9** |
| two-net rip-up, every near pair, both insertion orders | **7 / 9 — no improvement** |
| 8-net run with `SCK` excluded (`SKIP`) | 7 / 8 — `DIO3` still fails |
| 8-net run with `DIO3` given first claim (`FIRST`) | 6 / 8 — `DIO3` lands, `RESET_N` and `DIO2` fail instead |

The `FIRST` row is the informative one: giving `DIO3` the corridor does not create a net, it
**moves the failure** to two other nets. That is the signature of a genuinely saturated region,
not of a bad ordering.

## Conclusion, stated as a recommendation

**Stop extending this router.** Six orderings, one- and two-net rip-up, and an isolated-net control
have now been run. The remaining work is:

1. **`SPI1_SCK`** — a geometry problem. Cheapest real fix is a fan-out escape: start the route at a
   point clear of the U1 pad's clearance ring and connect it back with a short stub, which is what
   KiCad's router does automatically. My router starts at the pad centre and cannot leave.
2. **`E28_DIO3`** — congestion in a saturated region. KiCad's interactive router, or a rip-up that
   removes **three or more** nets and re-optimises them together, would be the way.

Neither is a good use of another hand-written router. ADR-140 D3 wants **9/9** before the
placement gate opens; 7/9 with clean copper is evidence the interface is routable, not a signed
gate.

## Reproduce

```bash
# the control that splits the two diseases
/usr/bin/python3 tracker/hardware/tmp_probes/probe_net_alone.py

# 7/9
/usr/bin/python3 tracker/hardware/route_lora1280_ripup.py \
    --board <swap-board>.kicad_pcb --out /tmp/r.kicad_pcb --budget 300

# the negative results
SKIP=/SPI1_SCK  ... --budget 280     # 7/8, DIO3 still out
SKIP=/SPI1_SCK FIRST=/E28_DIO3 ...   # 6/8, failure moves to RESET_N and DIO2
```

Refused throughout, and recorded so it cannot resurface: `RCLEAR=0.25` yields more nets only by
leaving the track edge 0.15 mm from foreign copper against a 0.20 mm rule.

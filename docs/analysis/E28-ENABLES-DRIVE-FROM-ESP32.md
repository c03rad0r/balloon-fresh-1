# E28 RX_EN / TX_EN — yes, we drive them from the ESP32 (correction)

Status: **correction of a wrong recommendation** (2026-10-26). Supersedes the "strap both to +3V3"
advice I gave, which contradicted the design of record.

---

## 1. The wrong recommendation, and why it was wrong

I recommended strapping `RX_EN` and `TX_EN` to `+3V3` on the grounds that "no free ESP32-S3 GPIO
remains". That came from **ADR-108**, which is the **v9** pin plan. I applied a v9 conclusion to hub
**v10** without checking. v10 has its own source of truth — `connectivity/v10_pinmap.reg` — and its
own open-items file.

The operator's question was the correct one: *why leave them floating if we can control them?*

## 2. The design of record already says: drive them

`docs/adr/123-*.md`:

- line 31 — the GPIO budget table contains **`E28 extras (RX_EN, TX_EN) | 2`**.
- line 38 — *"32 needed < 34 assignable → **fits with 2 spare**"*.
- line 40 — *"CS assignment avoids strapping pins (GPIO0 = J_PROG; **3/45/46 usable with care**)"*.

`connectivity/OPEN-ITEMS.md` — `OPEN-E28-EN`:

> **State:** unassigned. **ADR-123 budgeted two spare GPIOs for them but named no pads.**

So the intent was never to float or strap them. The item is open only because **nobody had resolved
which pads the two spare GPIOs are**. That is now done below.

## 3. Pad → GPIO map for `U1` (ESP32-S3-WROOM-1U), corroborated 20 ways

The board's `U1` footprint is synthetic and carries no pin-function data, so the map was derived from
the standard WROOM-1 pad numbering and then **cross-checked against the registry**: every assigned pad
agrees with ADR-108's GPIO table. Twenty independent matches, no contradictions — including
`IO19/IO20 = USB_DN/DP`, `IO11/IO12 = U3_IRQ/U3_CS_N`, `IO13 = F33_VSENSE`, `IO14 = SPI1_SCK`,
`IO38..IO41 = E28_BUSY/RESET/DIO1/DIO3`, `IO43/IO44 = GNSS TX/RX`, `IO47/IO48 = U3_BUSY/RESET_N`,
`IO21 = GNSS_PPS`, `IO1/IO2 = I2C`.

The eight `UNASSIGNED` pads therefore resolve to:

| pad | GPIO | status | usable for `RX_EN`/`TX_EN`? |
|---|---|---|---|
| 15 | `IO3` | strapping (JTAG source select) | with care — boot strap must still read correctly |
| 16 | `IO46` | strapping (ROM message) | with care — same |
| 26 | `IO45` | strapping (**VDD_SPI select**) | **no** — must be low at boot on a 3.3 V flash part |
| 27 | `IO0` | boot strap — **and J_PROG pin 6** | **no** — needed by `OPEN-16` |
| 28 | `IO35` | octal PSRAM (`-N8R8`) | **no** |
| 29 | `IO36` | octal PSRAM | **no** |
| 30 | `IO37` | octal PSRAM | **no** |
| 35 | `IO42` | **fully free, not a strap** | **yes — clean** |

This matches ADR-123's arithmetic: PSRAM eats 3, `IO0` is `J_PROG`, leaving exactly the "2 spare" it
counted — one clean (`IO42`) and two "usable with care" (`IO3`, `IO46`), which is precisely the
wording ADR-123 uses.

## 4. Recommended assignment

```
TX_EN  -> IO42  (U1 pad 35)   clean, no strap conflict
RX_EN  -> IO46  (U1 pad 16)   strapping pin, load is a high-Z module input
```

Rationale for putting `TX_EN` on the clean pin: it is the one that gates the **power amplifier**,
which is the large current consumer and the thing you actually want firmware able to shut off. If the
`RX_EN` strap risk is unwanted, the fallback is `RX_EN` tied high with a resistor — the LNA stays on,
which costs a little receive current and nothing else.

**Not yet applied to the board.** Both nets need to be created, routed, and re-graded; and the
`IO46` strapping behaviour should be confirmed from the WROOM-1 datasheet first (the same document
`OPEN-16` is blocked on). Two nets is a netlist change, so it belongs in a recorded assignment, not a
drive-by edit.

## 5. Two repository defects this uncovered

### 5.1 `OPEN-ITEMS.md` names the wrong pads for "the free I/O block"

`OPEN-17 / OPEN-25` says:

> *"Free an ADC-capable pin by relocating one digital assignment onto the **free IO22–IO34 block
> (currently `U1.26..U1.30`)**"*

That is wrong. `U1.26..U1.30` are **IO45, IO0, IO35, IO36, IO37** — two strapping pins and three
octal-PSRAM pins. None of them are in the IO22–IO34 range, and none are a "free block". This matters
because it is the document the registry points to for resolving open pins: a future session following
it would try to relocate a digital line onto pins that cannot take one.

### 5.2 `OPEN-16` can be closed — `GPIO0` is `U1` pad 27

`OPEN-16` says the WROOM-1U's `GPIO0` pad number "is not named by any in-repo source", and that an
earlier guess of pad 25 was wrong (pad 25 is `IO48`, which is `/U3_RESET_N`).

Given the corroborated map in §3, **`GPIO0` = pad 27** — which the registry already lists as
`U1.27 UNASSIGNED`, consistent with it being the `J_PROG` pin that dangles. That is why the pad is
free and why `J_PROG` pin 6 has nothing on it.

This still wants the datasheet table pasted in before it is treated as verified, but the registry
data now agrees with it rather than contradicting it.

## 6. For future sessions

- **`v10_pinmap.reg` is the pin source of truth for hub v10. ADR-108 is the v9 plan — do not apply its
  GPIO conclusions to v10.**
- `U1` pad → GPIO (WROOM-1 standard): `15=IO3 16=IO46 26=IO45 27=IO0 28=IO35 29=IO36 30=IO37 35=IO42`.
- `IO42` (pad 35) is the only clean spare GPIO on this board.
- The E28 enables are **not** to be strapped by default; ADR-123 budgets two GPIOs for them.

# Hub radio link — why the router fails, and what actually blocks it

**Date:** 2026-10-25 · **Board:** `hub_board_v10.kicad_pcb` @ `e74e1ea4`
**Status:** DIAGNOSIS. The radio link is **still unrouted**. This document records *why*, with
measurements, so nobody re-runs the same failing command.

---

## 1. The requirement

Operator: *"I need the board as a way to connect the LR2021 boards to the ESP32 for the first
flight."* That is 12 nets:

```
/SPI1_SCK  /SPI1_MOSI  /SPI1_MISO        ESP32 <-> radio SPI bus (4 pads each)
/E28_CS_N  /E28_BUSY   /E28_DIO1..3      E28 control + IRQ (2 pads each)
/E28_RESET_N
/SPI2_SCK  /F33_RESET_N /F33_IRQ         second radio select (2 pads each)
```

Measured pad positions (all four parts):

| part | position | pads on |
|---|---|---|
| `U1` ESP32-S3-WROOM-1U | (19.8, 42.3) | **F.Cu** |
| `U_E28` E28-2G4M27SX | (53.0, 69.0) | **B.Cu** |
| `U2` LoRa2021F33_2G4 | (29.8, 20.1) | — |
| `U3` LoRa2021_Castellated | (20.9, 16.7) | — |

**The E28 nets must change layer** — U1's pads are F.Cu, U_E28's are B.Cu. Every E28 route
therefore needs at least one via, which is where the difficulty starts.

## 2. What was tried, and how it failed

| attempt | result |
|---|---|
| router, 29 zero-copper nets, default budget (2 M expansions) | routed **0**, failed 20 |
| router, `/E28_CS_N` + `/E28_DIO2` only, **20 M** expansions, constrained order | routed **0**, failed 2 |

**A 10× expansion budget changed nothing.** That is the decisive result: the failures are not
search-limited. Something is physically in the way.

## 3. Measured obstruction (the probe)

`tracker/hardware/probe_corridor.py` reports every pad/track within a radius of the straight
line between two pads. For `/E28_CS_N` (`U1.10` → `U_E28.6`, 46.74 mm):

```
TRACK /USB_DN    19 hits, nearest 0.12 mm
TRACK /I2C_SCL   10 hits, nearest 0.01 mm   <- a continuous F.Cu run at y=53.5, x 33->51
PAD              7 hits, nearest 0.07 mm   (U_HUB_CVT.6 at 0.07 mm clear)
PAD GND          4 hits, nearest 0.17 mm
```

`/I2C_SCL` crosses the corridor at **0.01 mm**. The direct corridor is not tight; it is illegal.

## 4. The real blocker is PLACEMENT

Measured geometry of U1 and its surroundings:

```
U1 body   x  8.6 .. 29.6    y 32.4 .. 54.6
U1 pads   x 11.1 .. 28.6    y 33.9 .. 51.6
```

Every one of the 12 nets starts on a U1 pad at **y ≈ 51.65**, i.e. on U1's *bottom* edge, and
the destination is **below** (U_E28 at y=69, U2 at y=20.1-30.6, U3 at y=16.7).

To get below U1, a route must exit its bottom edge and travel down. Measured occupancy in the
three natural escape columns:

| corridor | what is in it |
|---|---|
| x ≈ 12, y 47–56 | `/F33_BUSY`, `/GNSS_RX`, `/GNSS_TX`, `/USB_DN`, **PAD:U1**, PAD:U5 |
| x ≈ 13.5, y 47–56 | `/GNSS_PPS`, `/GNSS_RX`, `/GNSS_TX`, `/USB_DN`, **PAD:U1** |
| x ≈ 15, y 47–56 | `/GNSS_PPS`, `/USB_DN`, **PAD:U1** |

and horizontally:

| corridor | what is in it |
|---|---|
| y ≈ 54–55.5, x 12–34 | `/GNSS_RX`, `/GNSS_TX`, PAD:J_PROG, PAD:U5 |
| y ≈ 56.8, x 12–48 | **CLEAR** |

So a clean horizontal channel *does* exist at **y ≈ 56.8**, and B.Cu at **x 47–48.6, y 56–62**
is entirely empty. **But there is no legal way DOWN to it from U1's bottom pads:** the left is
saturated, and to the right `/I2C_SCL` (y≈55) and `/U3_CS_N` form a solid row across
x ≈ 25–40 at y 52–57.

**Conclusion: the 12 radio nets cannot be routed without moving parts or re-assigning U1's
pins.** No amount of router tuning, net ordering, rip-up, or expansion budget fixes a placement
that leaves no escape corridor. This is the same class of finding AGENTS.md describes: an
operator asked to choose between routing options that were never measured.

## 5. What the options actually cost

| option | change | risk |
|---|---|---|
| **A. Move `U_E28` up** onto the y≈56.8 channel's right end | frees the long vertical leg; U1 still needs a short escape | low — U_E28 is a module on B.Cu with clear space around x47–58 |
| **B. Re-assign the radio nets to U1's TOP/right pads** | no routing change; U1 pads are GPIO-flexible | medium — pin map is in firmware; needs a pinmap + schematic + parity pass |
| **C. Move `U_HUB_CVT` / `U6`** clearing the x 40–47 corridor | opens the direct path | medium — those carry the harvester and are already routed |
| **D. Widen the board** | adds a routing channel | changes the outline (ADR-068 is 72×80) |

**Recommended: A then B**, because A is a placement nudge with measured-clear space, and B
removes the geometry problem entirely instead of fighting it. Both are design decisions, not
routing work.

## 6. What is NOT claimed

- This does **not** say the hub is unroutable. It says these 12 nets have no escape from U1's
  bottom edge as currently placed.
- The other ~26 signal nets were never attempted; they may be fine.
- No board change was made for this diagnosis. The board on disk is unchanged at 775 tracks /
  104 unrouted.

## 7. Reproduce

```bash
/usr/bin/python3 tracker/hardware/probe_corridor.py U1.10 U_E28.6
/usr/bin/python3 -c "import pcbnew;b=pcbnew.LoadBoard('tracker/hardware/hub_board_v10.kicad_pcb');\
print([ (f.GetReference(), f.GetBoundingBox().GetX()/1e6) for f in b.GetFootprints() if f.GetReference()=='U1'])"
```

# Runbook — route the last two LoRa1280 nets in KiCad's interactive router

**Why this exists.** A hand-written maze router got the LoRa1280 interface from 0/9 to **7/9** at
the legal 0.30 mm centre margin with zero new DRC violations. The remaining two nets do not yield
to that approach, and the measurements say why:

| net | status | cause |
|---|---|---|
| `E28_DIO3` | routes in **814 pts** alone on a clean board | **congestion** — other nets hold the corridor |
| `SPI1_SCK` | **fails even with the board empty** | **geometry** — the two free regions are not connected for this net |

KiCad's router solves both for free: it fans out of a pad before routing (which is exactly what
`SPI1_SCK` needs) and it rips up interactively while you drag (which is what `E28_DIO3` needs).
Everything else — footprint, swap, 7 routed nets, DRC baseline — is already committed.

**Gate this satisfies.** ADR-140 **D3** requires a route-completion trial, **9/9**, on a copy of the
real board, before the placement gate opens. Finishing these two closes it.

---

## 1. What you need installed

```bash
make kicad-setup        # ansible playbook: ansible/pcb-workstation.yml
make kicad-verify       # proves it actually works, before you trust it
```

`kicad-setup` installs KiCad 9 from the official repository, the symbol/footprint/3D libraries,
`gerbv`, `freecad`, `meshlab`, and the Python bindings. `kicad-verify` checks the four things that
have silently been wrong on this project before:

- `kicad-cli --version` answers (KiCad **9.x**, not 7.x — Ubuntu 24.04 ships 7.0.11 by default and
  a playbook using `state: present` will happily leave it there)
- `python3 -c 'import pcbnew'` works under the **distro** python (`/usr/bin/python3`), not the venv
- the 3D model libraries resolve (`/usr/share/kicad/3dmodels` exists)
- the project's own test suite is green

If you prefer not to use ansible:

```bash
sudo add-apt-repository -y ppa:kicad/kicad-9.0-releases
sudo apt-get update
sudo apt-get install -y --no-install-recommends kicad kicad-symbols kicad-footprints \
    kicad-templates kicad-packages3d gerbv python3-pip python3-venv
```

---

## 2. Open the board

```bash
make lora1280-open      # opens tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb
```

That file is the current state: `U_LORA1280` placed at **(53.000, 68.100), rotation 0, front (F.Cu)**,
seven nets routed, two missing. Do **not** open the plain `hub_board_v10.kicad_pcb` — that one still
carries the old `U_E28`.

**Three things you must not change**, or the work behind this file is thrown away:

1. **Do not move or flip `U_LORA1280`.** Moving a part invalidates routing done before it — this repo
   has already paid for that lesson once.
2. **Do not change the design rules.** Clearance **0.20 mm**, track **0.20 mm**, via **0.50 mm**,
   drill **0.30 mm**. A previous router "succeeded" by relaxing these to 0.175 and was rejected.
   If you are ever tempted to relax a rule to make a net fit, the honest answer is that the net
   does not fit.
3. **Do not run `--append` routing scripts** against this file; they have no zone model and will
   fight the GND pour. You are here precisely because a human router does better.

---

## 3. Set up the interactive router (once per session)

`Route ▸ Interactive Router Settings…`

| setting | value | why |
|---|---|---|
| Mode | **Highlight collisions** | you see the conflict before the copper exists |
| Allow DRC violations | **OFF** | a routed net that breaks a rule is not routed |
| Remove redundant tracks | ON | collapses the stubs the fan-out leaves |
| Optimize pad connections | ON | enters pads on the pad's own axis |
| Use mouse path / free angle | ON | 45° is fine; the two nets have no room for 90° only |

Then `Inspect ▸ Design Rules Checker` once on the untouched board and **write down the baseline**:

```
expected: 79 violations, 0 clearance, 0 shorting, 0 solder_mask_bridge
```

Those 79 are pre-existing (34 hole-size, 16 edge, 19 library, 7 silk, 3 thermal/courtyard). They are
not yours and not this task. What matters is that **you add none**.

---

## 4. The two nets

### 4a. `E28_DIO3` — congestion. Do this one first.

- From: `U1.34` → To: `U_LORA1280.2`
- This net routes in 814 points when the board is empty, so a path exists. It loses to copper that
  other nets legitimately own.
- Start at the module end and work back toward `U1`: the module end is open, the `U1` end is not.
- If a drag will not complete, hover the blocking track and press **`D`** to drag it out of the way;
  KiCad re-routes it immediately. That is the interactive rip-up, done by hand.
- Expect roughly 60–80 mm of track. If you are past ~150 mm you are going the long way and should
  back out and try the other side of `U1`.

### 4b. `SPI1_SCK` — geometry. The hard one.

- From: `U1.22` → To: `U_LORA1280.7`
- **This net cannot route from the pad centre.** With 0.5 mm pad pitch, the pad's own 0.30 mm
  clearance ring merges with its neighbours' into an unbroken wall. Both endpoints test free, and
  there is still no path — that is the signature.
- **The fix is a fan-out**: click the pad and drag **straight out, away from the `U1` body**, for
  1.5–2 mm before turning. Once outside the pad row, the wall ends and normal routing applies.
  KiCad does this automatically when you start a track on a pad and leave along the pad's axis —
  which is why this is a two-minute job for the tool and impossible for my router.
- If the outward direction is blocked, `Edit ▸ Move` a single neighbouring track aside with **`D`**
  (drag), route `SCK` through, then drag the other back. The router will refuse to leave a DRC
  violation, so if it accepts, it is legal.

---

## 5. Before you hand it back

```bash
make lora1280-verify     # DRC + net census + fresh renders, all in one
```

It prints, and fails on anything that is not clean:

- nets routed, and the names of any still unrouted
- violation counts **per class**, compared against the 79 baseline
- `clearance`, `shorting_items`, `solder_mask_bridge` — these three must stay **0**
- fresh 3D and 2D renders into `docs/fab/status/`

Then:

```bash
git checkout -b pr/lora1280-interactive
git add tracker/hardware/hub_board_v10_lora1280_7of9.kicad_pcb docs/fab/status/
git commit -m "route(hub): finish SPI1_SCK and E28_DIO3 for the LoRa1280 site"
git push origin pr/lora1280-interactive
```

and tell me the branch name. I will review the diff, re-grade at the original rules, and open the
placement gate per ADR-140 D3.

---

## 6. What I need from you, concretely

1. Run `make kicad-setup` (needs sudo), then `make kicad-verify` and paste the output if anything
   is not green.
2. Open the board with `make lora1280-open`.
3. Record the DRC baseline **before** touching anything (79 expected).
4. Route `E28_DIO3`, then `SPI1_SCK` with a fan-out from the pad.
5. Save — **in place**, same filename, so the diff is the routing only.
6. Run `make lora1280-verify` and check the three counts are still zero.
7. Push the branch and tell me its name.

That is the whole manual surface. Everything else — footprint, swap, the other seven nets, the 3D
body, the DRC baseline — is already done and merged.

---

## 7. If it goes wrong

| symptom | cause | what to do |
|---|---|---|
| router refuses every attempt near `U1` | pad pitch + clearance, as analysed | fan-out first, 1.5–2 mm, then turn |
| DRC says "clearance 1 mm" | your local **design rules** were reset by opening a fresh project | `Board Setup ▸ Constraints`, set 0.20/0.20/0.50/0.30 |
| module body missing in 3D | `.wrl` path is absolute (`tracker/hardware/footprints/lora1280/LoRa1280.wrl`) | re-attach in `Footprint Properties ▸ 3D Models` |
| board looks empty in 3D | `kicad-cli` exits 0 with no warning when a model does not resolve | run `make kicad-verify`; it checks this explicitly |
| a routed net vanishes after saving | zones refilled over it | `Edit ▸ Fill All Zones`, re-check |

---

## 8. Reproduce the automated work

```bash
make lora1280-board     # regenerate the 7/9 board from the swap + router, deterministically
make lora1280-drc       # DRC with per-class counts against the baseline
make lora1280-render    # 3D top/bottom + 2D routed/missing figure
```

Background and evidence: `docs/analysis/ROUTER-ZERO-OF-NINE-DIAGNOSIS.md`,
`docs/analysis/LORA1280-LAST-TWO-NETS.md`, `docs/adr/140-placement-approval-requires-route-trial.md`.

# KiCad / pcbnew environment — corrected 2026-10-25

**This file corrects a stale instruction in `AGENTS.md` "Environment gotchas" (first bullet).**
`AGENTS.md` is a protected agent-instruction file, so the correction is recorded here and the
AGENTS.md line needs an explicit operator edit (see §4).

---

## 1. What AGENTS.md currently says — and why it is wrong

> "- KiCad's Python bindings (`pcbnew`) load **only under `/usr/bin/python3.14`**, NOT the 3.11 the
> test suite uses."

**`/usr/bin/python3.14` does not exist on this host.** Measured:

```
$ ls /usr/bin/python3*
/usr/bin/python3
/usr/bin/python3-config
/usr/bin/python3.12
/usr/bin/python3.12-config
```

The only `python3.14`-named binary in the repo's own instructions fails like this:

```
$ /usr/bin/python3.14 tracker/hardware/route_v10_astar.py --help
timeout: failed to run command '/usr/bin/python3.14': No such file or directory
```

## 2. What is true (measured)

```
$ /usr/bin/python3 -c "import pcbnew; print(pcbnew.Version())"
9.0.9

$ /usr/bin/python3.12 -c "import pcbnew; print(pcbnew.Version())"
9.0.9
```

`pcbnew` lives in the **distro** python's site-packages (`/usr/lib/python3/dist-packages`), not in
the Hermes/venv interpreter the test suite uses.

**Working invocations:**

```bash
# run any pcbnew-using script
/usr/bin/python3 <script>.py

# run the project's pytest, which uses the venv interpreter but needs pcbnew importable
PYTHONPATH=/usr/lib/python3/dist-packages python3 -m pytest tests/ -q
```

## 3. The hazard that is still real

The third clause of the original note remains true and was never the problem: importing `pcbnew`
under an incompatible interpreter can **segfault** and take the whole pytest run with it. So:

- probe `pcbnew` in a **subprocess**, never in-process;
- treat a non-zero probe as "unavailable" and SKIP loudly, never as a pass.

`tests/test_wing_board_gates.py` and `tests/test_wing_sch_gates.py` both follow this pattern.

## 4. Behaviour changed as a result

`tracker/hardware/check_schematic_parity.py` used to `import pcbnew` once and return `None` on
failure, which made gates G3/G4 **REFUSE every board** under the venv interpreter. A permanent
refusal is indistinguishable from a gate nobody can run, so it now inserts
`/usr/lib/python3/dist-packages` and retries once before refusing.

Measured after the fix:

| target | result |
|---|---|
| wing interconnect | G1–G4 PASS, G5 skipped (no registry named), `PARITY: 0 failure(s)`, rc 0 |
| hub v10 (with `--registry`) | G1–G5 PASS, 58 nets both ways, rc 0 |
| `--self-test` | refusal paths still return rc 1 — **the gate can still fail** |

## 5. The AGENTS.md line to replace

Replace the first bullet under "Environment gotchas" with:

```
- KiCad's Python bindings (`pcbnew`) live in the DISTRO python's site-packages, not the venv the
  test suite runs in. CORRECTED 2026-10-25: this note used to name `/usr/bin/python3.14`, which does
  not exist on this host. Measured working form: `/usr/bin/python3 -c 'import pcbnew'` -> 9.0.9,
  and `PYTHONPATH=/usr/lib/python3/dist-packages python3 -m pytest ...` for the project's pytest.
  The real hazard is unchanged: importing `pcbnew` under the WRONG interpreter can segfault and kill
  the whole pytest run, so probe it in a subprocess, never in-process.
```

## 6. Reproduce

```bash
ls /usr/bin/python3*
/usr/bin/python3 -c "import pcbnew; print(pcbnew.Version())"
PYTHONPATH=/usr/lib/python3/dist-packages python3 -m pytest tests/test_wing_board_gates.py -q
python3 tracker/hardware/check_schematic_parity.py \
  --board tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb \
  --sch tracker/hardware/schematics/wing_interconnect/wing_interconnect.kicad_sch
```

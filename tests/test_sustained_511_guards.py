#!/usr/bin/env python3
"""Host tests for scripts/sustained_511.py — the guards only, no radio.

The script exists to measure 511 B sustained throughput. Two things must never
silently regress:

1. It must refuse LEN 512. 511 is the driver-documented maximum
   (lr20xx_radio_flrc_types.h:210) and the bench firmware clamps it
   (BENCH_START_LEN_MAX_FLRC 511u). A 512 request is a bug, not a variant.

2. It must refuse to run a tight-gap 511 B point without an explicit ack, because
   BENCH-CONSOLE-SPEC §7 says hosts MUST use GAP >= 40000 us for LEN > 256. The
   measurement is still worth taking, but the conflict with the written spec has
   to be acknowledged rather than tripped over.

Run:  python3 tests/test_sustained_511_guards.py
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "sustained_511.py"


def run(*args):
    """Invoke the script CLI. Returns (rc, combined output)."""
    p = subprocess.run(
        [sys.executable, str(SCRIPT), "--tx", "/dev/null", "--rx", "/dev/null", *args],
        capture_output=True, text=True, timeout=60,
    )
    return p.returncode, p.stdout + p.stderr


def test_len_512_is_refused():
    """512 is not a legal FLRC payload — the script must say so and stop."""
    rc, out = run("--lengths", "512")
    assert rc == 2, f"expected rc=2, got {rc}; out={out!r}"
    assert "512" in out and "not legal" in out.lower(), out


def test_len_511_is_allowed_past_the_length_guard():
    """511 must pass the length check (it may fail later on missing hardware,
    which is rc=3 — the point is that it is NOT rejected as illegal)."""
    rc, out = run("--lengths", "511", "--mode", "spec")
    assert rc != 2 or "not legal" not in out.lower(), out


def test_fast_mode_big_len_requires_ack():
    """--mode fast with LEN>256 contradicts spec §7 and needs --ack-spec-conflict."""
    rc, out = run("--mode", "fast", "--lengths", "511")
    assert rc == 2, f"expected refusal, got rc={rc}"
    assert "§7" in out or "40000" in out, out
    assert "--ack-spec-conflict" in out, out


def test_spec_mode_rejects_gap_below_40ms():
    """Spec mode must not accept a sub-40 ms gap for LEN>256."""
    rc, out = run("--mode", "spec", "--lengths", "511", "--gap", "5000")
    assert rc == 2, f"expected refusal, got rc={rc}"
    assert "40000" in out, out


def test_no_hardware_gives_clean_error_not_traceback():
    """Missing boards must produce guidance, not a serial traceback."""
    p = subprocess.run(
        [sys.executable, str(SCRIPT), "--tx", "/dev/nonexistent_xyz",
         "--rx", "/dev/nonexistent_xyz", "--lengths", "127", "--duration", "1"],
        capture_output=True, text=True, timeout=60,
    )
    out = p.stdout + p.stderr
    assert p.returncode == 3, f"expected rc=3, got {p.returncode}; out={out!r}"
    assert "Traceback" not in out, out
    assert "lsusb" in out, out


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)

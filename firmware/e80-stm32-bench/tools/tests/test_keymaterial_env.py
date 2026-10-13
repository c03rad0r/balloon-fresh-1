#!/usr/bin/env python3
"""test_keymaterial_env.py — env-driven loading tests for keymaterial.load_keys().

Card: "Write env-driven loading tests (happy path, hexkey form, missing vars)."
Module under test: ``firmware/e80-stm32-bench/tools/keymaterial.py``.

Scope
-----
Exactly one new file.  ``keymaterial.py`` is NOT modified, and nothing outside
``tools/`` is touched.  No key file is ever read and no real key is committed:
every secret used here is the decimal scalar 17 / 42 / 99 written as 64-char
hex, i.e. a test vector, never a live key.

Environment variables (the five names the module reads, per its own docstring
and its ``ENV_*`` constants — resolved from the module, not hard-coded here):

    E80_CLIENT_NSEC    nsec1... client key          (or)
    E80_CLIENT_HEXKEY  64-char-hex client key
    E80_SERVER_NSEC    nsec1... server key          (or)
    E80_SERVER_PUBKEY  x-only hex / npub1... server pubkey
    E80_RELAY_AUTH     optional relay-auth key

Provenance note on the briefed fixtures
---------------------------------------
The brief asked for fixtures from ``tools/tests/conftest.py``
(``TEST_HEX_A``, ``TEST_HEX_B``, ``TEST_HEX_SERVER``, ``nsec_from_hex``,
``set_env``, ``clear_env``, ``client_secrets``).  That conftest does not exist:
not on disk, not in any local or remote ref of this repo, and not in any other
worktree.  The task allows exactly one new file, so those fixture *names* are
defined locally below (same names and semantics), built on the module's real
constants and pytest's ``monkeypatch`` (the brief's mandated env mechanism).

Run (from ``firmware/e80-stm32-bench``):
    python -m pytest tools/tests/test_keymaterial_env.py -q
"""

from __future__ import annotations

import os
import pathlib
import re
import sys

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: pytest puts the *test file's* directory (tools/tests) on sys.path,
# not the tools/ dir that holds the module under test.
# ---------------------------------------------------------------------------
TOOLS_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import keymaterial as km  # noqa: E402  (needs the bootstrap above)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")

# The module is the single source of truth for the env names it reads.
ENV_CLIENT_NSEC = km.ENV_CLIENT_NSEC
ENV_CLIENT_HEXKEY = km.ENV_CLIENT_HEXKEY
ENV_SERVER_NSEC = km.ENV_SERVER_NSEC
ENV_SERVER_PUBKEY = km.ENV_SERVER_PUBKEY
ENV_RELAY_AUTH = km.ENV_RELAY_AUTH
ALL_ENV_NAMES = (ENV_CLIENT_NSEC, ENV_CLIENT_HEXKEY, ENV_SERVER_NSEC,
                 ENV_SERVER_PUBKEY, ENV_RELAY_AUTH)

# ---------------------------------------------------------------------------
# Independent x-only (BIP-340) reference.
#
# Deliberately NOT keymaterial._xonly_pubkey: asserting the module against
# itself would prove nothing.  This second implementation is anchored on the
# published BIP-340 test vector index 0 (seckey 0x00...03 ->
# f9308a019258c31049344f85f89d5229b531c845836f99b08601f113bce036f9) by
# test_reference_matches_published_bip340_vector below, then used as the
# expected-value oracle for every pubkey assertion in this file.
# ---------------------------------------------------------------------------
_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_GX = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
_GY = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8

#: BIP-340 vector 0 (a *pubkey*, not a secret — safe to embed).
_BIP340_VEC0_SECRET_HEX = "00" * 31 + "03"
_BIP340_VEC0_XONLY = (
    "f9308a019258c31049344f85f89d5229b531c845836f99b08601f113bce036f9"
)


def _ref_point_double(x, y):
    if y == 0:
        return 0, 0
    m = (3 * x * x) * pow(2 * y, _P - 2, _P) % _P
    nx = (m * m - 2 * x) % _P
    ny = (m * (x - nx) - y) % _P
    return nx, ny


def _ref_point_add(x1, y1, x2, y2):
    if x1 == 0 and y1 == 0:
        return x2, y2
    if x2 == 0 and y2 == 0:
        return x1, y1
    m = (y2 - y1) * pow(x2 - x1, _P - 2, _P) % _P
    nx = (m * m - x1 - x2) % _P
    ny = (m * (x1 - nx) - y1) % _P
    return nx, ny


def _ref_xonly(secret_hex: str) -> str:
    """x-only secp256k1 pubkey of a 32-byte secret (independent oracle)."""
    d = int.from_bytes(bytes.fromhex(secret_hex), "big")
    if not 1 <= d < _N:
        raise ValueError("test scalar out of secp256k1 range")
    rx, ry = 0, 0
    for bit in bin(d)[2:]:
        rx, ry = _ref_point_double(rx, ry)
        if bit == "1":
            rx, ry = _ref_point_add(rx, ry, _GX, _GY)
    return format(rx, "064x")


# ---------------------------------------------------------------------------
# Fixtures / constants (names as briefed; see provenance note above).
# ---------------------------------------------------------------------------
def _secret_hex(scalar: int) -> str:
    return format(scalar, "064x")


TEST_HEX_A = _secret_hex(17)        # well-behaved client key
TEST_HEX_B = _secret_hex(42)        # second client key (re-read / rotation)
TEST_HEX_SERVER = _secret_hex(99)   # server key material

_BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32_GENERATOR = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)


def _bech32_polymod(values):
    chk = 1
    for value in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ value
        for i in range(5):
            chk ^= _BECH32_GENERATOR[i] if ((top >> i) & 1) else 0
    return chk


def _bech32_hrp_expand(hrp):
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def nsec_from_hex(hex_secret: str) -> str:
    """The bech32 ``nsec1...`` form of a 32-byte secret."""
    acc, bits, data5 = 0, 0, []
    for byte in bytes.fromhex(hex_secret):
        acc = (acc << 8) | byte
        bits += 8
        while bits >= 5:
            bits -= 5
            data5.append((acc >> bits) & 31)
    if bits:
        data5.append((acc << (5 - bits)) & 31)
    polymod = _bech32_polymod(_bech32_hrp_expand("nsec") + data5 + [0] * 6) ^ 1
    checksum = [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]
    return "nsec1" + "".join(_BECH32_CHARSET[d] for d in data5 + checksum)


#: Every secret string this suite uses, in both spellings the brief names.
#: Leak assertions check absence of ALL of these.
client_secrets = (
    TEST_HEX_A,
    TEST_HEX_B,
    TEST_HEX_SERVER,
    nsec_from_hex(TEST_HEX_A),
    nsec_from_hex(TEST_HEX_B),
    nsec_from_hex(TEST_HEX_SERVER),
)

EXPECTED_PUBKEY_A = _ref_xonly(TEST_HEX_A)
EXPECTED_PUBKEY_B = _ref_xonly(TEST_HEX_B)
EXPECTED_PUBKEY_SERVER = _ref_xonly(TEST_HEX_SERVER)

#: A relay-auth secret (optional key; the module stores it verbatim).
RELAY_AUTH_NSEC = nsec_from_hex(_secret_hex(1234))


def set_env(monkeypatch, **values) -> None:
    """Set env vars via monkeypatch (``None`` unsets).  The only key source."""
    for name, value in values.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)


def clear_env(monkeypatch) -> None:
    """Remove every env name the module reads (monkeypatch auto-restores)."""
    for name in ALL_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """No key env var leaks in from the host; monkeypatch restores on exit."""
    clear_env(monkeypatch)
    yield


def _assert_no_secret(text: str) -> None:
    """No secret string, in any spelling, appears in ``text``."""
    assert isinstance(text, str)
    for secret in client_secrets:
        assert secret not in text, "secret material leaked into: {!r}".format(text)
    for token in re.findall(r"[0-9a-fA-F]{64}", text):
        assert token.lower() not in {s.lower() for s in client_secrets}, (
            "64-char hex secret leaked into: {!r}".format(text))


def _set_valid_server_pair(monkeypatch) -> None:
    """A valid, agreeing server key pair."""
    set_env(monkeypatch,
            **{ENV_SERVER_NSEC: nsec_from_hex(TEST_HEX_SERVER),
               ENV_SERVER_PUBKEY: EXPECTED_PUBKEY_SERVER})


# ---------------------------------------------------------------------------
# Oracle self-check.
# ---------------------------------------------------------------------------
def test_reference_matches_published_bip340_vector():
    """The independent oracle reproduces the published BIP-340 vector."""
    assert _ref_xonly(_BIP340_VEC0_SECRET_HEX) == _BIP340_VEC0_XONLY
    # d = 1 -> the secp256k1 generator X coordinate.
    assert _ref_xonly(_secret_hex(1)) == format(_GX, "064x")


def test_test_keys_are_distinct_and_wellformed():
    assert _HEX64.match(TEST_HEX_A)
    assert len({TEST_HEX_A, TEST_HEX_B, TEST_HEX_SERVER}) == 3
    assert len({EXPECTED_PUBKEY_A, EXPECTED_PUBKEY_B, EXPECTED_PUBKEY_SERVER}) == 3


def test_module_reads_the_documented_env_names():
    """Pin the exact literal env names the contract documents.

    The rest of this suite resolves names through ``km.ENV_*`` so that it tracks
    the module, which means a *rename* of a literal would otherwise pass
    unnoticed.  This test is the detector: ``load_keys`` must read exactly
    ``E80_CLIENT_NSEC`` / ``E80_CLIENT_HEXKEY`` / ``E80_SERVER_NSEC`` /
    ``E80_SERVER_PUBKEY`` / ``E80_RELAY_AUTH``.
    """
    assert km.ENV_CLIENT_NSEC == "E80_CLIENT_NSEC"
    assert km.ENV_CLIENT_HEXKEY == "E80_CLIENT_HEXKEY"
    assert km.ENV_SERVER_NSEC == "E80_SERVER_NSEC"
    assert km.ENV_SERVER_PUBKEY == "E80_SERVER_PUBKEY"
    assert km.ENV_RELAY_AUTH == "E80_RELAY_AUTH"


# ---------------------------------------------------------------------------
# 1. Happy path.
# ---------------------------------------------------------------------------
def test_happy_path_nsec_yields_derived_xonly_pubkeys(monkeypatch):
    set_env(monkeypatch,
            **{ENV_CLIENT_NSEC: nsec_from_hex(TEST_HEX_A),
               ENV_SERVER_NSEC: nsec_from_hex(TEST_HEX_SERVER)})

    keys = km.load_keys()

    assert isinstance(keys, km.KeyMaterial)
    # shape: x-only, lowercase, 64 chars
    assert _HEX64.match(keys.client_pubkey), keys.client_pubkey
    assert _HEX64.match(keys.server_pubkey), keys.server_pubkey
    # equality against the independent oracle, not just shape
    assert keys.client_pubkey == EXPECTED_PUBKEY_A
    assert keys.server_pubkey == EXPECTED_PUBKEY_SERVER
    assert keys.client_pubkey != keys.server_pubkey


def test_happy_path_accepts_both_server_forms_agreeing(monkeypatch):
    set_env(monkeypatch,
            **{ENV_CLIENT_NSEC: nsec_from_hex(TEST_HEX_A)})
    _set_valid_server_pair(monkeypatch)

    keys = km.load_keys()

    assert keys.server_pubkey == EXPECTED_PUBKEY_SERVER
    assert keys.client_pubkey == EXPECTED_PUBKEY_A


# ---------------------------------------------------------------------------
# 2. Call-time read / no caching.
# ---------------------------------------------------------------------------
def test_env_is_read_at_call_time_not_cached(monkeypatch):
    set_env(monkeypatch,
            **{ENV_CLIENT_NSEC: nsec_from_hex(TEST_HEX_A),
               ENV_SERVER_NSEC: nsec_from_hex(TEST_HEX_SERVER)})
    first = km.load_keys()
    assert first.client_pubkey == EXPECTED_PUBKEY_A

    # rotate the client env var *after* the first call
    set_env(monkeypatch, **{ENV_CLIENT_NSEC: nsec_from_hex(TEST_HEX_B)})
    second = km.load_keys()

    assert second.client_pubkey == EXPECTED_PUBKEY_B
    assert second.client_pubkey != first.client_pubkey
    # server key untouched by the rotation
    assert second.server_pubkey == first.server_pubkey == EXPECTED_PUBKEY_SERVER

    # independent objects, not a shared/cached instance
    assert first is not second
    sentinel = "0" * 64
    first.client_pubkey = sentinel
    assert second.client_pubkey == EXPECTED_PUBKEY_B
    first.client_pubkey = EXPECTED_PUBKEY_A


def test_returned_objects_are_independent_not_aliased(monkeypatch):
    set_env(monkeypatch,
            **{ENV_CLIENT_NSEC: nsec_from_hex(TEST_HEX_A),
               ENV_SERVER_NSEC: nsec_from_hex(TEST_HEX_SERVER)})
    a1 = km.load_keys()
    a2 = km.load_keys()

    assert a1 is not a2
    assert a1 == a2                      # same values, distinct objects
    a1.server_pubkey = "f" * 64
    assert a2.server_pubkey == EXPECTED_PUBKEY_SERVER
    # repr of one never carries the other's state or any secret
    _assert_no_secret(repr(a2))
    assert EXPECTED_PUBKEY_A in repr(a2)


# ---------------------------------------------------------------------------
# 3. Alternate + conflicting forms.
# ---------------------------------------------------------------------------
def test_hexkey_form_matches_nsec_form(monkeypatch):
    set_env(monkeypatch,
            **{ENV_CLIENT_HEXKEY: TEST_HEX_A,
               ENV_SERVER_NSEC: nsec_from_hex(TEST_HEX_SERVER)})

    keys = km.load_keys()

    assert keys.client_pubkey == EXPECTED_PUBKEY_A
    assert _HEX64.match(keys.client_pubkey)


def test_conflicting_client_forms_raise_loud_error(monkeypatch):
    set_env(monkeypatch,
            **{ENV_CLIENT_NSEC: nsec_from_hex(TEST_HEX_A),
               ENV_CLIENT_HEXKEY: TEST_HEX_B,   # different key -> ambiguous
               ENV_SERVER_NSEC: nsec_from_hex(TEST_HEX_SERVER)})

    with pytest.raises(RuntimeError) as excinfo:
        km.load_keys()

    message = str(excinfo.value)
    # names both client variables ...
    assert ENV_CLIENT_NSEC in message
    assert ENV_CLIENT_HEXKEY in message
    # ... and leaks no key material
    _assert_no_secret(message)


def test_agreeing_client_forms_are_accepted(monkeypatch):
    set_env(monkeypatch,
            **{ENV_CLIENT_NSEC: nsec_from_hex(TEST_HEX_A),
               ENV_CLIENT_HEXKEY: TEST_HEX_A,   # same key, both spellings
               ENV_SERVER_NSEC: nsec_from_hex(TEST_HEX_SERVER)})

    keys = km.load_keys()

    assert keys.client_pubkey == EXPECTED_PUBKEY_A


# ---------------------------------------------------------------------------
# 4. Missing variables.
#
# The module reports a *pair* of alternatives in one message ("<A> or <B> is
# not set"), so the brief's stricter clause — message contains the missing var
# and NONE of the other four — can only hold for names that are not one half of
# an "or" pair, i.e. for the client/server roles it must be read as "none of
# the OTHER ROLE's names".  Each case below therefore asserts:
#   (a) the message names the missing variable,
#   (b) it names no variable from a different role (no cross-contamination),
#   (c) it carries no secret material.
# test_missing_pair_messages_name_both_spellings_reconciliation pins (b)'s
# boundary explicitly (see below) — it is not silently relaxed.
# ---------------------------------------------------------------------------
_MISSING_CASES = (
    # (unset_name, extra_names_to_leave_unset, names_that_must_not_appear)
    (ENV_CLIENT_NSEC, (ENV_CLIENT_HEXKEY,), (ENV_SERVER_NSEC, ENV_SERVER_PUBKEY, ENV_RELAY_AUTH)),
    (ENV_CLIENT_HEXKEY, (ENV_CLIENT_NSEC,), (ENV_SERVER_NSEC, ENV_SERVER_PUBKEY, ENV_RELAY_AUTH)),
    (ENV_SERVER_NSEC, (ENV_SERVER_PUBKEY,), (ENV_CLIENT_NSEC, ENV_CLIENT_HEXKEY, ENV_RELAY_AUTH)),
    (ENV_SERVER_PUBKEY, (ENV_SERVER_NSEC,), (ENV_CLIENT_NSEC, ENV_CLIENT_HEXKEY, ENV_RELAY_AUTH)),
)


@pytest.mark.parametrize("unset_name,also_unset,forbidden", _MISSING_CASES,
                         ids=[c[0] for c in _MISSING_CASES])
def test_missing_variable_raises_and_names_it(monkeypatch, unset_name,
                                              also_unset, forbidden):
    # a fully-populated, otherwise-valid environment ...
    set_env(monkeypatch,
            **{ENV_CLIENT_NSEC: nsec_from_hex(TEST_HEX_A),
               ENV_CLIENT_HEXKEY: None,
               ENV_SERVER_NSEC: nsec_from_hex(TEST_HEX_SERVER),
               ENV_SERVER_PUBKEY: None,
               ENV_RELAY_AUTH: RELAY_AUTH_NSEC})
    # ... then unset exactly the variable under test (and, for the "or"-paired
    # names, its alternative — the only state in which it is the cause).
    for name in (unset_name,) + tuple(also_unset):
        set_env(monkeypatch, **{name: None})

    with pytest.raises(RuntimeError) as excinfo:
        km.load_keys()

    message = str(excinfo.value)
    assert unset_name in message, (
        "error for a missing {} must name it; got: {!r}".format(unset_name, message))
    for other in forbidden:
        assert other not in message, (
            "error for a missing {} must not name {}; got: {!r}".format(
                unset_name, other, message))
    _assert_no_secret(message)


def test_missing_client_key_names_a_client_variable(monkeypatch):
    """With no client material at all the error names the client variables."""
    set_env(monkeypatch,
            **{ENV_SERVER_NSEC: nsec_from_hex(TEST_HEX_SERVER),
               ENV_RELAY_AUTH: RELAY_AUTH_NSEC})

    with pytest.raises(RuntimeError) as excinfo:
        km.load_keys()

    message = str(excinfo.value)
    assert ENV_CLIENT_NSEC in message or ENV_CLIENT_HEXKEY in message
    assert ENV_SERVER_NSEC not in message
    assert ENV_SERVER_PUBKEY not in message
    assert ENV_RELAY_AUTH not in message
    _assert_no_secret(message)


def test_missing_pair_messages_name_both_spellings_reconciliation(monkeypatch):
    """Pin the module's real pair-naming error shape (brief reconciliation).

    ``load_keys`` reports an absent *role* as ``"<A> or <B> is not set"``.  For
    a missing client var the message therefore always names BOTH
    ``E80_CLIENT_NSEC`` and ``E80_CLIENT_HEXKEY``; likewise for the server pair.
    The brief's clause "contains NONE of the other four var names" is thus
    unsatisfiable for those four names — it is recorded here rather than
    weakened away, and the mismatch is reported with the deliverable.
    """
    # client pair
    set_env(monkeypatch, **{ENV_SERVER_NSEC: nsec_from_hex(TEST_HEX_SERVER)})
    with pytest.raises(RuntimeError) as excinfo:
        km.load_keys()
    client_message = str(excinfo.value)
    assert ENV_CLIENT_NSEC in client_message
    assert ENV_CLIENT_HEXKEY in client_message   # <-- the unsatisfiable clause
    _assert_no_secret(client_message)

    # server pair — clear the client pair's *server* env from the half above,
    # then remove both server names so only the server role is unset.
    set_env(monkeypatch,
            **{ENV_SERVER_NSEC: None,
               ENV_SERVER_PUBKEY: None,
               ENV_CLIENT_NSEC: nsec_from_hex(TEST_HEX_A)})
    with pytest.raises(RuntimeError) as excinfo:
        km.load_keys()
    server_message = str(excinfo.value)
    assert ENV_SERVER_NSEC in server_message
    assert ENV_SERVER_PUBKEY in server_message   # <-- same shape for the server
    _assert_no_secret(server_message)


def test_relay_auth_is_optional_not_required(monkeypatch):
    """``E80_RELAY_AUTH`` is optional: unset, ``load_keys`` still succeeds.

    The brief lists five "required" vars; the module documents relay auth as
    optional (``_clean(env.get(ENV_RELAY_AUTH)) or None``).  Pinned as the real
    contract so the discrepancy with the brief is explicit, not papered over.
    """
    set_env(monkeypatch,
            **{ENV_CLIENT_NSEC: nsec_from_hex(TEST_HEX_A),
               ENV_SERVER_NSEC: nsec_from_hex(TEST_HEX_SERVER),
               ENV_RELAY_AUTH: None})

    keys = km.load_keys()
    assert keys.client_pubkey == EXPECTED_PUBKEY_A
    assert keys.relay_auth is None

    # and when set, it is carried through verbatim
    set_env(monkeypatch, **{ENV_RELAY_AUTH: RELAY_AUTH_NSEC})
    assert km.load_keys().relay_auth == RELAY_AUTH_NSEC

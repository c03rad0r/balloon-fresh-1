# Report — MeshCore-style mesh transport core (`firmware/lib/meshcore`)

Task: implement and host-test a MeshCore-style mesh transport core (packet
framing, TTL flooding with duplicate suppression, ACK reliability,
fragmentation/reassembly) with a deterministic simulated mesh proving multi-hop
delivery, in the `feat/lib-meshcore` worktree, TDD with a proven counter-test.

Module path: `firmware/lib/meshcore/` (worktree `/home/c03rad0r/worktrees/lib-meshcore`).
Host: `cobrador`. Toolchain: plain `g++` 15.2.0, C++17, no PlatformIO.

## What was built

| file | role |
| --- | --- |
| `meshcodec.h` / `meshcodec.cpp` | L1 packet header codec: version, type, src, dst, pkt_id, hop_limit (TTL), frag_index/frag_count, payload_len + payload. Strict, all-or-nothing decode. |
| `mesh.h` / `mesh.cpp` | Transport core: `Node` (flood/TTL/dedup/ACK/frag state machine), `DupCache` (bounded seen-cache), `Reassembly` (presence-based), `RadioHalFake` (our own device model). |
| `meshsim.h` / `meshsim.cpp` | Deterministic simulated mesh: virtual clock, adjacency matrix, derived receiver sets, exact-delivery-set proof, stable digests, Graphviz DOT. |
| `test_meshcore.cpp` | The single translation unit with `main()`: 281 checks, plus the `--check` and `--dot` CLI. |
| `template_values.sh` | Single source of truth for every sizing constant. |
| `meshcore.h` | **Generated** from `template_values.sh` (checked in, verified in-test). |
| `scripts/gen_meshcore_header.py` | Renders `meshcore.h`; `--check` fails when it is stale. |
| `README.md` | Module documentation and semantics. |

`firmware/lib/Makefile` was **not** edited: it auto-discovers any directory with
`test_*.cpp`. The frozen contract `firmware/lib/radio_core/radio_hal.h` is
included as `../radio_core/radio_hal.h`; `radio_core.cpp` is **not** linked and
`make_radio_hal()` is deliberately never defined, so a test that accidentally
pulled in `radio_core` would fail at link time.

### Note on one `main()`

`firmware/lib/Makefile` compiles **every** `*.cpp` in a module into a **single**
executable, and `harness.h` stores its check counters in `static` (per-translation
unit) variables. Two `main()` translation units would each link but each keep its
own silent counters. All tests therefore live in `test_meshcore.cpp`, and the
library files define no `main()`. (This is why `meshsim.cpp` carries no tests.)

## Observed RED (real output, not reconstructed)

TDD order: tests first, run, observed failing, then implementation.

**RED #1** — only the tests + generated/template artifacts present, no
implementation at all:

```
== meshcore ==
meshcore/test_meshcore.cpp:19:10: fatal error: meshcodec.h: No such file or directory
   19 | #include "meshcodec.h"  // the compiled constants the template values must match
      |          ^~~~~~~~~~~~~
compilation terminated.
RESULT: FAILURES
make: *** [Makefile:16: test] Error 1
```

**RED #2** — headers present, implementations absent:

```
== meshcore ==
/usr/bin/x86_64-linux-gnu-ld.bfd: ... undefined reference to `balloon::mesh::Node::flush(unsigned int)'
/usr/bin/x86_64-linux-gnu-ld.bfd: ... undefined reference to `balloon::mesh::encode_header(...)'
/usr/bin/x86_64-linux-gnu-ld.bfd: ... undefined reference to `balloon::mesh::RadioHalFake::push_incoming(...)'
/usr/bin/x86_64-linux-gnu-ld.bfd: ... undefined reference to `vtable for balloon::mesh::RadioHalFake'
```

**RED #3** (first GREEN attempt, genuine implementation failures, later fixed):
`FAIL 9 of 278 checks failed` — an off-by-one in the TTL rule (a TTL of N
reached N+1 hops), a receive-only node never acquiring its radio (so
`receive()` refused with `NotAcquired`), a `Segfault` from dereferencing that
empty result, an ACK that could not be relayed to a neighbour, and a test that
addressed a topology *index* where a `NodeId` was meant.

## GREEN

```
== meshcore ==
  ok   281 checks passed
RESULT: all module tests green
```

`./build/meshcore.test --check` exits 0 and prints, per scenario, the deliveries,
the derived receiver set and a stable digest. Highlights from that real output:

```
== line6        ok=yes digest=33e811f49e59e7e5 ==
pkt=100 expect=2,3,4,5,6 got=2:4c494e4536;3:4c494e4536;4:4c494e4536;5:4c494e4536;6:4c494e4536 must_not=7,8
forwarded=5 duplicates=4 reroute=0 own_echo=1 corrupt=0
== line8_tight  ok=yes digest=d5dfc676242c178f ==
pkt=100 expect=2,3,4,5 got=2:5449474854;... must_not=6,7,8
forwarded=3 duplicates=2 reroute=0 own_echo=1 corrupt=0
== diamond      ok=yes digest=0484c3a3cf8fd33c ==
pkt=200 expect=2,3,4 ... forwarded=3 duplicates=3 own_echo=2 corrupt=0
== ring6        ok=yes digest=7d55d67eac00d9ea ==
pkt=300 expect=2,3,4,5,6 ... forwarded=5 duplicates=5 own_echo=2 corrupt=0
== stress line6   ok=yes digest=e1809fffd776ac51 ==
node1: 0 0 0 0 0 0   node2..node6: 1 1 1 1 1 1   node7/8: 0 0 0 0 0 0
deliveries_total=30 forwarded=30 duplicates=24
== ack_relay ok=yes digest=8680590593973271687 ==
pkt=700 delivered=1 acks_sent=1 acks_received=1 tx_attempts=1 retransmits=0 failures=0
CHECK: OK
```

Each multi-path topology reports `duplicates > 0`, so the exact-one-delivery
result is non-vacuous: real duplicates were produced and suppressed.

## Mandated sabotage counter-tests (all three observed failing)

Each sabotage was applied to the implementation, the suite re-run, the failure
observed, then the file restored from a pristine copy and the restore verified by
sha256 (`SABOTAGE` residue count: none).

**SABOTAGE 1 — duplicate-suppression check disabled**
(`mesh.cpp`: `if (cfg_.dedup_enabled && dup_.seen_or_add(...))` →
`if (false && dup_.seen_or_add(...))`):

```
  FAIL ...:128 [the same frame again is suppressed as a duplicate]  n.stats().rx_duplicates = 0, expected 1 = 1
  FAIL ...:129 [the same frame again is suppressed as a duplicate]  n.stats().delivered = 2, expected 1 = 1
  FAIL ...:176 [the duplicate of that broadcast is dropped, not re-flooded]  n.stats().forwarded = 2, expected 1 = 1
  FAIL ...:177 [the duplicate of that broadcast is dropped, not re-flooded]  n.stats().rx_duplicates = 0, expected 1 = 1
  FAIL ...:289 [dedup on: 5 identical frames -> exactly one delivery]  n.stats().delivered = 5, expected 1 = 1
  [sim] pkt 100 delivered 22 time(s); expected exactly 5
  [sim] pkt 100 reached node 2 4 time(s)
  [sim] pkt 100 reached node 3 8 time(s)
  FAIL ...:619 [sim/line6: a flood reaches 5 hops away, exactly once per node]  r.ok
  FAIL ...:626 [sim/line8_tight: ...]  r.ok
  FAIL ...:633 [sim/diamond: ...]  r.ok
```

The mesh storms exactly as predicted: the line6 flood delivered a packet 22
times where 5 were expected, one node receiving it 8 times.

**SABOTAGE 2 — let a truncated header parse**
(`meshcodec.cpp`: the `size < frame → Truncated` rejection removed):

```
  FAIL ...:579 [a truncated frame is dropped and never reaches the reassembler]  n.stats().drops_bad_frame = 0, expected 1 = 1
  FAIL ...:580 [a truncated frame is dropped and never reaches the reassembler]  n.stats().delivered = 1, expected 0 = 0
  FAIL ...:581 [a truncated frame is dropped and never reaches the reassembler]  !n.reassembly().has_completed()
  FAIL 3 of 281 checks failed
```

A one-byte-short frame was accepted and delivered as if complete.

**SABOTAGE 3 — unbounded ACK retry**
(`mesh.cpp`: the `attempts >= max_attempts → give up` branch removed):

```
  FAIL ...:373 [ACK: gives up after exactly max_attempts, never loops forever]  n.stats().tx_attempts = 6, expected 3 = 3
  FAIL ...:374 [ACK: gives up after exactly max_attempts, never loops forever]  n.stats().retransmits = 5, expected 2 = 2
  FAIL ...:375 [ACK: gives up after exactly max_attempts, never loops forever]  n.stats().failures = 0, expected 1 = 1
  FAIL ...:377 [ACK: gives up after exactly max_attempts, never loops forever]  n.next_wake_ms() = 17265, expected MESH_NO_WAKE = 4294967295
  FAIL 4 of 281 checks failed
```

The retry loop kept rescheduling (`next_wake_ms()` never reached "no wake"), i.e.
it no longer terminated.

Additional counter-tests in the suite (not part of the three above, but they keep
the safety properties honest): `dedup_enabled = false` on the same five frames
yields five deliveries (proving the check is what makes the count 1);
`run_stress_no_dedup(line6)` breaks the one-delivery-per-receiver invariant;
`Reassembly::corrupt_completions()` stays 0 when a duplicate fragment is offered
in place of a missing one; the generated-header check is shown to *fail* on a
mutated constant; and `DupCache` eviction is asserted directly (oldest evicted,
capacity unchanged after 100 inserts).

## Semantics implemented

* **Flood**: a broadcast is delivered locally and re-broadcast. A unicast frame is
  forwarded only towards a **direct neighbour**; a unicast to a node outside
  direct range is dropped (`drops_no_route`), never blindly flooded. Multi-hop
  reach is by flooding, since this core has no route table.
* **TTL**: `hop_limit` is decremented on every forward, and a frame is forwarded
  only while `hop_limit >= 2`, so a TTL of N reaches exactly N hops.
* **Own packets**: a frame whose `src` is our own id is our own flood returning and
  is dropped (`drops_own`), never delivered to our own application.
* **Dedup**: bounded ring keyed on `(src, pkt_id, frag_index)`; evicts, O(1)
  memory.
* **ACK**: single-fragment unicast `Data` arms a retransmit timer; a matching
  `Ack` cancels it; otherwise at most `max_attempts - 1` retransmits with
  exponential backoff (span bounded by `MESH_MAX_BACKOFF_MS`), then a reported
  failure. `Ack` frames are never flooded and never ACKed; an ACK may be relayed
  one hop to a direct neighbour, which is what lets a two-hop unicast be
  acknowledged (`run_ack_relay`: 1 attempt, 0 retransmits, 0 failures).
* **Fragmentation/reassembly**: presence-based — every fragment index must be
  present; completion is never decided by an arrival count, so a duplicate cannot
  stand in for a missing fragment.

## Honesty

**The simulated mesh is a model, not field evidence.** There is no radio in this
work: no RF hardware was touched, no packet was transmitted, and no real node
exists. Frames are relayed through an adjacency matrix on a host clock. These
tests prove the protocol **semantics** — whole-flood duplicate suppression,
hop-budget reach, the exact delivery set of a given topology, bounded retries,
and fragment integrity. They say **nothing** about RF range, airtime, packet
loss, interference, or the SX1280/LR2021 driver. Closing that gap requires
on-hardware testing, which has not been done here.

Two modelling choices are worth stating plainly because they make the tests
easier than reality, not harder:

1. **Zero relay latency.** A relayed frame is delivered with no per-hop delay, so
   one flood completes within a single virtual instant and is therefore
   deterministic. Real airtime would drift each node's clock independently.
2. **No loss and no interference.** Every frame in range is received. The suite
   tests retransmission by withholding an ACK, not by dropping an over-the-air
   frame.

Also worth stating: there is no "one byte wider header" template *bug* to fix
here — this is a new module. The `template_values.sh` → `meshcore.h` →
compiled-constants chain, with the host test diffing all three and a counter-test
that the check fails on drift, is deliberate single-source-of-truth hygiene for
the new code, not a repair of an existing defect.

## Delivery

Branch `feat/lib-meshcore`, worktree `/home/c03rad0r/worktrees/lib-meshcore`.
Four atomic commits, pushed to both remotes and verified by `git ls-remote`:

```
9f03641b  (pre-existing) feat(radio_core): freeze the radio HAL contract
59cb8905  test(meshcore): RED host suite + frozen interfaces
e2663e2c  feat(meshcore): strict L1 header codec with all-or-nothing decode
cf859d51  feat(meshcore): flood/TTL transport core with dedup, ACK retry, reassembly
9810f0de  docs(report): MeshCore transport core -- RED/sabotage evidence

local  : 9810f0de350d9a7340551cd3b4f49659415725b2
github : 9810f0de350d9a7340551cd3b4f49659415725b2   MATCH
ngit   : 9810f0de350d9a7340551cd3b4f49659415725b2   MATCH
```

Push notes, stated plainly:

* **ngit needed a PATH fix, and the first attempt genuinely failed.** The push
  first returned
  `git: 'remote-nostr' is not a git command. See 'git --help'.`
  `fatal: remote helper 'nostr' aborted session` (exit 128). The `nostr` remote
  helper is installed at `~/.local/bin/git-remote-nostr`
  (`/home/c03rad0r/.local/bin/git-remote-nostr`), which is not on the PATH of a
  non-interactive `ssh cobrador` session. Re-running with
  `export PATH="$HOME/.local/bin:$PATH"` pushed correctly. **No force was used.**
  The fix is in the invoking environment, not the repository: the worktree's git
  config was not modified.
* **ngit reached 1 of 2 relays.** The push reported
  `Published 1 state event to 1/2 relays (failed: nos.lol)`. The branch is
  published to `relay.ngit.dev`; the second relay did not accept the state event.
  That is a partial relay publication, not a silent success.
* The GitHub push reported `* [new branch] feat/lib-meshcore -> feat/lib-meshcore`
  and passed the repository's pre-push secret scanner
  (`✓ No secrets detected in full repo history.`).

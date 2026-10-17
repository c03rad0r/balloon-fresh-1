"""Append the board-ruling note to the drivers fragment (card t_73c3244e, run 396).

Append-only: asserts pre-bytes are a strict prefix. Records WHY the addendum's scope
is the radiolib-master record rather than the card-pinned path, per the manager's
already-landed decision on this card family. Sourcing/bookkeeping only.
"""

import hashlib
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAGMENT = os.path.join(REPO, "SCRATCH/lr2021-manifest-parts/drivers.md")

with open(FRAGMENT, "rb") as fh:
    pre = fh.read()
pre_sha = hashlib.sha256(pre).hexdigest()

note = """
---

## Scope note — why the addendum lives at a different provenance record

Bookkeeping only (no technical content). Recorded so the merge step and the manager
can audit the scope choice without re-deriving it.

The card `t_73c3244e` pins its read-only INPUT at `docs/lr2021-research/drivers/provenance.md`.
That path has never existed on any ref of this clone, and its producer card `t_c6dd8d63`
is terminal without having run. This is F1 above and it is not retracted.

The manager has already closed this family on the board:

- `t_6d053fcd` (done) archived 21 superseded LR2021 sourcing-duplicate cards, `t_c6dd8d63` among them, because the deliverable was published elsewhere.
- `t_72f4873c` (archived, superseded) records the decision in its own result: the RadioLib
  driver class is "DONE, snapshot @ 75e486a5 (7.7.1-dev), 15 LR2021 files + LR11x0 shared
  headers, provenance sha256 `3ecd892c57b17664f03b1856901bf95d83184fcf9901072ca53041034cdab26a`",
  and names `docs/lr2021-research/SOURCES.md` as the published manifest.

So the corpus of record for drivers is `docs/lr2021-research/radiolib-master/PROVENANCE.md`,
not the pinned path. The addendum above normalises that record so the merge step has the
drivers category in the mandated shape. It does not resurrect `t_c6dd8d63`, does not invent
entries for the absent path, and leaves F1's counts standing.

Verification for this pass (local only, no network):

- every size and sha256 in the addendum was recomputed from disk with `sha256sum` +
  `stat -c %s`; none was copied from the provenance record
- `verify/verify_drivers_fragment.py` -> `148/148 PASS, 0 FAIL`
- `docs/lr2021-research/` unmodified: `git status --porcelain -- docs/lr2021-research` empty
- the provenance record's own sha256 recomputed here equals the value `t_72f4873c` recorded
  (`3ecd892c...b26a`), so the record the addendum describes is the one the manager accepted
- append-only: the pre-existing 3851 B are a strict byte prefix of this file
  (prefix sha256 `0343a048fc669f07941dfc22743dca8ef14cc030ea746faa0d6f466c036a1a6b`)

No register-behaviour claims, no technical conclusions, no upstream prose paraphrased.
"""

with open(FRAGMENT, "ab") as fh:
    fh.write(note.encode("utf-8"))

with open(FRAGMENT, "rb") as fh:
    post = fh.read()

assert post.startswith(pre), "append-only violated"
post_sha = hashlib.sha256(post).hexdigest()
print(f"pre_bytes={len(pre)} pre_sha256={pre_sha}")
print(f"appended_bytes={len(note.encode('utf-8'))}")
print(f"post_bytes={len(post)} post_sha256={post_sha}")
print("strict_prefix=PASS")
sys.exit(0)

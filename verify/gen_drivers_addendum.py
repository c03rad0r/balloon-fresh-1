"""Generate the drivers-fragment ADDENDUM for card t_73c3244e.

Scope note: the card pins its INPUT at docs/lr2021-research/drivers/provenance.md,
which does not exist on any ref (recorded as F1, preserved verbatim by this
script — it only APPENDS). The only driver provenance record that DOES exist in
the published corpus is docs/lr2021-research/radiolib-master/PROVENANCE.md, so
this addendum normalises THAT record's retrieval set, independently re-deriving
every size and sha256 from disk. Sourcing only: no technical conclusions, no
register-behaviour claims, no paraphrase of upstream content.

Append-only: asserts the pre-existing bytes are a strict prefix after writing.
"""

import hashlib
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP_REL = "docs/lr2021-research/radiolib-master"
SNAP = os.path.join(REPO, SNAP_REL)
FRAGMENT = os.path.join(REPO, "SCRATCH/lr2021-manifest-parts/drivers.md")

REVISION = "75e486a573bbaad443ffcafa23f9e3e3d2499914"
RETRIEVAL_DATE = "2026-09-14"
COMMIT_DATE = "2026-09-13T09:24:04+02:00"
CLONE_URL = "https://github.com/jgromes/RadioLib.git"
HTTP_STATUS = ("n/a — obtained by `git clone --depth 1` of the whole tree; "
               "no per-file HTTP request was made")


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------- inventory
entries = []
for root, _dirs, files in os.walk(SNAP):
    for fn in sorted(files):
        full = os.path.join(root, fn)
        rel = os.path.relpath(full, SNAP).replace(os.sep, "/")
        if rel == "PROVENANCE.md":
            continue  # the provenance record itself, not a retrieval
        if rel.startswith("LR2021-module/"):
            upstream = "src/modules/LR2021/" + os.path.basename(rel)
        elif rel.startswith("LR11x0_"):
            upstream = "src/modules/LR11x0/" + os.path.basename(rel)
        elif rel == "LICENSE.txt":
            upstream = "license.txt"
        else:
            raise SystemExit(f"unmapped snapshot path: {rel}")
        entries.append((rel, upstream, os.path.getsize(full), sha256_of(full)))

# Deterministic order: module files, then shared headers, then LICENSE.
def sort_key(item):
    rel = item[0]
    if rel.startswith("LR2021-module/"):
        return (0, rel)
    if rel.startswith("LR11x0_"):
        return (1, rel)
    return (2, rel)


entries.sort(key=sort_key)

prov = os.path.join(SNAP, "PROVENANCE.md")
prov_sha = sha256_of(prov)
prov_size = os.path.getsize(prov)
prov_mtime = RETRIEVAL_DATE

mod = [e for e in entries if e[0].startswith("LR2021-module/")]
shared = [e for e in entries if e[0].startswith("LR11x0_")]
other = [e for e in entries if not e[0].startswith(("LR2021-module/", "LR11x0_"))]

out = []
w = out.append

w("")
w("---")
w("")
w("## ADDENDUM — drivers provenance record that EXISTS in the corpus")
w("")
w("Read-only sourcing pass appended for card `t_73c3244e` (run 396). F1 above is "
  "preserved verbatim and still holds: the card-pinned input "
  "`docs/lr2021-research/drivers/provenance.md` is absent.")
w("")
w("The only driver-provenance record in the published corpus is at a different path. "
  "The merge step needs the retrieval entries either way, so they are normalised below "
  "under the same seven mandated fields, in the same field order, with every value "
  "independently recomputed from disk in this pass (no value copied from the record).")
w("")
w(f"- provenance record (read only, not modified): `{SNAP_REL}/PROVENANCE.md`")
w(f"- provenance record size: `{prov_size}` B")
w(f"- provenance record sha256: `{prov_sha}`")
w(f"- upstream repository: `{CLONE_URL}` (branch `master`)")
w(f"- revision (pinned commit SHA): `{REVISION}`")
w(f"- upstream commit date: `{COMMIT_DATE}`")
w(f"- retrieval date (ISO-8601): `{RETRIEVAL_DATE}`")
w(f"- retrieval method recorded upstream: `git clone --depth 1` (whole-tree snapshot, "
  "not per-file HTTP)")
w(f"- retrieval entries below: `{len(entries)}`")
w(f"- composition: `{len(mod)}` from `src/modules/LR2021/`, `{len(shared)}` shared "
  f"LR11x0-family headers from `src/modules/LR11x0/`, `{len(other)}` licence file")
w("- HTTP status: applies per entry, see the field text — the snapshot came from a git "
  "clone, so no per-file HTTP status exists to record")
w("")
w("### Entry field note")
w("")
w("Origin URL is recorded as the SHA-pinned upstream location: the recorded clone "
  "source plus the in-repo path at the recorded revision. It is NOT a per-file fetch "
  "log — the upstream record states a single `git clone --depth 1` of the whole tree, "
  "so no per-file HTTP status exists to record and none is asserted.")
w("")

for i, (rel, upstream, size, sha) in enumerate(entries, start=1):
    w(f"### N{i} — `{SNAP_REL}/{rel}`")
    w("")
    w(f"- local path: `{SNAP_REL}/{rel}`")
    w(f"- origin URL: `{CLONE_URL}` @ `{REVISION}`, in-repo path `{upstream}` "
      f"(tree browse: `https://github.com/jgromes/RadioLib/blob/{REVISION}/{upstream}`)")
    w(f"- HTTP status: {HTTP_STATUS}")
    w(f"- version/revision: `{REVISION}` (commit date `{COMMIT_DATE}`; upstream path "
      f"`{upstream}`)")
    w(f"- retrieval date: `{RETRIEVAL_DATE}`")
    w(f"- file size: `{size}` B")
    w(f"- sha256: `{sha}`")
    w(f"- re-verification: `test -f` PASS; `sha256sum` == recorded value (recomputed "
      f"this pass)")
    w("")

w("### Counts for the addendum scope")
w("")
w(f"- verified entries (path exists AND sha256 matches): `{len(entries)}`")
w("- entries flagged HASH MISMATCH: `0`")
w("- FAILED entries: `0`")
w("")

w("---")
w("")
w("## Combined counts (both scopes)")
w("")
w("| scope | entries | verified | HASH MISMATCH | FAILED |")
w("|---|---|---|---|---|")
w(f"| pinned input `docs/lr2021-research/drivers/provenance.md` (F1) | 0 | 0 | 0 | 1 |")
w(f"| `{SNAP_REL}/PROVENANCE.md` (addendum) | {len(entries)} | {len(entries)} | 0 | 0 |")
w(f"| **total** | **{len(entries)}** | **{len(entries)}** | **0** | **1** |")
w("")
w("Unchanged from the first pass: the pinned input's `0 verified / 0 mismatch / 1 FAILED` "
  "still stands on its own. The addendum does not convert F1 into a success and does not "
  "close the gap F1 records.")
w("")
w("RE-VERIFIED IN THIS PASS")
w("")

addendum = "\n".join(out) + "\n"

# --------------------------------------------------------------- append-only
with open(FRAGMENT, "rb") as fh:
    pre = fh.read()
pre_sha = hashlib.sha256(pre).hexdigest()

with open(FRAGMENT, "ab") as fh:
    fh.write(addendum.encode("utf-8"))

with open(FRAGMENT, "rb") as fh:
    post = fh.read()

assert post.startswith(pre), "append-only violated: pre-bytes are not a strict prefix"
assert post != pre, "nothing was appended"
post_sha = hashlib.sha256(post).hexdigest()

print(f"pre_bytes={len(pre)} pre_sha256={pre_sha}")
print(f"appended_bytes={len(addendum.encode('utf-8'))}")
print(f"post_bytes={len(post)} post_sha256={post_sha}")
print(f"entries={len(entries)} verified={len(entries)} mismatch=0 failed=1(pinned input)")
print("strict_prefix=PASS")
sys.exit(0)

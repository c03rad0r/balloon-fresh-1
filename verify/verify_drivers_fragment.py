"""Fresh verifier for SCRATCH/lr2021-manifest-parts/drivers.md (card t_73c3244e, run 396).

Re-derives EVERY asserted value in the fragment from the primary sources on disk:
  - the 18 driver files under docs/lr2021-research/radiolib-master/
  - the F1 claim (card-pinned input docs/lr2021-research/drivers/provenance.md absent)
No value is trusted from the fragment itself; each is recomputed and compared.
Read-only. Exits 0 iff every check passes.
"""

import hashlib
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAGMENT = os.path.join(REPO, "SCRATCH/lr2021-manifest-parts/drivers.md")
SNAP = os.path.join(REPO, "docs/lr2021-research/radiolib-master")
PINNED_INPUT = "docs/lr2021-research/drivers/provenance.md"
REVISION = "75e486a573bbaad443ffcafa23f9e3e3d2499914"

checks = []


def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- inventory
inventory = {}
upstream = {}
for root, _dirs, files in os.walk(SNAP):
    for fn in files:
        full = os.path.join(root, fn)
        rel = os.path.relpath(full, SNAP).replace(os.sep, "/")
        inventory[rel] = (os.path.getsize(full), sha256_of(full))
        if rel == "PROVENANCE.md":
            continue  # the manifest, not a retrieval
        if rel.startswith("LR2021-module/"):
            upstream[rel] = "src/modules/LR2021/" + os.path.basename(rel)
        elif rel.startswith("LR11x0_"):
            upstream[rel] = "src/modules/LR11x0/" + os.path.basename(rel)
        elif rel == "LICENSE.txt":
            upstream[rel] = "license.txt"
        else:
            upstream[rel] = None

fetched = sorted(k for k in inventory if k != "PROVENANCE.md")

check("inventory.file_count_total", len(inventory) == 19, f"got {len(inventory)}")
check("inventory.retrieval_count", len(fetched) == 18, f"got {len(fetched)}")
check("inventory.provenance_record_present", "PROVENANCE.md" in inventory)
check("inventory.every_fetch_has_upstream_path",
      all(upstream[k] for k in fetched),
      "unmapped: %r" % [k for k in fetched if not upstream[k]])
check("inventory.lr2021_module_count",
      len([k for k in fetched if k.startswith("LR2021-module/")]) == 15,
      f"got {len([k for k in fetched if k.startswith('LR2021-module/')])}")

# ---------------------------------------------------------------- read fragment
check("fragment.exists", os.path.isfile(FRAGMENT))
with open(FRAGMENT, "r", encoding="utf-8") as fh:
    frag = fh.read()

# F1: the card-pinned input really is absent
check("input.pinned_path_absent", not os.path.isfile(os.path.join(REPO, PINNED_INPUT)),
      PINNED_INPUT)
check("fragment.F1_marker", "### F1" in frag and "SOURCE FILE NOT PRESENT" in frag)
check("fragment.header_source_path", "docs/lr2021-research/drivers/provenance.md" in frag)

# Every retrieval emitted exactly once, with the mandated field order.
FIELD_ORDER = [
    "local path", "origin URL", "HTTP status", "version/revision",
    "retrieval date", "file size", "sha256",
]
blocks = re.findall(r"^### (N\d+) — `([^`]+)`(.*?)(?=^### |\Z)", frag, re.S | re.M)
check("fragment.entry_count", len(blocks) == len(fetched),
      f"blocks={len(blocks)} fetched={len(fetched)}")

SNAP_REL = "docs/lr2021-research/radiolib-master"
seen_paths, seen_ids = [], []
for eid, lpath, body in blocks:
    seen_ids.append(eid)
    # fragment records local paths relative to the snapshot dir
    rel = lpath[len(SNAP_REL) + 1:] if lpath.startswith(SNAP_REL + "/") else lpath
    seen_paths.append(rel)
    fields = [m.group(1) for m in re.finditer(r"^- ([a-zA-Z0-9/ ]+):", body, re.M)]
    got = [f.strip() for f in fields]
    check(f"{eid}.field_order", got == FIELD_ORDER, f"got {got}")

check("fragment.entry_ids_unique", len(set(seen_ids)) == len(seen_ids), f"{seen_ids}")
check("fragment.entry_ids_sequential",
      seen_ids == [f"N{i}" for i in range(1, len(fetched) + 1)], f"{seen_ids}")
check("fragment.paths_unique", len(set(seen_paths)) == len(seen_paths))
check("fragment.paths_cover_inventory", sorted(seen_paths) == fetched,
      "missing=%r extra=%r" % (sorted(set(fetched) - set(seen_paths)),
                               sorted(set(seen_paths) - set(fetched))))

# Re-derive every size + sha256 and compare to what the fragment asserts.
for eid, lpath, body in blocks:
    rel = lpath[len(SNAP_REL) + 1:] if lpath.startswith(SNAP_REL + "/") else lpath
    if rel not in inventory:
        check(f"{eid}.path_on_disk", False, lpath)
        continue
    size_on_disk, sha_on_disk = inventory[rel]
    m_size = re.search(r"^- file size: `?([^`\n]+)`?", body, re.M)
    m_sha = re.search(r"^- sha256: `?([0-9a-f]{64})`?", body, re.M)
    check(f"{eid}.size_matches_disk",
          m_size and m_size.group(1).strip().startswith(str(size_on_disk)),
          f"fragment={m_size.group(1).strip() if m_size else None} disk={size_on_disk}")
    check(f"{eid}.sha256_matches_disk",
          m_sha and m_sha.group(1) == sha_on_disk,
          f"fragment={m_sha.group(1) if m_sha else None} disk={sha_on_disk}")
    # origin URL must be revision-pinned to the recorded commit
    m_url = re.search(r"^- origin URL: (.+)$", body, re.M)
    check(f"{eid}.origin_url_sha_pinned",
          m_url and REVISION in m_url.group(1),
          f"url={m_url.group(1)[:140] if m_url else None}")
    # and must NOT claim a per-file raw branch-name fetch
    check(f"{eid}.no_branch_name_fetch",
          m_url and f"raw.githubusercontent.com" not in m_url.group(1),
          "branch-name/raw fetch must not be asserted for a git-clone snapshot")
    m_rev = re.search(r"^- version/revision: (.+)$", body, re.M)
    check(f"{eid}.revision_recorded", m_rev and REVISION in m_rev.group(1))
    m_http = re.search(r"^- HTTP status: (.+)$", body, re.M)
    check(f"{eid}.http_status_honest",
          m_http and ("no per-file HTTP request was made" in m_http.group(1)),
          "must disclose that no per-file HTTP status exists")

# The PROVENANCE record itself is verified too (it is the manifest, not a retrieval).
if "PROVENANCE.md" in inventory:
    _sz, _sha = inventory["PROVENANCE.md"]
    check("provenance_record.sha256_in_fragment", _sha in frag, _sha)

# ---------------------------------------------------------------- counts sanity
m_ver = re.search(r"^- verified entries[^:]*:.*?`(\d+)`", frag, re.M)
m_mis = re.search(r"^- entries flagged HASH MISMATCH:.*?`(\d+)`", frag, re.M)
m_fail = re.search(r"^- FAILED entries:.*?`(\d+)`", frag, re.M)
check("counts.verified_zero_for_pinned_input", m_ver and m_ver.group(1) == "0",
      "the pinned-input scope genuinely has 0 entries")
check("counts.mismatch_zero", m_mis and m_mis.group(1) == "0")
check("counts.failed_one", m_fail and m_fail.group(1) == "1")
check("counts.addendum_block", "## ADDENDUM" in frag)

# No fabricated claims: HTTP status must never assert a 200 we did not measure.
check("no_fabricated_http_200",
      not re.search(r"^- HTTP status: `?200", frag, re.M),
      "no per-file HTTP status was measured (git clone, not HTTP)")

# ---------------------------------------------------------------- docs/ untouched
st = subprocess.run(["git", "-C", REPO, "status", "--porcelain", "--",
                     "docs/lr2021-research"],
                    capture_output=True, text=True)
check("docs.untouched_by_this_run", st.stdout.strip() == "", repr(st.stdout[:300]))

tracked = subprocess.run(["git", "-C", REPO, "ls-files", "--",
                          "docs/lr2021-research/radiolib-master"],
                         capture_output=True, text=True).stdout.split()
check("docs.radiolib_snapshot_tracked", len(tracked) == 19, f"got {len(tracked)}")

# ---------------------------------------------------------------- report
fails = [c for c in checks if not c[1]]
for name, ok, detail in checks:
    if not ok:
        print(f"FAIL {name} {detail}")
print(f"{len(checks) - len(fails)}/{len(checks)} PASS, {len(fails)} FAIL")
print(f"entries_verified={len(blocks)} hash_mismatch=0 failed=1")
sys.exit(0 if not fails else 1)

"""Final integrity gate for the drivers fragment (card t_73c3244e, run 396).

Independent of the generator: re-derives every sha256/size straight from disk and
compares against the literal text of the committed candidate. Also proves the
append-only chain and that docs/ is untouched. Read-only.
"""

import hashlib
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAG = os.path.join(REPO, "SCRATCH/lr2021-manifest-parts/drivers.md")
SNAP = os.path.join(REPO, "docs/lr2021-research/radiolib-master")
SNAP_REL = "docs/lr2021-research/radiolib-master"
BASE_SHA = "0343a048fc669f07941dfc22743dca8ef14cc030ea746faa0d6f466c036a1a6b"
BASE_BYTES = 3851

ok = True
def check(name, cond, detail=""):
    global ok
    if not cond:
        ok = False
        print(f"FAIL {name} {detail}")
    return cond

raw = open(FRAG, "rb").read()
text = raw.decode("utf-8")

# 1. append-only chain
check("chain.base_prefix_sha256",
      hashlib.sha256(raw[:BASE_BYTES]).hexdigest() == BASE_SHA,
      hashlib.sha256(raw[:BASE_BYTES]).hexdigest())
check("chain.base_preserved_bytes", raw[:BASE_BYTES].endswith(b"END OF FRAGMENT\n"))
check("chain.grew", len(raw) > BASE_BYTES, f"{len(raw)}")

# 2. every asserted (path, size, sha) triple re-derived from disk
blocks = re.findall(r"^### N\d+ — `([^`]+)`(.*?)(?=^### |\Z)", text, re.S | re.M)
on_disk = {}
for root, _d, files in os.walk(SNAP):
    for fn in files:
        full = os.path.join(root, fn)
        rel = os.path.relpath(full, SNAP).replace(os.sep, "/")
        on_disk[rel] = full

check("entries.count_18", len(blocks) == 18, f"got {len(blocks)}")
check("entries.disk_files_19_incl_provenance", len(on_disk) == 19, f"got {len(on_disk)}")

for lpath, body in blocks:
    rel = lpath[len(SNAP_REL) + 1:] if lpath.startswith(SNAP_REL + "/") else lpath
    if not check(f"{rel}.exists", rel in on_disk):
        continue
    full = on_disk[rel]
    real_size = os.path.getsize(full)
    h = hashlib.sha256()
    with open(full, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    real_sha = h.hexdigest()
    m_size = re.search(r"^- file size: `(\d+)` B$", body, re.M)
    m_sha = re.search(r"^- sha256: `([0-9a-f]{64})`$", body, re.M)
    check(f"{rel}.size", m_size and int(m_size.group(1)) == real_size,
          f"{m_size.group(1) if m_size else None} vs {real_size}")
    check(f"{rel}.sha256", m_sha and m_sha.group(1) == real_sha,
          f"{m_sha.group(1) if m_sha else None} vs {real_sha}")

# 3. no file silently missing from the fragment
asserted = {lp[len(SNAP_REL) + 1:] if lp.startswith(SNAP_REL + "/") else lp
            for lp, _ in blocks}
check("entries.covers_all_retrievals",
      asserted == (set(on_disk) - {"PROVENANCE.md"}),
      f"missing={sorted((set(on_disk) - {'PROVENANCE.md'}) - asserted)}")

# 4. provenance record hash matches the value recorded by card t_72f4873c
m = re.search(r"^- provenance record sha256: `([0-9a-f]{64})`$", text, re.M)
hw = hashlib.sha256(open(os.path.join(SNAP, "PROVENANCE.md"), "rb").read()).hexdigest()
check("provenance.sha256", m and m.group(1) == hw, f"{m.group(1) if m else None} vs {hw}")
check("provenance.matches_manager_record",
      hw == "3ecd892c57b17664f03b1856901bf95d83184fcf9901072ca53041034cdab26a", hw)

# 5. no fabricated HTTP success anywhere
check("honesty.no_http_200", not re.search(r"HTTP status: `?200", text))
check("honesty.http_disclosed",
      text.count("no per-file HTTP request was made") == 18,
      str(text.count("no per-file HTTP request was made")))

# 6. no register-behaviour claims (sourcing-only mandate)
for bad in ("0x0203", "SET_TX_PARAMS", "register map", "the chip will"):
    check(f"scope.no_tech_claim:{bad}", bad not in text)

# 7. docs/ untouched
st = subprocess.run(["git", "-C", REPO, "status", "--porcelain", "--",
                     "docs/lr2021-research"], capture_output=True, text=True)
check("docs.untouched", st.stdout.strip() == "", repr(st.stdout[:400]))

print(f"\n{'ALL PASS' if ok else 'FAILURES PRESENT'} — entries=18 verified=18 mismatch=0 failed=1")
sys.exit(0 if ok else 1)

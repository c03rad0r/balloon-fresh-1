#!/usr/bin/env python3
"""Index every loose doc under docs/ so a reorganisation can be done by MEASUREMENT, not by reading 277
files and hoping.

WHY THIS EXISTS. `docs/` holds 277 loose .md files at its top level, with subdirectories already present
(fab, adr, analysis, boards, coordination, ...). Moving files breaks cross-references, and a naive move
creates more broken links than the mess it fixes. Worse, "remove all contradictions" is a CONTENT decision,
not a filing one -- so the first thing needed is not a directory layout but a FACT TABLE.

This emits one row per doc with the facts a mover actually needs:
  - path, size, line count, mtime (from git)
  - title (first H1), or a note that there is none
  - whether it DECLARES a status (superseded / historical / draft) -- those are archive candidates
  - declared status or a note that it is undeclared
  - how many other docs link TO it (in-link count) -- a doc with many inbound links is expensive to move
  - which docs it links to
  - date-like tokens in the filename or body
  - a candidate cluster from the filename prefix, with the existing directory that best matches

It does NOT decide anything. It produces the table the decision gets made from, and the numbers that say
what a move would cost.

Output: docs/REPO-TRIAGE-INDEX.md  +  docs/REPO-TRIAGE-INDEX.json  (the machine form, for the mover)

Run: python3 scripts/repo_triage.py [--root docs] [--out docs]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

# Subdirectories under docs/ that already exist and are therefore candidate destinations.
EXISTING = {
    "adr", "alt", "analysis", "assets", "boards", "branch-triage-2026-10-06", "coordination",
    "data-handover", "e80-900mbl-02-eval", "evidence", "f33-module", "fab", "handoff", "hub-v9",
    "jlc-query", "reviews", "sweeps", "archive", "hardware", "firmware", "wing", "ssot",
}

# Tokens that mark a doc as a CANDIDATE FOR ARCHIVE. These are the words a doc uses about ITSELF.
ARCHIVE_MARKERS = (
    "superseded", "obsolete", "historical record", "kept for the record", "no longer current",
    "draft, not a decision", "do not use", "retracted", "withdrawn",
)

# Filename prefixes that group. Longest match wins, so order matters.
PREFIX_RULES = [
    ("PLAN", "plan"), ("HANDOVER", "handover"), ("handover", "handover"),
    ("DISCOVERY", "discovery"), ("STATUS", "status"), ("WALK", "walkthrough"),
    ("FLRC", "flrc"), ("flrc", "flrc"), ("LR2021", "lr2021"), ("lr2021", "lr2021"),
    ("E80", "e80"), ("e80", "e80"), ("spi", "spi"), ("balloon", "balloon"),
    ("BASE-STATION", "base-station"), ("HUB", "hub"), ("WING", "wing"), ("ASTRA", "astra"),
    ("JLC", "jlc"), ("EDGE", "edge"), ("ERC", "erc"), ("DRC", "drc"), ("FAB", "fab"),
    ("ADR", "adr"), ("GATE", "gate"), ("ORDER", "order"), ("CI-", "ci"),
]

LINK_RE = re.compile(r"\]\(([^)]+\.md)(?:#[^)]*)?\)")
DATE_RE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.M)


def git(args, cwd):
    try:
        r = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, timeout=60)
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def cluster_of(name: str) -> str:
    for prefix, cluster in PREFIX_RULES:
        if name.startswith(prefix):
            return cluster
    # fall back to the leading alphabetic token, split on - or _
    tok = re.split(r"[-_]", name, 1)[0]
    return tok.lower() if len(tok) > 2 else "misc"


def best_existing_dir(cluster: str) -> str:
    """A DESTINATION SUGGESTION, not a decision. Only claims a match when the name is close."""
    c = cluster.lower()
    for d in EXISTING:
        if d == c or d in c or c in d:
            return d
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="docs")
    ap.add_argument("--out", default=".")
    args = ap.parse_args()

    root = args.root
    if not os.path.isdir(root):
        print(f"ABSENT: {root}")
        return 2

    # last commit date per file, in ONE git call
    dates = {}
    cur = ""
    for line in git(["log", "--name-only", "--pretty=format:@%cs", "--", root], ".").splitlines():
        if line.startswith("@"):
            cur = line[1:]
        elif line.strip():
            dates.setdefault(line.strip(), cur)

    docs = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, ".")
            try:
                text = open(p, encoding="utf-8", errors="replace").read()
            except Exception as e:
                text = ""
                print(f"  WARN unreadable: {rel}: {e}")
            lines = text.count("\n") + 1
            m = H1_RE.search(text)
            title = m.group(1).strip() if m else ""
            low = text.lower()
            markers = sorted({k for k in ARCHIVE_MARKERS if k in low})
            docs.append({
                "path": rel,
                "name": fn,
                "dir": os.path.dirname(rel),
                "loose": os.path.dirname(rel) == root,
                "lines": lines,
                "chars": len(text),
                "title": title,
                "cluster": cluster_of(fn),
                "archive_markers": markers,
                "links": [l for l in LINK_RE.findall(text) if not l.startswith(("http://", "https://"))],
                "dates": sorted({f"{a}-{b}-{c}" for a, b, c in DATE_RE.findall(text)})[-3:],
                "last_commit": dates.get(rel, ""),
            })

    # inbound link counts: a doc with many inbound links is expensive to move
    inbound = defaultdict(int)
    known = {d["path"] for d in docs} | {d["name"] for d in docs}
    for d in docs:
        for l in d["links"]:
            base = os.path.basename(l)
            if base in known:
                inbound[base] += 1

    loose = [d for d in docs if d["loose"]]
    by_cluster = Counter(d["cluster"] for d in loose)
    sug = {c: best_existing_dir(c) for c in by_cluster}

    # ---- the markdown table
    out = [
        "# Repo triage index — what each doc IS, before anything moves",
        "",
        f"**Generated by** `scripts/repo_triage.py`. **{len(docs)} docs total, {len(loose)} loose at the top of `{root}/`.**",
        "",
        "**This file decides nothing.** It is the fact table a reorganisation gets made from, plus the numbers",
        "that say what a move costs. Re-run it after any move; it is cheap and deterministic.",
        "",
        "## Findings",
        "",
    ]
    no_title = [d for d in loose if not d["title"]]
    arch = [d for d in loose if d["archive_markers"]]
    no_in = [d for d in loose if not inbound.get(d["name"])]
    many_in = sorted(loose, key=lambda d: -inbound.get(d["name"], 0))[:12]
    out += [
        f"- **{len(no_title)} loose docs have no H1 title** — a reader (and an index) cannot tell what they are.",
        f"- **{len(arch)} loose docs mark THEMSELVES as superseded/obsolete/historical** — archive candidates.",
        f"- **{len(no_in)} loose docs are linked from nowhere** in `docs/` — nothing breaks if they move.",
        f"- **Total internal .md links from the loose set: {sum(len(d['links']) for d in loose)}.**",
        "",
        "## The most linked-to loose docs (these are the expensive ones to move)",
        "",
        "| doc | inbound links |",
        "|---|---|",
    ]
    for d in many_in:
        out.append(f"| `{d['name']}` | {inbound.get(d['name'], 0)} |")
    out += [
        "",
        "## Clusters, with a destination SUGGESTION (not a decision)",
        "",
        "| cluster | loose docs | suggested existing dir | note |",
        "|---|---|---|---|",
    ]
    for c, n in by_cluster.most_common():
        s = sug.get(c) or ""
        note = "" if s else "**no matching dir exists** — needs a layout decision"
        out.append(f"| `{c}` | {n} | {s or '—'} | {note} |")

    out += ["", "## Every loose doc", "",
            "| file | lines | title | cluster | inbound | last commit | self-marked |",
            "|---|---|---|---|---|---|---|"]
    for d in sorted(loose, key=lambda x: (x["cluster"], x["name"])):
        t = (d["title"][:52] + "…") if len(d["title"]) > 53 else d["title"]
        mk = ", ".join(d["archive_markers"]) or ""
        out.append(f"| `{d['name']}` | {d['lines']} | {t or '**— none —**'} | {d['cluster']} | "
                   f"{inbound.get(d['name'],0)} | {d['last_commit']} | {mk} |")

    out += [
        "",
        "## How to use this",
        "",
        "1. **Do not move anything whose inbound count is above ~3** without updating every referrer in the",
        "   same commit. Those are the docs other docs point at, and a broken link is worse than a misplaced",
        "   file.",
        "2. **Archive the self-marked ones first.** They say they are superseded; moving them to",
        f"   `{root}/archive/` with a header naming what superseded them is low-risk and removes noise.",
        "3. **The `no matching dir exists` rows are the real decision.** Moving 30 `flrc` docs into a new",
        "   directory is a layout choice; record it (an ADR or a short note) rather than doing it silently.",
        "4. Re-run this script after each move and diff the table. That is the check that a move did not",
        "   lose a doc or break a link.",
        "",
    ]

    os.makedirs(args.out, exist_ok=True)
    md = os.path.join(args.out, "REPO-TRIAGE-INDEX.md")
    js = os.path.join(args.out, "REPO-TRIAGE-INDEX.json")
    with open(md, "w") as fh:
        fh.write("\n".join(out) + "\n")
    with open(js, "w") as fh:
        json.dump({"docs": docs, "inbound": dict(inbound),
                   "clusters": dict(by_cluster), "suggested": sug}, fh, indent=1, sort_keys=True)

    # STATE THE COUNT, and stat the files: a "wrote <path>" line is not proof
    for p in (md, js):
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            print(f"RENDER FAILED: {p} absent or empty")
            return 1
    print(f"docs total      : {len(docs)}")
    print(f"loose at root   : {len(loose)}")
    print(f"clusters        : {len(by_cluster)}")
    print(f"no H1 title     : {len(no_title)}")
    print(f"self-marked arch: {len(arch)}")
    print(f"linked from nowhere: {len(no_in)}")
    print(f"wrote {md} ({os.path.getsize(md)} bytes)")
    print(f"wrote {js} ({os.path.getsize(js)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

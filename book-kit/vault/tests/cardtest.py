#!/usr/bin/env python3
"""cardtest.py — the shared setup for the card-tool tests: a copy of the sample vault and a way to run a tool in it.

    import cardtest as T
    with T.sample_copy() as v:            # a temp copy of sample/, page snapshot fresh
        r = T.run(v, "check-card-notes.py", "--json")

Every card test works on a copy: the sample vault and its page snapshot
(`sample/Handoffs/editor-tools/page-snapshot/`, the same files as
`tests/fixtures/page-snapshot/`) are never written. The copy's TAKEN file is
set to now, so a tool that refuses a stale snapshot reads it as fresh.
"""
import contextlib
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KIT_VAULT = Path(__file__).resolve().parent.parent
SAMPLE = Path(os.environ.get("BOOK_SAMPLE") or KIT_VAULT.parent / "sample")
TOOLS = KIT_VAULT / "tools"
FIXTURES = KIT_VAULT / "tests" / "fixtures"
SNAP_REL = Path("Handoffs") / "editor-tools" / "page-snapshot"

# The four cards in the sample page snapshot.
APPLIED = "ch01-paine-society-cite"        # (a) applied; changed Ch 1's paragraph with the "carries" sentence
NOTE_ARGUES = "ch02-fed1-note-interpretation"  # (b) open; [^fed1_test] with the interpretation sentence
ON_CLOSED = "ch01-carries-sentence"        # (c) open; on the paragraph card (a) changed
CHOICE = "ch02-reflection-choice"          # (d) open; "reflection and design" -> "reflection and choice"


@contextlib.contextmanager
def sample_copy():
    with tempfile.TemporaryDirectory() as t:
        v = Path(t) / "vault"
        shutil.copytree(SAMPLE, v)
        snap = v / SNAP_REL
        if not (snap / "proposals").is_dir():
            shutil.rmtree(snap, ignore_errors=True)
            shutil.copytree(FIXTURES / "page-snapshot", snap)
        (snap / "TAKEN").write_text(datetime.datetime.now(datetime.timezone.utc)
                                    .isoformat(timespec="seconds") + "\n")
        yield v


def run(vault, tool, *args, timeout=150):
    env = dict(os.environ, BOOK_VAULT=str(vault))
    return subprocess.run([sys.executable, str(TOOLS / tool), *map(str, args)], cwd=vault,
                          env=env, capture_output=True, text=True, timeout=timeout)


def rows(r):
    return [json.loads(l) for l in r.stdout.splitlines() if l.strip().startswith("{")]


def card_path(vault, cid):
    return vault / SNAP_REL / "proposals" / f"{cid}.json"


def edit_card(vault, cid, **fields):
    p = card_path(vault, cid)
    d = json.loads(p.read_text(encoding="utf-8"))
    d.update(fields)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def ledger(vault, n, title):
    """The chapter's ledger in the copy, made when the sample has none."""
    fact = vault / "Fact Check"
    hits = [p for p in fact.glob(f"Ch. {n:02d} — *.md")]
    if hits:
        return hits[0]
    p = fact / f"Ch. {n:02d} — {title}.md"
    p.write_text(f"# Ch. {n:02d} — {title}: fact-check ledger\n", encoding="utf-8")
    return p


def files(root):
    """Every file and its bytes, bytecode caches left out (importing a tool makes them)."""
    return {p: p.read_bytes() for p in Path(root).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts}


def finish(name, bad, ok_msg):
    if bad:
        print("\n".join("  " + b for b in bad))
        raise SystemExit(f"{name} regressed")
    print(ok_msg)

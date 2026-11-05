#!/usr/bin/env python3
"""cardtest.py — the shared setup for the card-tool tests: a copy of the sample vault and a way to run a tool in it.

    import cardtest as T
    with T.sample_copy() as v:            # a temp copy of sample/, its card store included
        r = T.run(v, "check-card-notes.py", "--json")
        T.edit_card(v, T.CHOICE, status="approved")     # a new version line in the copy's store
        T.press(v, T.CHOICE, "approve")                 # a press of the author's, as the card desk records it

Every card test works on a copy: the sample vault and its card store
(`sample/Fact Check/Cards/cards.jsonl`) are never written. A test writes
version lines straight into the copy's store, past the gates in
`tools/cards.py`, so each tool is tested on the card shapes it must handle.
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
STORE_REL = Path("Fact Check") / "Cards" / "cards.jsonl"
FILES_REL = Path("Handoffs") / "editor-tools" / "card-files"

# The four cards in the sample card store.
APPLIED = "ch01-paine-society-cite"        # (a) applied; changed Ch 1's paragraph with the "carries" sentence
NOTE_ARGUES = "ch02-fed1-note-interpretation"  # (b) open; [^fed1_test] with the interpretation sentence
ON_CLOSED = "ch01-carries-sentence"        # (c) open; on the paragraph card (a) changed
CHOICE = "ch02-reflection-choice"          # (d) open; "reflection and design" -> "reflection and choice"


@contextlib.contextmanager
def sample_copy():
    with tempfile.TemporaryDirectory() as t:
        v = Path(t) / "vault"
        shutil.copytree(SAMPLE, v)
        yield v


def run(vault, tool, *args, timeout=150, session="test-auditor"):
    """Run a tool in the copy, as the session `session` (the second-session gate reads it)."""
    env = dict(os.environ, BOOK_VAULT=str(vault), BOOK_SESSION=session)
    return subprocess.run([sys.executable, str(TOOLS / tool), *map(str, args)], cwd=vault,
                          env=env, capture_output=True, text=True, timeout=timeout)


def rows(r):
    return [json.loads(l) for l in r.stdout.splitlines() if l.strip().startswith("{")]


def _lines(vault):
    p = vault / STORE_REL
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def newest(vault, cid):
    """The newest version line's card record, with its id."""
    got = [l for l in _lines(vault) if l["id"] == cid]
    return dict(got[-1]["card"], id=cid) if got else None


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def card_path(vault, cid):
    """A card file holding the card's newest version, for a tool's --card. edit_card keeps it current."""
    p = vault / FILES_REL / f"{cid}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(newest(vault, cid), ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def put_card(vault, cid, record, by="test", session="test-writer"):
    """Append one version line for `cid` to the copy's store."""
    have = [l["version"] for l in _lines(vault) if l["id"] == cid]
    rec = {k: v for k, v in record.items() if k != "id"}
    line = {"id": cid, "version": (max(have) + 1) if have else 1, "at": _now(), "by": by, "session": session,
            "source": "test", "card": rec}
    p = vault / STORE_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    f2 = vault / FILES_REL / f"{cid}.json"
    if f2.exists():
        card_path(vault, cid)
    return line["version"]


def edit_card(vault, cid, **fields):
    """A new version of the card with these fields changed."""
    d = newest(vault, cid)
    d.update(fields)
    return put_card(vault, cid, d)


def replace_store(vault, records):
    """The copy's store holds only these cards, one version each: {id: record}."""
    (vault / STORE_REL).write_text("", encoding="utf-8")
    for cid, rec in records.items():
        put_card(vault, cid, rec)


def press(vault, cid, kind, text="", version=None, **extra):
    """One press of the author's on a card, as tools/card-desk.py records it. Returns the event hash."""
    v = version if version is not None else max(l["version"] for l in _lines(vault) if l["id"] == cid)
    code = ("import sys, json; sys.path.insert(0, sys.argv[1]); import bookconfig as B, vaultlog; "
            "a = json.loads(sys.argv[2]); print(vaultlog.append('decision.recorded', actor=B.AUTHOR_ACTOR, **a)['hash'])")
    args = dict(card=cid, card_version=v, decision_kind=kind, **({"text": text} if text else {}), **extra)
    r = subprocess.run([sys.executable, "-c", code, str(TOOLS), json.dumps(args)], cwd=vault,
                       env=dict(os.environ, BOOK_VAULT=str(vault)), capture_output=True, text=True, check=True)
    return r.stdout.strip()


def desk_press(vault, view, desk_id, **fields):
    """One press of the author's on the card desk's Asks or Sources view, as the desk records it."""
    code = ("import sys, json; sys.path.insert(0, sys.argv[1]); import bookconfig as B, vaultlog; "
            "a = json.loads(sys.argv[2]); print(vaultlog.append('decision.recorded', actor=B.AUTHOR_ACTOR, **a)['hash'])")
    args = dict(desk_view=view, desk_id=desk_id, **fields)
    r = subprocess.run([sys.executable, "-c", code, str(TOOLS), json.dumps(args)], cwd=vault,
                       env=dict(os.environ, BOOK_VAULT=str(vault)), capture_output=True, text=True, check=True)
    return r.stdout.strip()


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

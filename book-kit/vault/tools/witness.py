#!/usr/bin/env python3
"""witness.py — lists files that changed with no logged event saying why.

    python3 tools/witness.py            # unexplained changes since the last seal
    python3 tools/witness.py --seal     # record the current state as accounted for
    python3 tools/witness.py --json     # one JSON line per finding

Exit status: 0 when every change is explained, 1 when one is not, 2 when no
seal is on file.

WHAT IT IS FOR

    An editor's own file history captures what happens between commits, the
    window git cannot see, but its store may not be readable from where the
    tools run. So the vault keeps its own between-commit history, and this is
    the half that cannot be forgotten.

WHY A RETROFIT IS NOT ENOUGH ON ITS OWN

    `vaultlog.write_file` / `record_write` has to be CALLED by a tool, and a
    tool that never calls it goes on writing silently. So this does not trust
    the retrofit. It keeps a hash of every file it watches and asks one
    question: did this file's content change with no `file.written` event
    accounting for the change? A tool that skips the log is caught by
    arithmetic, never by anyone's memory of which tools were patched.

    In the original system a tool deleted a chapter's body paragraph and wrote
    a duplicate footnote definition in its place, and nothing noticed for a
    day. Under this check it is an unexplained change on the next run,
    whoever caused it and whatever they meant to do.

    A file written several times between seals is explained when the logged
    writes form an unbroken path from the sealed hash to the hash on disk.

WHAT IT WATCHES

    The chapters, the appendices, the Claims files and the methodology files.
    Not the event log itself, which is append-only and verified by its own
    hash chain, and not backups, which are snapshots rather than the book.

PUBLIC FUNCTIONS

    watched() -> iterator of paths
    digest(path) -> str
    current() -> {relative path: hash}
    explained() -> {(path, before_hash, after_hash)}
    unexplained(old, now=None) -> [(path, what, before, after)]
    SEAL, WATCH
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402

SEAL = B.FACT / ".witness.json"

WATCH = [
    (B.CHAPTERS, "*.md"),
    (B.CLAIMS, "*.jsonl"),
    (B.METHODOLOGY, "*.md"),
    (B.APPENDICES, "*.md"),
]


def watched():
    for folder, pattern in WATCH:
        if not folder.is_dir():
            continue
        for f in sorted(folder.glob(pattern)):
            if B.is_backup(f):
                continue
            yield f


def digest(f: Path) -> str:
    return hashlib.sha256(f.read_bytes()).hexdigest()[:16]


def _rel(f: Path) -> str:
    try:
        return str(f.resolve().relative_to(B.VAULT))
    except ValueError:
        return str(f)


def current():
    return {_rel(f): digest(f) for f in watched()}


def explained():
    """(path, before_hash, after_hash) triples a tool logged for itself."""
    import vaultlog
    return {(e.get("path"), e.get("before_hash"), e.get("after_hash"))
            for e in vaultlog.fold("file.written")}


def _reachable(path, start, goal, ok):
    """Is there an unbroken path of logged writes from `start` to `goal`?"""
    edges = {}
    for p, a, b in ok:
        if p == path:
            edges.setdefault(a, set()).add(b)
    seen, todo = {start}, [start]
    while todo:
        h = todo.pop()
        for nxt in edges.get(h, ()):
            if nxt == goal:
                return True
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return False


def unexplained(old: dict, now: dict = None):
    """[(path, what, before_hash, after_hash)] for every change no event explains."""
    now = current() if now is None else now
    ok = explained()
    rows = []
    for path, h in now.items():
        was = old.get(path)
        if was is None:
            rows.append((path, "NEW FILE", "", h))
        elif was != h and not _reachable(path, was, h, ok):
            rows.append((path, "CHANGED, NOTHING LOGGED IT", was, h))
    for path in old:
        if path not in now:
            rows.append((path, "GONE", old[path], ""))
    return rows


def main():
    if "--seal" in sys.argv:
        state = current()
        SEAL.parent.mkdir(parents=True, exist_ok=True)
        SEAL.write_text(json.dumps(state, indent=1), encoding="utf-8")
        print(f"\n  sealed {len(state)} file(s).\n")
        return

    as_json = "--json" in sys.argv
    if not SEAL.exists():
        print("\n  NO SEAL ON FILE — this check cannot tell a change from a baseline.")
        print("  Run --seal once, deliberately, on a clean tree.\n")
        sys.exit(2)

    old = json.loads(SEAL.read_text(encoding="utf-8"))
    now = current()
    rows = unexplained(old, now)

    if as_json:
        for path, what, a, b in rows:
            print(json.dumps({"check": "witness", "where": path, "coord": "—",
                              "what": f"{what} ({a or '—'} -> {b or '—'})"}))
        sys.exit(1 if rows else 0)

    print(f"\n  {len(now)} file(s) watched.  {len(rows)} unexplained change(s).\n")
    for path, what, a, b in rows:
        print(f"    {what:<28}{path}")
        if a or b:
            print(f"      {a or '—'} -> {b or '—'}")
    if not rows:
        print("    Every change since the seal has an event accounting for it.\n")
    else:
        print("\n  A change with no event is a change nobody can explain later.\n")
    sys.exit(1 if rows else 0)


if __name__ == "__main__":
    main()

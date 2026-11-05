#!/usr/bin/env python3
"""cards.py — the cards the author rules on, in one file, and the one way a card goes in.

    tools/cards.py list                                  # each card: status now, version, id, title
    tools/cards.py show <id>                             # the newest version of one card, whole, as JSON
    tools/cards.py counts                                # cards by status
    tools/cards.py add <card.json> --why "<reason>" [--by "<role>"]   # one version in, through add_version()
    tools/cards.py applied <id> --version <n> --edit-event <hash>      # Production: the card is in the book
    tools/cards.py hold <id> --by "<role>" --reason "<why>" [--unread-facts]   # off the author's desk
    tools/cards.py release <id> --by "<role>"            # back before the author; the word and read gates run

    import cards
    cards.fold()                 # {id: card now}: the newest version, then the author's presses after it
    cards.card(id)               # the newest version of one card, or None
    cards.add_version(id, record, by=..., why=...)

WHY ONE FILE

    The system this kit comes from first kept its cards on a claude.ai page
    with a database. No script could open the page, so every check worked from
    a snapshot a chat had copied, and a snapshot is out of date the moment the
    author presses a button. The author then asked for "a small server of its
    own ... One queue still holds: the cards live in one place and I rule in one
    place." This file is that one place, and `tools/card-desk.py` is the server.

THE STORE

    `Fact Check/Cards/cards.jsonl` (book.toml [paths] cards). One line per card
    version, and the file only grows:

        {"id": ..., "version": n, "at": ..., "by": ..., "session": ...,
         "source": ..., "card": {the card record}}

    The newest line for an id is the card; older lines stay, so a version the
    author saw can be shown whole. Nothing rewrites a line.

    The status inside a record is where the card stood when its line was
    written. After that the event log decides: `fold()` reads the author's
    presses (`decision.recorded` with `card`, actor = book.toml [book]
    author_actor) and Production's applies (`edit.applied` with `card`) written
    after the line, oldest first.

    Statuses: yours (waiting for the author), submitted (the author sent edits
    for checking), approved, applied, held (its owner took it off the desk:
    not ready), superseded (closed; never goes in).

THE GATES A VERSION PASSES ON THE WAY IN (`add_version`)

    - the card's chapter is in the workflow (book.toml [workflow] out_of_workflow);
    - every field in REQUIRED is there: a card shows the words;
    - the word gate: no banned word in the text the author would approve
      (`tools/check-card-words.py`, `card_hits`);
    - the read gate: every name, number, date and quotation in that text has an
      opened, logged read in `Fact Check/Claims/` (`tools/card_reads.py`).

    `book.toml [gates]` sets each of the last two to "warn" (the writer sees
    the list, the card goes in, and the card desk holds it) or "refuse" (nothing
    is written). Each starts at warn and goes to refuse on the author's ok to a
    sample. The card desk applies the rest live, every time it draws a card:
    the note check, the closed-line check, the prose audit by a second session,
    and the refresh after an apply.
"""
import contextlib
import copy
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import bookconfig as B  # noqa: E402

STORE = B.CARD_STORE
LOCKFILE = STORE.parent / ".write.lock"
TOOL = "tools/cards.py"
OPEN = ("yours", "submitted")
#: What a new version must give. A card without the words the author would approve is unfinished.
REQUIRED = ("title", "chapter", "where", "current", "proposedPara", "status")
#: The author's presses on a card, as tools/card-desk.py records them.
PRESS_KINDS = ("approve", "edit", "directive", "card-note", "withdraw", "reopen", "keep_closed")


class Refused(Exception):
    """A card write that would put something in the store nobody can trust."""


def rel(p) -> str:
    try:
        return str(Path(p).resolve().relative_to(B.VAULT))
    except ValueError:
        return str(p)


def chapter_of(card: dict):
    """The chapter number from the card's own `chapter` field ("Ch 02" -> 2), or None."""
    m = re.match(r"\s*Ch(?:apter)?\.?\s*0*(\d+)\b", str(card.get("chapter") or ""))
    return int(m.group(1)) if m else None


def locked(card: dict) -> str:
    """'' when the card's chapter is in the workflow; otherwise the reason, in words."""
    ch = chapter_of(card or {})
    if ch in B.OUT_OF_WORKFLOW:
        return f"Chapter {ch} is out of the workflow (book.toml [workflow] out_of_workflow)"
    return ""


_CACHE = {"key": None, "lines": []}


def _parsed():
    """Every version line, parsed once per state of the file on disk."""
    if not STORE.exists():
        return []
    st = STORE.stat()
    key = (st.st_size, st.st_mtime_ns, st.st_ino)
    if _CACHE["key"] == key:
        return _CACHE["lines"]
    out = []
    for n, raw in enumerate(STORE.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError as e:
            raise Refused(f"{rel(STORE)} line {n} is not JSON ({e}). A store with a broken line is read by nobody.")
    _CACHE["key"], _CACHE["lines"] = key, out
    return out


def versions(card_id: str) -> list:
    return copy.deepcopy([l for l in _parsed() if l["id"] == card_id])


def _as_card(line: dict) -> dict:
    c = dict(line["card"])
    c["id"] = line["id"]
    c["_version"] = line["version"]
    c["_at"] = line["at"]
    c["_by"] = line.get("by") or ""
    c["_session"] = line.get("session") or ""
    return c


def latest() -> dict:
    """{id: card} for the newest version of each card, as written."""
    newest = {}
    for l in _parsed():
        newest[l["id"]] = l
    return {cid: _as_card(copy.deepcopy(l)) for cid, l in newest.items()}


def card(card_id: str):
    return latest().get(card_id)


_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


def _t(s) -> datetime:
    """A time string as a time: the log writes "+00:00" and the store "Z", and as text they sort wrong."""
    s = str(s or "").strip()
    if not s:
        return _EPOCH
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return _EPOCH
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _press(c: dict, e: dict):
    """Set on one card the fields a press of the author's sets."""
    k, at = e.get("decision_kind"), e.get("ts", "")
    open_ = c.get("status") not in ("approved", "applied")
    if k == "approve":
        c.update(status="approved", approvedAt=at)
    elif k == "edit":
        c.update(status="submitted", submittedAt=at, proposedPara=e.get("text") or "",
                 submittedPara=e.get("text") or "")
        if e.get("note") is not None:
            c.update(proposedNote=e["note"], submittedNote=e["note"])
    elif k in ("directive", "card-note"):
        c.update(note=e.get("text") or "", notedAt=at)
        if k == "directive":
            c["directiveAt"] = at
            if open_:
                c.update(status="submitted", submittedAt=at, submittedPara=c.get("proposedPara") or "")
    elif k == "withdraw":
        c.update(status="yours", approvedAt="", withdrawnAt=at)
    elif k == "reopen" and e.get("what") == "applied":
        c.update(status="yours", reopenedAt=at)
    elif k == "reopen":
        c.update(lineReopenedAt=at, lineReopenText=c.get("reviewedPara") or c.get("proposedPara") or "",
                 lineReopenWords=e.get("text") or "", lineKeptAt="")
    elif k == "keep_closed":
        c.update(lineKeptAt=at, lineKeptText=c.get("reviewedPara") or c.get("proposedPara") or "",
                 lineKeepWords=e.get("text") or "")


def card_events(ids=None):
    """The author's card presses and Production's card applies, oldest first."""
    import vaultlog
    out = []
    for kind in ("decision.recorded", "edit.applied"):
        for e in vaultlog.fold(kind):
            if e.get("card") and (ids is None or e["card"] in ids):
                out.append(e)
    return sorted(out, key=lambda e: _t(e.get("ts")))


def fold(cards: dict | None = None) -> dict:
    """{id: card now}: each card's newest line, then the author's presses on that version and
    Production's applies written after it. The store is not touched."""
    cards = latest() if cards is None else cards
    out = {cid: dict(c) for cid, c in cards.items()}
    for e in card_events(set(out)):
        c = out[e["card"]]
        if _t(e.get("ts")) < _t(c["_at"]):
            continue
        if e["kind"] == "edit.applied":
            c.update(status="applied", appliedAt=e.get("ts", ""))
        elif e.get("actor") == B.AUTHOR_ACTOR and e.get("card_version") in (None, c["_version"]):
            _press(c, e)
    return out


def presses(card_id: str | None = None) -> list:
    """The author's card presses from the event log, oldest first, in the shape the closed-line
    check reads: {card, action, result, at, words}."""
    out = []
    for e in card_events(None if card_id is None else {card_id}):
        if e["kind"] == "decision.recorded" and e.get("actor") == B.AUTHOR_ACTOR:
            out.append({"card": e["card"], "action": e.get("decision_kind"), "result": "saved",
                        "at": e.get("ts", ""), "words": e.get("text") or "", "version": e.get("card_version")})
    return out


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@contextlib.contextmanager
def _write_lock():
    """Two chats, one file: the read, the version number and the write happen under one lock."""
    STORE.parent.mkdir(parents=True, exist_ok=True)
    try:
        import fcntl
    except ImportError:          # Windows: one writer at a time is the user's to keep
        yield
        return
    fd = os.open(LOCKFILE, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _append(card_id: str, rec: dict, *, by: str, source: str, why: str) -> int:
    import vaultlog
    with _write_lock():
        have = [l for l in _parsed() if l["id"] == card_id]
        version = (max(l["version"] for l in have) + 1) if have else 1
        line = json.dumps({"id": card_id, "version": version, "at": _now(), "by": by,
                           "session": vaultlog.session_id(), "source": source, "card": rec},
                          ensure_ascii=False)
        before = STORE.read_text(encoding="utf-8") if STORE.exists() else ""
        sep = "" if (not before or before.endswith("\n")) else "\n"
        vaultlog.write_file(STORE, before + sep + line + "\n", tool=TOOL,
                            why=f"card {card_id} v{version} — {why}", backup=False)
    return version


def _gate(key: str, card_id: str, findings: list, label: str):
    """Warn or refuse, as book.toml [gates] says for `key`."""
    if not findings:
        return
    why = f"{card_id}: {label}:\n  - " + "\n  - ".join(findings)
    if B.gate_mode(key) == "refuse":
        raise Refused(why + "\nNothing written.")
    print("WARNING " + why + "\n(The card goes in, and the card desk holds it until this is fixed.)", file=sys.stderr)


def word_findings(card_id: str, record: dict) -> list:
    import importlib.util
    spec = importlib.util.spec_from_file_location("ccw", TOOLS / "check-card-words.py")
    ccw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ccw)
    return [f"{h['field']}: {h['word']!r} …{h['context']}… (carve-out: {h['carve_out'] or 'none'})"
            for h in ccw.card_hits(dict(record, id=card_id))]


def read_findings(card_id: str, record: dict) -> list:
    import card_reads
    return [f"{k}: {v[:160]}" for k, v in card_reads.unread_facts(dict(record, id=card_id))]


def _gates(card_id: str, record: dict):
    if record.get("status") not in ("yours", "submitted", "approved"):
        return
    _gate("card_words", card_id, word_findings(card_id, record),
          "banned word(s) in the text the author would approve (Methodology/Word Lists.md)")
    _gate("card_reads", card_id, read_findings(card_id, record),
          "fact(s) in the passage with no opened read in Fact Check/Claims/; the Fact-checker reads and logs each first")


def add_version(card_id: str, record: dict, *, by: str, why: str, source: str = "") -> dict:
    """Put one card version in the store. THE ONE WAY A CARD GOES IN. Refuses, and writes nothing,
    when the chapter is out of the workflow, a REQUIRED field is empty, or the record names another
    id; then the word and read gates (above)."""
    import vaultlog
    why_not = locked(record)
    if why_not:
        raise Refused(f"{card_id}: {why_not}; nothing written.")
    rid = record.get("id")
    if rid and rid != card_id:
        raise Refused(f"the record gives id {rid!r}, not {card_id!r}; nothing written.")
    missing = [f for f in REQUIRED if record.get(f) in (None, "", [])]
    if missing:
        raise Refused(f"{card_id}: no {', '.join(missing)}; a card shows the words. Nothing written.")
    if not str(why or "").strip():
        raise Refused(f"{card_id}: no --why; nothing written.")
    _gates(card_id, record)
    rec = {k: v for k, v in record.items() if k != "id" and not k.startswith("_")}
    version = _append(card_id, rec, by=by, source=source, why=why)
    ev = vaultlog.append("proposal.written", actor=by, card=card_id, version=version,
                         where=record.get("where"), title=record.get("title"), why=why)["hash"]
    return {"id": card_id, "version": version, "proposal_event": ev}


def status(card_id: str):
    c = card(card_id)
    return fold({card_id: c})[card_id].get("status") if c else None


def mark_applied(card_id: str, version: int, *, edit_event: str, by: str = "Production") -> str:
    """Production's one way to mark a card applied: one `edit.applied` event with `card` and
    `card_version`. Refuses unless the card is approved now and `version` is its newest version.
    Then tools/card_refresh.py looks at every other open card of the chapter."""
    import vaultlog
    c = card(card_id)
    if c is None:
        raise Refused(f"no card {card_id!r} in {rel(STORE)}; nothing written.")
    now = fold({card_id: c})[card_id].get("status")
    if now != "approved":
        raise Refused(f"{card_id} is {now!r}, not 'approved'; nothing written.")
    if int(version) != c["_version"]:
        raise Refused(f"{card_id}: v{version} is not the newest version (v{c['_version']}); nothing written.")
    if not edit_event:
        raise Refused(f"{card_id}: no edit event naming the chapter write; nothing written.")
    h = vaultlog.append("edit.applied", actor=by, card=card_id, card_version=int(version),
                        coord=c.get("where"), edit_event=edit_event,
                        why=f"card {card_id} v{version} applied; the chapter write is event {edit_event}")["hash"]
    # No collisions: each other open card of the chapter shows the chapter as it reads now, or goes back to its owner.
    try:
        import card_refresh
        ch = chapter_of(c)
        if ch is not None:
            for line in card_refresh.run(ch, applied=f"{card_id} v{version}"):
                print(f"card_refresh: {line}", file=sys.stderr)
    except Exception as e:  # noqa: BLE001  a fault here never undoes the apply
        print(f"card_refresh did not run: {type(e).__name__}: {e}", file=sys.stderr)
    return h


def hold(card_id: str, *, reason: str, by: str, facts=None) -> int:
    """Take a card waiting for the author off the desk until its owner releases it: one version line,
    status "held", with heldBy, heldReason, heldFacts and heldAt. The author sees only cards that are ready."""
    c = card(card_id)
    if c is None:
        raise Refused(f"no card {card_id!r}; nothing written.")
    now = fold({card_id: c})[card_id].get("status")
    if now not in OPEN:
        raise Refused(f"{card_id} is {now!r}; only a card waiting for the author (yours, submitted) is held.")
    if not str(reason or "").strip() or not str(by or "").strip():
        raise Refused(f"{card_id}: a hold names its owner (--by) and its reason (--reason); nothing written.")
    rec = dict(versions(card_id)[-1]["card"])
    rec.update(status="held", heldBy=by, heldReason=reason.strip(), heldFacts=list(facts or []),
               heldAt=_now(), heldFrom=now)
    return _append(card_id, rec, by=by, source="cards.hold", why=f"held by {by}: {reason.strip()}")


def release(card_id: str, *, by: str) -> int:
    """Put a held card back before the author. It reaches the desk, so the word and read gates run."""
    c = card(card_id)
    if c is None:
        raise Refused(f"no card {card_id!r}; nothing written.")
    if fold({card_id: c})[card_id].get("status") != "held":
        raise Refused(f"{card_id} is not held; nothing written.")
    rec = {k: v for k, v in versions(card_id)[-1]["card"].items()
           if k not in ("heldBy", "heldReason", "heldFacts", "heldAt", "heldFrom")}
    rec["status"] = c.get("heldFrom") or "yours"
    _gates(card_id, rec)
    return _append(card_id, rec, by=by, source="cards.release", why=f"released by {by}")


def _opt(argv, name, default=""):
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default


def main(argv):
    if not argv or argv[0] not in ("list", "show", "counts", "add", "applied", "hold", "release"):
        print(__doc__)
        return 2
    cmd = argv[0]
    try:
        if cmd == "add":
            if len(argv) < 2 or not _opt(argv, "--why"):
                print('usage: tools/cards.py add <card.json> --why "<reason>" [--by "<role>"]')
                return 2
            record = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
            cid = record.get("id")
            if not cid:
                print(f"{argv[1]} gives no id; nothing written.")
                return 1
            got = add_version(cid, record, by=_opt(argv, "--by", "Editor"), why=_opt(argv, "--why"),
                              source=rel(argv[1]))
            print(f"{got['id']} v{got['version']} written; proposal.written {got['proposal_event']}")
            return 0
        if cmd == "applied":
            if len(argv) < 2 or not _opt(argv, "--version"):
                print("usage: tools/cards.py applied <id> --version <n> --edit-event <hash>")
                return 2
            h = mark_applied(argv[1], int(_opt(argv, "--version")), edit_event=_opt(argv, "--edit-event"),
                             by=_opt(argv, "--by", "Production"))
            print(f"{argv[1]} marked applied; edit.applied {h}")
            return 0
        if cmd == "hold":
            if len(argv) < 2 or not _opt(argv, "--by") or not _opt(argv, "--reason"):
                print('usage: tools/cards.py hold <id> --by "<role>" --reason "<why>" [--unread-facts]')
                return 2
            facts = read_findings(argv[1], card(argv[1]) or {}) if "--unread-facts" in argv else []
            v = hold(argv[1], reason=_opt(argv, "--reason"), by=_opt(argv, "--by"), facts=facts)
            print(f"{argv[1]} v{v} held by {_opt(argv, '--by')}" + (f"; {len(facts)} unread fact(s) listed" if facts else ""))
            return 0
        if cmd == "release":
            if len(argv) < 2 or not _opt(argv, "--by"):
                print('usage: tools/cards.py release <id> --by "<role>"')
                return 2
            v = release(argv[1], by=_opt(argv, "--by"))
            print(f"{argv[1]} v{v} released to the author's desk")
            return 0
    except Refused as e:
        print(f"REFUSED: {e}")
        return 1
    now = fold()
    if cmd == "show":
        c = now.get(argv[1]) if len(argv) > 1 else None
        if c is None:
            print(f"no card {argv[1:] and argv[1]!r} in {rel(STORE)}")
            return 1
        print(json.dumps(c, ensure_ascii=False, indent=1))
        return 0
    if cmd == "counts":
        from collections import Counter
        n = Counter(c.get("status") for c in now.values())
        print(f"{len(now)} cards in {rel(STORE)}: " + (", ".join(f"{k} {v}" for k, v in n.most_common()) or "none"))
        return 0
    for cid, c in sorted(now.items(), key=lambda kv: (chapter_of(kv[1]) or 999, kv[0])):
        print(f"{c.get('status', ''):<10} v{c['_version']:<3} {cid:<32} {str(c.get('title', ''))[:90]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

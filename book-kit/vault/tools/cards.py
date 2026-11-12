#!/usr/bin/env python3
"""cards.py — the cards the author rules on, in one store, and the one way a card goes in.

    tools/cards.py list                                  # each card: status now, version, id, title
    tools/cards.py show <id>                             # the newest version of one card, whole, as JSON
    tools/cards.py counts                                # cards by status
    tools/cards.py add <card.json> --why "<reason>" [--by "<role>"]   # one version in, through add_version()
    tools/cards.py applied <id> --version <n> --edit-event <hash>      # Production: the card is in the book
    tools/cards.py hold <id> --by "<role>" --reason "<why>" [--unread-facts]   # off the author's desk
    tools/cards.py rehold <id> --by "<role>" --reason "<why>"          # a held card's new hold reason
    tools/cards.py release <id> --by "<role>"            # back before the author: the gates run again, the
                                                         # prose audit by a second session and the reviewer's PASS
    tools/cards.py withdraw <id> --by "<owner>" --reason "<why>"       # its writer closes a held card never approved
    tools/cards.py supersede <id> --by-card <other> --by "<owner>" --reason "<why>"   # ... replaced by another card
    tools/cards.py review-pass <id> --version <n> --by "<role>" --verdict PASS|FAIL --note "<what was read>"
                                [--finding "<one fault, with its fix>" ...]
    tools/cards.py review-fix <id> --by "<role>" --fix "1=<the words in the new version that answer finding 1>" ...
    tools/cards.py lift-stop <id> --by "Managing Editor" --reason "<why>"  # lifts the three-version stop
    tools/cards.py desk-why <id>                         # the lane the card desk gives the card, and each reason
    tools/cards.py split-by-day [--write]                # cards.jsonl into one file a day (below)

    import cards
    cards.fold()                 # {id: card now}: the newest version, then the author's presses after it
    cards.card(id)               # the newest version of one card, or None
    cards.add_version(id, record, by=..., why=...)

WHY ONE STORE

    The system this kit comes from first kept its cards on a claude.ai page with a database. No script could open
    the page, so every check worked from a snapshot a chat had copied, and a snapshot is out of date the moment the
    author presses a button. The author then asked for "a small server of its own ... One queue still holds: the
    cards live in one place and I rule in one place." This store is that one place, and `tools/card-desk.py` is the
    server.

THE STORE

    `Fact Check/Cards/` (book.toml [paths] cards names its first file). One line per card version, and the store
    only grows:

        {"id": ..., "version": n, "at": ..., "by": ..., "session": ...,
         "source": ..., "card": {the card record}}

    The newest line for an id is the card; older lines stay, so a version the author saw can be shown whole.
    Nothing rewrites a line.

    A store begins as one file, `cards.jsonl`. A busy book's store grows by megabytes a day, and GitHub refuses a
    file over 100 MB, so `split-by-day --write` turns it into one file a day, `cards-YYYY-MM-DD.jsonl` (UTC, the
    day of each line's `at`), read in date order as one sequence. After the split each new line goes to today's
    file. A folder holding both shapes is read by nobody: a writer on old code wrote it.

    The status inside a record is where the card stood when its line was written. After that the event log
    decides: `fold()` reads the author's presses (`decision.recorded` with `card`, actor = book.toml [book]
    author_actor) and Production's applies (`edit.applied` with `card`) written after the line, oldest first.

    Statuses: yours (waiting for the author), submitted (the author sent edits or a directive), approving (the
    author pressed Approve less than book.toml [desk] approve_wait_seconds ago, five minutes by default: his Undo
    still stands, and no tool acts on it), approved, applied, held (its owner took it off the desk: not ready),
    superseded (closed; never goes in).

    The author's words on the five minutes, in the system this kit comes from: "often there is a delay between
    hitting the accept button and realizing I missed something, so I end up hitting the back button in a panic."

THE GATES A VERSION PASSES ON THE WAY IN (`add_version`)

    Always refused, nothing written:
    - the card's chapter is out of the workflow (book.toml [workflow] out_of_workflow);
    - a field in REQUIRED is empty: a card shows the words;
    - the card is applied or superseded: a closed card takes no new version (a new fix goes on a new id).

    book.toml [gates], each "warn" (the writer sees the list, the card goes in) or "refuse" (nothing is written):
    - card_words      no banned word in the text the author would approve (`tools/check-card-words.py`);
    - card_own_words  no banned word in the card's own words to him: title, tldr, answer, each why and label;
    - card_reads      every name, number, date and quotation in that text has an opened, logged read
                      (`tools/card_reads.py`);
    - card_pointer, card_overlap, card_format_only, card_summary, card_choices, card_answer
                      (`tools/card_shape.py`, which says what each one checks);
    - card_three_versions  three versions that change the book's words since the author's newest directive or
                      edits, with no Approve of his: a fourth goes to the Managing Editor instead. The author, in
                      the system this kit comes from, after a card took eighteen versions past his directive.

    Each starts at warn and goes to refuse on the author's ok to a sample.

    Two rules keep a card's place:
    - A HOLD SURVIVES A NEW VERSION. A version written to a held card goes in held, with its hold, until its owner
      releases it. Writing a version never puts a card back on the author's desk; `release` does.
    - QUEUED BEHIND. A card with `queuedBehind: <other id>` waits behind that open card on the same lines: it goes
      in held (the overlap gate lets it past that one card), and when the card ahead is applied, `mark_applied`
      releases it, through the gates, to be checked against the chapter as the card ahead left it.

AT RELEASE

    `release` runs the word, read and pointer gates again, then three more, before a held card reaches the author:
    - card_cross_audit  a session that wrote no version of the card has audited this exact text (`tools/prose.py`);
    - card_desk_audit   the card's page, drawn as the author will see it, shows no asterisk, role name, file
                        path, code or gate name (`tools/desk_audit.py`);
    - card_review       a fresh reviewer's PASS covers this version (`review-pass`, or the six reviewers of
                        `tools/review_pipeline.py`). A FAIL is answered in ONE new version, and `review-fix`
                        quotes, for each finding, the words in that version that answer it; the reviewers do not
                        run again. "Six, once, at release."
"""
import contextlib
import copy
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import bookconfig as B  # noqa: E402

STORE = B.CARD_STORE                 # the one file a store begins as
DIR = B.CARD_DIR
DAY_RX = re.compile(r"^cards-(\d{4}-\d{2}-\d{2})\.jsonl$")
LOCKFILE = DIR / ".write.lock"
TOOL = "tools/cards.py"
OPEN = ("yours", "submitted")
#: What a new version must give. A card without the words the author would approve is unfinished.
REQUIRED = ("title", "chapter", "where", "current", "proposedPara", "status")
#: The author's presses on a card, as tools/card-desk.py records them.
PRESS_KINDS = ("approve", "edit", "directive", "card-note", "withdraw", "reopen", "keep_closed")
#: Store lines that change no book word: they never count toward the three-version stop.
NO_COUNT = ("cards.hold", "cards.rehold", "cards.release", "cards.release_queued", "card_refresh")
THREE_VERSIONS = 3
HOLD_FIELDS = ("heldBy", "heldReason", "heldFacts", "heldAt", "heldFrom")


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


# ---- the store -------------------------------------------------------------------------------------------------
def store_files() -> list:
    """The store's files in the order their lines were written. Refuses a folder holding both shapes."""
    days = sorted(p for p in DIR.glob("cards-*.jsonl") if DAY_RX.match(p.name)) if DIR.is_dir() else []
    if STORE.exists():
        if days:
            raise Refused(f"{rel(STORE)} and {len(days)} day file(s) are both in {rel(DIR)}. A writer on old code "
                          f"wrote {STORE.name}; run tools/cards.py split-by-day --write to fold its lines in first.")
        return [STORE]
    return days


def append_file() -> Path:
    """Where a new line goes: the one file before the split; after it, today's file (UTC), or the newest day file
    when its day is later, so the files in date order stay in the order of writing."""
    files = store_files()
    if not files or files == [STORE]:
        return STORE              # a store begins as one file
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return DIR / f"cards-{max(today, DAY_RX.match(files[-1].name).group(1))}.jsonl"


_CACHE = {"key": None, "lines": []}


def _parsed():
    """Every version line, parsed once per state of the files on disk."""
    files = store_files()
    key = tuple((f.name, f.stat().st_size, f.stat().st_mtime_ns, f.stat().st_ino) for f in files)
    if _CACHE["key"] == key:
        return _CACHE["lines"]
    out = []
    for f in files:
        for n, raw in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if not raw.strip():
                continue
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError as e:
                raise Refused(f"{rel(f)} line {n} is not JSON ({e}). A store with a broken line is read by nobody.")
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
    c["_source"] = line.get("source") or ""
    return c


def latest() -> dict:
    """{id: card} for the newest version of each card, as written."""
    newest = {}
    for l in _parsed():
        newest[l["id"]] = l
    return {cid: _as_card(copy.deepcopy(l)) for cid, l in newest.items()}


def card(card_id: str):
    return latest().get(card_id)


# ---- the author's presses ----------------------------------------------------------------------------------------
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


def _z(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _press(c: dict, e: dict):
    """Set on one card the fields a press of the author's sets."""
    k, at = e.get("decision_kind"), e.get("ts", "")
    open_ = c.get("status") not in ("approved", "approving", "applied")
    if k == "approve":
        c.update(status="approved", approvedAt=at, approvedChoice=e.get("choice"),
                 approvedText=e.get("choice_text") or "")
        due = _t(at) + timedelta(seconds=B.APPROVE_WAIT)
        if datetime.now(timezone.utc) < due:
            c.update(status="approving", settlesAt=_z(due))
    elif k == "edit":
        c.update(status="submitted", submittedAt=at, proposedPara=e.get("text") or "",
                 submittedPara=e.get("text") or "")
        if e.get("note") is not None:
            c.update(proposedNote=e["note"], submittedNote=e["note"])
    elif k in ("directive", "card-note"):
        c.update(note=e.get("text") or "", notedAt=at)
        if k == "directive" and e.get("what") == "leave":
            # "Keep it the way it is": his "leave it", and the card leaves his desk unapplied
            c.update(status="superseded", leftAt=at, closedReason="you kept the line the way it is")
        elif k == "directive":
            c["directiveAt"] = at
            if open_:
                c.update(status="submitted", submittedAt=at, submittedPara=c.get("proposedPara") or "")
    elif k == "withdraw":
        c.update(status="yours", approvedAt="", settlesAt="", withdrawnAt=at,
                 undoneAt=at if e.get("what") == "undo" else c.get("undoneAt", ""))
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
    """{id: card now}: each card's newest line, then the author's presses on that version and Production's applies
    written after it. The store is not touched."""
    cards = latest() if cards is None else cards
    out = {cid: dict(c) for cid, c in cards.items()}
    for e in card_events(set(out)):
        c = out[e["card"]]
        if _t(e.get("ts")) < _t(c["_at"]):
            continue
        if e["kind"] == "edit.applied":
            c.update(status="applied", appliedAt=e.get("ts", ""))
        elif e.get("actor") == B.AUTHOR_ACTOR and e.get("card_version") in (None, c["_version"]) \
                and e.get("decision_kind"):
            _press(c, e)
    return out


def status(card_id: str):
    c = card(card_id)
    return fold({card_id: c})[card_id].get("status") if c else None


def presses(card_id: str | None = None) -> list:
    """The author's card presses from the event log, oldest first, in the shape the closed-line check reads:
    {card, action, result, at, words}."""
    out = []
    for e in card_events(None if card_id is None else {card_id}):
        if e["kind"] == "decision.recorded" and e.get("actor") == B.AUTHOR_ACTOR and e.get("decision_kind"):
            out.append({"card": e["card"], "action": e.get("decision_kind"), "result": "saved",
                        "at": e.get("ts", ""), "words": e.get("text") or "", "version": e.get("card_version")})
    return out


def open_directive(card_id: str):
    """The author's newest directive, or edits with his words, on this card, when he has approved no version since:
    the event, or None. A card that answers it carries `answer` and counts toward the three-version stop."""
    best = None
    for e in card_events({card_id}):
        if e["kind"] != "decision.recorded" or e.get("actor") != B.AUTHOR_ACTOR:
            continue
        k = e.get("decision_kind")
        if k in ("directive", "edit") and str(e.get("text") or "").strip() and e.get("what") != "leave":
            best = e
        elif k == "approve":
            best = None
    return best


# ---- writing -----------------------------------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@contextlib.contextmanager
def _write_lock():
    """Two chats, one store: the read, the version number and the write happen under one lock."""
    DIR.mkdir(parents=True, exist_ok=True)
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
        target = append_file()
        before = target.read_text(encoding="utf-8") if target.exists() else ""
        sep = "" if (not before or before.endswith("\n")) else "\n"
        vaultlog.write_file(target, before + sep + line + "\n", tool=TOOL,
                            why=f"card {card_id} v{version} — {why}", backup=False)
    return version


def _gate(key: str, card_id: str, findings: list, label: str):
    """Warn or refuse, as book.toml [gates] says for `key`."""
    if not findings:
        return
    why = f"{card_id}: {label}:\n  - " + "\n  - ".join(findings)
    if B.gate_mode(key) == "refuse":
        raise Refused(why + "\nNothing written.")
    print("WARNING " + why + "\n(The card goes in; fix it before the author sees it.)", file=sys.stderr)


def _ccw():
    import importlib.util
    spec = importlib.util.spec_from_file_location("ccw", TOOLS / "check-card-words.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def word_findings(card_id: str, record: dict) -> list:
    return [f"{h['field']}: {h['word']!r} …{h['context']}… (carve-out: {h['carve_out'] or 'none'})"
            for h in _ccw().card_hits(dict(record, id=card_id))]


def own_word_findings(card_id: str, record: dict) -> list:
    return [f"{h['field']}: {h['word']!r} …{h['context']}…" for h in _ccw().own_hits(dict(record, id=card_id))]


def read_findings(card_id: str, record: dict) -> list:
    import card_reads
    return [f"{k}: {v[:160]}" for k, v in card_reads.unread_facts(dict(record, id=card_id))]


def queue_chain(record: dict, limit: int = 30) -> list:
    """The open cards up this card's `queuedBehind` chain, nearest first."""
    out, x = [], str(record.get("queuedBehind") or "")
    while x and x not in out and len(out) < limit:
        c = card(x)
        if c is None or fold({x: c})[x].get("status") in ("applied", "superseded"):
            break
        out.append(x)
        x = str(c.get("queuedBehind") or "")
    return out


def open_cards() -> dict:
    """{id: (card now, status)} for each card not yet in the book or closed."""
    return {cid: (c, c.get("status")) for cid, c in fold().items()
            if c.get("status") in ("yours", "submitted", "held", "approving", "approved") and not locked(c)}


def book_words(rec: dict) -> tuple:
    """The words the card would put in the book: the paragraph, the note and each choice's text."""
    import card_shape as S
    w = S.words
    return (tuple(w(rec.get("proposedPara"))), tuple(w(rec.get("proposedNote"))),
            tuple(tuple(w(c.get("text"))) for c in S.choices_of(rec)))


def stop_lifted(card_id: str, since: str):
    """The newest lift of the three-version stop after `since`: the author's own ruling on the card from his chat
    (a decision.recorded naming the card with no desk press kind), or `lift-stop` by the Managing Editor."""
    import vaultlog
    best = None
    for e in vaultlog.read_all():
        if e.get("card") != card_id or _t(e.get("ts")) <= _t(since):
            continue
        if (e.get("kind") == "note.recorded" and e.get("stop_lift")) or \
                (e.get("kind") == "decision.recorded" and e.get("actor") == B.AUTHOR_ACTOR and not e.get("decision_kind")):
            best = e
    return best


def _versions_since(card_id: str, since: str) -> int:
    n, prev = 0, None
    for l in versions(card_id):
        b = book_words(l["card"])
        if _t(l.get("at")) > _t(since) and l.get("source") not in NO_COUNT and b != prev:
            n += 1
        prev = b
    return n


def stop_reached(card_id: str):
    """(versions counted, the directive) when the three-version stop stands on the card now; else None. The card
    desk puts such a card in Questions for you."""
    d = open_directive(card_id)
    if not d:
        return None
    since = d.get("ts", "")
    lift = stop_lifted(card_id, since)
    if lift:
        since = lift.get("ts", "")
    n = _versions_since(card_id, since)
    return (n, d) if n >= THREE_VERSIONS else None


def _gates(card_id: str, record: dict, *, new: bool = False):
    import card_shape as S
    st = record.get("status")
    if st not in ("yours", "submitted", "approved", "held"):
        return
    if st in ("yours", "submitted", "approved"):
        _gate("card_words", card_id, word_findings(card_id, record),
              "banned word(s) in the text the author would approve (Methodology/Word Lists.md)")
        _gate("card_reads", card_id, read_findings(card_id, record),
              "fact(s) in the passage with no opened read in Fact Check/Claims/; the Fact-checker reads and logs each first")
    _gate("card_own_words", card_id, own_word_findings(card_id, record),
          "banned word(s) in the card's own words to the author")
    _gate("card_pointer", card_id, [f"…{h}…" for h in S.card_pointers(record)],
          "body text or a note that points the reader to another part of this book")
    if new and st != "approved":
        behind = queue_chain(record)
        hits = [h for h in S.collisions(card_id, record, open_cards()) if h[0] not in behind]
        _gate("card_overlap", card_id, [f"{oid} [{ost}] shares block(s) {', '.join(b)}" for oid, ost, b in hits],
              "its paragraph, or a note anchored in it, is already worked by another open card; fold it into that "
              "card, or give it `queuedBehind`")
    if st in ("yours", "submitted"):
        ok, why = S.format_only(record)
        if ok and record.get("reopenedBy") != "format-only":
            _gate("card_format_only", card_id, [why],
                  "a formatting change goes to Production without the author's desk: write it at status "
                  "\"approved\" with reopenedBy \"format-only\"")
        _gate("card_summary", card_id, S.summary_faults(record),
              "the card does not open with its TLDR, recommendation and subject, or a change has no reason")
        _gate("card_choices", card_id, S.choices_faults(record), "the card's choices are not one decision each")
        f = S.answer_fault(record, open_directive(card_id))
        _gate("card_answer", card_id, [f] if f else [], "the author's words are not answered at the top")


def _three_versions_gate(card_id: str, record: dict):
    """THREE VERSIONS, THEN THE MANAGING EDITOR. A fourth version that changes the book's words since the author's
    newest directive or edits, with no Approve of his and no lift, goes to the Managing Editor instead."""
    d = open_directive(card_id)
    vs = versions(card_id)
    if not d or not vs or book_words(record) == book_words(vs[-1]["card"]):
        return
    since = d.get("ts", "")
    lift = stop_lifted(card_id, since)
    if lift:
        since = lift.get("ts", "")
    n = _versions_since(card_id, since)
    if n >= THREE_VERSIONS:
        _gate("card_three_versions", card_id,
              [f"{n} versions since the author's {d.get('decision_kind')} of {str(since)[:16]} (event {d.get('hash')}), "
               f"and he has approved none"],
              "send the card to the Managing Editor (Handoffs/Managing Editor.md, Inbox) with what each version tried")


def add_version(card_id: str, record: dict, *, by: str, why: str, source: str = "") -> dict:
    """Put one card version in the store. THE ONE WAY A CARD GOES IN. Refuses, and writes nothing, when the chapter
    is out of the workflow, a REQUIRED field is empty, the record names another id, or the card is closed; then the
    gates in book.toml [gates] (above)."""
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
    prev = card(card_id)
    now = fold({card_id: prev})[card_id].get("status") if prev else None
    if now in ("applied", "superseded"):
        raise Refused(f"{card_id} v{prev['_version']} is {now!r}; a closed card takes no new version. Open a new card "
                      f"id for the new fix; nothing written.")
    rec = {k: v for k, v in record.items() if k != "id" and not k.startswith("_")}
    _gates(card_id, rec, new=prev is None)
    _three_versions_gate(card_id, rec)
    behind = str(rec.get("queuedBehind") or "")
    if behind and rec.get("status") in OPEN:
        ahead = card(behind)
        if ahead is None or fold({behind: ahead})[behind].get("status") in ("applied", "superseded"):
            raise Refused(f"{card_id}: `queuedBehind` names {behind!r}, which is not an open card; write the card "
                          f"without it, its lines as the chapter reads now. Nothing written.")
        rec.update(heldFrom=rec["status"], status="held", heldBy=by, heldAt=_now(), heldFacts=[],
                   heldReason=f"queued behind {behind}: it goes before the author when {behind} is applied")
    elif prev is not None and now == "held" and rec.get("status") in OPEN:
        rec["heldFrom"] = rec["status"]
        rec["status"] = "held"
        for k in HOLD_FIELDS[:-1]:
            if k in prev:
                rec[k] = prev[k]
        print(f"NOTE {card_id}: held by {prev.get('heldBy') or 'its owner'}; this version goes in held. "
              f"`tools/cards.py release {card_id} --by \"<owner>\"` puts it before the author.", file=sys.stderr)
    version = _append(card_id, rec, by=by, source=source, why=why)
    ev = vaultlog.append("proposal.written", actor=by, card=card_id, version=version,
                         where=record.get("where"), title=record.get("title"), why=why)["hash"]
    return {"id": card_id, "version": version, "proposal_event": ev}


def mark_applied(card_id: str, version: int, *, edit_event: str, by: str = "Production") -> str:
    """Production's one way to mark a card applied: one `edit.applied` event with `card` and `card_version`.
    Refuses unless the card is approved now (an approval still inside its wait is not) and `version` is its newest.
    Then tools/card_refresh.py looks at every other open card of the chapter, and each card queued behind this one
    is released through the gates."""
    import vaultlog
    c = card(card_id)
    if c is None:
        raise Refused(f"no card {card_id!r} in {rel(DIR)}; nothing written.")
    now = fold({card_id: c})[card_id]
    if now.get("status") == "approving":
        raise Refused(f"{card_id} was approved less than {int(B.APPROVE_WAIT)} seconds ago, and the author can still "
                      f"undo it; apply it after {now.get('settlesAt')}. Nothing written.")
    if now.get("status") != "approved":
        raise Refused(f"{card_id} is {now.get('status')!r}, not 'approved'; nothing written.")
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
    for line in release_queued(card_id, by=by):
        print(f"queued: {line}", file=sys.stderr)
    return h


def release_queued(applied_id: str, *, by: str) -> list:
    """Each held card whose `queuedBehind` is `applied_id`, released through the gates; a card the gates refuse
    stays held, with the reason, for its owner."""
    out = []
    for cid, c in fold().items():
        if c.get("status") != "held" or c.get("queuedBehind") != applied_id:
            continue
        rec = {k: v for k, v in versions(cid)[-1]["card"].items() if k not in HOLD_FIELDS and k != "queuedBehind"}
        rec["status"] = c.get("heldFrom") or "yours"
        try:
            _gates(cid, rec)
            _append(cid, rec, by=by, source="cards.release_queued", why=f"{applied_id} applied; the card ahead is in")
            out.append(f"{cid} released: {applied_id} is in the book")
        except Refused as e:
            out.append(f"{cid} stays held: {str(e).splitlines()[0]}")
    return out


def _held_by_owner(card_id: str, by: str) -> dict:
    """The card, when `by` owns it, it is held, and the author approved no version of it; else Refused."""
    c = card(card_id)
    if c is None:
        raise Refused(f"no card {card_id!r}; nothing written.")
    if fold({card_id: c})[card_id].get("status") != "held":
        raise Refused(f"{card_id} is not held by its owner; this door closes only a card its owner holds.")
    owner = str(c.get("heldBy") or versions(card_id)[-1].get("by") or "").strip()
    if owner != str(by or "").strip():
        raise Refused(f"{card_id} is held by {owner!r}, not {by!r}; only its owner closes it. Nothing written.")
    if any(x["action"] == "approve" for x in presses(card_id)) or \
            any(l["card"].get("status") in ("approved", "applied") for l in versions(card_id)):
        raise Refused(f"{card_id}: a version of it was approved; a card the author approved closes only through "
                      f"Production. Nothing written.")
    return c


def withdraw(card_id: str, *, reason: str, by: str) -> int:
    """Its writer closes its own held card, never approved, that no other card replaces: status "superseded", with
    `withdrawn`, `closedReason`, `closedAt`. The desk lists it among closed cards as "Withdrawn by its writer"."""
    _held_by_owner(card_id, by)
    if not str(reason or "").strip():
        raise Refused(f"{card_id}: no reason given; nothing written.")
    rec = dict(versions(card_id)[-1]["card"])
    rec.update(status="superseded", withdrawn=True, closedReason=reason.strip(), closedAt=_now())
    return _append(card_id, rec, by=by, source="cards.withdraw", why=f"withdrawn by its writer: {reason.strip()}")


def supersede(card_id: str, *, by_card: str, reason: str, by: str) -> int:
    """Its writer closes its own held card, never approved, as replaced by another open card."""
    _held_by_owner(card_id, by)
    other = card(by_card)
    if other is None or by_card == card_id or \
            fold({by_card: other})[by_card].get("status") in ("superseded",):
        raise Refused(f"{card_id}: {by_card!r} is not another open card; nothing written.")
    if not str(reason or "").strip():
        raise Refused(f"{card_id}: no reason given; nothing written.")
    rec = dict(versions(card_id)[-1]["card"])
    rec.update(status="superseded", supersededBy=by_card, closedReason=reason.strip(), closedAt=_now())
    return _append(card_id, rec, by=by, source="cards.supersede", why=f"superseded by {by_card}: {reason.strip()}")


def hold(card_id: str, *, reason: str, by: str, facts=None) -> int:
    """Take a card waiting for the author off the desk until its owner releases it: one version line, status
    "held", with heldBy, heldReason, heldFacts and heldAt. The author sees only cards that are ready."""
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


def rehold(card_id: str, *, reason: str, by: str) -> int:
    """A held card's holder gives it a new hold reason; nothing else changes."""
    c = card(card_id)
    if c is None or fold({card_id: c})[card_id].get("status") != "held":
        raise Refused(f"{card_id} is not held; nothing written.")
    if by not in (c.get("heldBy"), "Managing Editor") or not str(reason or "").strip():
        raise Refused(f"{card_id}: only its holder ({c.get('heldBy')}) or the Managing Editor gives a new hold "
                      f"reason, and gives it in words; nothing written.")
    rec = dict(versions(card_id)[-1]["card"])
    rec.update(heldReason=reason.strip(), heldAt=_now())
    return _append(card_id, rec, by=by, source="cards.rehold", why=f"new hold reason from {by}: {reason.strip()}")


def lift_stop(card_id: str, *, by: str, reason: str) -> str:
    """The Managing Editor lifts the three-version stop: one note.recorded naming the card. The count starts again."""
    import vaultlog
    if by != "Managing Editor":
        raise Refused(f"{card_id}: only the Managing Editor lifts the three-version stop; nothing written.")
    if not str(reason or "").strip() or card(card_id) is None:
        raise Refused(f"{card_id}: a lift names a card in the store and gives its reason; nothing written.")
    return vaultlog.append("note.recorded", actor=by, card=card_id, stop_lift=True, reason=reason.strip(),
                           why=f"three-version stop lifted: {reason.strip()}")["hash"]


# ---- the fresh reviewer ------------------------------------------------------------------------------------------
_STANDING = HOLD_FIELDS + ("status", "queuedBehind", "approvedAt", "appliedAt", "submittedAt")


def review_sig(rec: dict) -> str:
    """A short hash of what the author will read on the card: every field but the ones that say where it stands."""
    body = {k: v for k, v in (rec or {}).items() if k not in _STANDING and not k.startswith("_")}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def _rec_at(card_id: str, version):
    for l in versions(card_id):
        if int(l["version"]) == int(version or -1):
            return l["card"]
    return None


def review_pass(card_id: str, *, version: int, by: str, verdict: str, note: str, findings=None) -> str:
    """A fresh reviewer's verdict on the newest version: one note.recorded event with the hash of the text read,
    so `release` can tell the verdict covers the version it puts before the author."""
    import vaultlog
    verdict = str(verdict or "").strip().upper()
    if verdict not in ("PASS", "FAIL"):
        raise Refused(f"{card_id}: the verdict is PASS or FAIL; nothing written.")
    if not str(note or "").strip():
        raise Refused(f"{card_id}: a verdict gives its note (--note): what the reviewer read and found; nothing written.")
    vs = versions(card_id)
    if not vs:
        raise Refused(f"no card {card_id!r}; nothing written.")
    if int(version) != int(vs[-1]["version"]):
        raise Refused(f"{card_id}: v{version} is not the newest version (v{vs[-1]['version']}); the reviewer reads "
                      f"the version that will go before the author. Nothing written.")
    findings = [str(f).strip() for f in (findings or []) if str(f).strip()] or ([str(note).strip()] if verdict == "FAIL" else [])
    return vaultlog.append("note.recorded", actor=by, card=card_id, review_pass=True, version=int(version),
                           verdict=verdict, sig=review_sig(vs[-1]["card"]), note=str(note).strip(),
                           **({"findings": findings} if verdict == "FAIL" else {}),
                           why=f"fresh reviewer {verdict} on {card_id} v{version}")["hash"]


def _reviews(card_id: str) -> list:
    import vaultlog
    return [e for e in vaultlog.read_all() if e.get("card") == card_id and e.get("kind") == "note.recorded"
            and (e.get("review_pass") or e.get("review_fix"))]


def review_verdict(card_id: str, rec: dict):
    """The newest reviewer verdict on this exact text, or None."""
    sig = review_sig(rec)
    hits = [e for e in _reviews(card_id) if e.get("review_pass") and e.get("sig") == sig]
    return hits[-1] if hits else None


def _last_fail(card_id: str):
    fails = [e for e in _reviews(card_id) if e.get("review_pass") and e.get("verdict") == "FAIL"]
    return fails[-1] if fails else None


def _words_of(rec: dict) -> str:
    out = []

    def walk(x):
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, dict):
            for k, v in x.items():
                if k not in _STANDING:
                    walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)
    walk(rec or {})
    return re.sub(r"\s+", " ", " ".join(out))


def review_fix(card_id: str, *, by: str, fixes: dict) -> str:
    """THE FIX LIST AFTER A FAIL. One note.recorded event on the newest version: for each finding of the newest FAIL,
    by its number, the words in this version that answer it. Refuses unless this is the one new text written after
    the version the FAIL read, every finding is answered, and each answer's words stand in this version."""
    import vaultlog
    vs = versions(card_id)
    f = _last_fail(card_id)
    if not vs or f is None:
        raise Refused(f"{card_id}: no reviewer has recorded a FAIL on it; a fix list answers a FAIL. Nothing written.")
    rec = vs[-1]["card"]
    later = []
    for l in vs:
        if int(l["version"]) > int(f["version"]) and review_sig(l["card"]) not in later + [f["sig"]]:
            later.append(review_sig(l["card"]))
    if not later or later[-1] != review_sig(rec):
        raise Refused(f"{card_id}: the newest version has the text the FAIL read; write the fixed version first.")
    if len(later) > 1:
        raise Refused(f"{card_id}: {len(later)} new texts were written after the FAIL on v{f['version']}; the fix goes "
                      f"in one new version, and a second one goes back to a reviewer. Nothing written.")
    finds = f.get("findings") or [f.get("note", "")]
    fixes = {int(k): str(v).strip() for k, v in (fixes or {}).items()}
    missing = [i for i in range(1, len(finds) + 1) if not fixes.get(i)]
    if missing:
        raise Refused(f"{card_id}: the fix list leaves out finding(s) {missing}:\n  "
                      + "\n  ".join(f"{i}. {finds[i - 1][:200]}" for i in missing) + "\nNothing written.")
    words = _words_of(rec)
    absent = [i for i, w in sorted(fixes.items()) if re.sub(r"\s+", " ", w) not in words]
    if absent:
        raise Refused(f"{card_id}: the words given for finding(s) {absent} are not in v{vs[-1]['version']}; quote the "
                      f"words of the new version that answer each finding. Nothing written.")
    return vaultlog.append("note.recorded", actor=by, card=card_id, review_fix=True, version=int(vs[-1]["version"]),
                           sig=review_sig(rec), fail=f.get("hash"), fixes={str(k): v for k, v in sorted(fixes.items())},
                           why=f"fix list on {card_id} v{vs[-1]['version']} for the FAIL on v{f['version']}")["hash"]


def review_findings(card_id: str, rec: dict) -> list:
    """[] when a PASS covers this text, or a fix list on it answers the newest FAIL; else why not, in one line."""
    v = review_verdict(card_id, rec)
    if v and v.get("verdict") == "PASS":
        return []
    f = _last_fail(card_id)
    fx = [e for e in _reviews(card_id) if e.get("review_fix") and f and e.get("fail") == f.get("hash")
          and e.get("sig") == review_sig(rec)]
    if fx:
        return []
    if v:
        return [f"the newest verdict on this text is FAIL: {str(v.get('note'))[:200]}"]
    return [f"no fresh reviewer has read this version; one reads it as the author will see it "
            f"(python3 tools/card-desk.py --show <id>) and records the verdict (tools/cards.py review-pass)"]


def release(card_id: str, *, by: str) -> int:
    """Put a held card back before the author. It reaches the desk, so the gates run again, then the second
    session's prose audit of this text (card_cross_audit) and the fresh reviewer's verdict (card_review)."""
    import prose
    c = card(card_id)
    if c is None:
        raise Refused(f"no card {card_id!r}; nothing written.")
    if fold({card_id: c})[card_id].get("status") != "held":
        raise Refused(f"{card_id} is not held; nothing written.")
    rec = {k: v for k, v in versions(card_id)[-1]["card"].items() if k not in HOLD_FIELDS}
    rec["status"] = c.get("heldFrom") or "yours"
    _gates(card_id, rec)
    text = prose.card_text(rec)
    if text.strip():
        oa = prose.other_audit(card_id, prose.text_sha(text))
        _gate("card_cross_audit", card_id, [] if oa and oa.get("verdict", "ok") == "ok" else
              ["no session that wrote none of its versions has audited this text with verdict ok"],
              "a second session works the newest text through the neurolinguistic-prose skill (prose.py --record-card)")
    _gate("card_review", card_id, review_findings(card_id, dict(versions(card_id)[-1]["card"])),
          "a fresh reviewer's PASS on this version, or a fix list answering the newest FAIL")
    import desk_audit
    _gate("card_desk_audit", card_id, [f"{k}: …{w[:140]}…" for k, w in desk_audit.card_faults(card_id, rec)[:8]],
          "its page on the author's desk would show what has no place there (tools/desk_audit.py)")
    return _append(card_id, rec, by=by, source="cards.release", why=f"released by {by}")


def split_by_day(write: bool = False) -> dict:
    """cards.jsonl into one file per UTC day of each line's `at`. With `write`, the day files are written, every
    card is checked to fold to the same record, and cards.jsonl moves to cards.jsonl.split-<time> beside them."""
    if not STORE.exists():
        raise Refused(f"no {rel(STORE)} to split.")
    before = fold()
    lines = [l for l in STORE.read_text(encoding="utf-8").splitlines() if l.strip()]
    days = {}
    for raw in lines:
        day = str(json.loads(raw).get("at") or "")[:10] or "0000-00-00"
        days.setdefault(day, []).append(raw)
    plan = {f"cards-{d}.jsonl": len(v) for d, v in sorted(days.items())}
    if not write:
        return plan
    import vaultlog
    with _write_lock():
        for d, v in sorted(days.items()):
            vaultlog.write_file(DIR / f"cards-{d}.jsonl", "\n".join(v) + "\n", tool=TOOL,
                                why="split-by-day: the store into one file a day", backup=False)
        STORE.rename(STORE.with_name(STORE.name + ".split-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")))
    _CACHE["key"] = None
    after = fold()
    bad = [cid for cid in before if json.dumps(before[cid], sort_keys=True, default=str)
           != json.dumps(after.get(cid), sort_keys=True, default=str)]
    if bad:
        raise Refused(f"after the split {len(bad)} card(s) fold differently: {bad[:5]}. The old file is beside the "
                      f"day files; move it back and remove them.")
    return plan


def _opt(argv, name, default=""):
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default


def _opts(argv, name):
    return [argv[i + 1] for i, a in enumerate(argv) if a == name and i + 1 < len(argv)]


COMMANDS = ("list", "show", "counts", "add", "applied", "hold", "rehold", "release", "withdraw", "supersede",
            "review-pass", "review-fix", "lift-stop", "desk-why", "split-by-day")


def main(argv):
    if not argv or argv[0] not in COMMANDS:
        print(__doc__)
        return 2
    cmd, cid = argv[0], (argv[1] if len(argv) > 1 else "")
    by = _opt(argv, "--by")
    try:
        if cmd == "add":
            if len(argv) < 2 or not _opt(argv, "--why"):
                print('usage: tools/cards.py add <card.json> --why "<reason>" [--by "<role>"]')
                return 2
            record = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
            if not record.get("id"):
                print(f"{argv[1]} gives no id; nothing written.")
                return 1
            got = add_version(record["id"], record, by=by or "Editor", why=_opt(argv, "--why"), source=rel(argv[1]))
            print(f"{got['id']} v{got['version']} written; proposal.written {got['proposal_event']}")
            return 0
        if cmd == "applied":
            h = mark_applied(cid, int(_opt(argv, "--version", "0")), edit_event=_opt(argv, "--edit-event"),
                             by=by or "Production")
            print(f"{cid} marked applied; edit.applied {h}")
            return 0
        if cmd == "hold":
            facts = read_findings(cid, card(cid) or {}) if "--unread-facts" in argv else []
            v = hold(cid, reason=_opt(argv, "--reason"), by=by, facts=facts)
            print(f"{cid} v{v} held by {by}" + (f"; {len(facts)} unread fact(s) listed" if facts else ""))
            return 0
        if cmd == "rehold":
            print(f"{cid} v{rehold(cid, reason=_opt(argv, '--reason'), by=by)} held, with the new reason")
            return 0
        if cmd == "release":
            print(f"{cid} v{release(cid, by=by)} released to the author's desk")
            return 0
        if cmd == "withdraw":
            print(f"{cid} v{withdraw(cid, reason=_opt(argv, '--reason'), by=by)} withdrawn by its writer")
            return 0
        if cmd == "supersede":
            v = supersede(cid, by_card=_opt(argv, "--by-card"), reason=_opt(argv, "--reason"), by=by)
            print(f"{cid} v{v} superseded by {_opt(argv, '--by-card')}")
            return 0
        if cmd == "review-pass":
            h = review_pass(cid, version=int(_opt(argv, "--version", "0")), by=by, verdict=_opt(argv, "--verdict"),
                            note=_opt(argv, "--note"), findings=_opts(argv, "--finding"))
            print(f"{cid}: verdict recorded, event {h}")
            return 0
        if cmd == "review-fix":
            fixes = dict(x.split("=", 1) for x in _opts(argv, "--fix") if "=" in x)
            print(f"{cid}: fix list recorded, event {review_fix(cid, by=by, fixes=fixes)}")
            return 0
        if cmd == "lift-stop":
            print(f"{cid}: three-version stop lifted, event {lift_stop(cid, by=by, reason=_opt(argv, '--reason'))}")
            return 0
        if cmd == "split-by-day":
            plan = split_by_day(write="--write" in argv)
            for f, n in plan.items():
                print(f"  {f}: {n} line(s)")
            print(("written; every card folds as before" if "--write" in argv else "dry run; --write splits"))
            return 0
    except Refused as e:
        print(f"REFUSED: {e}")
        return 1
    now = fold()
    if cmd == "desk-why":
        if cid not in now:
            print(f"no card {cid!r}")
            return 1
        import importlib.util
        spec = importlib.util.spec_from_file_location("desk", TOOLS / "card-desk.py")
        d = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(d)
        lane, why = d.Gates().lane(cid, now[cid])
        print(f"{cid} v{now[cid]['_version']} [{now[cid].get('status')}]: {d.LANE_NAME[lane]}")
        for w in why:
            print(f"  - {w}")
        v = review_verdict(cid, versions(cid)[-1]["card"])
        print(f"  reviewer: {v.get('verdict') + ' by ' + str(v.get('actor')) if v else 'no verdict on this text'}")
        return 0
    if cmd == "show":
        c = now.get(cid)
        if c is None:
            print(f"no card {cid!r} in {rel(DIR)}")
            return 1
        print(json.dumps(c, ensure_ascii=False, indent=1))
        return 0
    if cmd == "counts":
        from collections import Counter
        n = Counter(c.get("status") for c in now.values())
        print(f"{len(now)} cards in {rel(DIR)}: " + (", ".join(f"{k} {v}" for k, v in n.most_common()) or "none"))
        return 0
    for cid, c in sorted(now.items(), key=lambda kv: (chapter_of(kv[1]) or 999, kv[0])):
        print(f"{c.get('status', ''):<10} v{c['_version']:<3} {cid:<32} {str(c.get('title', ''))[:90]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

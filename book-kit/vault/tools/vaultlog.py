#!/usr/bin/env python3
"""vaultlog.py — the append-only, hash-chained event log that every tool writes to.

    import vaultlog
    vaultlog.append("note.recorded", actor="claude", text="...")
    vaultlog.write_file(path, new_text, tool="my-tool.py", why="...")
    python3 tools/vaultlog.py --verify      # is the chain whole?

The author's rulings are recorded with actor = bookconfig.AUTHOR_ACTOR.

WHY THIS FILE IS THE FOUNDATION

    In the system this kit comes from, nothing the author typed was recorded
    anywhere except the markdown file it landed in. One bug in a save routine
    deleted 58 of the author's rulings (443 answered items went in, 385 came
    out), and it was caught only because somebody happened to count. A second
    bug cleared the status of six more. Neither left a trace. With this log in
    place, every ruling is recoverable word for word.

WHY JSONL AND NOT A DATABASE FILE

    Anything built from the log is disposable: delete it, rebuild it from the
    log, and nothing is lost. Nothing in the log is ever changed after it is
    written, so state cannot be corrupted by an update. The log stays
    greppable, diffable and readable in git.

THE HASH CHAIN

    Every record holds the hash of the one before it. A truncated log, a
    hand-edited line or a lost write breaks the chain, and `verify_chain()`
    says where. A log that cannot prove it is whole is a log nobody should
    trust.

WHAT AN EVENT IS

    An event says what happened, never what is true now. Current state is
    worked out by folding the log; it is never stored and never edited.

        decision.recorded      the author answered an item
        proposal.raised        an item was put to the author
        edit.applied           text was written into a chapter
        edit.reverted          text was put back
        block.assigned         block ids were stamped into the chapters
        block.changed          a chapter block's content hash moved
        block.deleted          a chapter block stopped existing
        source.read            somebody opened a source and read a page
        claim.made             a number was asserted, with the method that made it
        disagreement.opened    two sources answered one question differently
        disagreement.resolved  with a verdict AND a cause, both required
        file.written           a tool wrote a file (see write_file)

PUBLIC FUNCTIONS

    append(kind, actor="claude", **payload) -> dict
    read_all() -> list
    verify_chain() -> (ok, problems)
    fold(kind=None, include_retracted=False, **match) -> iterator
    retract(event, why, actor="claude") -> dict
    retracted_hashes() -> set
    record_write(path, before, after, tool, why="") -> dict
    record_edit(*, path, old, new, sheet="", item="", block="", coord="",
                role="", tool="", why="", idx=None) -> dict
    edits_applied(sheet="", item="") -> list
    write_file(path, new_text, tool, why="", backup=True) -> dict | None
    is_chapter(path) -> bool

    KINDS, LOGDIR, BLOCK_ID_RE, CHAPTER_DOORS, ALLOW_DROP, IN_BLOCKEDIT,
    IN_BLOCKID, LAST_LINE_PARTIAL
"""
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402

VAULT = B.VAULT
LOGDIR = B.EVENTS

# An event kind not on this list is a typo, and a typo that writes is a silent
# hole in the record. Add a kind deliberately, here, before the first tool
# writes it: in the original system a new review page raised ValueError on the
# author's first ruling because nobody had added its kind, and the guard was
# right to refuse.
KINDS = {
    "decision.recorded", "proposal.raised", "item.superseded",
    "edit.applied", "edit.reverted", "edit.refused",
    "block.assigned", "block.changed", "block.deleted",
    "source.read", "source.absent",
    "claim.made", "disagreement.opened", "disagreement.resolved",
    "rule.stated", "note.recorded", "file.written", "file.changed.unexplained",
    # A proposal a machine can apply: `block_id`, `old_hash` and `new_text` —
    # which line, what it said when the proposal was written, and the whole
    # replacement. Applying it is
    # `blockedit.replace(block_id, new_text, expect_hash=old_hash)`: no parsing,
    # no matching on opening words, and a stale proposal is refused instead of
    # overwriting newer words. In the original system nearly every ruled item
    # held only prose saying what to change, so applying meant exact-match
    # surgery by hand, one item at a time.
    "proposal.written",
    # The prose audit, recorded against the exact text it audited: `text_sha`
    # (the hash of the proposed text) and `findings`. The author could tell
    # from one phrase that a proposal had skipped the prose audit, and nothing
    # recorded whether it had been run. Hashing the text means a rewritten
    # proposal's audit goes stale on its own, because the audit was of the old
    # words.
    "prose.audited",
    # The author's ruling on one footnote, addressed by chapter and slug:
    # `chapter`, `slug`, `note_kind` (apply, promote, no_change, instruct or
    # skip) and the author's words.
    "note.ruled",
    # Markup put back into one of the author's submissions after a plain-text
    # round trip stripped carets, italics or block ids. `of` is the hash of the
    # author's own event, so the repair is tied to that submission. The
    # author's words are never changed; only markup is restored.
    "submission.repaired",
    # Something Claude told the author that turned out false, and the
    # correction: `claim`, `said_when`, `wrong_because`, `corrected_to`,
    # `found_by`. The author asked whether Claude was logging "what I said
    # earlier was wrong"; it was not, and every wrong statement lived in the
    # chat and nowhere else.
    "claim.corrected",
    # A chapter locked or unlocked, written by tools/lock.py: `chapter`,
    # `state` (locked / unlocked) and `note`; the actor is the role.
    "lock.changed",
}


def _logfile(ts: datetime) -> Path:
    LOGDIR.mkdir(parents=True, exist_ok=True)
    return LOGDIR / f"{ts:%Y-%m}.jsonl"


def _last_hash() -> str:
    """The hash of the most recent record anywhere in the log."""
    files = sorted(LOGDIR.glob("*.jsonl")) if LOGDIR.is_dir() else []
    for f in reversed(files):
        lines = [l for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        if lines:
            return json.loads(lines[-1])["hash"]
    return "0" * 16


def _hash(record: dict) -> str:
    body = json.dumps({k: v for k, v in record.items() if k != "hash"},
                      sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def append(kind: str, actor: str = "claude", **payload) -> dict:
    """Write one event and return it. Never overwrites, never updates.

    The write is atomic: the line is built whole, then appended with a single
    os.write to a file opened O_APPEND, and fsynced. A crash mid-write cannot
    leave a half-record, which is how the original system lost 58 rulings.
    """
    if kind not in KINDS:
        raise ValueError(f"unknown event kind {kind!r} — add it to KINDS deliberately")
    ts = datetime.now(timezone.utc)
    rec = {
        "ts": ts.isoformat(timespec="seconds"),
        "kind": kind,
        "actor": actor,
        "prev": _last_hash(),
        **payload,
    }
    rec["hash"] = _hash(rec)
    _READ_CACHE["key"] = None          # this process just changed the log
    line = json.dumps(rec, ensure_ascii=False) + "\n"
    path = _logfile(ts)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
        os.fsync(fd)          # on disk before the caller goes on to touch a file
    finally:
        os.close(fd)
    return rec


# Set when read_all() had to skip a half-written final line, so the caller can
# say so instead of pretending the log is shorter than it is.
LAST_LINE_PARTIAL = []


# THE LOG IS PARSED ONCE PER FILE STATE, NOT ONCE PER QUESTION.
#
# In the original system a page rebuild re-read the whole log for every item it
# showed — hundreds of full reads and millions of json.loads calls to answer
# the same question, and the author waited over a minute for a button. The
# cache key is the state of the files themselves (each log file's name, mtime
# in nanoseconds, and size), so it cannot go stale: the moment append() writes,
# the key changes and the next read re-parses. A cache keyed on anything else
# would be a guess about when the log changed.
_READ_CACHE = {"key": None, "rows": None}


def _log_key():
    """Every log file's identity and state. One stat per file."""
    if not LOGDIR.is_dir():
        return ()
    out = []
    for f in sorted(LOGDIR.glob("*.jsonl")):
        st = f.stat()
        out.append((f.name, st.st_mtime_ns, st.st_size))
    return tuple(out)


def read_all():
    """Every event, oldest first.

    A READER CAN ARRIVE MID-APPEND, AND THAT IS NOT CORRUPTION.

    append() writes each record with one O_APPEND write and fsyncs it, so a
    reader can only ever catch the LAST line half-written; every earlier line
    is whole. An unparseable final line is skipped and named in
    LAST_LINE_PARTIAL. An unparseable line anywhere else still raises, because
    that is real damage and must not pass quietly. (In the original system a
    page rebuild died on a half-written last line while a ruling was being
    saved, and told the author his counts might lag, when nothing was lost.)
    """
    key = _log_key()
    if _READ_CACHE["key"] == key and _READ_CACHE["rows"] is not None:
        return _READ_CACHE["rows"]
    del LAST_LINE_PARTIAL[:]
    if not LOGDIR.is_dir():
        return []
    out = []
    files = sorted(LOGDIR.glob("*.jsonl"))
    for f in files:
        lines = [l for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        for i, line in enumerate(lines):
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                if i == len(lines) - 1 and f == files[-1]:
                    LAST_LINE_PARTIAL.append(f"{f.name} line {i + 1}")
                    continue
                raise
    _READ_CACHE["key"], _READ_CACHE["rows"] = key, out
    return out


def verify_chain():
    """(ok, problems). A log that cannot prove it is whole is not evidence."""
    problems = []
    prev = "0" * 16
    for i, rec in enumerate(read_all(), 1):
        if rec.get("prev") != prev:
            problems.append(f"record {i} ({rec.get('ts')}) expected prev={prev} "
                            f"got {rec.get('prev')} — a record was removed or reordered")
        if _hash(rec) != rec.get("hash"):
            problems.append(f"record {i} ({rec.get('ts')}) was edited after it was written")
        prev = rec.get("hash", "")
    return (not problems), problems


def fold(kind=None, include_retracted: bool = False, **match):
    """Events of one kind (or all), matching every key=value given.
    Retracted events are left out unless asked for.

    A RETRACTION NOTHING READS IS NOT A RETRACTION. In the original system
    fold() returned every event and left each of its thirty-odd callers to
    remember retracted_hashes() on its own. Three forgot, and the author found
    each one: a gate went on refusing a card whose blocking edit had been
    withdrawn, a check reported a withdrawn item as vanished, and a test's
    fixture card showed up on the author's real review board. One cause: the
    default was wrong. A caller that wants the raw history asks for it by name.
    """
    gone = set() if include_retracted else retracted_hashes()
    for rec in read_all():
        if kind and rec.get("kind") != kind:
            continue
        if not include_retracted and rec.get("hash") in gone:
            continue
        if all(rec.get(k) == v for k, v in match.items()):
            yield rec


def retract(event: dict, why: str, actor: str = "claude") -> dict:
    """Undo ONE event by naming its hash. The event itself stays on the record.

    A RETRACTION NAMES AN EVENT, NEVER A ROW. In the original system two test
    rulings were retracted by naming the item they landed on, and from then on
    every later ruling on that item was discarded too: the author clicked a
    button four times, all four rulings reached the log, and all four were
    thrown away. An address is not an identity. The hash is.
    """
    return append("note.recorded", actor=actor,
                  retracts_hash=event["hash"], text=why)


def retracted_hashes() -> set:
    """Every event hash undone by a later `note.recorded` with `retracts_hash`."""
    return {n["retracts_hash"] for n in read_all()
            if n.get("kind") == "note.recorded" and n.get("retracts_hash")}


def _rel(p: Path) -> str:
    """A path as the log records it: relative to the vault when inside it."""
    try:
        return str(Path(p).resolve().relative_to(VAULT))
    except ValueError:
        return str(p)


def record_write(path, before: str, after: str, tool: str, why: str = "") -> dict:
    """Log a file write BEFORE it happens. Returns the event.

    WHY THIS IS MANDATORY

    An editor's own file history captures what happens between commits, the
    window git cannot see, but its store may not be readable from where the
    tools run. So the vault keeps its own between-commit history. append()
    closes that window for the author's submissions; this closes it for tool
    writes — the window in which, in the original system, a tool deleted a
    whole body paragraph, put a duplicate footnote definition in its place,
    and nothing noticed for a day.

    The hashes and a unified diff are stored; the file itself is in git, and
    the diff tells a reader what moved. `witness.py` matches `before_hash` and
    `after_hash` against the files on disk.
    """
    import difflib
    payload = {
        "path": _rel(path),
        "tool": tool,
        "why": why,
        "before_hash": hashlib.sha256(before.encode("utf-8")).hexdigest()[:16],
        "after_hash": hashlib.sha256(after.encode("utf-8")).hexdigest()[:16],
        "before_lines": len(before.splitlines()),
        "after_lines": len(after.splitlines()),
        "diff": "".join(difflib.unified_diff(
            before.splitlines(True), after.splitlines(True), n=1))[:20000],
    }
    return append("file.written", actor=tool, **payload)


def record_edit(*, path, old: str, new: str, sheet: str = "", item: str = "",
                block: str = "", coord: str = "", role: str = "",
                tool: str = "", why: str = "", idx=None):
    """ONE EDIT, with the exact strings, tied to the card that caused it.

    `sheet` and `item` name the card the edit served, when it served one
    (empty otherwise).

    WHY THIS EXISTS

        A proposal is what was asked for. This record is what was done. In the
        original system only whole-file diffs were logged, and none said which
        item they served; once the proposals were rewritten or deleted after
        being applied, the reconciliation page reported 65 applied rulings as
        never having existed.

    THE STRINGS ARE KEPT WHOLE

        No slicing, no ellipsis, no cap. A record of an edit that cut the edit
        short would be the same fault one layer down.
    """
    p = Path(path)
    bid = block
    if not bid:
        m = BLOCK_ID_RE.search((old or "") + (new or ""))
        if m:
            bid = m.group(1)
    return append("edit.applied", actor=tool or "claude",
                  sheet=sheet, item=str(item), idx=idx,
                  path=_rel(p), block=bid, coord=coord, role=role,
                  old=old, new=new, why=why,
                  old_hash=hashlib.sha256((old or "").encode()).hexdigest()[:16],
                  new_hash=hashlib.sha256((new or "").encode()).hexdigest()[:16])


def edits_applied(sheet: str = "", item: str = ""):
    """Every `edit.applied` event, newest last, filtered by card when asked."""
    out = []
    for e in fold("edit.applied"):
        if sheet and e.get("sheet") != sheet:
            continue
        if item and str(e.get("item")) != str(item):
            continue
        out.append(e)
    return out


# ---------------------------------------------------------------------------
# A CHAPTER LINE CANNOT LOSE ITS BLOCK ID. ONE CHOKEPOINT.
#
# The author: "DO NOT CREATE AN INTERFACE THAT ALLOWS ME TO MESS UP THE BLOCK
# IDS. THAT IS A BAD DESIGN."
#
# It had already happened twice that hour: the author typed a paragraph into a
# textarea, which cannot hold a `<!-- b:... -->` comment, and the line went
# into the chapter without one, invisible to the block index every comparison
# relies on. Rather than retrofit each writer and hope the next one remembers,
# the check lives here, where every write already passes. A write that drops an
# id raises; nothing is logged and nothing is written.
BLOCK_ID_RE = re.compile(r"<!--\s*b:([a-z0-9]{6})\s*-->")


def _block_ids(text: str) -> set:
    return set(BLOCK_ID_RE.findall(text or ""))


def is_chapter(path) -> bool:
    """Is this file one of the book's chapters (backups left out)?"""
    p = Path(path)
    if p.suffix != ".md" or B.is_backup(p):
        return False
    try:
        same_dir = p.resolve().parent == B.CHAPTERS.resolve()
    except OSError:
        return False
    return same_dir and B.chapter_number(p) is not None


# A BLOCK MAY BE DELETED, BUT ONLY BY NAME.
#
# The lost-id guard cannot tell a deliberate deletion from a line that fell out
# of a bad replace, so it refuses both — and that once left no way to remove a
# paragraph a stale card had duplicated into a chapter. The answer was to make
# the remover say which id it is removing before the write, never to weaken the
# guard. `blockedit.remove()` is the only thing that sets this, it sets exactly
# one id, and it clears it in a finally block.
ALLOW_DROP = set()


def _refuse_lost_block_ids(p, before: str, after: str, tool: str):
    """Raise when a write to a chapter would drop or duplicate a block id."""
    if not is_chapter(p) or not before:
        return
    lost = (_block_ids(before) - _block_ids(after)) - ALLOW_DROP
    if lost:
        raise ValueError(
            f"REFUSED: this write to {p.name} would drop {len(lost)} block id(s) — "
            f"{', '.join(sorted(lost)[:6])}. A line without its id is invisible to the "
            f"block index. Write through blockedit.replace(), which owns the id. "
            f"(tool: {tool})")
    found = BLOCK_ID_RE.findall(after)
    dupes = sorted({i for i in found if found.count(i) > 1})
    if dupes:
        raise ValueError(
            f"REFUSED: this write to {p.name} would give {len(dupes)} id(s) to more "
            f"than one line — {', '.join(dupes[:6])}. An id names one block "
            f"or it names nothing. (tool: {tool})")


# ONE DOOR INTO THE CHAPTERS.
#
# The author: "These need to be consolidated into a single, fault-tolerant,
# system with checks-and-balances."
#
# Counting the scripts that write chapters is a claim; in the original system
# the inventory counted files by name while the event log showed thirteen
# differently-labelled tools writing chapters, and hundreds of writes that
# recorded no tool at all. Every write to a chapter passes through here, so
# refusing here is the one refusal that cannot be gone around by adding a file
# with a different name.
#
# Each entry names the question that tool alone answers. A tool not on this
# list is never added to it to make an error go away; it is routed through
# `blockedit`, which owns the block id.
CHAPTER_DOORS = {
    "blockedit.replace": "rewriting or inserting a block, by block id",
    "blockedit.remove":  "deleting a named block, by id, with ALLOW_DROP set",
    "blockid.py":        "stamping the ids themselves; it writes addresses, not prose",
}

#: Raised by `blockedit` around its own write_file call, and by nothing else.
#: A tool name alone would let any tool spell its way in; the flag means the
#: caller has to be inside blockedit's own code to pass.
IN_BLOCKEDIT = []
#: The same flag for `blockid.py`, raised only around its own writes.
IN_BLOCKID = []


def _refuse_undeclared_chapter_write(p, tool: str):
    """Raise when something other than the one door writes to a chapter."""
    if not is_chapter(p):
        return
    if tool in ("blockedit.replace", "blockedit.remove") and IN_BLOCKEDIT:
        return
    if tool == "blockid.py" and IN_BLOCKID:
        return
    raise PermissionError(
        f"REFUSED: {tool} tried to write {p.name} directly.\n"
        f"  Chapters are written through blockedit.replace(), insert_after() or\n"
        f"  remove(), and block ids are stamped by blockid.py. That is the whole door:\n"
        + "".join(f"    {k:<20} {v}\n" for k, v in CHAPTER_DOORS.items()))


def write_file(path, new_text: str, tool: str, why: str = "", backup: bool = True):
    """Log the change, then write it. The one way a tool should touch a file.

    A tool gets logging by calling this, never by remembering to. `witness.py`
    catches the tools that do not call it.

    The order is fixed:

        1. read what is there now
        2. refuse an undeclared chapter write, or a write that loses a block id
        3. append the event, fsynced
        4. copy the old file aside
        5. write

    If step 5 fails, the event and the backup are both already on disk and the
    change is recoverable.

    Returns the event. Writing identical text logs nothing and returns None:
    an unchanged file is not a change, and logging it would bury the real ones.
    """
    import shutil
    p = Path(path)
    before = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    if before == new_text:
        return None
    _refuse_undeclared_chapter_write(p, tool)
    _refuse_lost_block_ids(p, before, new_text, tool)
    ev = record_write(p, before, new_text, tool=tool, why=why)
    if backup and p.exists():
        shutil.copy(p, str(p) + f".bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(new_text, encoding="utf-8")
    return ev


if __name__ == "__main__":
    if "--verify" in sys.argv:
        ok, problems = verify_chain()
        n = len(read_all())
        print(f"\n  {n} event(s) in the log.")
        print("  chain intact.\n" if ok else f"  {len(problems)} PROBLEM(S):\n")
        for prob in problems:
            print(f"    {prob}")
        sys.exit(0 if ok else 1)
    print(__doc__)

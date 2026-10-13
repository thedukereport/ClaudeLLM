#!/usr/bin/env python3
"""cardlib.py — the one place that says whether a card's reads are on record.

    Imported by tools/card-log.py (writes), tools/check-card-logged.py
    (checks) and the other card tools. Nothing here writes on import; the
    write functions are called only by card-log.py with --write.

WHY THIS EXISTS

    Cards on the Source Rulings page (a claude.ai artifact, collection
    `proposals`; its address is `[page] url` in book.toml) are written by the
    Editor through the chat. No script in the vault can open that page, so no
    check could see whether a source a card names had reached
    `Fact Check/Claims/Ch NN.jsonl`, the chapter's ledger, and a `source.read`
    event in `Fact Check/events/`. The author's rule: "A read that is not
    logged did not happen, because the next pass will do it again."

    In the system this kit comes from, the first cards checked this way had
    every read in Claims and none in the ledger or the event log. Each of the
    three records answers a different reader, so each one is checked.

WHAT A CARD'S READ LIST IS

    `Handoffs/editor-tools/cards/<card id>.reads.json` (the folder is
    `[paths] card_reads` in book.toml), written by the Editor while building
    the card:

        {"card": "ch02-reflection-choice",
         "title": "Ch 02 · Hamilton wrote \\"reflection and choice\\"",
         "chapter": 2,
         "reads": [ {author, title, drive_path, location, states, ref, ...} ]}

    Each read uses the field names `Fact Check/Claims/*.jsonl` already uses.
    `drive_path` is the file's path in the library. The card id is the page's
    document id.

HOW "ALREADY LOGGED" IS DECIDED, STATED SO NOBODY HAS TO READ THE CODE

    A read matches a Claims row when author, title, location and ref are the
    same strings after collapsing runs of whitespace. Exact, never fuzzy: "A
    path that opens the wrong book is worse than no path", and a fuzzy matcher
    is judgment wearing a script's costume. A read that differs by one word
    from an existing row gets a new row.

    The ledger section is found by its heading, which names the card id.
    The event is found by kind `source.read`, the card id, and the same four
    fields.
"""
import datetime
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402

VAULT = B.VAULT
FACT = B.FACT
CLAIMS = B.CLAIMS
EVENTS = B.EVENTS
CARDS = B.CARDS
SNAPSHOT = B.SNAPSHOT
# Cards the Editor owes a read list for, one card id per line ("#" starts a
# comment). Work owed, never permission: a card not listed fails the day it
# appears.
BACKLOG = CARDS.parent / "card-log-backlog.txt"
PAGE = B.PAGE_URL or "(the page's address is not set: [page] url in book.toml)"

REQUIRED = ("author", "title", "location", "ref")
CHECKED_STATUSES = ("yours", "submitted", "approved")


def norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def key(r: dict) -> tuple:
    return tuple(norm(r.get(k)) for k in REQUIRED)


def rel(p) -> str:
    """A vault path for messages; the full path when it lies outside the vault."""
    try:
        return str(Path(p).resolve().relative_to(VAULT))
    except ValueError:
        return str(p)


def claims_file(chapter: int) -> Path:
    return B.claims_file(chapter)


def ledger_file(chapter: int) -> Path:
    """The chapter's one ledger. Stops when there is none or more than one:
    which file is the ledger is not a guess."""
    return B.ledger_file(chapter, must=True)


def claims_rows(chapter: int):
    """[(line number, row)] for the chapter's Claims file."""
    p = claims_file(chapter)
    out = []
    if not p.exists():
        return out
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            out.append((i, json.loads(line)))
        except json.JSONDecodeError as e:
            raise SystemExit(f"{rel(p)} line {i} is not JSON ({e}). "
                             f"Stopping before anything is written.")
    return out


def find_row(chapter: int, read: dict):
    k = key(read)
    for i, r in claims_rows(chapter):
        if key(r) == k:
            return i, r
    return None


def heading(card: dict, day: str) -> str:
    return f"## {day} — the sources named on card {card['card']}: {norm(card['title'])}"


def ledger_has_card(chapter: int, card_id: str) -> str:
    """The heading line of this card's section in the ledger, or ''."""
    pat = re.compile(r"^## .* — the sources named on card " + re.escape(card_id) + r": ")
    for line in ledger_file(chapter).read_text(encoding="utf-8").splitlines():
        if pat.match(line):
            return line
    return ""


def source_read_events():
    """Every source.read event, parsed only on lines that name the kind,
    because the log grows large and the other kinds are not needed here."""
    out = []
    if not EVENTS.is_dir():
        return out
    for f in sorted(EVENTS.glob("*.jsonl")):
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                if '"source.read"' not in line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("kind") == "source.read":
                    out.append(e)
    return out


def event_for(events, card_id: str, read: dict):
    k = key(read)
    for e in events:
        if e.get("card") == card_id and key(e) == k:
            return e
    return None


def load_card(path: Path) -> dict:
    """A card's read list, checked whole before anything uses it."""
    path = Path(path)
    card = json.loads(path.read_text(encoding="utf-8"))
    card["_source"] = rel(path)
    bad = []
    for f in ("card", "title", "chapter", "reads"):
        if not card.get(f):
            bad.append(f"the card file has no '{f}'")
    for n, r in enumerate(card.get("reads") or [], 1):
        for f in REQUIRED:
            if not norm(r.get(f)):
                bad.append(f"read {n} ({norm(r.get('author')) or '?'}) has no '{f}'")
        dp = norm(r.get("drive_path"))
        # A path inside Claude's sandbox opens nowhere else; the next reader
        # cannot follow it.
        if dp.startswith("/sessions/") or dp.startswith("/mnt/user-data/"):
            bad.append(f"read {n}: drive_path {dp} opens only in Claude's sandbox")
        if not dp and not norm(r.get("where_read")):
            bad.append(f"read {n}: no drive_path, and no 'where_read' saying where "
                       f"it was read instead (a cited book names its path in the library)")
    if bad:
        raise SystemExit(f"{path.name}: refusing, nothing written.\n  - "
                         + "\n  - ".join(bad))
    return card


def ledger_section(card: dict, day: str, rows: list, source: str = "") -> str:
    """rows: [(read, line_no, is_new)]. source: the read-list file, as a vault path."""
    ch = int(card["chapter"])
    source = source or rel(CARDS / (card["card"] + ".reads.json"))
    claims = rel(claims_file(ch))
    lines = [heading(card, day), "",
             f"Card on the Source Rulings page ({PAGE}), id `{card['card']}`. "
             f"Logged by `tools/card-log.py` for the Editor, from "
             f"`{source}`.", ""]
    for read, ln, is_new in rows:
        where = f"`{claims}` line {ln}, " + ("new row" if is_new else "already there")
        dp = norm(read.get("drive_path")) or ("not in the library; read at "
                                             + norm(read.get("where_read")))
        lines.append(f"- **{norm(read['author'])}**, *{norm(read['title'])}* — "
                     f"{norm(read['location'])}. For {norm(read['ref'])}. "
                     f"Read {norm(read.get('date_read')) or day}. `{dp}`. "
                     f"Claims: {where}.")
        if norm(read.get("states")):
            lines.append(f"  - The source: {norm(read['states'])}")
    return "\n".join(lines) + "\n"


def today_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


def _doc(p: Path) -> dict:
    """One document from the snapshot. A file holds the document's fields, or
    wraps them in "data" beside its id and version; both are read."""
    d = json.loads(p.read_text(encoding="utf-8"))
    return dict(d.get("data", d)) if isinstance(d.get("data", d), dict) else {}


def snapshot_taken():
    """The UTC time written in the snapshot's TAKEN file, or raises."""
    taken = SNAPSHOT / "TAKEN"
    if not taken.exists():
        raise FileNotFoundError(
            f"no page snapshot at {rel(SNAPSHOT)}/ — the page has "
            f"not been read, so no card was checked")
    when = datetime.datetime.fromisoformat(taken.read_text().strip().replace("Z", "+00:00"))
    if when.tzinfo is None:
        when = when.replace(tzinfo=datetime.timezone.utc)
    return when


def snapshot_collection(name: str) -> dict:
    """{doc id: fields} for one collection of the snapshot ({} when absent)."""
    d = SNAPSHOT / name
    if not d.is_dir():
        return {}
    return {p.stem: _doc(p) for p in sorted(d.glob("*.json"))}


def snapshot_cards():
    """(taken_at, [card dict with 'id']) from the page snapshot, or raises."""
    when = snapshot_taken()
    cards = []
    for cid, data in snapshot_collection("proposals").items():
        data["id"] = cid
        cards.append(data)
    return when, cards


def backlog() -> set:
    if not BACKLOG.exists():
        return set()
    return {l.split("#")[0].strip() for l in BACKLOG.read_text().splitlines()
            if l.split("#")[0].strip()}


def chapter_of(card: dict):
    m = re.search(r"\d+", str(card.get("chapter", "")))
    return int(m.group(0)) if m else None

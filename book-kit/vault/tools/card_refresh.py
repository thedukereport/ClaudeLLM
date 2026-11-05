#!/usr/bin/env python3
"""card_refresh.py — after a card is applied, every other open card of that chapter shows the chapter as it reads now.

    python3 tools/card_refresh.py                 # every chapter: what it would do, writing nothing
    python3 tools/card_refresh.py --chapter 3     # one chapter
    python3 tools/card_refresh.py --chapter 3 --write   # do it (book.toml [gates] "card_refresh": "write")

WHY THIS EXISTS: NO COLLISIONS BETWEEN CARDS

    In the system this kit comes from, a card showed the author the paragraph
    below its line; Production then applied another card that cut that
    paragraph; and the author approved the first card with a paragraph on it
    that was no longer in the book. Nothing looked at the open cards again
    after an apply. The author's ruling, "Both fixes": faulty lines next to
    each other in one paragraph go on one card, with the whole paragraph as it
    will read; and when a card is applied, every other open card of the
    chapter is checked against the disk.

WHAT IT DOES, FOR EACH OTHER OPEN CARD OF THE CHAPTER (`assess`)

    "ok"       its own lines, and the paragraphs it shows above and below, read as on disk.
    "refresh"  its own lines read as on disk and a neighbour does not: a new version gives
               `before` and `after` as on disk now, and no other field changes. Only a
               card waiting for the author ("yours") is refreshed.
    "back"     a line of its own no longer reads as on disk, or a "submitted" card's
               neighbour changed (the author's sent words stay on the author's press): the
               card is held off the author's desk and its owner gets an item in its
               hand-off Inbox, so the owner writes a new version.
    An approved card is never rewritten: the author's Approve names its version. When
    only a neighbour changed, the approval stands. When a line of its own changed, its
    owner gets the Inbox item, and the fault comes back as a new card.

    The write is gated (a sample before any bulk write): book.toml [gates]
    "card_refresh" is "report" until the author's ok to a sample, then "write".
    The card desk holds a "back" card in either mode.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import bookconfig as B  # noqa: E402
import blocks  # noqa: E402
import cards  # noqa: E402

BID = re.compile(r"(?:\bblock\s+|\bb:)([0-9a-f]{6})\b")
INSERT = re.compile(r"goes? after|go after|^\s*after\b|new lines? go|between L\d+", re.I)
NOTEDEF = re.compile(r"^\s*\[\^[A-Za-z0-9_\-]+\]:")
OPEN = ("yours", "submitted", "approved")


def norm(s):
    return re.sub(r"\s+", " ", blocks.IDRE.sub("", s or "")).strip()


def _lines(chapter):
    """[(line number, text, is a note definition)] of the chapter's non-blank lines, rules left out."""
    f = B.chapter_file(chapter)
    if f is None:
        return []
    out = []
    for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        t = norm(line)
        if t and t != "---":
            out.append((n, t, bool(NOTEDEF.match(t))))
    return out


def _body(chapter):
    """(paragraphs, notes): [(line number, text)] each, from the chapter on disk."""
    ls = _lines(chapter)
    return [(n, t) for n, t, nd in ls if not nd], [(n, t) for n, t, nd in ls if nd]


def _own(card, rows, notes=False):
    """[(index in rows or None, the card's text for it)] for each `current` entry that names a line of its
    own: the paragraphs when `notes` is False, the note definitions when True."""
    idx = blocks.index(rebuild=True)
    out = []
    for c in card.get("current") or []:
        if not isinstance(c, dict) or INSERT.search(str(c.get("where") or "")):
            continue
        text = norm(c.get("text"))
        if bool(NOTEDEF.match(text)) != notes:
            continue
        m = BID.search(str(c.get("where") or ""))
        at = None
        if m and m.group(1) in idx:
            line = idx[m.group(1)].line
            at = next((k for k, (n, _) in enumerate(rows) if n == line), None)
        if at is None:
            at = next((k for k, (_, t) in enumerate(rows) if t == text), None)
        out.append((at, text))
    return out


def assess(card, body=None):
    """{"action": ok | refresh | back, "why": words, "before": text, "after": text}."""
    ch = cards.chapter_of(card)
    paras, notes = _body(ch) if body is None else body
    own = _own(card, paras)
    own_notes = _own(card, notes, notes=True)
    moved = [t for at, t in own if at is None or paras[at][1] != t]
    moved += [t for at, t in own_notes if at is None or notes[at][1] != t]
    if moved:
        return {"action": "back", "why": f"{len(moved)} line(s) of its own no longer read as on disk: "
                + "; ".join(f"“{t[:80]}…”" for t in moved)}
    if not own:
        return {"action": "ok", "why": "its notes read as on disk, and it names no paragraph of its own"}
    first, last = min(at for at, _ in own), max(at for at, _ in own)
    before = paras[first - 1][1] if first > 0 else ""
    after = paras[last + 1][1] if last + 1 < len(paras) else ""
    stale = [k for k, disk in (("before", before), ("after", after))
             if card.get(k) is not None and norm(card.get(k)) != disk]
    if not stale:
        return {"action": "ok", "why": "its lines and neighbours read as on disk"}
    why = "the paragraph " + " and ".join("above" if k == "before" else "below" for k in stale) + " changed on disk"
    if card.get("status") == "yours":
        return {"action": "refresh", "why": why, "before": before, "after": after}
    if card.get("status") == "submitted":
        return {"action": "back", "why": why + "; the author sent words on this version, so its owner writes a new one"}
    return {"action": "ok", "why": why + "; the author's approval stands"}


def owner_inbox(card):
    by = str(card.get("_by") or "")
    for f in sorted(B.HANDOFFS.glob("*.md")):
        if f.stem.lower() in by.lower():
            return f
    return B.HANDOFFS / "Editor.md"


def _inbox(card, why, applied):
    import vaultlog
    f = owner_inbox(card)
    text = f.read_text(encoding="utf-8") if f.exists() else "## Inbox\n"
    day = datetime.now(timezone.utc).date().isoformat()
    item = (f"- {day}, from tools/card_refresh.py: card `{card['id']}` v{card['_version']} ({card.get('where')}) "
            f"needs a new version: {why}. Applied before it: {applied}.")
    if item in text:
        return
    text = text.rstrip("\n") + "\n" + item + "\n"
    vaultlog.write_file(f, text, tool="tools/card_refresh.py", why=f"inbox item for card {card['id']}")


def run(chapter, applied="", write=None):
    """Assess (and with write, act on) each open card of the chapter. Yields one line per card that is not ok."""
    write = (B.gate_mode("card_refresh", "report") == "write") if write is None else write
    body = _body(chapter)
    for cid, c in sorted(cards.fold().items()):
        if cards.chapter_of(c) != chapter or c.get("status") not in OPEN:
            continue
        a = assess(c, body)
        if a["action"] == "ok":
            continue
        did = "reported (card_refresh is in report mode)"
        if write and a["action"] == "refresh":
            rec = dict(cards.versions(cid)[-1]["card"], before=a["before"], after=a["after"])
            v = cards._append(cid, rec, by=c.get("_by") or "Editor", source="card_refresh",
                              why=f"neighbours as on disk after {applied or 'an apply'}")
            did = f"v{v} written with before/after as on disk"
        elif write and a["action"] == "back":
            if c.get("status") in cards.OPEN:
                cards.hold(cid, reason=a["why"], by=c.get("_by") or "Editor")
            _inbox(c, a["why"], applied or "a card")
            did = "held, and its owner's Inbox told"
        yield f"{cid} v{c['_version']}: {a['action']}: {a['why']} — {did}"


def main(argv):
    chs = [int(argv[argv.index("--chapter") + 1])] if "--chapter" in argv else \
        [B.chapter_number(f) for f in B.chapter_files()]
    write = "--write" in argv
    if write and B.gate_mode("card_refresh", "report") != "write":
        print('NOT WRITTEN: book.toml [gates] "card_refresh" is not "write". Show the author a sample first.')
        return 2
    n = 0
    for ch in chs:
        if ch is None or ch in B.OUT_OF_WORKFLOW:
            continue
        for line in run(ch, write=write):
            n += 1
            print(f"Ch{ch:02d}  {line}")
    print(f"\n{n} open card(s) that do not read as the chapter does now.")
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

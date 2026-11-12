#!/usr/bin/env python3
"""check-card-words.py — never offer the author a banned word on a card.

    tools/check-card-words.py            # every card waiting on the author or approved
    tools/check-card-words.py --json     # one object per finding
    tools/check-card-words.py --card ID  # one card

WHOSE RULE THIS IS

    The author's, on a proposal that offered a banned word: "Don't suggest
    banned words, fix your logic." Standing rule: never offer the author a
    banned word.

    `check-banned-words.sh` sweeps the chapters. Text on a card is not in a
    chapter until it is applied, so without this file a card's text passed no
    banned-word check at all.

WHAT IT READS

    Cards in the card store (`tools/cards.py`, folded with the author's
    presses) whose status is yours, submitted or approved. On each, the text the author
    would approve: `reviewedPara` / `reviewedNote` when set, else
    `proposedPara` / `proposedNote`.

    The word list is the machine list in `Methodology/Word Lists.md`, read
    by the loader in `tools/check-banned-words.sh` and nowhere else — one
    list, one parser. Its mechanical carve-outs apply as they do there: the 40
    characters either side of the hit are tested against the carve-out regex.

    A word inside double quotation marks or *italics* belongs to whoever said
    it and is not flagged. A word that stands, with its 40 characters either
    side, in the author's own submitted text (`submittedPara` /
    `submittedNote`) is the author's, under the author-voice carve-out, and is
    not flagged.

    A word whose 25 characters either side stand word for word in the chapter
    text the card quotes (`current`) is the chapter's, and the card does not
    offer it; `check-banned-words.sh` sweeps the chapters. These are counted
    and named in the summary, never listed as hits. On its first run in the
    system this kit comes from, most hits were of this kind.

    A hit is a coordinate, never a verdict: the carve-out prints beside it so
    a reader can rule in one glance. It exits 1 when there are hits, 2 when the
    word list is missing — a check that did not run.
"""
import importlib.machinery
import importlib.util
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cardlib as C  # noqa: E402

FIELDS = (("reviewedPara", "proposedPara", "body"),
          ("reviewedNote", "proposedNote", "note"))


def banned_words():
    spec = importlib.util.spec_from_loader(
        "cbw", importlib.machinery.SourceFileLoader(
            "cbw", str(Path(__file__).resolve().parent / "check-banned-words.sh")))
    cbw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cbw)
    return cbw.load_list()      # [(compiled, pattern, carve-out, auto regex or None)]


def blank(m):
    return " " * len(m.group(0))


def strip_quoted(text):
    """Blank quotations and italics, keeping every other character's position."""
    text = re.sub(r"<!--.*?-->", blank, text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", blank, text)
    text = re.sub(r'"[^"\n]{0,400}"', blank, text)
    text = re.sub(r"“[^”\n]{0,400}”", blank, text)
    text = re.sub(r"\*[^*\n]{1,200}\*", blank, text)
    return text


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


_WORDS = []


def card_hits(card, words=None, counter=None):
    """Each banned word the card offers in the text the author would approve. The one check:
    tools/cards.py runs it on each version as it goes in, and tools/card-desk.py on each card it draws."""
    if words is None:
        if not _WORDS:
            _WORDS.extend(banned_words())
        words = _WORDS
    hits = []
    his = norm((card.get("submittedPara") or "") + " " + (card.get("submittedNote") or ""))
    chapter = norm(" ".join(c.get("text", "") for c in (card.get("current") or [])
                            if isinstance(c, dict)))
    for reviewed, proposed, label in FIELDS:
        text = card.get(reviewed) or card.get(proposed) or ""
        if not text.strip() or (label == "note" and card.get("noteless")):
            continue
        field = reviewed if card.get(reviewed) else proposed
        stripped = strip_quoted(text)
        for rx, pattern, carve, rx_auto in words:
            for m in rx.finditer(stripped):
                window = text[max(0, m.start() - 40):m.end() + 40]
                if rx_auto is not None and rx_auto.search(window):
                    continue
                if his and norm(window) in his:
                    continue
                if chapter and norm(text[max(0, m.start() - 25):m.end() + 25]) in chapter:
                    if counter is not None:
                        counter.append(1)
                    continue
                hits.append({
                    "check": "check-card-words",
                    "where": C.norm(card.get("where")) or card.get("chapter", "—"),
                    "card": card.get("id", ""),
                    "title": C.norm(card.get("title")) or card.get("id", ""),
                    "status": card.get("status"),
                    "field": field,
                    "word": m.group(0),
                    "carve_out": carve,
                    "context": norm(text[max(0, m.start() - 58):m.end() + 52]),
                    # The fields the issue register reads, so it can show a
                    # card's hit beside every other finding.
                    "coord": C.norm(card.get("where")) or "—",
                    "what": f"banned word '{m.group(0)}' on card \"{C.norm(card.get('title'))}\"",
                })
    return hits


def own_texts(card):
    """[(field, text)]: the card's own words to the author, outside the book text: its title, tldr, recommendation,
    subject, the answer to his words, each change's why, each choice's label and reason."""
    out = [(k, card.get(k)) for k in ("title", "tldr", "recommendation", "subject", "summary", "job")]
    a = card.get("answer") if isinstance(card.get("answer"), dict) else {}
    out.append(("answer", a.get("answer")))
    for i, c in enumerate(card.get("changeList") or [], 1):
        if isinstance(c, dict):
            out.append((f"changeList[{i}].why", c.get("why")))
            for j, o in enumerate(c.get("choices") or [], 1):
                if isinstance(o, dict):
                    out += [(f"changeList[{i}].choices[{j}].label", o.get("label")),
                            (f"changeList[{i}].choices[{j}].reason", o.get("reason"))]
    for j, o in enumerate(card.get("choices") or [], 1):
        if isinstance(o, dict):
            out += [(f"choices[{j}].label", o.get("label")), (f"choices[{j}].reason", o.get("reason"))]
    return [(k, str(v)) for k, v in out if isinstance(v, str) and v.strip()]


def own_hits(card, words=None):
    """Each banned word in the card's own words to the author (own_texts). The author reads these too, so the
    standing rule holds for them: never offer the author a banned word. Quotations and italics are set aside."""
    if words is None:
        if not _WORDS:
            _WORDS.extend(banned_words())
        words = _WORDS
    hits = []
    for field, text in own_texts(card):
        stripped = strip_quoted(text)
        for rx, pattern, carve, rx_auto in words:
            for m in rx.finditer(stripped):
                if rx_auto is not None and rx_auto.search(text[max(0, m.start() - 40):m.end() + 40]):
                    continue
                hits.append({"field": field, "word": m.group(0), "carve_out": carve,
                             "context": norm(text[max(0, m.start() - 58):m.end() + 52])})
    return hits


def main(argv):
    as_json = "--json" in argv
    cards = C.store_cards()
    if "--card" in argv:
        want = argv[argv.index("--card") + 1]
        cards = [c for c in cards if c["id"] == want]
    try:
        words = banned_words()
    except (FileNotFoundError, SystemExit) as e:
        print(f"NOT RUN: the word list could not be read ({e})")
        return 2
    if not words:
        print("NOT RUN: no machine list found in Methodology/Word Lists.md")
        return 2
    hits, in_chapter, checked = [], [], 0
    for card in cards:
        if card.get("status") not in C.CHECKED_STATUSES:
            continue
        checked += 1
        hits += card_hits(card, words, in_chapter)
    in_chapter = len(in_chapter)
    if as_json:
        for h in hits:
            print(json.dumps(h, ensure_ascii=False))
    else:
        print(f"{checked} cards checked (yours, submitted, approved); "
              f"{len(words)} banned-word patterns from Word Lists.md.\n")
        for h in hits:
            print(f"  {h['where']}\n    {h['title']}  [{h['status']}, {h['field']}]\n"
                  f"    {h['word']!r}    carve-out: {h['carve_out'] or 'none'}\n"
                  f"    …{h['context']}…\n")
        print(f"{len(hits)} banned word(s) the cards offer. A hit is a coordinate: "
              f"read the sentence before changing it.")
        print(f"{in_chapter} more stand word for word in the chapter text the cards "
              f"quote; those are check-banned-words.sh's.")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

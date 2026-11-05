#!/usr/bin/env python3
"""card_reads.py — no card reaches the author with an unread fact in it.

    python3 tools/card_reads.py                # every open card: the facts in its passage with no opened read
    python3 tools/card_reads.py --card <id>    # one card
    python3 tools/card_reads.py --summary      # one line per card

WHOSE RULE THIS IS

    The author of the system this kit comes from, on finding cards whose facts
    nobody had read: "How am I getting cards that have not been fact-checked?"
    The rule that came of it: a card goes to the author's desk only when every
    name, number, date and quotation in the passage on the card, and not only
    in the fix, has an opened, logged read in `Fact Check/Claims/`. A Claims row
    with no reader, or with a path a script filled in without opening the file,
    counts as unread.

WHAT IT READS AS A FACT, IN THE PASSAGE THE AUTHOR WOULD APPROVE (reviewedPara, else proposedPara; the note too)

    quotation   words in double quotation marks, three words or more (a gloss
                after "means", "rendered", "called" and the like is not one)
    name        two or more capitalised words in a row ("John Jay", "Bank of England")
    date        a year (1000–2099), with its day and month when the text gives them
    number      any other figure of two digits or more ("6,443", "75–95%")
    Left out: footnote markers, block ids, Ch/L coordinates, Greek and Hebrew
    script, locators such as "2.44.2", a capital that only opens a sentence, and
    the book's own coined terms (`tools/card_reads_book_terms.txt`).

WHAT COUNTS AS AN OPENED READ

    A row of `Fact Check/Claims/*.jsonl` with a `reader`, a `drive_path` that is
    neither empty nor "NOT IN THE LIBRARY", and no `path_resolved_by_match`. The
    fact is covered when its words stand in that row's text fields (states,
    quotes, claim, title, author, location, ref and the like). A match here is a
    pointer that the read exists; the row is what a reader checks.

    `tools/card_reads_exempt.jsonl` takes a fact out for one card, one JSON
    object per line: {"card", "fact", "reason", "by", "at"}, where reason is
    "the author's account" (with "ledger_line": where the ledger records it) or
    "illustration" (an example sentence the chapter makes up).

THE GATE

    `tools/cards.py` runs `unread_facts` on each version as it goes in
    (book.toml [gates] "card_reads": warn or refuse), and the card desk holds
    a card that still has one.
"""
import json
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import bookconfig as B  # noqa: E402

TEXT_FIELDS = ("states", "quotes", "quote", "claim", "subject", "title", "subtitle", "author", "location",
               "evidence_quotes", "ref", "words", "text")
SMALL = {"of", "de", "la", "le", "von", "van", "der", "du", "da", "di", "del", "della", "des", "ibn", "bin"}
GLOSS = re.compile(r"(mean(s|ing|t)?|rendered|renders|render|became|become|becomes|gloss(ed|es)?|translat\w*|"
                   r"the word|the sense|in English|in Latin|in Greek|called)\W{0,12}$", re.I)
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
TERMS = TOOLS / "card_reads_book_terms.txt"
EXEMPT = TOOLS / "card_reads_exempt.jsonl"
try:
    _DICT = set(open("/usr/share/dict/words", encoding="utf-8").read().split())
except OSError:
    _DICT = set()
OPENERS = {"The", "A", "An", "In", "On", "At", "By", "For", "From", "When", "While", "After", "Before", "If", "As",
           "This", "That", "These", "Those", "His", "Her", "Its", "Their", "Our", "Each", "Both", "Under", "Over"}


def norm(s):
    s = str(s or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", re.sub(r"[*_`]", "", s)).strip().lower()


def clean(text):
    t = "\n".join("" if l.lstrip().startswith("#") else l for l in str(text or "").split("\n"))
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)
    t = re.sub(r"\[\^[^\]]+\]:?", " ", t)
    t = re.sub(r"\bCh\s*\d+/L\d+\b|\bL\d+\b", " ", t)
    t = re.sub(r"[Ͱ-Ͽἀ-῿֐-׿]+", " ", t)
    return t.replace("\n\n⁂\n\n", "\n\n")


def book_terms():
    """The book's own coined terms, one per line as `term | ChNN/LNN where the chapter defines it`."""
    out = set()
    try:
        for l in TERMS.read_text(encoding="utf-8").splitlines():
            if l.lstrip().startswith("#"):
                continue
            term = l.split("|", 1)[0].strip()
            if term:
                out.add(norm(term))
    except OSError:
        pass
    return out


def _opens_sentence(word, before):
    s = before.rstrip()
    at_start = not s or s[-1] in ".!?:;\n\"”—("
    return at_start and (word in OPENERS or (word.lower() in _DICT and word not in _DICT))


def facts(text):
    """[(kind, the fact as written)] in the order they stand."""
    t = clean(text)
    out, seen, quoted = [], set(), []

    def add(k, v):
        key = (k, norm(v))
        if norm(v) and key not in seen:
            seen.add(key)
            out.append((k, v.strip()))

    for m in re.finditer(r'"([^"\n]{3,600})"|“([^”\n]{3,600})”', t):
        q = (m.group(1) or m.group(2)).strip()
        quoted.append(m.span())
        before, after = t[max(0, m.start() - 40):m.start()], t[m.end():m.end() + 3]
        if len(q.split()) < 3 or GLOSS.search(before) or re.match(r"\s*\(", after):
            continue
        add("quotation", q)

    def inq(i):
        return any(a <= i < b for a, b in quoted)

    for m in re.finditer(rf"\b(?:(?:\d{{1,2}} )?(?:{MONTHS})(?: \d{{1,2}},?)? )?(1\d{{3}}|20\d{{2}})\b(?:s\b)?", t):
        if not inq(m.start()):
            add("date", m.group(0))
    for m in re.finditer(r"(?<![\w.])\d[\d,.]*\d(?:\s?[-–]\s?\d[\d,.]*)?\s?%?|\b\d{2,}\b", t):
        v = m.group(0)
        if inq(m.start()) or re.fullmatch(r"(1\d{3}|20\d{2})s?", v.strip()) or v.count(".") >= 2:
            continue
        add("number", v)
    terms = book_terms()
    word = r"[A-Z][\w'’.-]*[\w]"
    for m in re.finditer(rf"{word}(?:\s+(?:(?:{'|'.join(SMALL)})\s+)*{word})+", t):
        if inq(m.start()):
            continue
        parts = m.group(0).split()
        if _opens_sentence(parts[0], t[:m.start()]):
            parts = parts[1:]
        while parts and parts[-1].lower() in SMALL:
            parts = parts[:-1]
        if len(parts) < 2:
            continue
        name = " ".join(parts)
        if norm(name) in terms:
            continue
        add("name", name)
    return out


_ROWS = {"stamp": None, "rows": []}


def opened_rows():
    """[normalised text] of each Claims row that records an opened read, read again whenever a Claims file changes."""
    files = sorted(B.CLAIMS.glob("*.jsonl")) if B.CLAIMS.is_dir() else []
    stamp = tuple((str(f), f.stat().st_mtime_ns) for f in files)
    if stamp == _ROWS["stamp"]:
        return _ROWS["rows"]
    rows = []
    for f in files:
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            dp = str(o.get("drive_path") or "").strip()
            if not str(o.get("reader") or "").strip() or not dp or dp.upper().startswith("NOT IN THE LIBRARY") \
                    or o.get("path_resolved_by_match"):
                continue
            rows.append(norm(" ".join(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
                                      for k, v in o.items() if k in TEXT_FIELDS and v)))
    _ROWS.update(stamp=stamp, rows=rows)
    return rows


def covered(kind, fact, rows):
    f = re.sub(r"'s$", "", norm(fact)).rstrip(" .,;:")
    if kind == "name":
        f = re.sub(r"^the ", "", f)
    if kind == "quotation":
        f = f.strip(" ,.;:!?")[:80]
    if kind == "number":
        f = f.replace(" ", "")
        return any(f in r.replace(" ", "") for r in rows)
    return any(f in r for r in rows)


def passage(card):
    para = card.get("reviewedPara") or card.get("proposedPara") or ""
    note = "" if card.get("noteless") else (card.get("reviewedNote") or card.get("proposedNote") or "")
    return para + ("\n\n" + note if note.strip() else "")


def exempt(card_id):
    out = set()
    try:
        lines = EXEMPT.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for l in lines:
        try:
            o = json.loads(l)
        except json.JSONDecodeError:
            continue
        if o.get("card") not in (card_id, "*") or not o.get("fact") or not o.get("by"):
            continue
        r = str(o.get("reason") or "").lower()
        if (r.startswith("the author's account") and o.get("ledger_line")) or r.startswith("illustration"):
            out.add(norm(o["fact"]).rstrip(" .,;:"))
    return out


def unread_facts(card):
    """[(kind, fact)] in the passage on the card that no opened read holds and no exemption names."""
    rows = opened_rows()
    ex = exempt(card.get("id") or "")
    return [(k, v) for k, v in facts(passage(card))
            if not covered(k, v, rows) and norm(v).rstrip(" .,;:") not in ex]


def main(argv):
    import cards
    folded = cards.fold()
    if "--card" in argv:
        cid = argv[argv.index("--card") + 1]
        if cid not in folded:
            print(f"no card {cid!r} in the store")
            return 1
        ids = [cid]
    else:
        ids = sorted(cid for cid, c in folded.items() if c.get("status") in ("yours", "submitted")
                     and not cards.locked(c))
    total = 0
    for cid in ids:
        c = dict(folded[cid], id=cid)
        allf, miss = facts(passage(c)), unread_facts(c)
        total += bool(miss)
        if "--summary" in argv:
            print(f"{len(miss):>3} of {len(allf):>3} unread  {cid}  {c.get('where')}")
            continue
        print(f"{cid} v{c['_version']} [{c.get('status')}] {c.get('where')}: {len(miss)} of {len(allf)} facts with no opened read")
        for k, v in miss:
            print(f"    {k:<9} {v[:150]}")
    print(f"\n{total} of {len(ids)} card(s) carry a fact with no opened read.")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

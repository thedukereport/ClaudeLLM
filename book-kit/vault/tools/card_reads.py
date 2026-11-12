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

    quotation   words in quotation marks, three words or more, the marks paired in
                order line by line (a gloss after "means", "rendered", "called",
                "reads" and the like, or after a bold or italic term and a dash,
                is not one)
    title       a quoted title in a citation ("The Red Pill,"): a credit, which
                needs a read that holds it
    full name   a name spelled out in parentheses after a proper noun or its
                acronym
    name        two or more capitalised words in a row ("John Jay", "Bank of England")
    date        a year (1000–2099), with its day and month when the text gives them
    number      any other figure of two digits or more ("6,443", "75–95%")
    Left out: footnote markers, block ids, Ch/L coordinates, Greek and Hebrew
    script, locators such as "2.44.2", a capital that only opens a sentence, and
    the book's own coined terms (`tools/card_reads_book_terms.txt`).

WHAT COUNTS AS AN OPENED READ

    A row of `Fact Check/Claims/*.jsonl` with a `reader`, a `drive_path` that is
    neither empty nor "NOT IN THE LIBRARY", no `path_resolved_by_match`, and a
    `type` that records no failed search or work not read (NEGATIVE_TYPES: a row
    saying no source gives a date once covered that date). The fact is covered
    when its words stand in one of that row's text fields (states, quotes,
    claim, title, author, location and the like); never in `ref`, which quotes
    the book's own words under check. A match here is a
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
               "evidence_quotes", "words", "text", "where_read")
#: "ref" is left out: it quotes the BOOK's words under check, so a fact matched there is the book covering itself.
#: Claims row types that record a search that failed, a work not read or a question still open: never a read.
NEGATIVE_TYPES = {"search_negative", "source_absent", "source_wanted", "not_established", "not_read", "not_found",
                  "search_record", "open_item"}
SMALL = {"of", "de", "la", "le", "von", "van", "der", "du", "da", "di", "del", "della", "des", "ibn", "bin"}
GLOSS = re.compile(r"(mean(s|ing|t)?|rendered|renders|render|became|become|becomes|gloss(ed|es)?|"
                   r"translat\w*(?:\s+(?:as|to|into))?|the word|the sense|in English|in Latin|in Greek|called|reads)"
                   r"\W{0,12}$", re.I)
#: The list form of a gloss: a term in bold or italics, a dash, then its English in quotation marks.
LISTGLOSS = re.compile(r"(?:\*\*[^*\n]{1,60}\*\*|(?<!\*)\*[^*\n]{1,60}\*)\s*[—–:]\s*$")
MINOR = {"a", "an", "the", "of", "in", "on", "and", "to", "for", "with", "at", "by", "from", "or", "as", "into", "vs"}
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


def is_title(q):
    """A quoted string set as a title in a citation: the comma or full stop inside the marks, and each word but the
    small ones capitalised ("The Red Pill,"). A sentence quoted from a person does not read so. It is still a credit,
    and needs a read that holds it."""
    q = str(q or "").strip()
    if not q or q[-1] not in ",.":
        return False
    letters = [w for w in re.split(r"[\s/-]+", q.strip(" ,.")) if w and re.match(r"[^\W\d_]", w)]
    return len(letters) >= 2 and letters[0][0].isupper() and all(w[0].isupper() or w.lower() in MINOR for w in letters)


def quote_spans(t):
    """[(start, end, inner)]: quotation marks paired in order, line by line. Straight marks pair first with second,
    third with fourth; a curly “ opens and ” closes. A quotation of any length is found: a pattern with a length
    limit skips a long one and pairs its closing mark with the next opening mark."""
    out, pos = [], 0
    for line in t.split("\n"):
        stack, opened = [], None
        for i, ch in enumerate(line):
            if ch == '"':
                if opened is None:
                    opened = i
                else:
                    if i - opened - 1 >= 3:
                        out.append((pos + opened, pos + i + 1, line[opened + 1:i]))
                    opened = None
            elif ch == "“":
                stack.append(i)
            elif ch == "”" and stack:
                j = stack.pop()
                if not stack and i - j - 1 >= 3:
                    out.append((pos + j, pos + i + 1, line[j + 1:i]))
        pos += len(line) + 1
    return sorted(out)


def facts(text):
    """[(kind, the fact as written)] in the order they stand."""
    t = clean(text)
    out, seen, quoted = [], set(), []

    def add(k, v):
        key = (k, norm(v))
        if norm(v) and key not in seen:
            seen.add(key)
            out.append((k, v.strip()))

    for a, b, q in quote_spans(t):
        q = q.strip()
        quoted.append((a, b))
        before, after = t[max(0, a - 40):a], t[b:b + 3]
        if len(q.split()) < 3 or GLOSS.search(before) or LISTGLOSS.search(before) or re.match(r"\s*\(", after):
            continue
        if is_title(q):
            add("title", q.strip(" ,."))
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
    # A full name given in parentheses after a proper noun or its acronym ("Satys (Société d'Application des
    # Techniques ...)") is a fact, tested whole: it was once added to a card with no read behind it.
    for m in re.finditer(r"(?:\*[A-Z][^*\n]{0,40}\*|\b[A-Z][\w’'-]*[A-Z\w])\s*\(\s*[“\"]?([A-ZÀ-Ý][^()“”\"\n]{10,140}?)[”\"]?\s*\)", t):
        inner = m.group(1).strip()
        ws = inner.split()
        if len(ws) >= 3 and sum(1 for w in ws if w[:1].isupper()) >= 2 and not inq(m.start()) \
                and not re.search(r"\d|[:;]|\b(?:p|pp|ch|vol)\.", inner):
            add("full name", inner)
    terms = book_terms()
    word = r"[A-Z][\w'’.-]*[\w]"
    for m in re.finditer(rf"{word}(?:\s+(?:(?:{'|'.join(SMALL)})\s+)*{word})+", t):
        if inq(m.start()):
            continue
        parts = m.group(0).split()
        if _opens_sentence(parts[0], t[:m.start()]) or (
                not t[:m.start()].rstrip() or t[:m.start()].rstrip()[-1] in ".!?:;\n\"”—(") \
                and re.fullmatch(r"[A-Z][a-z]+(?:ing|ed)", parts[0]):
            parts = parts[1:]          # "Answering Celsus, who …": a verb that opens the sentence is no part of a name
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
                    or o.get("path_resolved_by_match") or str(o.get("type") or "") in NEGATIVE_TYPES:
                continue
            # Fields joined by \x01, which no fact holds: a fact matches inside one field, never across two.
            rows.append("\x01".join(norm(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))
                                     for k, v in o.items() if k in TEXT_FIELDS and v))
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
    if kind in ("title", "full name"):
        f = f.strip(" ,.;:")
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

#!/usr/bin/env python3
"""check-note-content.py — find footnote sentences that hold body content instead of a citation.

    tools/check-note-content.py              # every chapter, every note
    tools/check-note-content.py 26           # one chapter
    tools/check-note-content.py --json       # one line per finding, for a dashboard or register
    tools/check-note-content.py --new        # only notes not in the backlog file
    tools/check-note-content.py --write-backlog   # record today's findings as known work

WHY THIS EXISTS, IN THE AUTHOR'S WORDS

    "No, you make the same mistake so many times that I have this saved as a
    macro: 'Again. Notes are for citations and sources. The content/context in
    the note looks like it belongs in the body. Show me a new proposal.'"

    The author typed that sentence at item after item in one sitting, and at
    other chapters before that. The fault is not one bad note: a drafter writes
    notes that hold the chapter's content, the author catches them one at a
    time, and nothing in the vault looked for them.

    `check-footnotes.sh` asks this question (its BELONGS IN THE BODY? block),
    but only of notes already over the 150-word cap. The macro does not care
    about length. A 60-word note whose second sentence is a fact the chapter
    needs is the same fault at a third the size.

WHAT IT CALLS A FAULT

    A note holds three things: who said it and where; the words the body
    relies on, if the body has not printed them; and one clause where a reader
    following the citation would otherwise land in the wrong place. So this
    reads every sentence of every note and asks which of the three it is:

      * a LOCATOR: it has a bibliographic signal: a page, chapter, section,
        volume, number, an edition, an archive, a date of a letter, a title.
      * a WARNING: it says another edition or another writer gives something
        different, which is what keeps a reader off the wrong page.
      * THE WORDS THE BODY RELIES ON: a quotation whose words are in the body's
        paragraph, given in the note because the body quotes them.

    A sentence that is none of the three is CONTENT, and content belongs in the
    body or in the chapter's ledger under `Fact Check/`. That is the sentence
    the macro is about.

    Every finding is a coordinate, not a verdict. Some will be right to keep,
    and a keep is recorded in `Fact Check/Note Content Rulings.md`, by the
    author, so the check stops reporting it. One line per ruling, in the form
    `- Ch02 [^slug] kept: why`. Nothing here edits a chapter.

WHAT OTHER TOOLS IMPORT FROM HERE
    LOCATOR, WARNING, TITLE, NAME, NOTEDEF, QUOTED, BID, sentences(),
    quoted_runs(), titlecased(), words(), anchors(), chapter_files(), judge(),
    ruled(), rows(). tools/assess-notes.py and tools/check-card-notes.py load
    this file as a module.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402
import notelib          # noqa: E402

VAULT = B.VAULT
# THE BLOCK-ID PATTERN LIVES IN notelib AND NOWHERE ELSE.
BID = notelib.BID

RULINGS = B.FACT / "Note Content Rulings.md"
BACKLOG = B.FACT / "note-content-backlog.txt"

# A BIBLIOGRAPHIC SIGNAL — the marks of a pointer to a place in a work.
LOCATOR = re.compile(
    r"\bpp?\.\s*\d|\bp\s\d|§|\bch(?:ap|apter)?s?\.?\s*\d|\bvol\.|\bno\.\s*\d"
    r"|\bfol\.|\bs\.vv?\.|\bsig\.|\bline[s]?\s+\d|\bbook\s+[IVXLC\d]"
    r"|\b\d{1,4}[:.]\d{1,4}\b"                     # 1.30.2, 12:355
    r"|\(\s*\d{3,4}\s*\)"                          # (1859)
    r"|\b(?:19|20|1[0-8])\d\d\b"                   # a year anywhere
    r"|\bed\.|\beds\.|\btrans\.|\brev\.|\bedition\b|\bpress\b|\buniversity\b"
    r"|\bFounders Online\b|\bArchives?\b|\bLibrary\b|\bProject\b|\bOCLC\b"
    r"|\bPDF\b|\bmanuscript\b|\bMS\b"
    r"|\bLXX\b|\bByzantine\b|\bNestle-Aland\b|\bPerseus\b|\bAvalon\b|\bTLG\b"
    # CANONICAL REFERENCE FORMS. "Diels-Kranz 28 B2" is a citation; it has no
    # page and no year, and the first version called it a statement.
    r"|\bcanonical reference\b|\bfragment[s]?\s+[A-Z]?\d|\bfrag\.|\bDiels[–-]Kranz\b"
    r"|\bDK\s*\d|\btlg\d|\bs\.v\.|\bad loc\.|\bl{1,2}\.\s*\d"
    # HOW THE WORDS GOT ONTO THE PAGE is part of who said it and where.
    r"|\btranslations? (?:by|are|mine)\b|\bmy translation\b|\btranslated by\b"
    r"|\btext (?:from|after)\b|\bEnglish after\b|\bverbatim\b",
    re.I)

# A WARNING — it keeps a reader off the wrong page or the wrong words.
WARNING = re.compile(
    r"\b(?:misprint|misprints|misquot|differs?|differ|prints?|printed|renders?|"
    r"reads?|omits?|truncat|variant|mistranslat|misattribut|supplied|repunctuat|"
    r"spelling|transliterat\w*|both ways|either form|transcrib\w* from|the same passage|where the (?:manuscript|source|"
    r"text)|a reader (?:who|following)|do not confuse|not to be confused)\b", re.I)

# TITLES AND NAMES — an italicised title or a Chicago-shaped name.
TITLE = re.compile(r"\*[^*\n]{4,120}\*|\"[A-Z][^\"\n]{6,120}\"|“[A-Z][^”\n]{6,120}”")
NAME = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z]\.)*\s+[A-Z][A-Za-z'’-]+\b")

# A HIDDEN RUN STILL STARTS A SENTENCE.
#
# Quotations, abbreviations and initials are replaced by \x01 markers before
# the split, and this lookahead once left that character out. So in
#
#     Paine, *Common Sense*, 14. "In the early ages of the world…"
#
# the full stop after 14 was followed by a hidden quotation rather than by a
# capital, the sentence never ended, and the citation came back welded to the
# quotation.
SENT = re.compile(r"(?<=[.!?\x02])\s+(?=[A-Z“\"\[*\x01])")
ABBR = re.compile(
    r"\b(?:Mr|Mrs|Ms|Dr|Prof|St|Rev|Hon|Sr|Jr|vol|no|ed|eds|trans|rev|ch|chap|"
    # `v.` and `vs.`: a case name is one unit. Splitting inside one kept the
    # defendant with a dangling asterisk and dropped the plaintiff.
    r"v|vs|et al|Ibid|Rev|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec|"
    r"pp|p|fol|cf|viz|etc|Esq|Co|Inc|Univ|BC|AD)\.", re.I)
INITIAL = re.compile(r"\b[A-Z]\.")
# A NUMBERED LIST MARKER, AND NOTHING ELSE.
#
# Written as `\d{1,2}\.\s` this hid the full stop in "Diels-Kranz 28 B2. Greek
# read from…", so a citation and the sentence after it came back as ONE
# sentence, and because the merged sentence held a citation, the clause that
# should go could not be seen. A list marker opens its own run: it follows the
# start of the text, a quotation mark, or a colon or semicolon.
LISTNUM = re.compile(r"(?:(?<=^)|(?<=[“\"(:;])|(?<=[:;]\s))\d{1,2}\.\s")
INQUOTE = re.compile(r"[“\"][^”\"]{12,}[”\"]")


def sentences(s):
    """Split into sentences without breaking abbreviations, initials or quotations.

    THE FIRST VERSION SPLIT ON EVERY FULL STOP AND REPORTED NONSENSE: one
    quotation came back as three findings, one of them ending at a courtesy
    title ("…the editorial literary skill of Mr."). A check that hands the
    author garbage is a check the author learns to skip. So abbreviations,
    single initials, numbered lists and anything between quotation marks are
    hidden before the split and restored after.
    """
    keep = {}

    def hide(m):
        k = "\x01%d\x01" % len(keep)
        keep[k] = m.group(0)
        # A quotation that ends its sentence ("…General Introduction." This
        # shows…) hides its full stop inside the quote marks. The \x02 after the
        # placeholder lets the split see that stop, so the next sentence is
        # judged on its own.
        return k + ("\x02" if re.search(r"[.!?][”\"]$", m.group(0)) else "")

    for pat in (INQUOTE, ABBR, INITIAL, LISTNUM):
        s = pat.sub(hide, s)
    out = []
    for piece in SENT.split(s):
        piece = piece.replace("\x02", "")
        for k, v in keep.items():
            piece = piece.replace(k, v)
        out.append(piece)
    return out


NOTEDEF = re.compile(r"(?m)^\[\^([A-Za-z0-9_\-]+)\]:\s*(.*)$")
QUOTED = re.compile(r"[\"“]([^\"”]{12,})[\"”]")


def quoted_runs(s):
    """Every run inside quotation marks, found by splitting, never by spanning.

    `["“]([^"”]{12,})["”]` matches from the opening quote of one short term to
    the opening quote of the next. A note glossing two short quoted phrases
    came back with the span between them as a thirty-character "quotation the
    body does not print". Splitting cannot mis-pair: in well-formed text every
    odd piece is inside a quote.
    """
    pieces = re.split(r"[\"“”]", s or "")
    return [p for i, p in enumerate(pieces) if i % 2 == 1 and p.strip()]


def titlecased(q):
    """True when a quoted run reads like a work's title rather than a sentence."""
    ws = [w for w in re.findall(r"[A-Za-z][A-Za-z'’-]*", q) if len(w) >= 4]
    if len(ws) < 3:
        return False
    return sum(1 for w in ws if w[0].isupper()) / len(ws) >= 0.6


def words(s):
    return set(re.findall(r"[a-z']+", (s or "").lower()))


def ruled():
    """{(chapter, slug)} the author has ruled stay as they are."""
    out = set()
    if not RULINGS.exists():
        return out
    for line in RULINGS.read_text(encoding="utf-8").split("\n"):
        m = re.match(r"\s*[-*|]?\s*Ch\s*(\d+)\D+\[\^([A-Za-z0-9_\-]+)\]", line)
        if m:
            out.add((int(m.group(1)), m.group(2)))
    return out


def chapter_files():
    """{chapter number: path}, backups left out."""
    return {B.chapter_number(f): f for f in B.chapter_files()}


def anchors(text, slug):
    """The body blocks that hold [^slug]."""
    return [l for l in text.split("\n")
            if f"[^{slug}]" in l and not l.startswith(f"[^{slug}]:")]


def judge(note_text, body_words):
    """[(sentence, why)] for every sentence that is neither a locator nor a warning.

    `body_words` is the set of words (see words()) in the note's anchor
    paragraph; a quotation whose words are there is the words the body relies on.
    """
    bad = []
    body_quotes = body_words
    for s in sentences(note_text.strip()):
        s = s.strip()
        if len(s.split()) < 4:
            continue
        if LOCATOR.search(s) or WARNING.search(s):
            continue
        if TITLE.search(s) and len(s.split()) <= 25:
            continue
        # A QUOTED TITLE IS A CITATION, HOWEVER LONG THE TITLE IS. A long
        # article title in quotation marks was read as a quotation the body
        # fails to print. Titles are title-cased; sentences are not.
        if any(titlecased(q) for q in QUOTED.findall(s)):
            continue
        # A QUOTATION THE BODY ALSO PRINTS is the words the body relies on.
        q = QUOTED.search(s)
        if q and len(words(q.group(1)) - body_quotes) <= 2:
            continue
        if q:
            bad.append((s, "a quotation the body does not print — it belongs in the "
                           "body, beside the sentence that rests on it"))
            continue
        if NAME.search(s) and len(s.split()) <= 12:
            continue
        bad.append((s, "a sentence that states something rather than pointing at a "
                       "page — content, in the author's words"))
    return bad


def rows(only=None):
    """[{where, chapter, slug, findings}] for every note with a finding."""
    out = []
    keep = ruled()
    for ch, f in chapter_files().items():
        if only and ch != only:
            continue
        text = f.read_text(encoding="utf-8")
        for m in NOTEDEF.finditer(text):
            slug, body = m.group(1), BID.sub("", m.group(2))
            if (ch, slug) in keep:
                continue
            bw = words(" ".join(anchors(text, slug)))
            bad = judge(body, bw)
            if bad:
                out.append({"where": f"Ch{ch:02d}", "chapter": ch, "slug": slug,
                            "findings": bad})
    return out


def backlog():
    """{(where, slug)} already known and owed — work, not permission."""
    out = set()
    if not BACKLOG.exists():
        return out
    for line in BACKLOG.read_text(encoding="utf-8").split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.rsplit(" ", 1)
        if len(parts) == 2:
            out.add((parts[0].strip(), parts[1].strip().strip("[]^")))
    return out


def main():
    only = next((int(a) for a in sys.argv[1:] if a.isdigit()), None)
    rs = rows(only)
    if "--write-backlog" in sys.argv:
        # THE NOTES ALREADY IN THE BOOK ARE WORK OWED, NOT PERMISSION.
        import vaultlog
        lines = ["# Notes holding a sentence that belongs in the body, as found by "
                 "check-note-content.py --write-backlog.",
                 "# Work owed, one chapter at a time. Nothing here is approved.",
                 "# check-note-content.py --new reports anything NOT in this list."]
        lines += [f"{r['where']} [^{r['slug']}]" for r in rs]
        vaultlog.write_file(BACKLOG, "\n".join(lines) + "\n", tool="check-note-content.py",
                            why="baseline of notes holding body content")
        print(f"  baseline written: {len(rs)} note(s).")
        return
    if "--new" in sys.argv:
        known = backlog()
        rs = [r for r in rs if (r["where"], r["slug"]) not in known]
    if "--json" in sys.argv:
        for r in rs:
            for s, why in r["findings"]:
                print(json.dumps(
                    {"check": "check-note-content.py", "where": r["where"],
                     "coord": f"[^{r['slug']}]",
                     "what": f"{why}: {s[:160]}"}, ensure_ascii=False))
        sys.exit(1 if rs else 0)

    n = sum(len(r["findings"]) for r in rs)
    if not rs:
        print("\n  No note in the chapters holds a sentence that belongs in the body.\n")
        return
    print(f"\n  {len(rs)} note(s) in the chapters hold {n} sentence(s) that are neither a "
          f"citation nor a warning.\n")
    for r in rs:
        print(f"    {r['where']}  [^{r['slug']}]")
        for s, why in r["findings"]:
            print(f"        {why}")
            print(f"        > {s[:200]}")
        print()
    print("  Each one goes into the body, or into the chapter's ledger under "
          "`Fact Check/`, or the author rules it stays and the ruling goes in\n"
          f"  `{RULINGS.relative_to(VAULT)}`. Nothing here was changed.\n")
    sys.exit(1)


if __name__ == "__main__":
    main()

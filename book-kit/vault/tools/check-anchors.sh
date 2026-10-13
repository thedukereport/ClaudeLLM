#!/usr/bin/env python3
"""check-anchors.sh — check that each footnote gives a reader a way to find the passage it cites.

    tools/check-anchors.sh 26            # chapter 26
    tools/check-anchors.sh --all         # the whole book
    tools/check-anchors.sh --all --bare  # one line per note, for counting
    tools/check-anchors.sh --rule        # print the rule this enforces

THE QUESTION

    Can a reader holding the cited edition find the passage?

    check-footnotes.sh measures length, duplication, orphans and self-talk. Not
    one of its classes asks this. So an agent trimming a note could delete the
    only thing answering it, and a review could report "no page number" as a
    fault when a page number is often the WRONG anchor: "A citation that says
    'p. 47' of an EPUB is fictional."

    The original author wrote the rule into the book itself, as a published
    appendix on citation conventions, and still had to remind the drafters of
    it: "WE WROTE IT IN THE BOOK ALREADY." A rule a person has to remember is a
    rule that gets forgotten, so this file tests against it.

THE RULE: WHAT COUNTS AS AN ANCHOR

    1. A page in a named edition.
    2. The work's internal structure: chapter, section heading, book, part,
       letter, number, entry, preface, title page.
    3. A canonical reference system (Stephanus 509d, book.chapter.verse).
    4. A primary-document identifier (a record group, a manuscript number, a
       statute, a document number).
    5. A URL, a dated document or address, a timecode in a recording.
    6. When the source has no internal structure to point at: "a quoted passage
       long enough to be locatable through any reader's search function."

    So a note that gives a passage is not waste by default. Where the source
    has no structure to point at, THE PASSAGE IS THE ANCHOR. Any pass that
    strips quoted passages out of notes has to check this first.

    A quoted run of eight or more consecutive words counts as a searchable
    anchor, because that is what a reader types into a search box.

    If your book states its own citation conventions, put them in
    Methodology/Citation Conventions.md and `--rule` prints that file.

WHAT IT REPORTS

    ANCHORED    the note has a page, a structure, an archival id, a URL, or a
                named section. Which one is named.
    SEARCH-ONLY the note's ONLY anchor is a quoted passage. Legal under rule 6,
                and worth a human eye: if the source has a chapter heading,
                name it and the passage can go.
    NO ANCHOR   a reader cannot reach the source from this note at all.
    MARGINALIA  the author's own note on the prose (e.g. "Nominalization: …"),
                not a citation.

WHAT IT DOES NOT DO

    It does not know which edition is in the library, so it cannot tell a
    genuine EPUB-only source from a print book whose page nobody looked up.
    SEARCH-ONLY is the line where a person decides that.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402

RULE_FILE = B.METHODOLOGY / "Citation Conventions.md"

# Each anchor kind maps to the rule number above that allows it.
ANCHORS = [
    # A bare page after the imprint is Chicago's own form: "(Oxford: OUP,
    # 2011), 38." Requiring "p." reported a correctly cited page as no anchor.
    # A bare page after an italic short title is Chicago's short form:
    # "Paine, *Common Sense*, 14". Requiring "pp." or an imprint parenthesis
    # reported such a note as unanchored after an edit that made its anchor
    # better.
    ("page", r"\bpp?\.\s*\d|\bpp?\s*\d+–\d|\bat\s+\d{3,4}\b|\bfol\.\s*\d"
             r"|\),\s*\d{1,4}(?:[-–]\d{1,4})?\s*[,.;]"
             r"|\*,\s*\d{1,4}(?:[-–]\d{1,4})?\b"
             # An ARTICLE's short title is quoted, not italicised, so Chicago's
             # short form puts the page after a closing quotation mark:
             # Author, "Article Title," 141. Matching only the italic form
             # reported such a note as unanchored while it had two pages.
             r"|,[\"”]\s*\d{1,4}(?:[-–]\d{1,4})?\b",
     "1 page in a named edition"),
    ("structure", r"\b(?:chs?|chaps?|chapters?|bks?|books?|vols?|secs?|pts?|parts?|canto|act|scene|"
                  r"hymn|oration|epistle|letter|entry|thesis|theses|no)\.?\s*[\dIVXL]"
                  r"|§+\s*\d|\bAppendix[: ]|\bcanon\s+\d|\bsession\s+[IVXL]"
                  r"|\bArticle\s+[IVX\d]|\bAmendment\b|\bclause\s+\d"
                  r"|\b(?:preface|introduction|preamble|prologue|epilogue|foreword"
                  r"|afterword|colophon|frontispiece|dedication|title[- ]page)\b"
                  r"|\bs\.v\.|\bsub verbo\b"
                  # "in the section on monarchy": a named division of the work.
                  r"|\b\d+(?:st|nd|rd|th)\s+degree\b"
                  r"|\bin the (?:section|chapter|part|entry) on\b",
     "2 the work's internal structure"),
    # Canonical systems. A trailing letter is part of the reference (Stephanus
    # 509d, Bekker 1356a), so the number cannot end on a word boundary.
    # Requiring one reported every such reference as unanchored on the
    # original's first run.
    ("canonical", r"\b\d+\.\d+(?:\.\d+)?[a-e]?\b|\b\d{3,4}[ab]\b"
                  r"|\b\d+[a-e]–\d|\b\d+[a-e]\b(?=[,.;)\s])"
                  r"|\b(?:tlg|phi)\d{4}\.(?:tlg|phi)\d{3}"
                  # Scripture: book + chapter + verse.
                  r"|\b[1-3]?\s?[A-Z][a-z]{2,}\.?\s+\d+:\d+"
                  # A line or section range given after the work: 202-217.
                  r"|[,(]\s*\d+–\d+\s*[).,;]",
     "3 canonical reference system"),
    # CASE-SENSITIVE, and that matters. Every other pattern runs under re.I,
    # which turned the uppercase-prefix branch into a machine for inventing
    # anchors out of ordinary prose: "in 1973", "May 2026", "of 1787" all
    # matched once case was ignored. A note with no locator at all reported
    # ANCHORED. A check that manufactures the thing it is checking for is
    # worse than no check.
    ("archival", (r"\b(?:RG|MS|MSS|P\.?L\.?)[ -]?\d"
                  r"|\b\d{2}-\d{2}-\d{2}-\d{3,4}\b|\bHouse Doc\.|\bReels?\s*\d"
                  r"|\bU\.?S\.?C\.?\b|\b\d+\s+U\.?\s?S\.?\s+\d+|\bDoc\. No\.", 0),
     "4 primary-document identifier"),
    ("archival-id", (r"\b[A-Z]{2,4}[ -]\d{3,}(?:-[A-Z]{2})?\b", 0),
     "4 document number"),
    # A URL in a footnote is usually written without its scheme, because the
    # scheme is noise to a reader who is going to type the address. Requiring
    # `https?://` reported a note citing two sources by address as unanchored.
    ("url", r"https?://|\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)+"
            r"(?:/[^\s,;)]*)?(?:\.html?|\.pdf|/)|"
            r"\b[a-z0-9-]+\.(?:com|org|net|gov|edu|io|uk)\b",
     "5 URL or web address"),
    ("date", r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|"
             r"September|October|November|December)\s+\d{4}"
             r"|\b(?:January|February|March|April|May|June|July|August|September|"
             r"October|November|December)\s+\d{1,2}?,?\s*\d{4}",
     "5 dated document or address"),
    ("timecode", r"\b\d{2}:\d{2}:\d{2}", "5 recorded address, timecode"),
]

QUOTE = re.compile(r'"([^"]{12,})"|“([^”]{12,})”|\*"([^"]{12,})"\*')
SEARCHABLE_WORDS = 8


def searchable(note):
    """The longest quoted run in the note, in words. Rule 6 accepts a passage
    'long enough to be locatable through any reader's search function' as the
    anchor of last resort."""
    best = 0
    for m in QUOTE.finditer(note):
        q = m.group(1) or m.group(2) or m.group(3) or ""
        best = max(best, len(q.split()))
    return best


SECTION_NAME = re.compile(
    r"(?:section|chapter|entry|appendix|part|titled|headed|s\.v\.)\s*[,:]?\s*"
    r'["“]([^"”]{3,80})["”]', re.I)

# CHICAGO'S SHORT FORM FOR A SECTION: Author, *Title*, "Section Heading."
# A quoted, title-cased heading right after an italic title is a named section,
# the first anchor rule 6 asks for, even with no "section" before it.
SECTION_AFTER_TITLE = re.compile(r'\*,\s*["“]([^"”]{3,80})["”]')


def _titlecased(q):
    ws = [w for w in re.findall(r"[A-Za-z][A-Za-z'’-]*", q) if len(w) >= 4]
    return len(ws) >= 1 and sum(1 for w in ws if w[0].isupper()) / len(ws) >= 0.6


def strip_quotes(note):
    """Anchors must come from the note's OWN words. A page number inside a
    quotation belongs to the source's prose, not to this book's citation.

    A SECTION HEADING in quotes is the note's own words, though, and is the
    first anchor rule 6 asks for. Stripping every quoted string once reported
    a note as unanchored when it named the section it cites: the checker
    deleted the anchor, then complained it was missing.
    """
    kept = " ".join(f"section {m.group(1)}" for m in SECTION_NAME.finditer(note))
    # A PAGE THAT FOLLOWS A QUOTED TITLE SURVIVES THE STRIP. Stripping every
    # quoted run took the closing quotation mark and the page with it.
    kept += " " + " ".join(m.group(0) for m in
                           re.finditer(r',["”]\s*\d{1,4}(?:[-–]\d{1,4})?', note))
    return QUOTE.sub(" ", note) + " " + kept


MARGINALIA = re.compile(
    r"^\[\^[^\]]+\]:\s*(?:Nominalization|Compression|Abstraction|Passive|"
    r"Mind[- ]reading|Telegraph\w*)\b[.:]", re.I)


def classify(note):
    """(verdict, [(kind, why)], longest quoted run in words) for one note line."""
    # An author's marginal note is not a citation and has no source to point
    # at: it explains why a sentence compressed something. Reporting it as
    # unanchored asks a note to cite a decision the author made, which no page
    # can settle.
    if MARGINALIA.match(note.strip()):
        return "MARGINALIA", [("marginalia", "author's own note, not a citation")], 0
    body = strip_quotes(note)

    def _hit(rx):
        """A pattern may carry its own flags as (pattern, flags). The archival
        identifier branch is case-SENSITIVE; everything else is not."""
        if isinstance(rx, tuple):
            return re.search(rx[0], body, rx[1])
        return re.search(rx, body, re.I)
    found = [(kind, why) for kind, rx, why in ANCHORS if _hit(rx)]
    # A note that NAMES the section it cites is anchored, whatever the section
    # is called.
    if SECTION_NAME.search(note) or any(
            _titlecased(m.group(1)) for m in SECTION_AFTER_TITLE.finditer(note)):
        found.append(("section", "2 the section is named"))
    words = searchable(note)
    if found:
        return "ANCHORED", found, words
    if words >= SEARCHABLE_WORDS:
        return "SEARCH-ONLY", [], words
    return "NO ANCHOR", [], words


def scan(path):
    """[(line, slug, words, verdict, found, longest quoted run)] for one file."""
    out = []
    for i, l in enumerate(Path(path).read_text(encoding="utf-8").split("\n"), 1):
        m = re.match(r"\[\^([^]]+)\]:", l)
        if m:
            verdict, found, words = classify(l)
            out.append((i, m.group(1), len(l.split()), verdict, found, words))
    return out


def main():
    if "--rule" in sys.argv:
        if RULE_FILE.exists():
            print(RULE_FILE.read_text(encoding="utf-8"))
        else:
            print(__doc__.split("THE RULE:")[1].split("WHAT IT REPORTS")[0])
        return
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    bare = "--bare" in sys.argv
    if "--all" in sys.argv:
        files = B.chapter_files()
    else:
        files = [f for a in args if a.isdigit() for f in [B.chapter_file(int(a))] if f]
    if not files:
        print(__doc__.split("THE QUESTION")[0])
        return

    tally = {"ANCHORED": 0, "MARGINALIA": 0, "SEARCH-ONLY": 0, "NO ANCHOR": 0}
    for f in files:
        rows = scan(f)
        bad = [r for r in rows if r[3] not in ("ANCHORED", "MARGINALIA")]
        for _, _, _, v, _, _ in rows:
            tally[v] += 1
        if not bare:
            print(f"\n{'=' * 74}\n{f.name}   "
                  f"{len(rows)} note(s), {len(bad)} without a structural anchor")
        for ln, slug, w, v, found, words in rows:
            if v in ("ANCHORED", "MARGINALIA") and not bare:
                continue
            note = f"   {v:<12} [^{slug}]".ljust(44)
            tail = (f"{w}w   longest quoted run {words}w"
                    if v == "SEARCH-ONLY" else f"{w}w")
            print(note + tail)

    print(f"\n{'-' * 74}")
    for k in ("ANCHORED", "MARGINALIA", "SEARCH-ONLY", "NO ANCHOR"):
        print(f"  {k:<13}{tally[k]:>5}")
    print("\nSEARCH-ONLY is legal: rule 6 makes a searchable passage the anchor when")
    print("the source has no internal structure to point at. Before cutting a")
    print("passage out of one, check whether the source has a chapter.")
    print("NO ANCHOR means a reader cannot reach the source from the note at all.")


if __name__ == "__main__":
    main()

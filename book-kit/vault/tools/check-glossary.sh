#!/usr/bin/env python3
"""check-glossary.sh — check that each term of art is glossed where the reader first meets it.

    tools/check-glossary.sh 25          # one chapter
    tools/check-glossary.sh --all
    tools/check-glossary.sh --terms     # list the defined terms, and which are not used yet
    tools/check-glossary.sh --unlisted  # phrases the book uses like terms and no glossary defines
    tools/check-glossary.sh --per-chapter 25   # first use in each chapter, for a chapter read alone
    tools/check-glossary.sh --all --strict     # exit 1 when anything is found

WHERE THE TERMS COME FROM

    Methodology/Glossary Terms.md. Each entry is a bold term at the head of its
    line, followed by a colon or a dash and the gloss:

        **Common sense**: Paine's name for ...

    That file may also name other files to read entries from, one per line,
    in the form `glossary-file: Appendices/Appendix B - Glossary.md` (a path
    relative to the vault). Use this when your book prints its own glossary.
    An entry heading may hold two names: "**Term One / Term Two**".

WHY THIS EXISTS

    The original author, on three sentences of a draft: "I'm struggling with
    this abstraction. What are you talking about?" The sentences described a
    distinction between two kinds of a thing and never used the word for it.
    The fault has a name, abstraction by omission: a thing referred to and not
    named.

    The rule already said every author gets a gloss at first mention. A term
    of art is the same problem: the reader meets a word doing technical work
    and has to guess or scroll.

WHAT IT CHECKS, AND WHAT IT CANNOT

    It checks ONE thing, which has a hard answer: is a glossary term's first
    appearance close to a gloss?

    A gloss is an em-dash or colon or parenthesis followed by explanation, a
    "which means" / "the claim that" / "that is" construction, or an italic
    definition, inside the same sentence or the one after.

    IT CANNOT CATCH ABSTRACTION BY OMISSION IN GENERAL. That fault is a MISSING
    referent, and only a reader who knows what the sentence is about can see
    it. A probe for it in the original book returned 27 hits, nearly all false.
    A checker that cries wolf on good sentences teaches people to skip its
    output. This file does only the half a machine can settle.

THE GLOSSARY MAY RUN AHEAD OF THE BOOK

    The author: "There may be items I want in the glossary that have not been
    used in the book (yet)." So a defined term that appears in no chapter is
    NOT a fault. `--terms` reports it as defined-and-unused, and nothing else
    does. The reverse IS worth seeing: `--unlisted` reports capitalised or
    hyphenated phrases the chapters use like terms of art and no glossary
    defines.
"""
import collections
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402

TERMS_FILE = B.METHODOLOGY / "Glossary Terms.md"

# An entry is a bold term at the head of its line: **Term**: ... or **Term** — ...
ENTRY = re.compile(r"(?m)^\*\*([^*\n]{2,60}?)\*\*\s*(?::|—|-)\s")
EXTRA = re.compile(r"(?m)^\s*glossary-file:\s*(.+?)\s*$")
# Examples in a code fence are documentation, not entries.
FENCE = re.compile(r"(?ms)^```.*?^```[^\n]*$")


def _read(path):
    return FENCE.sub("", path.read_text(encoding="utf-8", errors="replace"))

# A gloss, in the common shapes.
GLOSS = re.compile(
    r"—[^—]{8,}|:\s+\S|\([^)]{12,}\)|"
    r"\b(?:which means|that is|the claim that|the practice of|the process|"
    r"defined as|in other words|short for|named for|the book's term)\b",
    re.I)


def glossaries():
    """The files entries are read from: Glossary Terms.md, then any it names."""
    out = [TERMS_FILE]
    if TERMS_FILE.exists():
        out += [B.VAULT / m.group(1) for m in EXTRA.finditer(_read(TERMS_FILE))]
    return out


def terms():
    """{term: file it is defined in}, longest first.

    Longest first, so a long term is tested before a short term inside it
    could ever match.
    """
    out = {}
    for g in glossaries():
        if not g.exists():
            continue
        for m in ENTRY.finditer(_read(g)):
            for part in re.split(r"\s*/\s*", m.group(1).strip()):
                part = part.strip()
                if len(part) > 2:
                    out.setdefault(part, g.name)
    return dict(sorted(out.items(), key=lambda kv: -len(kv[0])))


# A SINGLE ORDINARY WORD IS NOT A TERM OF ART, however it is typeset.
#
# The original's first run reported 98 findings, nearly all noise: "First",
# "Sources", "Practice". Two causes: a glossary that numbered a list as
# "**First** — …", which reads to the entry parser like a term; and matching
# without regard to case, which made every ordinary use of "practice" a hit.
#
# So a one-word term must be capitalised WHERE IT IS USED, and must not be a
# word the book also uses in the ordinary way. Multi-word terms, hyphenated
# coinages and trademarked ones keep the loose match.
ORDINAL = {"first", "second", "third", "fourth", "fifth", "sixth"}


def is_common(term, corpus):
    """Does the book use this word lowercase, in the ordinary way?"""
    if len(term.split()) > 1 or "-" in term or "™" in term:
        return False
    if term.lower() in ORDINAL:
        return True
    n = len(re.findall(rf"(?<![\w-]){re.escape(term.lower())}s?(?![\w-])", corpus))
    return n >= 3


def pattern_for(term):
    """Match the term as written, tolerating the trademark sign and plurals.

    Case-SENSITIVE for a single word: the capital is what marks it as the term
    rather than the ordinary word.
    """
    body = re.escape(term).replace(r"\ ", r"\s+")
    flags = 0 if len(term.split()) == 1 else re.I
    return re.compile(rf"(?<![\w-]){body}(?:™)?s?(?![\w-])", flags)


def chapter_files(nums):
    for f in B.chapter_files():
        n = B.chapter_number(f)
        if n is not None and (not nums or n in nums):
            yield n, f


def sentences_at(text, pos):
    """The sentence holding pos, and the one after it."""
    start = max(text.rfind(". ", 0, pos), text.rfind("\n", 0, pos)) + 1
    end = pos
    for _ in range(2):
        nxt = text.find(". ", end + 1)
        end = len(text) if nxt < 0 else nxt + 1
    return text[start:end]


def findings(nums=(), per_chapter=False):
    """{chapter: [(line, term, defined in, line text)]} for terms used without a gloss."""
    T = terms()
    corpus = "\n".join(f.read_text(encoding="utf-8", errors="replace")
                       for _, f in chapter_files(set())).lower()
    T = {k: v for k, v in T.items() if not is_common(k, corpus)}
    # FIRST USE IN THE BOOK, not first use per chapter. The book is read front
    # to back. A term glossed in Chapter 2 does not earn a second gloss in
    # Chapter 12; the original's first version reported one term three times
    # for exactly that reason. --per-chapter restores the stricter view, for a
    # chapter that will be read on its own.
    first = {}
    for n, f in chapter_files(set()):
        body = f.read_text(encoding="utf-8", errors="replace")
        for term in T:
            if term in first:
                continue
            m = pattern_for(term).search(body)
            if m:
                first[term] = (n, f, m.start())
    out = {}
    for n, f in chapter_files(set(nums)):
        body = f.read_text(encoding="utf-8", errors="replace")
        lines = body.splitlines()
        hits = []
        for term, src in T.items():
            if per_chapter:
                m = pattern_for(term).search(body)
                if not m:
                    continue
                pos = m.start()
            else:
                if first.get(term, (None,))[0] != n:
                    continue
                pos = first[term][2]
            if GLOSS.search(sentences_at(body, pos)):
                continue
            line_no = body.count("\n", 0, pos) + 1
            hits.append((line_no, term, src, lines[line_no - 1][:88]))
        if hits:
            out[n] = sorted(hits)
    return out


def main():
    nums = {int(a) for a in sys.argv[1:] if a.isdigit()}
    if not TERMS_FILE.exists():
        print(f"\n  No term list at {TERMS_FILE.relative_to(B.VAULT)}. Copy the template from the"
              " kit and add your terms of art.\n")
        return 0

    if "--terms" in sys.argv:
        T = terms()
        used = set()
        for _, f in chapter_files(set()):
            body = f.read_text(encoding="utf-8", errors="replace")
            used |= {t for t in T if pattern_for(t).search(body)}
        unused = [t for t in T if t not in used]
        print(f"\n  {len(T)} terms defined in {len([g for g in glossaries() if g.exists()])} file(s)")
        print(f"  {len(used)} of them appear in a chapter")
        print(f"  {len(unused)} defined and not yet used — NOT a fault\n")
        for t in sorted(unused):
            print(f"      {t}")
        return 0

    if "--unlisted" in sys.argv:
        # A ROUGH SIEVE, AND IT SAYS SO. The original's first version returned
        # 406 rows led by place names and people, not terms of art. Footnote
        # definition lines are dropped, because that is where authors,
        # publishers and cities live; a candidate must appear in at least three
        # chapters; and a stoplist holds the obvious ones. It exists to catch a
        # coinage the book uses like a term and nobody wrote down.
        STOP = re.compile(
            r"\b(?:New York|United States|University|Press|Chapter|Appendix|"
            r"Trust|Foundation|Institute|Society|Committee|Council|Department|"
            r"Report|Times|Post|Journal)\b")
        seen = collections.Counter()
        where = collections.defaultdict(set)
        CAND = re.compile(r"\b((?:[A-Z][a-z]+[- ]){1,3}(?:[A-Z][a-z]+))\b")
        for n, f in chapter_files(nums):
            body = f.read_text(encoding="utf-8", errors="replace")
            body = "\n".join(l for l in body.splitlines() if not l.startswith("[^"))
            body = re.sub(r"\[\^[^\]]+\]", " ", body)
            for m in CAND.finditer(body):
                phrase = m.group(1)
                if STOP.search(phrase):
                    continue
                seen[phrase] += 1
                where[phrase].add(n)
        known = {x.lower() for x in terms()}
        rows = [(c, p_, sorted(where[p_])) for p_, c in seen.items()
                if c >= 5 and len(where[p_]) >= 3 and p_.lower() not in known]
        rows.sort(reverse=True)
        print(f"\n  {len(rows)} phrases the book uses like terms of art, in body")
        print("  prose, across three or more chapters, and no glossary defines.")
        print("  A ROUGH SIEVE — people and places still get through.\n")
        for c, p_, ch in rows[:40]:
            print(f"    {c:>3}x  {p_:<40} Ch{', Ch'.join(f'{x:02d}' for x in ch[:6])}")
        return 0

    per_chapter = "--per-chapter" in sys.argv
    found = findings(nums, per_chapter)
    total = 0
    for n, hits in sorted(found.items()):
        print(f"\n--- Ch{n:02d}: {len(hits)} term(s) used without a gloss"
              f"{' (first use in this chapter)' if per_chapter else ' where the reader first meets them'}")
        for line_no, term, src, line in hits:
            print(f"    {B.coord(n, line_no):<12} {term}")
            print(f"              defined in {src}")
            print(f"              {line}")
        total += len(hits)
    print(f"\n{total} finding(s). A term of art earns its gloss where the reader")
    print("first meets it, the same as an author does. A defined term not yet used")
    print("in the book is not reported here — see --terms.\n")
    return 1 if (total and "--strict" in sys.argv) else 0


if __name__ == "__main__":
    sys.exit(main())

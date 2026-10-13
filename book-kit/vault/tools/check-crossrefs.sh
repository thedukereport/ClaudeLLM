#!/usr/bin/env python3
"""check-crossrefs.sh — check that each "Chapter N" cross-reference points at a chapter that holds what the sentence names.

    tools/check-crossrefs.sh                          # every chapter and appendix
    tools/check-crossrefs.sh Appendices               # one folder, relative to the vault
    tools/check-crossrefs.sh "Chapters/Chapter 04*"   # specific files (a glob, relative to the vault)

WHY THIS EXISTS
    In the system this kit comes from, a hand audit of the book's two
    glossaries found 27 wrong cross-references out of about 50. One appendix
    cited Chapter 22 for five terms that all live in Chapter 19: the digits
    transposed, repeatedly. Another sent readers to a chapter for a term
    defined four chapters later, and to a chapter for a term in no chapter at
    all.

    Nothing caught any of it. A cross-reference is the cheapest sentence to
    write and the least likely to be checked: it reads as scholarship, costs
    nothing, and no one re-opens the cited chapter.

    Three of the 27 were introduced by the fix pass itself. One declared a
    term absent from the book on a regex that could not match the plural the
    chapter uses. Hence the plural and variant handling below.

WHAT IT DOES
    For every "Chapter N" reference in the chapters and appendices:
      1. pulls the surrounding sentence
      2. extracts candidate key terms (bold, italic and quoted spans, the
         glossary entry name when the line is a definition, capitalised phrases)
      3. searches Chapter N for each candidate, with plural and hyphen variants
      4. reports nothing (PASS), or FLAG with the chapters that DO hold the term

    FLAG means "a person has to read this", not "this is wrong". The
    extraction is a heuristic. False positives are expected and cheap; a missed
    false citation is not.

WHAT IT DOES NOT DO
    It cannot tell whether a chapter treats a concept under different words.
    It checks vocabulary, not substance: a glossary entry listing step names a
    chapter never uses may still point at the right chapter, and only reading
    both settles that.

EXIT STATUS
    0 = no flags. 1 = flags to read.
"""
import glob
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402

_cache = {}


def chapter_text(n):
    """Chapter n's text, lowercased, or None when there is no such chapter file.

    Body prose writes "Chapter 7" while the file may be "Chapter 07 - …";
    bookconfig matches either.
    """
    n = int(n)
    if n not in _cache:
        f = B.chapter_file(n)
        _cache[n] = f.read_text(encoding="utf-8").lower() if f else None
    return _cache[n]


def variants(term):
    """front man / frontman / frontmen — the plural miss that motivated this."""
    t = term.lower().strip(" .,;:—-–'’")
    out = {t}
    out.add(t.replace("-", " "))
    out.add(t.replace(" ", "-"))
    out.add(t.replace("-", ""))
    if t.endswith("y"):
        out.add(t[:-1] + "ies")
    if t.endswith("man"):
        out.add(t[:-3] + "men")
    if t.endswith("s"):
        out.add(t[:-1])
    else:
        out.add(t + "s")
    # Single-word stems only, and long enough not to collide:
    # "nominalization" -> "nominaliz", but never "calibration" -> "calibr".
    if " " not in t and len(t) >= 11:
        out.add(t[:len(t) - 4])
    # Multiword terms: also accept the distinctive component on its own. A
    # two-word term cited to a chapter that uses only its longer word was a
    # real citation the phrase test failed.
    words = [w for w in re.split(r'[ -]', t) if len(w) >= 7]
    if len(t.split()) > 1 and words:
        out.add(max(words, key=len))
    # Keep the term itself whatever its length; the length floor applies only
    # to derived forms, which is where collisions come from.
    return {v for v in out if len(v) >= 6} | {t}


STOP = {"the", "a", "an", "of", "in", "to", "and", "or", "is", "are", "was", "were", "for", "with",
        "that", "this", "from", "as", "by", "on", "at", "it", "its", "their", "his", "her", "they",
        "we", "our", "you", "your", "not", "but", "see", "chapter", "chapters", "book"}


def key_terms(line, ctx):
    """Up to five candidate terms the sentence around a reference names."""
    out = []
    m = re.match(r'^\s*\*\*(.+?)\*\*', line)          # glossary entry name
    if m:
        out.append(m.group(1))
    out += re.findall(r'\*([A-Za-z][A-Za-z \-’\']{3,40})\*', ctx)
    out += re.findall(r'"([^"]{4,45})"', ctx)
    out += re.findall(r'\b((?:[A-Z][a-z]+[ -]){1,3}[A-Z][a-z]+)\b', ctx)
    seen, cleaned = set(), []
    for x in out:
        x = x.strip(" .,;:—-–")
        if not x or x.lower() in STOP:
            continue
        if re.search(r'\bchapters?\b', x, re.I):        # "See Chapter", "Chapter 8"
            continue
        if x.lower() in seen:
            continue
        seen.add(x.lower())
        cleaned.append(x)
    return cleaned[:5]


def targets(args):
    if not args:
        files = list(B.chapter_files())
        if B.APPENDICES.is_dir():
            files += sorted(p for p in B.APPENDICES.glob("*.md") if not B.is_backup(p))
        return files
    if len(args) == 1 and (B.VAULT / args[0]).is_dir():
        return sorted(p for p in (B.VAULT / args[0]).glob("*.md") if not B.is_backup(p))
    out = []
    for a in args:
        out += [Path(p) for p in sorted(glob.glob(str(B.VAULT / a)))]
    return [p for p in out if not B.is_backup(p)]


def check_file(path):
    """(pairs checked, [(line, n, terms, chapters elsewhere or None)]) for one file."""
    checked, flags = 0, []
    for lineno, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("<!--"):        # audit comments are not prose
            continue
        for m in re.finditer(r'Chapters?\s+(\d+(?:\s*(?:,|and|&|–|-)\s*\d+)*)', line):
            # "…(London: Publisher, 1977), Chapter 1." is a chapter of someone
            # else's book. Bibliographic citations put a closing paren, a year,
            # or a page marker immediately before the reference.
            before = line[max(0, m.start() - 40): m.start()]
            if re.search(r'(\)|\b(19|20)\d\d\b|\bpp?\.\s*\d+|,\s*)$', before) and \
               re.search(r'\)|\bed\.|\btrans\.|:\s|\bvol\.', before, re.I):
                continue
            nums = re.findall(r'\d+', m.group(1))
            ctx = line[max(0, m.start() - 130): m.end() + 130].strip()
            terms = key_terms(line, ctx)
            for n in nums:
                checked += 1
                txt = chapter_text(n)
                if txt is None:
                    flags.append((lineno, n, terms, None))
                    continue
                if not terms:
                    continue                        # nothing extractable; not a finding
                if any(v in txt for t in terms for v in variants(t)):
                    continue                        # PASS
                elsewhere = []
                for cand in B.chapter_files():
                    cn = B.chapter_number(cand)
                    if cn is None or cn == int(n):
                        continue
                    ct = chapter_text(cn)
                    if ct and any(v in ct for t in terms for v in variants(t)):
                        elsewhere.append(cn)
                flags.append((lineno, n, terms, sorted(set(elsewhere))))
    return checked, flags


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    total = nflags = 0
    for path in targets(args):
        checked, flags = check_file(path)
        total += checked
        nflags += len(flags)
        for lineno, n, terms, elsewhere in flags:
            if elsewhere is None:
                print(f"FLAG {path.name}:{lineno} → Chapter {n} — NO SUCH CHAPTER FILE")
                continue
            where = (f"  found in: Ch {', '.join(str(c) for c in elsewhere)}"
                     if elsewhere else "  found in: NO CHAPTER")
            print(f"FLAG {path.name}:{lineno} → Chapter {n}")
            print(f"       terms: {terms}")
            print(f"     {where}")
    print()
    print(f"{total} reference→chapter pairs checked, {nflags} flagged for reading.")
    return 1 if nflags else 0


if __name__ == "__main__":
    sys.exit(main())

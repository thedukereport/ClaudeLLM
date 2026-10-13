#!/usr/bin/env python3
"""assess-notes.py — split every footnote into sentences and sort each one into six piles.

    tools/assess-notes.py                 # the scope, book-wide and per chapter
    tools/assess-notes.py 22              # one chapter, note by note
    tools/assess-notes.py --write         # write Fact Check/Note Assessment.jsonl
    tools/assess-notes.py --json          # one line per finding, for a register

    CLEAN IS NOT A VERDICT ON A NOTE. It means no sentence in it matched a
    content pattern. In the original book, of the first 87 notes read by hand,
    15 that this file called CLEAN needed work: one note said a writer
    "characterises" a subject beside a body that gave those words as the
    subject's own; another cited nothing at all, because a sentence pointing at
    one of the book's own chapters looked like a citation. **This file finds
    candidates. It does not read.** Where a reading and this file disagree, the
    reading governs.

WHY THIS EXISTS, IN THE AUTHOR'S WORDS

    "We started working on every footnote that was over a certain cap, but now
    it seems that the content-in-a-note-that-should-be-in-the-body or is
    redundant, is more widespread. So while I'm asleep, I want you to look at
    every footnote and do an assessment… I want to know the scope of the
    problem."

    The 150-word cap found the long notes. It never looked at the short ones,
    and the fault the author kept catching has nothing to do with length: a
    note that holds the chapter's content, or repeats what the paragraph above
    it already says.

WHAT IT DOES, PER NOTE

    1. Finds the note's anchor paragraph: the body block holding `[^slug]`.
    2. Splits the note into sentences, protecting abbreviations, initials and
       quotations (check-note-content.sentences).
    3. Sorts every sentence into one of six piles (classify()):

       CITATION   a pointer to a place in a work: page, chapter, section,
                  volume, edition, archive, date of a letter, a title.
       WARNING    it says another edition or writer gives something different,
                  which is what keeps a reader off the wrong page.
       RELIED ON  a quotation whose words the anchor paragraph also gives: the
                  words the body rests on.
       REPEATS    a sentence whose words are almost all in the anchor paragraph
                  already. This is the redundancy. It is not length, and no cap
                  sees it.
       CONTENT    a statement that is neither a pointer nor a warning. It
                  belongs in the body or in the chapter's ledger under
                  `Fact Check/`.
       JUDGEMENT  it tells a reader how much to believe a source, asserts a
                  source's authority or access, or says what the book or the
                  chapter is about: classes I, J and K of check-footnotes.sh.

    4. Gives the note one verdict: CLEAN, REDUNDANT, CARRIES CONTENT, JUDGING,
       MIXED, or UNANCHORED.

    Every finding is a coordinate, not a ruling. Nothing here edits a chapter.

WHAT OTHER TOOLS IMPORT FROM HERE
    classify(), words(), overlap(), verdict(), rows(), and the patterns
    WARRANT, VERDICT, THESIS, SELFTALK, XREF. tools/check-card-notes.py loads
    this file as a module.
"""
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import bookconfig as B  # noqa: E402
import notelib          # noqa: E402

VAULT = B.VAULT

_spec = importlib.util.spec_from_file_location("cnc", TOOLS / "check-note-content.py")
cnc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cnc)

OUT = B.FACT / "Note Assessment.jsonl"
CAP = 150

# A BADGE OFFERED AS PROOF, not an office recorded as a fact.
#
# The first version fired on "director of", and a note came back as JUDGING
# for a sentence giving a man's office with its dates. That is biography the
# note may well owe a reader. The rule forbids a credential WORKING AS
# SUPPORT, so the words here are the ones that do that work, and plain offices
# are left out.
WARRANT = re.compile(
    r"\b(?:credential|authority on|leading (?:expert|scholar|authority)|"
    r"foremost|renowned|respected|eminent|distinguished|"
    r"award-?winning|peer-?reviewed|which lends|gives (?:him|her) standing|"
    r"qualifies (?:him|her)|is qualified to)\b", re.I)
VERDICT = re.compile(
    r"\b(?:reliable|unreliable|convincing|persuasive|credible|trustworthy|"
    r"partisan|polemical|sensational|debunk\w*|discredit\w*|stands as|"
    r"well-?documented|significant evidentiary|should be treated|"
    r"must be weighed|carries weight|not a neutral)\b", re.I)
THESIS = re.compile(
    r"\b(?:this (?:book|chapter)|the (?:book|chapter)'?s?)\b", re.I)
SELFTALK = re.compile(
    r"/Volumes/|/Users/|/home/|\bvault\b|\bOpen:|\bTODO\b|\bqueue\b|\bthis note\b|"
    r"\bI have not\b|\bI could not\b|\bfor our purposes\b", re.I)
XREF = re.compile(r"(?<!\^)\[\^[A-Za-z0-9_\-]+\]")


def words(s):
    """The words of s, lowercased, in order (a list, unlike cnc.words)."""
    return [w for w in re.findall(r"[a-z0-9']+", (s or "").lower())]


def overlap(sentence, body_words):
    """Share of the sentence's words over three letters that are in body_words."""
    ws = [w for w in words(sentence) if len(w) > 3]
    if not ws:
        return 0.0
    return sum(1 for w in ws if w in body_words) / len(ws)


def titlecased(q):
    return cnc.titlecased(q)


def classify(sent, body_words, body_text):
    """One of the six piles, and why: (pile, reason).

    ORDER MATTERS, AND IT USED TO BE WRONG. The judgement classes were tested
    before the locator, so a sentence giving an edition and a page was called a
    judgement because it also named an office. A sentence that routes a reader
    to a place in a work is a citation; the faults below live in sentences that
    route nowhere.
    """
    if XREF.search(sent):
        return "CONTENT", "points at another note by its slug, which renders literally"
    if SELFTALK.search(sent):
        return "CONTENT", "talks about the making of the book or the vault"
    if cnc.LOCATOR.search(sent) and not THESIS.search(sent):
        return "CITATION", "has a page, chapter, edition, archive or date"
    if WARRANT.search(sent):
        return "JUDGEMENT", "offers a credential as proof"
    if VERDICT.search(sent):
        return "JUDGEMENT", "tells a reader how much to believe it"
    if THESIS.search(sent):
        return "JUDGEMENT", "says what the book or the chapter is about"
    # A QUOTATION IS TESTED BEFORE THE LOCATOR, AND THE TEST CUTS BOTH WAYS.
    #
    # The standard says a note may hold "the words the body relies on, IF the
    # body has not already printed them." One signal, two readings:
    #
    #   the body gives these words    -> REPEATS. The note says it twice.
    #   the body does not give them   -> CONTENT. The words belong beside the
    #                                    sentence that rests on them, in the body.
    #
    # It goes before the locator test, because a note reprinting the body's
    # quotation usually has a page beside it, and the page is not the point.
    #
    # A title-cased quoted run is a section or article title, not a quotation:
    # check-note-content.judge() and the citations-only strip below already
    # treat it that way, and this test now agrees with them. Without this, a
    # Chicago short form citing a section heading in quotation marks came back
    # as "a quotation the body does not print".
    runs = [q for q in cnc.quoted_runs(sent)
            if len(words(q)) > 6 and not titlecased(q)]
    if runs:
        q = max(runs, key=lambda x: len(words(x)))
        if overlap(q, body_words) > 0.85:
            return "REPEATS", "the body gives these words already"
        return "CONTENT", "a quotation the body does not print"
    if overlap(sent, body_words) > 0.8 and len(words(sent)) > 8:
        return "REPEATS", "almost every word of it is in the anchor paragraph already"
    if cnc.LOCATOR.search(sent):
        return "CITATION", "has a page, chapter, edition, archive or date"
    if cnc.WARNING.search(sent):
        return "WARNING", "keeps a reader off the wrong page or the wrong words"
    if cnc.TITLE.search(sent) and len(sent.split()) <= 25:
        return "CITATION", "names a work"
    return "CONTENT", "states something rather than pointing at a page"


def verdict(piles):
    """One verdict for a note from its pile counts."""
    bad = {k: v for k, v in piles.items()
           if k in ("REPEATS", "CONTENT", "JUDGEMENT") and v}
    if not bad:
        return "CLEAN"
    if len(bad) > 1:
        return "MIXED"
    only = next(iter(bad))
    return {"REPEATS": "REDUNDANT", "CONTENT": "CARRIES CONTENT",
            "JUDGEMENT": "JUDGING"}[only]


def _is_citation(s):
    """True when a sentence would survive a citations-only strip.

    WHAT "CITATIONS ONLY" MEANS, TIGHTENED AFTER READING THE FIRST RESULTS. The
    first run kept three kinds of sentence it should not have, each because a
    pattern matched inside a sentence that is not a citation:

      * a cross-reference to the book itself ("Chapter 5 maps this…"), where
        `ch. 5` looked like a locator;
      * a quotation of the source with a page in it: the page is real, but the
        sentence is the body's business, not the note's;
      * biography, kept because an italic word or a run of years looked like a
        title or a locator.

    So a sentence survives only if it names a work and does not quote it at
    length, and the book's own chapters are never a locator. An italic single
    word is a term, not a title: a title has two words and a capital letter.
    """
    if re.search(r"\b[Cc]hapters?\s+\d+\b", s) and not cnc.TITLE.search(s):
        return False                      # a pointer at this book
    if [q for q in cnc.quoted_runs(s) if len(words(q)) > 6 and not titlecased(q)]:
        return False                      # quotes the source at length
    titled = [x for x in re.findall(r"\*([^*\n]{4,120})\*", s)
              if len(x.split()) > 1 and any(c.isupper() for c in x)]
    titled += [q for q in cnc.quoted_runs(s) if titlecased(q)]
    if not titled:
        return False
    return bool(cnc.LOCATOR.search(s) or titled)


def rows(only=None):
    """One dict per footnote definition in the chapters (or chapter `only`)."""
    out = []
    for ch, f in sorted(cnc.chapter_files().items()):
        if only and ch != only:
            continue
        text = f.read_text(encoding="utf-8")
        lines = text.split("\n")
        # WHERE EVERYTHING IS, IN THE AUTHOR'S NOTATION.
        #
        # The author, looking at the first version of the review page: "Show me
        # the ChXX/Lxx of the note, the paragraph the note is attached to, the
        # note itself… The previous and following paragraphs are helpful too."
        # So every row has its coordinates and its neighbourhood. A paragraph
        # here is a line: one block per line, blank lines between.

        def line_of(pred):
            for i, l in enumerate(lines, 1):
                if pred(l):
                    return i
            return 0

        def neighbours(idx):
            before = after = ""
            i = idx - 2
            while i >= 0:
                if (lines[i].strip() and not lines[i].startswith("[^")
                        and lines[i].strip() != "---"):
                    before = lines[i]
                    break
                i -= 1
            i = idx
            while i < len(lines):
                if (lines[i].strip() and not lines[i].startswith("[^")
                        and lines[i].strip() != "---"):
                    after = lines[i]
                    break
                i += 1
            return before, after

        for m in cnc.NOTEDEF.finditer(text):
            slug = m.group(1)
            note = cnc.BID.sub("", m.group(2)).strip()
            anchors = cnc.anchors(text, slug)
            body_text = " ".join(anchors)
            body_words = set(words(body_text))
            sents, piles, findings = cnc.sentences(note), Counter(), []
            for s in sents:
                s = s.strip()
                if len(s.split()) < 4:
                    continue
                pile, why = classify(s, body_words, body_text)
                piles[pile] += 1
                if pile in ("REPEATS", "CONTENT", "JUDGEMENT"):
                    findings.append({"pile": pile, "why": why, "sentence": s})
            # THE CUT, COMPUTED ONCE AND STORED, SO A REVIEW PAGE AND AN APPLIER AGREE.
            #
            # A note whose only faults are JUDGEMENT or REPEATS can be fixed by
            # deletion: the sentences come out and the citation stays. The text
            # is computed here so that whatever shows it and whatever writes it
            # read the same string. A note with a CONTENT fault gets no proposal:
            # where that content goes is the author's decision, not a deletion.
            cuts = [fd["sentence"] for fd in findings
                    if fd["pile"] in ("REPEATS", "JUDGEMENT")]
            # A CUT THAT LEAVES A FRAGMENT IS NOT A CUT. A computed cut is
            # offered only when every sentence it removes appears exactly once,
            # ends on real punctuation, and leaves text that still reads as
            # sentences.
            proposed = ""
            if cuts and not any(fd["pile"] == "CONTENT" for fd in findings):
                # A SENTENCE THAT HOLDS A CITATION IS NEVER CUT BY MACHINE. In
                # the original book two computed cuts would have taken a
                # citation out of the book to fix a clause beside it. So a cut
                # is offered only when every sentence it removes has no page,
                # no edition and no title. The rest need a sentence rewritten.
                ok = all(note.count(c) == 1 and c.rstrip()[-1:] in ".!?”\"')]"
                         and not cnc.LOCATOR.search(c) and not cnc.TITLE.search(c)
                         for c in cuts)
                if ok:
                    trial = note
                    for c in cuts:
                        trial = trial.replace(c, "")
                    trial = re.sub(r"\s{2,}", " ", trial).strip()
                    broken = (re.search(r"[,;:(\[]\s*$", trial)
                              or re.search(r"\s[,.;:]", trial)
                              or trial.rstrip()[-1:] not in ".!?”\"')]"
                              or len(trial.split()) < 8)
                    if not broken:
                        proposed = trial
            note_line = line_of(lambda l, s=slug: l.startswith("[^%s]:" % s))
            anchor_line = (line_of(lambda l, s=slug: ("[^%s]" % s) in l
                                   and not l.startswith("[^%s]:" % s))
                           if anchors else 0)
            before, after = neighbours(anchor_line) if anchor_line else ("", "")

            def strip(s):
                return cnc.BID.sub("", s).strip()

            # WHAT IS LEFT IF ONLY THE CITATIONS STAY.
            #
            # The author: "I need one more button to indicate to strip the
            # redundant context, and just leave the citations." This differs from
            # the cut above: the cut removes the flagged sentences and keeps the
            # rest; this keeps ONLY the sentences that point at a work, which is
            # what the rule says a note is for. Offered only when what is left
            # still reads as sentences and still names a source.
            keep = [s.strip() for s in sents if s.strip() and _is_citation(s.strip())]
            citations_only = " ".join(keep).strip()
            lost = [s for s in notelib.sources(note) if s not in citations_only]
            # A CITATION CAN BE FIVE WORDS LONG ("Paine, *Common Sense*, 14."),
            # so the floor is four words. A STRIP THAT LEAVES BROKEN MARKUP IS
            # NOT A STRIP: emphasis markers must balance and every kept sentence
            # must start like a sentence.
            broken_markup = (citations_only.count("*") % 2
                             or citations_only.count('"') % 2
                             or any(not re.match(r'^[\"“*\[(A-ZΑ-ΩÀ-Ü\d]', k)
                                    for k in keep))
            if (not keep or len(citations_only.split()) < 4 or lost or broken_markup
                    or citations_only.rstrip()[-1:] not in ".!?”\"')]"
                    or not (cnc.LOCATOR.search(citations_only)
                            or cnc.TITLE.search(citations_only))
                    or citations_only == note):
                citations_only = ""
            out.append({
                "citations_only": citations_only,
                "proposed": proposed,
                "note": note,
                "note_line": note_line,
                "anchor_line": anchor_line,
                "anchor_text": strip(anchors[0]) if anchors else "",
                "before_text": strip(before),
                "after_text": strip(after),
                "chapter": ch, "slug": slug,
                "words": len(note.split()),
                "over_cap": len(note.split()) > CAP,
                "anchored": bool(anchors),
                "piles": dict(piles),
                "verdict": "UNANCHORED" if not anchors else verdict(piles),
                "findings": findings,
                "note_words_in_body": round(overlap(note, body_words), 2),
            })
    return out


def main():
    only = next((int(a) for a in sys.argv[1:] if a.isdigit()), None)
    rs = rows(only)

    if "--write" in sys.argv:
        import vaultlog
        vaultlog.write_file(OUT, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rs),
                            tool="assess-notes.py", why="footnote assessment")
        print(f"  {len(rs)} note(s) written to {OUT.relative_to(VAULT)}")
        return

    if "--json" in sys.argv:
        for r in rs:
            for fd in r["findings"]:
                print(json.dumps(
                    {"check": "assess-notes.py",
                     "where": f"Ch{r['chapter']:02d}",
                     "coord": f"[^{r['slug']}]",
                     "what": f"{fd['pile']}: {fd['why']} — {fd['sentence'][:140]}"},
                    ensure_ascii=False))
        sys.exit(1 if any(r["findings"] for r in rs) else 0)

    if only:
        print(f"\n  Chapter {only:02d} — {len(rs)} note(s)\n")
        for r in rs:
            print(f"    [^{r['slug']}]  {r['words']} words  {r['verdict']}"
                  f"  (words also in its paragraph: {int(r['note_words_in_body']*100)}%)")
            for fd in r["findings"]:
                print(f"        {fd['pile']:<10} {fd['why']}")
                print(f"        > {fd['sentence'][:150]}")
            if r["findings"]:
                print()
        return

    # ── THE SCOPE ────────────────────────────────────────────────────────────
    total = len(rs)
    byv = Counter(r["verdict"] for r in rs)
    over = sum(1 for r in rs if r["over_cap"])
    clean_over = sum(1 for r in rs if r["over_cap"] and r["verdict"] == "CLEAN")
    bad_under = sum(1 for r in rs
                    if not r["over_cap"] and r["verdict"] != "CLEAN")
    piles = Counter()
    for r in rs:
        for fd in r["findings"]:
            piles[fd["pile"]] += 1

    print(f"\n  {total} footnote definitions in {len(set(r['chapter'] for r in rs))} "
          f"chapters.\n")
    print("  BY VERDICT")
    for v, n in byv.most_common():
        print(f"    {n:>5}  {v}")
    print("\n  SENTENCES THAT ARE NOT CITATIONS")
    for pl, n in piles.most_common():
        print(f"    {n:>5}  {pl}")
    print("\n  THE CAP IS THE WRONG INSTRUMENT, AND HERE IS THE NUMBER")
    print(f"    {over:>5}  notes over the {CAP}-word cap")
    print(f"    {clean_over:>5}  of those are CLEAN — the cap flagged them and they are "
          f"citations")
    print(f"    {bad_under:>5}  notes UNDER the cap hold content, repetition or a "
          f"judgement")
    print("\n  CHAPTERS, BY NOTES NEEDING WORK")
    per = defaultdict(lambda: [0, 0])
    for r in rs:
        per[r["chapter"]][0] += 1
        if r["verdict"] != "CLEAN":
            per[r["chapter"]][1] += 1
    for ch, (n, bad) in sorted(per.items(), key=lambda kv: -kv[1][1])[:12]:
        print(f"    Ch{ch:02d}   {bad:>3} of {n:>3} notes   "
              f"{int(100*bad/n) if n else 0}%")
    print()


if __name__ == "__main__":
    main()

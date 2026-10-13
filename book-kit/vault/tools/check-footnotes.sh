#!/usr/bin/env python3
"""check-footnotes.sh — check footnote structure: orphans, unanchored or doubled notes, self-talk, verdicts, length.

    tools/check-footnotes.sh 5            # one chapter
    tools/check-footnotes.sh --all        # every chapter and appendix
    tools/check-footnotes.sh 5 --json     # one JSON line per finding, for a register
    FOOTNOTE_CAP=200 tools/check-footnotes.sh 5     # a different length cap

Mechanical detection only. Every hit is a coordinate, not a verdict. Written in
the original system after a chapter pass found two faults no existing count
could see.

THE STANDARD
    A footnote holds who said it and where; the words the body relies on if
    the body has not given them; and one clause where a reader following the
    citation would otherwise land in the wrong place or read the wrong words.
    Nothing else.

    NAVIGATION, NOT EVALUATION. A note says where the thing is. It never says
    how much to believe it (class J), and it never asserts the source's
    authority or access (class I): that warrant goes in the BODY, or nowhere.

THE CLASSES
    A ORPHAN       a paragraph after the notes that is not indented renders as
                   body text, not as part of a note. Fails a lock.
    B UNMARKED     a quotation in the body with no note on it.
    C LENGTH       a note over the cap (FOOTNOTE_CAP, default 150 words).
    D SELF-TALK    a note discussing its own making, or printing a vault path.
    E XREF         a note pointing at another note by its slug.
    F FULL-CITE    the same work cited in full more than once in a chapter.
    G NO-DEF       a marker in the body with no definition. Fails a lock.
    G NO-ANCHOR    a definition no marker in the body points at. Fails a lock.
    G DUP-DEF      one slug defined twice: the reader sees only one of them.
                   Fails a lock.
    H DUPLICATE    a note repeating the body sentence it is anchored to.
    I WARRANT      a note asserting a source's authority or access.
    J VERDICT      a note telling the reader how much to believe a source.
    K THESIS       a note saying what a book is about rather than where.

WHAT THIS SCRIPT CANNOT SEE, AND THE QUESTION TO ASK BEFORE USING IT
    Everything here looks DOWN from a note to the sentence that anchors it:
    "the job of a footnote is fixed by the sentence that anchors it, and by
    nothing else."

    That is not the only question. The author: "What job is the paragraph
    doing?" That one looks UP, from the paragraph to what the chapter is
    arguing, and no check in this file can answer it. In the original book a
    224-word note tripped only the length class; its source argued something
    the chapter never claims, and since the note and its paragraph named the
    same person, nothing else tripped.

    So: say what job the paragraph does, from the chapter, BEFORE reading the
    note. If the source does not bear on that job, the fault is placement, and
    trimming cannot fix it.
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402
import notelib          # noqa: E402

CAP = int(os.environ.get("FOOTNOTE_CAP", "150"))

# THE BLOCK-ID COMMENT IS NOT PROSE, AND IT WAS BEING COUNTED. `<!-- b:xxxxxx -->`
# renders to nothing, but split() counted it as TWO WORDS, so every note
# measured two words heavier than it is. In the original book a note trimmed to
# 149 words, approved and applied, was then reported at 151 against a cap of 150.
_BID = notelib.BID

SLUG = re.compile(r'\[\^([^\]]+)\]')


def _vault_dirs():
    """Folder names a note must never print as a path: the vault's own folders."""
    names = {"Working Drafts"}
    for p in (B.CHAPTERS, B.APPENDICES, B.FACT, B.METHODOLOGY, B.HANDOFFS):
        try:
            names.add(p.relative_to(B.VAULT).parts[0])
        except (ValueError, IndexError):
            pass
    for r in B.LIBRARY_ROOTS:
        names.add(r.name)
    return sorted(n for n in names if n)


# D — SELF-TALK. A note a reader meets is no place for a note to the editor.
SELFTALK = [
    r'\bthis note\b', r'\bis used here\b', r'\bappears here as\b', r'\bthe body follows\b',
    r'\bthe body gives\b', r'\bquoted in the body\b', r'\bI have not (established|checked|read)\b',
    r'\bhas not been read here\b', r'\brecorded here\b', r'\bso nobody\b', r'\bfor reuse\b',
    r'\bwants (checking|corroboration|pinning)\b', r'\*\*Open:', r'\bPENDING\b',
    r'\bbefore lock\b', r'/Volumes/', r'/Users/', r'/home/', r'\blocal (copy|library)\b',
    r'\bthis (session|run)\b', r'\bnot offered again\b', r'\bread in full\b', r'\bgiven whole here\b',
    # Vault paths. A note that closed "Transcripts in the vault at
    # `Transcripts/`" addressed whoever is editing, in a note a reader meets, and
    # /Volumes/ was the only path shape the list could see.
    r'\bin the vault\b', r'\bon file with the author\b', r'`[^`]*/`',
    r'\b(' + "|".join(re.escape(d) for d in _vault_dirs()) + r')/',
]

# I — WARRANT. The note asserts the source's authority or access.
#
# The author, on a note recording that a writer was given access to sealed
# papers: "Why is [the] permission in the footnote?" That access is the reason
# the body's claim stands. A reason belongs where the claim is: a note never
# asserts a source's authority or access; the warrant goes in the BODY, or nowhere.
WARRANT = [
    r'\b(given|granted|had|with|denied|enjoyed) (unrestricted |privileged |full |direct |sole |exclusive )?access\b',
    r'\baccess to the (sealed|closed|restricted|private|unpublished)\b',
    r'\b(permission|authoris|authoriz)\w* (of|from|by|to (publish|quote|consult))\b',
    r'\b(gave|granted|withheld|refused) (him|her|them|his|the) permission\b',
    r'\bthe (first|only) (scholar|historian|writer|researcher|journalist) (to|who|with)\b',
    r'\bworked (from|with) the (family|estate|archive)\b',
    r'\bwrote with access\b', r'\bhad the (clearance|files|papers|documents) (himself|herself)\b',
    r'\b(Ph\.?D|LL\.?D|Litt\.?D|D\.?Phil)\b', r'\bprofessor of\b', r'\bchair (of|in) \w+ at\b',
    r'\b(Legion of Honour|Order of the Crown|decorated by)\b',
    r'\bcredentials\b', r'\bhis standing as\b',
]

# J — VERDICT. The note tells the reader how much to believe it, or gives an
# account of what the source concludes and why; that is the body's work.
#
# What this must NOT flag: a misprinted title, a stale edition, a variant text,
# an unclosed chain, a locator the source itself gets wrong. Those route a
# reader. They stay.
VERDICT = [
    r'\bstands as a\b', r'\bevidentiary\b', r'\bwell[- ]supported\b', r'\bpoorly supported\b',
    r'\bcarries (more|less|little|no) weight\b', r'\bshould be (treated|read|taken) as\b',
    r'\b(is|remains|are) (credible|convincing|persuasive|plausible|speculative|unreliable|reliable|authoritative|definitive|discredited)\b',
    r'\bholds? (the|his|her|this) (thesis|claim|argument) to\b',
    r'\bthe (strongest|weakest|best|thinnest) (case|evidence|version)\b',
    r'\bdoes not meet\b', r'\bfails to (establish|show|prove)\b',
    r'\b(a|the) documented hypothesis\b',
    r'\b(argues|contends|concludes|maintains|reasons|infers|surmises|posits) that\b',
    r'\bon (his|her|their|this) (account|reading|interpretation|view)\b',
    r'\b(interpretation|interprets|interpreted|his reading of|her reading of)\b',
    r'\bthe reason (he|she|they)\b', r'\bbecause (he|she|they) (believed|thought|held)\b',
    r'\b(rightly|wrongly|correctly|mistakenly) (says|writes|notes|argues|concludes)\b',
]

# K — THESIS SUMMARY. The note gives an account of what the book is about.
#
# The author: "These all need to go, in the whole book, and this has to be
# part of the footnote agent sweep. I don't know how many times I need to
# repeat this."
#
# DISTINCT FROM J. Class J catches a note telling the reader how much to
# believe a source. Class K catches a note telling the reader WHAT THE BOOK
# ARGUES, with no verdict language at all, so J never fires. These notes read
# as a helpful summary, and they survive because they are under the word cap
# and so were never opened by passes that cleaned the long ones.
#
# WHAT THIS MUST NOT FLAG: a locator sentence with a verb of the same family in
# it. "Paine gives the argument in the section on monarchy" routes a reader to
# a place. It stays. The tell of a class K hit is a sentence ABOUT the work
# with no page, chapter or section in it.
THESIS = [
    r"\b\w+'s (polemical|scholarly|academic|revisionist|standard|definitive|magisterial|seminal|foundational|landmark)\b",
    r'\b(his|her|their|the) \w+ (history|study|analysis|account|treatment|thesis|work) (traces|treats|situates|frames|presents|advances|develops|reconstructs|covers|explores|examines)\b',
    r'\b(analysis|treatment|account|study|scholarship|school) (treats|traces|situates|frames|presents|posits)\b',
    r'\bas the (prototype|model|origin|template|paradigm|forerunner|blueprint) (for|of)\b',
    r'\bthe (standard|leading|definitive|foundational|authoritative) (recent )?(academic |scholarly |modern )?(treatment|study|account|work|source)\b',
    r'\b(scholarly|institutional|academic|documentary|evidentiary)[- ](institutional[- ])?anchor\b',
    r'\bcross[- ]reference \w+ for\b',
    r'\b\w+[- ]school (analysis|reading|account|view|interpretation|treatment)\b',
    r'\b(is|are|remains) the chapter\'s\b',
    r'\bthe chapter\'s (twin )?(diagnostic|analytic) point',
]

QUOTE_SPAN = re.compile(r'“([^”]{1,600})”|"([^"]{1,600})"')


def _is_body(l):
    return bool(l.strip()) and not l.startswith('[^') and not l.startswith('#') \
        and not l.startswith('---') and not l.startswith('**Section')


def _shingles(s, k=6):
    w = re.findall(r"[a-z0-9']+", s.lower())
    return {tuple(w[i:i + k]) for i in range(len(w) - k + 1)}


def _slug(l):
    return SLUG.match(l).group(1)


def analyse(text, cap=CAP):
    """Everything this check knows about one file's text, as a dict.

    Keys: lines, notes, body, findings [(class, where, detail)], carved_short,
    carved_near, note_words, body_words.
    """
    lines = [_BID.sub("", l) for l in text.split('\n')]
    notes = [l for l in lines if l.startswith('[^')]
    body = [l for l in lines if l and not l.startswith('[^') and not l.startswith('#')
            and not l.startswith('---') and not l.startswith('**Section')]
    findings = []

    # A — ORPHANED PARAGRAPHS. A footnote's continuation must be indented, or
    # it renders as body text. Invisible to every other count.
    seen_def = False
    for i, l in enumerate(lines, 1):
        if re.match(r'^\[\^[^\]]+\]:', l):
            seen_def = True
            continue
        if not l.strip():
            continue
        if seen_def and not (l.startswith(' ') or l.startswith('\t') or l.startswith('[^')):
            findings.append(("A ORPHAN", f"L{i}", "renders as BODY TEXT, not as a note: " + l[:70]))

    # B — QUOTATION WITH NO MARKER. Two carve-outs, both added after a chapter
    # returned three hits and all three were false:
    #   1. SHORT SPAN: fewer than four words inside the marks is a scare quote
    #      or a named category, not a quotation of a source.
    #   2. ADJACENT ANCHOR: the citation is on the body paragraph immediately
    #      before or after. One anchor serves one source across a passage.
    # The second is a guess this script cannot check: it does not read the
    # neighbouring note. So both carve-outs are counted and the totals printed.
    # Nothing is hidden without saying how much was hidden.
    def neighbour_anchored(idx):
        for step in (-1, 1):
            j = idx + step
            while 0 <= j < len(lines):
                if lines[j].startswith('[^'):
                    break
                if _is_body(lines[j]):
                    if SLUG.search(lines[j]):
                        return True
                    break
                j += step
        return False

    carved_short = carved_near = 0
    for i, l in enumerate(lines, 1):
        if not _is_body(l) or SLUG.search(l):
            continue
        spans = [m.group(1) or m.group(2) or "" for m in QUOTE_SPAN.finditer(l)]
        if not spans:
            continue
        if max(len(s.split()) for s in spans) < 4:
            carved_short += 1
            continue
        if neighbour_anchored(i - 1):
            carved_near += 1
            continue
        findings.append(("B UNMARKED", f"L{i}", l[:70]))

    # C — LENGTH
    for l in notes:
        w = len(l.split())
        if w > cap:
            findings.append(("C LENGTH", f"[^{_slug(l)}]", f"{w} words (cap {cap})"))

    # D, I, J, K — patterns in the note text.
    for cls, pats, width, first_only in (("D SELF-TALK", SELFTALK, 30, False),
                                         ("I WARRANT", WARRANT, 40, True),
                                         ("J VERDICT", VERDICT, 40, True),
                                         ("K THESIS", THESIS, 40, True)):
        for l in notes:
            for pat in pats:
                m = re.search(pat, l, re.I)
                if m:
                    s = max(0, m.start() - width)
                    findings.append((cls, f"[^{_slug(l)}]", "…" + l[s:m.end() + width] + "…"))
                    if first_only:
                        break

    # H — DUPLICATION. The note repeats what its own body span already says.
    # Six-word shingles, so it catches restatement and not merely shared
    # vocabulary. The fix is almost always subtraction from the NOTE: the body
    # keeps the argument, the note keeps the citation.
    for l in body:
        for m in SLUG.finditer(l):
            slug = m.group(1)
            note = next((n for n in notes if n.startswith(f"[^{slug}]:")), None)
            if not note or len(note.split()) < 80:
                continue
            prev = 0
            for mm in SLUG.finditer(l):
                if mm.start() >= m.start():
                    break
                prev = mm.end()
            a, b = _shingles(l[prev:m.start()]), _shingles(note)
            if not a or not b:
                continue
            ov = len(a & b) / len(a)
            if ov > 0.18:
                findings.append(("H DUPLICATE", f"[^{slug}]",
                                 f"repeats {ov*100:.0f}% of its own body span "
                                 f"({len(note.split())} words)"))

    # E — FOOTNOTE CROSS-REFERENCE. A note pointing at another note.
    for l in notes:
        slug = _slug(l)
        for m in SLUG.finditer(l[len(slug) + 4:]):
            findings.append(("E XREF", f"[^{slug}]", f"points at [^{m.group(1)}]"))

    # F — REPEATED FULL CITATION. Same author and title with a publisher block
    # more than once in a chapter: short form after the first appearance.
    cites = {}
    for l in notes:
        slug = _slug(l)
        for m in re.finditer(r'([A-Z][A-Za-z.\'\- ]+?), \*([^*]{6,70})\*\s*\(', l):
            key = (m.group(1).split()[-1], m.group(2)[:28])
            cites.setdefault(key, []).append(slug)
    for key, where in cites.items():
        if len(where) > 1:
            findings.append(("F FULL-CITE x%d" % len(where), key[0],
                             f"*{key[1]}…* full in " + ", ".join(f"[^{w}]" for w in where)))

    # G — MISSING, UNANCHORED AND DOUBLED DEFINITIONS
    anch = set(SLUG.findall("\n".join(body)))
    def_slugs = [_slug(l) for l in notes if re.match(r'^\[\^[^\]]+\]:', l)]
    defs = set(def_slugs)
    for s in sorted(anch - defs):
        findings.append(("G NO-DEF", f"[^{s}]", "anchored, never defined"))
    for s in sorted(defs - anch):
        findings.append(("G NO-ANCHOR", f"[^{s}]", "defined, never anchored"))
    # Two definitions under one slug: the renderer keeps one and the reader
    # never sees the other, so a citation can vanish without a trace.
    for s in sorted({s for s in def_slugs if def_slugs.count(s) > 1}):
        findings.append(("G DUP-DEF", f"[^{s}]", f"defined {def_slugs.count(s)} times"))

    return {"lines": lines, "notes": notes, "body": body, "findings": findings,
            "carved_short": carved_short, "carved_near": carved_near,
            "note_words": sum(len(l.split()) for l in notes),
            "body_words": sum(len(l.split()) for l in body)}


def span_for_anchor(text, pos, slug):
    """Everything the note is answerable for: from the end of the previous
    anchor in this paragraph (or the start of the paragraph if there is none)
    up to and including its own anchor.

    The author: "Search the whole paragraph, or back to a previous note." A
    note placed at the end of a run of five sentences is answerable for all
    five; the reader met no other marker in between. Showing only the final
    sentence understates the job and invites a trim that strips evidence.

    Returns (span_text, words, from_where).
    """
    prev_end = 0
    from_where = "from the start of the paragraph"
    for m in SLUG.finditer(text):
        if m.start() >= pos:
            break
        prev_end = m.end()
        from_where = f"since {m.group(0)}"
    end = pos + len(f"[^{slug}]")
    span = re.sub(r'\s+', ' ', text[prev_end:end]).strip()
    return span, len(span.split()), from_where


def claims_in(text):
    """The checkable things a passage asserts: quotations, named people, works, dates.

    WHY THIS IS NOT A WORD COUNT. The author: "you are using a
    programmatic/numerical heuristic rather than a contextual one." A ratio of
    note words to span words says a note is big. It cannot say whether the
    note answers the span. A 140-word note that leaves a quotation unsourced is
    worse than a 300-word note that sources six. So this pulls out what the
    span asserts that a reader could dispute, and the report says which of
    those the note accounts for. Still mechanical, and still a coordinate, but
    a coordinate on the CLAIMS rather than on the length.
    """
    out = {}
    quotes = [a or b for a, b in re.findall(r'"([^"]{12,200})"|“([^”]{12,200})”', text)]
    if quotes:
        out["quotation"] = quotes
    titles = re.findall(r'\*([A-Z][^*]{4,80})\*', text)
    if titles:
        out["work"] = titles
    # PEOPLE, not capitalised phrases. Allowing "of/the/and" as connectors
    # matched place and document names: noise that would send a reader hunting
    # for a source for a phrase nobody asserted. A person is Firstname [M.]
    # [Middle] Lastname and nothing else.
    names = re.findall(
        r'\b([A-Z][a-z]{2,}(?:\s+[A-Z]\.?)*(?:\s+[A-Z][a-z]{2,}){1,2})\b', text)
    stop = {"The", "This", "That", "These", "Those", "By", "In", "On", "At",
            "After", "Before", "When", "Most", "Some", "Both", "Each"}
    names = [n for n in names
             if n.split()[0] not in stop and " of " not in n and " and " not in n
             and " the " not in n]
    if names:
        out["name"] = names
    dates = re.findall(r'\b(?:1[0-9]{3}|20[0-9]{2})\b', text)
    if dates:
        out["date"] = dates
    return out


def report(path, cap=CAP, as_json=False):
    """Print the findings for one file. Returns the findings list."""
    name = Path(path).name
    a = analyse(Path(path).read_text(encoding='utf-8'), cap)
    lines, notes, findings = a["lines"], a["notes"], a["findings"]
    if not notes:
        return []
    # STRUCTURED FINDINGS, SO A REGISTER NEVER HAS TO PARSE THIS PROSE. A
    # register built on a regex over another tool's prose once reported 2
    # findings where there were 44.
    if as_json:
        n = B.chapter_number(path)
        for kind, where, detail in findings:
            json.dump({"check": "check-footnotes.sh", "where": name,
                       "coord": (f"Ch{n:02d} " if n else "") + where,
                       "class": kind, "what": f"{kind} — {detail}"},
                      sys.stdout, ensure_ascii=False)
            sys.stdout.write("\n")
        return findings

    nw, bw = a["note_words"], a["body_words"]
    body_lines = [(i, l) for i, l in enumerate(lines, 1) if _is_body(l)]
    body_all = " ".join(l for _, l in body_lines).lower()

    def body_line_of(key):
        for i, l in body_lines:
            if key in l.lower():
                return i
        return None

    ratio = (nw * 100 // bw) if bw else 0
    flag = "  <-- the notes are longer than the body" if nw > bw else ""
    print(f"\n{name}")
    print(f"  notes {len(notes)}   note words {nw}   body words {bw}   ratio {ratio}%{flag}")
    print(f"  longest {max(len(l.split()) for l in notes)}   mean {nw // len(notes)}   "
          f"over cap {sum(1 for l in notes if len(l.split()) > cap)}")
    if a["carved_short"] or a["carved_near"]:
        print(f"  B carve-outs: {a['carved_short']} quotation(s) under four words, "
              f"{a['carved_near']} anchored on an adjacent paragraph (not read, not verified)")
    if not findings:
        print("  no findings")
        return findings
    print()
    for kind, where, detail in findings:
        print(f"    {kind:16} {where:24} {detail}")
    print(f"\n  {len(findings)} finding(s). A and G fail a lock. B, C, D, E, F, H, I, J, K are "
          "coordinates — read before ruling.\n  I and J are the navigation test. A note says WHERE "
          "the thing is. It never says how much to believe it, and it\n  never asserts the "
          "source's authority or access: that warrant goes in the BODY, or nowhere.")

    # ── THE JOB OF EACH FLAGGED NOTE ─────────────────────────────────────────
    #
    # Added after a single note was trimmed four times in one sitting and grew
    # twice, because nobody had said what it was for. True, interesting facts
    # were added and removed, none of which the body claimed. The author ended
    # it with one question: "What is the job of this footnote?"
    #
    # The job of a footnote is fixed by the sentence that anchors it. A note is
    # too long when it holds something its own sentence does not claim. So the
    # scanner prints that sentence BEFORE any trim can be proposed.
    flagged = []
    for _, where, _ in findings:
        m = re.match(r'\[\^([^\]]+)\]', where)
        if m and m.group(1) not in flagged:
            flagged.append(m.group(1))
    if not flagged:
        return findings
    print("\n  THE JOB OF EACH FLAGGED NOTE — the claim it exists to source.")
    print("  Nothing is cut, added or reworded until this has been read.")
    print("  FIRST, AND THIS SCRIPT CANNOT CHECK IT: say what job the PARAGRAPH")
    print("  does in the section's argument, from the chapter. If the note's")
    print("  source does not bear on that job, the fault is placement, not length.")
    print("  FIRST QUESTION ON EVERY NOTE: is there anything in it that")
    print("  belongs in the BODY? Cut / keep / promote — three outcomes.\n")
    for slug in flagged:
        job = None
        for i, l in enumerate(lines, 1):
            if l.startswith('[^') or not l.strip():
                continue
            p = l.find(f"[^{slug}]")
            if p != -1:
                job = (i,) + span_for_anchor(l, p, slug)
                break
        if not job:
            print(f"    [^{slug}]  NO ANCHOR IN THE BODY — it has no job. "
                  f"Anchor it or cut it; do not trim it.\n")
            continue
        ln, span, words, whence = job
        note_text = next((n for n in notes if n.startswith(f"[^{slug}]:")), "")
        print(f"    [^{slug}]  anchored at L{ln} — covers {words} words "
              f"of body, {whence}; the note is {len(note_text.split())} words")
        shown = span if len(span) <= 900 else span[:450] + "  […]  " + span[-450:]
        print(f"        {shown}\n")

        claims = claims_in(span)
        if not claims:
            continue
        nl = note_text.lower()
        for kind, items in claims.items():
            missing = [it for it in dict.fromkeys(items) if it.lower()[:40] not in nl]
            if missing:
                show = "; ".join(m[:56] for m in missing[:5])
                more = f" (+{len(missing)-5})" if len(missing) > 5 else ""
                print(f"        {kind.upper()+' NOT IN THE NOTE:':<26} {show}{more}")
        # Compare titles on their main title only: the body cites a short
        # title, the note gives the full one with its subtitle.
        span_l = span.lower()
        unasked = [t for t in claims_in(note_text).get("work", [])
                   if t.split(":")[0].strip().lower() not in span_l]
        if unasked:
            print(f"        {'WORKS THE SPAN NEVER ASKS FOR:':<26} "
                  f"{'; '.join(u[:56] for u in unasked[:6])}"
                  f"{f' (+{len(unasked)-6})' if len(unasked) > 6 else ''}")

        # ── BELONGS IN THE BODY? ──────────────────────────────────────────
        # The question the author asks of every long note: "is there anything
        # in the note which should be in the body? We need to address that
        # every time." A trim has THREE outcomes: cut it, keep it in the note,
        # or MOVE IT TO THE BODY. The drafter skipped the third by default, so
        # the check names the candidates. Quotations come first: a primary
        # source's own words in a note whose span paraphrases them is a rule
        # violation, not a style choice.
        #
        # Three outcomes, and the middle one is the trap:
        #   absent from the span AND from the chapter -> a candidate
        #   absent from the span, PRESENT elsewhere    -> ALREADY THERE
        #   present in the span                        -> nothing to do
        # The question is chapter-wide. A span-local answer once proposed
        # promoting a quotation the chapter already gave 24 lines further on.
        note_claims = claims_in(note_text)
        promote, elsewhere = {}, {}
        for kind in ("quotation", "date", "name"):
            got = []
            for it in dict.fromkeys(note_claims.get(kind, [])):
                key = it.lower()[:40]
                if key in span_l:
                    continue
                if key in body_all:
                    elsewhere.setdefault(kind, []).append((it, body_line_of(key)))
                else:
                    got.append(it)
            if got:
                promote[kind] = got
        if promote:
            print(f"        {'BELONGS IN THE BODY?':<26} "
                  f"in the note, absent from the WHOLE chapter body —")
            for kind, items in promote.items():
                show = "; ".join(i[:64] for i in items[:4])
                more = f" (+{len(items)-4})" if len(items) > 4 else ""
                print(f"        {'  ' + kind + ':':<26} {show}{more}")
            if "quotation" in promote:
                print(f"        {'':<26} a quotation here whose span "
                      f"paraphrases it must move; do not trim around it.")
        if elsewhere:
            print(f"        {'ALREADY IN THE BODY:':<26} "
                  f"do NOT promote — the chapter gives this elsewhere")
            for kind, items in elsewhere.items():
                show = "; ".join(f"{i[:48]} (L{n})" if n else i[:48] for i, n in items[:4])
                more = f" (+{len(items)-4})" if len(items) > 4 else ""
                print(f"        {'  ' + kind + ':':<26} {show}{more}")
        print()
    return findings


def main():
    args = sys.argv[1:]
    as_json = "--json" in args
    rest = [a for a in args if a != "--json"]
    if "--all" in rest:
        files = list(B.chapter_files())
        if B.APPENDICES.is_dir():
            files += sorted(p for p in B.APPENDICES.glob("*.md") if not B.is_backup(p))
    elif rest and rest[0].isdigit():
        f = B.chapter_file(int(rest[0]))
        if not f:
            print(f"no chapter {int(rest[0]):02d}")
            return 1
        files = [f]
    else:
        print("usage: tools/check-footnotes.sh NN | --all  [--json]   (env FOOTNOTE_CAP, default 150)")
        return 1
    for f in files:
        report(f, CAP, as_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())

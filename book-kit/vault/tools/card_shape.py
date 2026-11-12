#!/usr/bin/env python3
"""card_shape.py — the checks on a card's shape that tools/cards.py runs as a version goes in.

    python3 tools/card_shape.py <card id>     # every finding on the card as it stands now

Each check below is one rule from the system this kit comes from, kept as the author gave it there. Each is a gate in
book.toml [gates], "warn" (the writer is told, the card goes in) or "refuse" (nothing is written); every gate starts
at warn and goes to refuse on the author's ok to a sample (Methodology/UAT Log.md).

    card_pointer      a body line or note that points the reader to another part of this book ("in Chapter 7",
                      "Part Five", "Appendix B", "the next chapter", "as we will see in"). The author: "Putting it
                      in the log doesn't fix it if no one is checking that log."
    card_overlap      a NEW card whose paragraph, or a note anchored in it, another open card already works. Two
                      open cards on one paragraph ask the author to rule on the same line twice. Fold it into
                      that card, or queue it behind (`queuedBehind`).
    card_format_only  a card whose words are its current lines' words, case, punctuation, spacing and note numbers
                      aside, does not go to the author's desk ("I do not need cards for every minor formatting
                      change"). Its writer writes it at "approved" with `reopenedBy` "format-only".
    card_summary      a card for the desk opens with `tldr` (two or three plain sentences), `recommendation` (one
                      sentence) and `subject` (what the paragraph is about), and gives `changeList`: every change
                      as {before, after, why}. "There are no reasons given ... Fix this, and fix the system."
    card_choices      a card that offers two or more `choices` gives, in one `changeList` entry, an option for each
                      ({label, reason, after}), so the desk shows each choice's own words; and carries no change
                      that goes in the same under every choice (that change goes on a card of its own: one
                      decision, one press).
    card_answer       a card written after the author's directive or edits carries `answer`: {"his": his words,
                      quoted, "answer": the answer in full}. The desk shows it first, above the proposal.
"""
import json
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import bookconfig as B  # noqa: E402

SEP = "\n\n⁂\n\n"
IDRE = re.compile(r"<!--\s*b:([a-z0-9]{6})\s*-->")
BID = re.compile(r"(?:\bblock\s+|\bb:)([a-z0-9]{6})\b")
NOTE_DEF = re.compile(r"^\s*\[\^([^\]]+)\]:")
POINTER_EXEMPT = TOOLS / "card_pointer_exempt.jsonl"


def words(t):
    return re.findall(r"[^\W_]+", str(t or "").lower())


def sentences(t):
    return [s for s in re.split(r"(?<=[.!?])\s+", str(t or "").strip()) if s.strip()]


def para(card):
    return str(card.get("reviewedPara") or card.get("proposedPara") or "")


def note(card):
    return "" if card.get("noteless") else str(card.get("reviewedNote") or card.get("proposedNote") or "")


# ---- card_pointer ------------------------------------------------------------------------------------------------
NUM = r"(?:One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|[IVX]+|\d+)"
POINTER = re.compile(
    r"\b(?:[Ii]n|[Tt]o|[Ss]ee|[Ff]rom|[Aa]t|[Oo]f|[Uu]nder)\s+(?:Part\s+" + NUM + r"|Chapters?\s+\d+(?:['’]s)?|"
    r"Appendix\s+[A-Z]\b|Appendices\s+[A-Z])"
    r"|\b(?:[Tt]he\s+)?(?:next|previous|last|earlier|later|following|preceding|coming)\s+(?:chapter|part)s?\b"
    r"|\b(?:[Aa]s\s+)?we\s+(?:will|shall)\s+see\s+in\b|\b[Aa]s\s+we\s+saw\s+in\b"
    r"|\b(?:see|cf\.)\s+(?:note|n\.)\s*\d+\b", re.I)
# "Part I, sec. V", "Chapter 2 of *Title*": a part of a source, not of this book
SOURCE_PART = re.compile(r"^\s*(?:,\s*(?:sec|ch|bk|vol)\.|\s+of\s+[*_\"“])")


def _pointer_exempt():
    out = []
    try:
        for l in POINTER_EXEMPT.read_text(encoding="utf-8").splitlines():
            try:
                o = json.loads(l)
            except ValueError:
                continue
            if o.get("context") and o.get("reason") and o.get("by"):
                out.append(o["context"])
    except OSError:
        pass
    return out


def _masked(line):
    t = re.sub(r"<!--.*?-->", lambda m: " " * len(m.group(0)), line)
    return re.sub(r'"[^"\n]{0,600}"|“[^”\n]{0,600}”', lambda m: " " * len(m.group(0)), t)


def pointers(text):
    """[the pointer with the words around it] in body text and notes, quotations and comments set aside.
    `tools/card_pointer_exempt.jsonl` lets one place stand, one JSON object per line: {context, reason, by}, where
    `by` is the author's ruling that keeps it."""
    out, ex = [], _pointer_exempt()
    for line in str(text or "").replace(SEP, "\n").split("\n"):
        if line.lstrip().startswith("#") or any(c in line for c in ex):
            continue
        m_ = _masked(NOTE_DEF.sub(lambda m: " " * len(m.group(0)), line))
        for m in POINTER.finditer(m_):
            if SOURCE_PART.match(line[m.end():m.end() + 40]):
                continue
            out.append(line[max(0, m.start() - 50):m.end() + 30].strip())
    return out


def card_pointers(card):
    """The pointers in what the author would approve, outside lines the card leaves as the chapter has them."""
    cur = {re.sub(r"\s+", " ", IDRE.sub("", str(c.get("text") or ""))).strip()
           for c in card.get("current") or [] if isinstance(c, dict)}
    text = para(card) + (SEP + note(card) if note(card).strip() else "")
    keep = [s for s in text.split(SEP) if re.sub(r"\s+", " ", IDRE.sub("", s)).strip() not in cur]
    return pointers(SEP.join(keep))


# ---- card_format_only --------------------------------------------------------------------------------------------
COORD = re.compile(r"\bCh\s?\d+\s*/\s*L\d+\b|\bL\d+(?:[–-]L?\d+)?\b|\[\^\d+\]")


def bare_words(text):
    t = COORD.sub(" ", re.sub(r"<!--.*?-->", " ", str(text or "")))
    return re.findall(r"[^\W_]+", t)


def _quoted_words(text):
    t = re.sub(r"<!--.*?-->", " ", str(text or ""))
    return [w for q in re.findall(r"\"([^\"\n]*)\"|“([^”\n]*)”", t) for w in bare_words(q[0] or q[1])]


def format_only(card):
    """(True, why) when the card changes only case, punctuation, spacing, or line and note numbers; else (False, why).
    A capital changed inside a quotation is a change to the source's words, and does not qualify. A hyphen that joins
    or splits a word changes the word."""
    old = " ".join(str(c.get("text") or "") for c in card.get("current") or [] if isinstance(c, dict))
    new = " ".join(para(card).split(SEP)) + (" " + note(card) if note(card).strip() else "")
    if not old.strip() or not new.strip():
        return False, "the card shows no current text, or proposes none"
    if re.sub(r"\s+", " ", old).strip() == re.sub(r"\s+", " ", new).strip():
        return False, "the card changes nothing"
    a, b = bare_words(old), bare_words(new)
    if [w.lower() for w in a] != [w.lower() for w in b]:
        return False, "it changes a word"
    if a != b and _quoted_words(old) != _quoted_words(new):
        return False, "a capital changes inside a quotation, and a quotation's words are the source's"
    return True, "the same words in the same order; only case, punctuation, spacing or line and note numbers change"


# ---- card_overlap ------------------------------------------------------------------------------------------------
def _norm(s):
    return re.sub(r"\s+", " ", IDRE.sub("", str(s or ""))).strip()


def changed_blocks(card):
    """The block ids of the current lines the card changes (a line the proposal keeps word for word is no change)."""
    new = _norm(" ".join(para(card).split(SEP)) + " " + note(card))
    out = set()
    for c in card.get("current") or []:
        if isinstance(c, dict) and _norm(c.get("text")) and _norm(c.get("text")) not in new:
            out |= set(BID.findall(str(c.get("where") or "")))
    return out


_CH = {}


def _chapter_lines(card):
    m = re.search(r"\d+", str(card.get("chapter") or ""))
    if not m:
        return []
    n = int(m.group(0))
    if n not in _CH:
        try:
            import card_refresh
            _CH[n] = [t for _n, t, _nd in card_refresh._lines(n)]
        except Exception:  # noqa: BLE001  no chapter on disk: the family is the card's own blocks
            _CH[n] = []
    return _CH[n]


def family(card):
    """The paragraphs a card works on: the blocks it changes, and for each note it changes, every body line that
    carries that note's marker. Two open cards whose families meet are one card."""
    out = set(changed_blocks(card))
    slugs = set()
    for c in card.get("current") or []:
        if isinstance(c, dict):
            m = NOTE_DEF.match(str(c.get("text") or ""))
            if m and set(BID.findall(str(c.get("where") or ""))) & out:
                slugs.add(m.group(1))
    for seg in para(card).split(SEP) + [note(card)]:
        m = NOTE_DEF.match(seg)
        if m:
            slugs.add(m.group(1))
    for sl in slugs:
        mark = f"[^{sl}]"
        for l in _chapter_lines(card):
            if mark in l and not l.lstrip().startswith(mark + ":"):
                out |= set(IDRE.findall(l))
    return out


def collisions(card_id, card, open_cards):
    """[(other id, its status, [shared block ids])] for each other open card whose family meets this card's."""
    mine = family(card)
    if not mine:
        return []
    out = []
    for oid, (o, st) in open_cards.items():
        if oid != card_id:
            both = mine & family(o)
            if both:
                out.append((oid, st, sorted(both)))
    return out


# ---- card_summary ------------------------------------------------------------------------------------------------
ROLE = re.compile(r"\b(?:the )?(?:Editor|Fact-checker|Fact Checker|Production|Managing Editor|Systems|QA)\b")


def summary_faults(record):
    bad = []
    if not 2 <= len(sentences(record.get("tldr"))) <= 3:
        bad.append("`tldr` gives the card in two or three plain sentences")
    if len(sentences(record.get("recommendation"))) != 1:
        bad.append("`recommendation` gives the press recommended, in one sentence")
    if ROLE.search(str(record.get("tldr") or "") + " " + str(record.get("recommendation") or "")):
        bad.append("`tldr` and `recommendation` name no role; they say what the card does")
    if not str(record.get("subject") or "").strip():
        bad.append("`subject` says in one line what the paragraph is about")
    cl = record.get("changeList")
    if not (isinstance(cl, list) and cl):
        bad.append("`changeList` gives each change as {before, after, why}")
    else:
        for i, c in enumerate(cl, 1):
            if not isinstance(c, dict) or not str(c.get("why") or "").strip():
                bad.append(f"change {i} in `changeList` has no `why`")
            elif c.get("before") in (None,) and c.get("after") in (None,):
                bad.append(f"change {i} in `changeList` gives neither `before` nor `after`")
            for o in (c.get("choices") or []) if isinstance(c, dict) else []:
                if isinstance(o, dict) and not str(o.get("label") or "").strip():
                    bad.append(f"an option in change {i} has no `label`, the one line on what it does")
    return bad


# ---- card_choices ------------------------------------------------------------------------------------------------
def choices_of(record):
    return [c if isinstance(c, dict) else {"text": str(c)} for c in record.get("choices") or [] if c]


def choices_faults(record):
    chs = choices_of(record)
    if len(chs) < 2:
        return []
    bad = []
    norm = lambda t: " ".join(words(t))
    shown = False
    for e in record.get("changeList") or []:
        if not isinstance(e, dict):
            continue
        afters = [norm((o or {}).get("after")) for o in e.get("choices") or [] if isinstance(o, dict)]
        if len(afters) >= len(chs) and all(afters) and len(set(afters)) == len(afters):
            shown = True
    if not shown:
        bad.append(f"the card offers {len(chs)} choices, and no `changeList` entry carries an option for each, each "
                   f"with its own `after`; the desk would show one proposed text and {len(chs)} buttons")
    shared = [e for e in record.get("changeList") or []
              if isinstance(e, dict) and not e.get("choices") and norm(e.get("before")) != norm(e.get("after"))]
    if shared:
        bad.append(f"{len(shared)} change(s) go in the same under every choice: move them to a card of their own, so "
                   f"each press rules on one decision (" + "; ".join(f"“{str(e.get('after') or '')[:80]}”" for e in shared) + ")")
    return bad


def choice_book_text(record, n):
    """The proposed paragraph as choice `n` (1-based) writes it: each changeList entry's option n put in place of the
    entry's own `after`. The text the author's "Approve choice n" approves."""
    text = para(record)
    for e in record.get("changeList") or []:
        if not isinstance(e, dict):
            continue
        opts = [o for o in e.get("choices") or [] if isinstance(o, dict)]
        if len(opts) >= n and e.get("after") and opts[n - 1].get("after") and e["after"] in text:
            text = text.replace(e["after"], opts[n - 1]["after"], 1)
    return text


# ---- card_answer -------------------------------------------------------------------------------------------------
def answer_fault(record, directive):
    """Why the card does not answer the author's open directive at the top, or ''."""
    if not directive:
        return ""
    flat = lambda t: re.sub(r"[\s\"“”‘’'*_]+", " ", str(t or "")).strip().lower()
    a = record.get("answer") if isinstance(record.get("answer"), dict) else {}
    want = flat(directive.get("text"))[:60]
    if want and want in flat(a.get("his")) and len(str(a.get("answer") or "").strip()) >= 20:
        return ""
    return (f"this version answers the author's {directive.get('decision_kind')} of "
            f"{str(directive.get('ts', ''))[:16]}: “{str(directive.get('text') or '')[:160]}”. Give the card `answer`: "
            f"{{\"his\": his words, quoted whole, \"answer\": the answer in full}}; the desk shows it first")


def main(argv):
    import cards
    if not argv:
        print(__doc__)
        return 2
    c = cards.fold().get(argv[0])
    if c is None:
        print(f"no card {argv[0]!r}")
        return 2
    out = [("card_pointer", p) for p in card_pointers(c)]
    ok, why = format_only(c)
    if ok:
        out.append(("card_format_only", why))
    out += [("card_summary", f) for f in summary_faults(c)]
    out += [("card_choices", f) for f in choices_faults(c)]
    f = answer_fault(c, cards.open_directive(argv[0]))
    if f:
        out.append(("card_answer", f))
    for k, f in out:
        print(f"{k:<17} {f}")
    print(f"\n{len(out)} finding(s) on {argv[0]}.")
    return 1 if out else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

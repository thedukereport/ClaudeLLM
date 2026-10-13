"""check-card-notes.py — no card reaches the author with a footnote the author's rules send back.

    tools/check-card-notes.py                 # every card on the page snapshot; exit 1 if any is refused
    tools/check-card-notes.py --json          # one object per card that proposes a footnote
    tools/check-card-notes.py --card F.json   # one card document, before it is written to the page
    tools/check-card-notes.py --patch-dir D   # also write D/<card id>.json = {"noteCheck": {...}}
                                              # for each card checked, to merge into the card on the page

THE PAGE'S HALF OF THE GATE

    The Source Rulings page holds a card that proposes a footnote when its
    `noteCheck` failed, when its text changed after the check, or when it was
    written after the page's note-gate time with no check (`noteGateFrom` in
    the page's `config` document; page function `noteHeld()`, called by
    `stage()`). A held card shows under "With Claude" with the findings and no
    Approve button. So the card-writing step is: build the card, run this with
    --card, merge its noteCheck into the card, write the card.

WHOSE RULES THESE ARE

    The author's: "Wire the note check into the Source Rulings page so every
    card's note is checked before it reaches me." A note navigates; it does
    not argue. The rules are the piles `assess-notes.py` sorts a note's
    sentences into (CITATION, WARNING, REPEATS, CONTENT, JUDGEMENT), the rule against saying a thing twice (a note does not repeat what
    its paragraph already says), and the author's per-note rulings
    (`note.ruled` events).

    The older note sorter tests a locator before a quotation, so a clause
    holding a page AND a quotation the paragraph already says passed as a
    citation. That is how a note repeating its paragraph reached the author
    once. This tool tests the quotation first.

WHAT IT DOES, PER CARD

    1. Finds each footnote definition the card proposes: the segments of the
       text the author would approve (`reviewedPara`, else `proposedPara`)
       that begin `[^slug]:`, and `proposedNote` on a card that has a note box.
    2. Finds the anchoring paragraph: the card's own proposed segment holding
       `[^slug]`, and the chapter line on disk holding it.
    3. Splits the note into sentences (`check-note-content.sentences`, which
       protects abbreviations and quotations) and each sentence into clauses at
       semicolons outside quotation marks, and sorts each clause into the
       piles with `assess-notes.classify` — after one test that sorter makes
       second: a quotation in the clause is tested BEFORE its locator.
         - quotation whose words the anchor prints (> 85%)        REPEATS
         - quotation the anchor says in its own words (>= 45%)    REPEATS
       The 45% line comes from the author's ruling that a note's quotation
       repeated its paragraph "in its own words": that quotation scored 50%,
       the nearest quotation below it (a work's title) 40%, the nearest above
       92%. Re-measure on your own cards before moving it.
    4. REFUSES the card on any REPEATS or JUDGEMENT clause, and on CONTENT when
       the card changes no body paragraph (nowhere for the content to go).
    5. Reads the author's last `note.ruled` for the chapter and slug
       (retractions excluded) and REFUSES a card that contradicts it:
         citations_only  and the note proposes anything but citations/warnings
         promote         and the card changes no body paragraph
         no_change       and the note differs from the chapter's note on disk
       An `instruct` ruling is printed with the finding for the reader; it
       refuses nothing by itself.

    A clause holding a citation is reported with its pile, never cut: this
    tool edits nothing, anywhere. Chapters listed in book.toml [workflow]
    out_of_workflow are skipped. Applied cards are skipped.
"""
import importlib.util, json, re, sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import bookconfig as B  # noqa: E402
import cardlib as C  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


cnc = _load("cnc", TOOLS / "check-note-content.py")
an = _load("assess_notes", TOOLS / "assess-notes.py")

SEP = "\n\n⁂\n\n"
NOTE = re.compile(r"^\[\^([A-Za-z0-9_\-]+)\]:\s*(.*)$", re.S)
MARK = re.compile(r"\s*<!-- b:[0-9a-f]+ -->\s*$")
OUT_OF_WORKFLOW = B.OUT_OF_WORKFLOW
FAULT = ("REPEATS", "JUDGEMENT")
PARAPHRASE = 0.45


def clauses(sentence):
    out, cur, inq = [], "", False
    for ch in sentence:
        if ch in "\"“”":
            inq = not inq if ch == '"' else (ch == "“")
        if ch == ";" and not inq:
            out.append(cur); cur = ""
        else:
            cur += ch
    out.append(cur)
    return [c.strip() for c in out if c.strip()]


CHTITLE = re.compile(r"\b(?:chs?\.|chapters?|part|section|essay|article)\s+[IVXLC0-9]+[a-z]?,?\s*$", re.I)
CHAPTER_ON = re.compile(r"\bthe (?:chapter|section|essay|article) (?:on|titled|called|headed)\b", re.I)


def _is_title(cl, q):
    """A quoted chapter or article title is a citation, however its words fall.
    A note that quotes a work's chapter titles after "ch. II," once read as a
    quotation the body repeats."""
    if cnc.titlecased(q):
        return True
    i = cl.find(q)
    return i > 0 and bool(CHTITLE.search(cl[:i].rstrip("\"“'‘ ")))


def sort_clause(cl, anchor_words, anchor_text):
    # "the chapter on *Some Title*" points at a chapter of a cited work; the
    # THESIS pattern in assess-notes reads it as a sentence about this book.
    if CHAPTER_ON.search(cl) and cnc.TITLE.search(cl):
        return "CITATION", "points at a chapter of a named work", None
    runs = [q for q in cnc.quoted_runs(cl) if len(an.words(q)) > 6 and not _is_title(cl, q)]
    if runs:
        q = max(runs, key=lambda x: len(an.words(x)))
        ov = an.overlap(q, anchor_words)
        if ov > 0.85:
            return "REPEATS", "the anchor paragraph prints these words already", ov
        if ov >= PARAPHRASE:
            return "REPEATS", "the anchor paragraph says this in its own words", ov
    pile, why = an.classify(cl, anchor_words, anchor_text)
    return pile, why, None


def last_rulings():
    import vaultlog
    out = {}
    for e in vaultlog.fold("note.ruled"):
        out[(int(e.get("chapter") or 0), e.get("slug"))] = e
    return out


def chapter_text(ch):
    f = B.chapter_file(ch)
    return (f.read_text(encoding="utf-8") if f else ""), f


def line_of(text, pred):
    for i, l in enumerate(text.split("\n"), 1):
        if pred(l):
            return i
    return 0


def check_card(cid, card, rulings):
    ch = C.chapter_of(card)
    if ch is None or ch in OUT_OF_WORKFLOW or card.get("status") == "applied":
        return None
    text = card.get("reviewedPara") or card.get("proposedPara") or ""
    segs = text.split(SEP) if text else []
    notes, body = [], []
    for s in segs:
        m = NOTE.match(s.strip())
        (notes.append((m.group(1), m.group(2).strip())) if m else body.append(s))
    pn = (card.get("reviewedNote") or card.get("proposedNote") or "").strip()
    if pn and not card.get("noteless"):
        m = NOTE.match(pn)
        notes.append((m.group(1), m.group(2).strip()) if m else ("?", pn))
    if not notes:
        return None
    chtext, chfile = chapter_text(ch)
    findings = []
    for slug, note in notes:
        anchor_card = [b for b in body if f"[^{slug}]" in b]
        anchor_disk = [MARK.sub("", l) for l in chtext.split("\n")
                       if f"[^{slug}]" in l and not l.startswith(f"[^{slug}]:")]
        anchor_text = " ".join(anchor_card + anchor_disk)
        anchor_words = set(an.words(anchor_text))
        ln = line_of(chtext, lambda l: l.startswith(f"[^{slug}]:"))
        where = f"Ch{ch:02d}/L{ln}" if ln else f"Ch{ch:02d} (new note)"
        piles = []
        for s in cnc.sentences(note):
            for cl in clauses(s.strip()):
                if len(cl.split()) < 4:
                    continue
                pile, why, ov = sort_clause(cl, anchor_words, anchor_text)
                piles.append(pile)
                refuse = pile in FAULT or (pile == "CONTENT" and not body)
                if refuse:
                    findings.append({"slug": slug, "where": where, "pile": pile, "why": why
                                     + (f" ({ov:.0%} of the quotation's words)" if ov is not None else "")
                                     + ("; the card changes no body paragraph to hold it" if pile == "CONTENT" else ""),
                                     "clause": cl, "cites": bool(cnc.LOCATOR.search(cl))})
        r = rulings.get((ch, slug))
        if r:
            k, said = r.get("note_kind"), (r.get("text") or "").strip()
            disk = MARK.sub("", next((l for l in chtext.split("\n") if l.startswith(f"[^{slug}]:")), ""))
            disk_note = NOTE.match(disk).group(2).strip() if NOTE.match(disk) else ""
            bad = None
            if k == "citations_only" and any(p not in ("CITATION", "WARNING") for p in piles):
                bad = "you ruled this note citations only; the card proposes more than citations"
            elif k == "promote" and not body:
                bad = "you ruled promote; the card changes no body paragraph"
            elif k == "no_change" and disk_note and re.sub(r"\s+", " ", disk_note) != re.sub(r"\s+", " ", note):
                bad = "you ruled leave it; the card changes the note"
            if bad:
                findings.append({"slug": slug, "where": where, "pile": "RULING", "why": bad
                                 + f" (your ruling {r.get('ts','')[:10]}" + (f': "{said}"' if said else "") + ")",
                                 "clause": "", "cites": False})
    if not findings:
        return {"card": cid, "title": C.norm(card.get("title")), "status": card.get("status"), "ok": True, "findings": [], "text": text}
    return {"card": cid, "title": C.norm(card.get("title")), "status": card.get("status"), "ok": False, "findings": findings, "text": text}


def main(argv):
    as_json = "--json" in argv
    rulings = last_rulings()
    if "--card" in argv:
        p = Path(argv[argv.index("--card") + 1])
        d = json.loads(p.read_text(encoding="utf-8")); d = d.get("data", d)
        cards = [(p.stem, d)]; taken = None
    else:
        try:
            taken, snap = C.snapshot_cards()
        except FileNotFoundError as e:
            print(f"NOT RUN: {e}"); return 2
        cards = [(c["id"], c) for c in snap]
    results = [r for r in (check_card(cid, c, rulings) for cid, c in cards) if r]
    if "--patch-dir" in argv:
        import datetime
        d = Path(argv[argv.index("--patch-dir") + 1]); d.mkdir(parents=True, exist_ok=True)
        at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        for r in results:
            (d / f"{r['card']}.json").write_text(json.dumps({"noteCheck": {
                "ok": r["ok"], "at": at, "text": r["text"], "tool": "tools/check-card-notes.py",
                "findings": r["findings"]}}, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = [r for r in results if not r["ok"]]
    if as_json:
        for r in results:
            print(json.dumps({k: v for k, v in r.items() if k != "text"}, ensure_ascii=False))
    else:
        if taken:
            skipped = ", ".join(str(n) for n in sorted(OUT_OF_WORKFLOW)) or "none"
            print(f"Page snapshot taken {taken.isoformat(timespec='minutes')}; {len(results)} cards propose a footnote "
                  f"(chapters out of the workflow, skipped: {skipped}).\n")
        for r in bad:
            print(f"REFUSED  {r['title']}  [{r['status']}]")
            for f in r["findings"]:
                print(f"    {f['where']} [^{f['slug']}]  {f['pile']}: {f['why']}")
                if f["clause"]:
                    print(f"      \"{f['clause'][:400]}\"" + ("   (holds a citation: reported, not cut)" if f["cites"] else ""))
            print()
        print(f"{len(bad)} card(s) refused of {len(results)} that propose a footnote.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

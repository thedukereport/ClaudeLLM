"""check-card-closed.py — no card reaches the author on a line or note the author has already approved.

    tools/check-card-closed.py                 # every open card on the page snapshot; exit 1 if any is held
    tools/check-card-closed.py --json          # one object per open card checked
    tools/check-card-closed.py --card F.json   # one card document, before it is written to the page
    tools/check-card-closed.py --patch-dir D   # also write D/<card id>.json = {"closedCheck": {...}}
    tools/check-card-closed.py --page-only     # only the closings the page can see for itself (see TWO KINDS)

WHOSE RULE THIS IS

    The author's, after a new version of an approved card appeared on the
    page: "I have already approved this and put it to bed, and now a new
    version appears. You must find the issue. Ad hoc break/fix is not working
    for me." And the standing rule that followed: "If something has been 1)
    read, 2) fact-checked, 3) approved, and 4) logged in the fact-checking
    documentation, do not open it again, ever." And: "wire it so no card can
    reach the page on a line or note I have already approved."

    The fault: nothing compared a new card's targets with the lines the
    author had approved. In the system this kit comes from, the Editor put
    five new cards or versions on approved lines in one evening.

WHAT COUNTS AS A LINE THE AUTHOR HAS APPROVED (THE CLOSED SET)

    From the page (the page can see these itself and holds the card live):
      1. every card with status approved or applied: the paragraphs and notes
         it changes;
      2. every card the author pressed "Approve for the chapter" on, result
         saved, in the page's presses collection — so a later version written
         over an approved card is caught even when the rewrite reset its
         status. A later saved press of "reopen" or "Withdraw approval" by the
         author lifts it.
    From the event log (Fact Check/events/), which the page cannot read:
      3. each edit.applied that names one of the author's rulings (an item, a
         page card, actor = book.toml [book] author_actor, or "ruled"/"ruling"/
         "approved"/"use my words" in its why) — the block it wrote;
      4. each note.ruled of kind no_change ("leave it"), the author's last per note.

    A target is a block id. A card's targets are its `current` entries, minus
    the ones that only mark where a new line goes ("the new line goes after
    this one"): an explicit "(block xxxxxx)" or "b:xxxxxx" is taken as given,
    otherwise the entry's text is matched to the chapter line on disk with the
    same words (whitespace collapsed, block marker removed) — exact, never
    fuzzy. A footnote named in a non-insert part of `where` or `current[].where`
    is a target by chapter and slug, and so is a note definition `[^slug]:`
    the card proposes for a note already in the chapter.

WHAT IT DOES

    Holds (exit 1) any card whose status is not approved or applied and whose
    targets meet the closed set. It prints the card's title, each closed target
    as Ch##/L## now, and what closed it in words the author can check: the
    card title and date, or the item and the author's ruling, or the note
    ruling.

    The ways past, both the author's own act: the card names in `reopenedBy`
    the hash of a decision.recorded event of the author's (actor author_actor)
    dated after every closing it meets; or the author pressed "Reopen this
    line" on the card in the page's "Reopen?" lane, which saves
    `lineReopenedAt` and `lineReopenText` (the text the author saw), dated
    after every closing, on a card whose text is still that text. A new
    version written over that text is held again.

TWO KINDS, AND WHY THE PAGE HOLDS ONLY THE FIRST BY ITSELF

    The page's `closedHeld()` computes kinds 1 and 2 from the cards and presses
    it already loads, so a card the Editor writes without running this tool is
    still held. Kinds 3 and 4 reach the page only as the `closedCheck` this
    tool writes with --patch-dir; writing those to the page is a bulk write and
    waits for the author's "ok" on a sample (Methodology/UAT Log.md).

    This tool edits nothing anywhere; --patch-dir writes files to D only.
    Chapters listed in book.toml [workflow] out_of_workflow are skipped.
"""
import collections
import datetime
import json
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import bookconfig as B  # noqa: E402
import blocks  # noqa: E402
import cardlib as C  # noqa: E402

SEP = "\n\n⁂\n\n"
BID = re.compile(r"(?:\bblock\s+|\bb:)([0-9a-f]{6})\b")
SLUG = re.compile(r"\[\^([A-Za-z0-9_\-]+)\]")
NOTEDEF = re.compile(r"^\s*\[\^([A-Za-z0-9_\-]+)\]:")
INSERT = re.compile(r"goes? after|go after|^\s*after\b|new lines? go|between L\d+", re.I)
RULED = re.compile(r"ruled|ruling|approved|use my words|the author's words|the author's own words", re.I)
OUT_OF_WORKFLOW = B.OUT_OF_WORKFLOW
AUTHOR = B.AUTHOR_ACTOR
CLOSED_STATUS = ("approved", "applied")


def norm(s):
    return re.sub(r"\s+", " ", blocks.IDRE.sub("", s or "")).strip()


def chnum(s):
    m = re.search(r"Ch\s*0*(\d+)", str(s or ""))
    return int(m.group(1)) if m else None


class Book:
    """The chapters on disk: block id -> Block, words -> [ids], (ch, slug) -> note block id."""
    def __init__(self):
        self.idx = blocks.index()
        self.bytext = collections.defaultdict(list)
        self.note = {}
        for b in self.idx.values():
            self.bytext[b.text].append(b.id)
            m = NOTEDEF.match(b.text)
            if m:
                self.note[(int(b.chapter[2:]), m.group(1))] = b.id

    def coord(self, bid):
        b = self.idx.get(bid)
        return b.coord if b else f"block {bid} (not in the book now)"


def card_targets(card, book, closing=False):
    """Block ids this card changes. closing=True adds what an approved card's text became."""
    ch = C.chapter_of(card)
    out = set()
    for cur in card.get("current") or []:
        w = cur.get("where", "") or ""
        if INSERT.search(w):
            continue
        ids = BID.findall(w)
        if ids:
            out.update(ids)
        else:
            out.update(book.bytext.get(norm(cur.get("text")), []))
        for s in SLUG.findall(w):
            if ch and (ch, s) in book.note:
                out.add(book.note[(ch, s)])
    for part in re.split(r";", card.get("where", "") or ""):
        if INSERT.search(part) or "new [^" in part:
            continue
        out.update(BID.findall(part))
        for s in SLUG.findall(part):
            c = chnum(part) or ch
            if c and (c, s) in book.note:
                out.add(book.note[(c, s)])
    text = card.get("reviewedPara") or card.get("proposedPara") or ""
    for seg in text.split(SEP) if text else []:
        m = NOTEDEF.match(seg)
        if m and ch and (ch, m.group(1)) in book.note:
            out.add(book.note[(ch, m.group(1))])
        if closing:
            out.update(book.bytext.get(norm(seg), []))
    return {b for b in out if b}


def load_presses():
    d = C.SNAPSHOT / "presses"
    out = []
    for p in sorted(d.glob("*.json")) if d.exists() else []:
        x = json.loads(p.read_text(encoding="utf-8")); x = x.get("data", x)
        out.append(x)
    return sorted(out, key=lambda x: x.get("at", ""))


def approved_by_press(presses):
    """card id -> the saved approve press still standing (no later saved reopen or withdraw)."""
    st = {}
    for x in presses:
        if x.get("result") != "saved":
            continue
        a, c = x.get("action"), x.get("card")
        if a == "approve":
            st[c] = x
        elif a in ("reopen", "withdraw"):
            st.pop(c, None)
    return st


def closed_set(cards, book, page_only=False):
    """block id -> [reason dict], each {kind, at, said, source}."""
    closed = collections.defaultdict(list)
    byid = {c["id"]: c for c in cards}
    applied_by_item = collections.defaultdict(set)
    events = []
    if not page_only:
        import vaultlog
        events = list(vaultlog.fold("edit.applied"))
    for e in events:
        b = e.get("block") or e.get("block_id")
        if b and e.get("item"):
            applied_by_item[str(e["item"])].add(b)
    pressed = approved_by_press(load_presses())
    for c in cards:
        ch = C.chapter_of(c)
        st = c.get("status")
        press = pressed.get(c["id"])
        if st not in CLOSED_STATUS and not press:
            continue
        if st in CLOSED_STATUS:
            at = c.get("appliedAt") if st == "applied" else c.get("approvedAt")
            said = f'you approved the card "{C.norm(c.get("title"))}"' + (" and it is in the book" if st == "applied" else "")
        else:
            at = press.get("at")
            said = (f'you pressed Approve on the card "{C.norm(c.get("title"))}"; '
                    f"the card on the page now is a later version written over that approval")
        for b in card_targets(c, book, closing=True) | applied_by_item.get(c["id"], set()):
            closed[b].append({"kind": "page", "at": at or "", "said": said, "source": c["id"]})
    if page_only:
        return closed
    seen_edit = set()
    for e in events:
        b = e.get("block") or e.get("block_id")
        if not b or (b, e.get("ts")) in seen_edit:
            continue  # one apply can be logged twice, once by each writer that saw it
        seen_edit.add((b, e.get("ts")))
        why = e.get("why") or ""
        if "Source Rulings" in why:
            continue  # a page card: kind 1 already holds it, with its title
        sheet, item = e.get("sheet"), e.get("item")
        if not (item or e.get("actor") == AUTHOR or RULED.search(why)):
            continue
        if sheet == "Source Rulings" or (item and str(item) in byid):
            continue  # a page card: kind 1 already holds it, with its title
        where = f"{sheet} item {item}" if sheet and item else (f"item {item}" if item else "a chapter line")
        closed[b].append({"kind": "log", "at": e.get("ts", ""), "source": e.get("hash", ""),
                          "said": f"your ruling on {where}, applied {e.get('ts','')[:10]}: {why[:160]}"})
    last = {}
    for e in vaultlog.fold("note.ruled"):
        last[(int(e.get("chapter") or 0), e.get("slug"))] = e
    for (ch, slug), e in last.items():
        if e.get("note_kind") == "no_change" and (ch, slug) in book.note:
            closed[book.note[(ch, slug)]].append({"kind": "log", "at": e.get("ts", ""), "source": e.get("hash", ""),
                                                  "said": f"your note ruling \"leave it\" on [^{slug}], {e.get('ts','')[:10]}"})
    return closed


def his_reopening(h):
    if not h:
        return None
    import vaultlog
    for e in vaultlog.fold("decision.recorded"):
        if e.get("hash") == h and e.get("actor") == AUTHOR:
            return e
    return None


def check_card(cid, card, book, closed):
    ch = C.chapter_of(card)
    if ch is None or ch in OUT_OF_WORKFLOW or card.get("status") in CLOSED_STATUS:
        return None
    reopen = his_reopening(card.get("reopenedBy"))
    seen_text = card.get("reviewedPara") or card.get("proposedPara") or ""
    if not reopen and card.get("lineReopenedAt") and card.get("lineReopenText") == seen_text:
        reopen = {"ts": card["lineReopenedAt"]}   # the author's press in the Reopen? lane
    findings = []
    for b in sorted(card_targets(card, book), key=lambda x: (book.idx[x].line if x in book.idx else 0)):
        why = [r for r in closed.get(b, []) if r["source"] != cid or r["kind"] == "page"]
        if not why:
            continue
        if reopen and all(reopen.get("ts", "") > (r["at"] or "") for r in why):
            continue
        seen, uniq = set(), []
        for r in why:
            if r["said"] not in seen:
                seen.add(r["said"]); uniq.append(r)
        findings.append({"where": book.coord(b), "block": b, "closedBy": uniq})
    text = (card.get("reviewedPara") or card.get("proposedPara") or "") + "\n" + (card.get("reviewedNote") or card.get("proposedNote") or "")
    return {"card": cid, "title": C.norm(card.get("title")), "status": card.get("status"),
            "ok": not findings, "findings": findings, "reopenedBy": card.get("reopenedBy") or "",
            "text": card.get("reviewedPara") or card.get("proposedPara") or "", "_all": text}


def main(argv):
    as_json = "--json" in argv
    page_only = "--page-only" in argv
    book = Book()
    try:
        taken, snap = C.snapshot_cards()
    except FileNotFoundError as e:
        print(f"NOT RUN: {e}"); return 2
    if "--card" in argv:
        p = Path(argv[argv.index("--card") + 1])
        d = json.loads(p.read_text(encoding="utf-8")); d = dict(d.get("data", d))
        cid = d.get("id") or p.stem.split(".")[0]
        cards = [(cid, d)]
    else:
        cards = [(c["id"], c) for c in snap]
    closed = closed_set(snap, book, page_only)
    results = [r for r in (check_card(cid, c, book, closed) for cid, c in cards) if r]
    if "--patch-dir" in argv:
        d = Path(argv[argv.index("--patch-dir") + 1]); d.mkdir(parents=True, exist_ok=True)
        at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        for r in results:
            (d / f"{r['card']}.json").write_text(json.dumps({"closedCheck": {
                "ok": r["ok"], "at": at, "text": r["text"], "tool": "tools/check-card-closed.py",
                "reopenedBy": r["reopenedBy"],
                "findings": [{"where": f["where"], "why": "; ".join(x["said"] for x in f["closedBy"])} for f in r["findings"]]}},
                ensure_ascii=False, indent=1), encoding="utf-8")
    held = [r for r in results if not r["ok"]]
    if as_json:
        for r in results:
            print(json.dumps({k: v for k, v in r.items() if k not in ("text", "_all")}, ensure_ascii=False))
    else:
        skipped = ", ".join(str(n) for n in sorted(OUT_OF_WORKFLOW)) or "none"
        print(f"Page snapshot taken {taken.isoformat(timespec='minutes')}; {len(results)} open card(s) checked"
              f"{' (page closings only)' if page_only else ''}; chapters out of the workflow, skipped: {skipped}.\n")
        for r in held:
            print(f"HELD  {r['title']}  [{r['status']}]")
            for f in r["findings"]:
                print(f"    {f['where']} — you have already approved this line:")
                for x in f["closedBy"]:
                    print(f"      · {x['said']}" + (f" ({x['at'][:16].replace('T', ' ')} UTC)" if x['at'] and x['kind'] == 'page' and "in the book" not in x['said'] else ""))
            print()
        print(f"{len(held)} card(s) held of {len(results)} open card(s) checked.")
    return 1 if held else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

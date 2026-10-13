#!/usr/bin/env python3
"""apply-card.py — Production applies one approved card from the page snapshot to its chapter.

    tools/apply-card.py CARD_ID            # dry run: prints Current and Proposed in full, writes nothing
    tools/apply-card.py CARD_ID --write    # applies the card, writes the ledger's apply entry
    tools/apply-card.py path/to/card.json  # a card document instead of an id

    CARD_ID is the card's document id on the Source Rulings page; the card is
    read from `<page snapshot>/proposals/<CARD_ID>.json` (book.toml [paths]
    page_snapshot).

WHAT IT DOES

    The card's text is `reviewedPara` (the text Claude checked and the author
    approved), split into segments at the page's separator (a line holding
    only ⁂), plus `reviewedNote` when the card has a note box. Segment k pairs
    with the card's `current[k]`:

      - `current[k].where` names a block ("(block a1b2c3)" or "b:a1b2c3"): that
        block is the target. Otherwise the target is the chapter line whose
        words equal `current[k].text` (whitespace collapsed, block marker
        removed) — exactly one line, or the card is refused.
      - `current[k].where` says the new line goes after this one ("goes
        after", "new line goes", ...): the segment is a NEW line, inserted after
        that block through `blockedit.insert_after`, which mints its id.
      - otherwise the segment replaces the target through
        `blockedit.replace`, which keeps the block id.
      - a segment with no `current` entry must be a footnote definition
        `[^slug]:`. It replaces the chapter's definition of that slug, or, when
        the chapter has none, goes in after the chapter's last footnote.

    Then it writes an apply entry at the end of the chapter's ledger, reads
    back every line it wrote, and prints the patch for the card on the page
    (status applied), which Claude writes with ArtifactData.

IT REFUSES THE WHOLE CARD, AND WRITES NOTHING, WHEN

    - any `current` entry's text differs from the chapter on disk (the chapter
      changed under the card: show the author both, never overwrite newer words);
    - the chapter is locked in `Fact Check/Locks.md` (🔒). The order is
      unlock, edit, relock, push, and reopening a locked chapter is the
      author's decision;
    - the chapter is in book.toml [workflow] out_of_workflow;
    - (--write only) the card's status is not approved, its text differs from
      the text Claude checked, the snapshot is over 24 hours old, or the
      chapter has no single ledger.

WHY

    The author approves a card on the page; the change reaches the chapter
    only when somebody applies it. Every chapter write goes through
    `blockedit`, which owns the block id: in the system this kit comes from,
    text pasted into a chapter without its id left the block index, and a
    stale card once put a superseded paragraph back beside the corrected one.
    Comparing the card's `current` text with the disk before writing is what
    stops a stale card. The dry run shows the whole Current and Proposed
    because a summary or an ellipsis is how a wrong edit looks acceptable.
"""
import datetime
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402
import cardlib as C  # noqa: E402
import blocks  # noqa: E402

TOOL = "tools/apply-card.py"
SEP = "\n\n⁂\n\n"
BID = re.compile(r"(?:\bblock\s+|\bb:)([0-9a-f]{6})\b")
INSERT = re.compile(r"goes? after|go after|^\s*after\b|new lines? go|between L\d+", re.I)
NOTEDEF = re.compile(r"^\s*\[\^([A-Za-z0-9_\-]+)\]:")
MAX_AGE_H = 24
LOCKED, UNLOCKED = "🔒", "🔓"


def norm(s):
    return re.sub(r"\s+", " ", blocks.IDRE.sub("", s or "")).strip()


def lock_state(ch):
    """('🔒' | '🔓' | '', the row) for a chapter, from Fact Check/Locks.md.
    The table is | chapter | state | date | by | note |; the last row for a
    chapter is its state."""
    if not B.LOCKS.exists():
        return "", ""
    state, row = "", ""
    for line in B.LOCKS.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        m = re.search(r"\d+", cells[0])
        if not m or int(m.group(0)) != ch:
            continue
        if LOCKED in cells[1]:
            state, row = LOCKED, line.strip()
        elif UNLOCKED in cells[1]:
            state, row = UNLOCKED, line.strip()
    return state, row


def load(arg):
    p = Path(arg)
    if p.suffix == ".json" and p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        d = dict(d.get("data", d))
        return d.get("id") or p.stem, d, None
    f = C.SNAPSHOT / "proposals" / f"{arg}.json"
    if not f.exists():
        raise SystemExit(f"REFUSED: no card {arg!r} in {C.rel(C.SNAPSHOT)}/proposals/. "
                         f"Take a fresh snapshot of the page, or check the id.")
    d = json.loads(f.read_text(encoding="utf-8"))
    return arg, dict(d.get("data", d)), C.snapshot_taken()


def plan(cid, card):
    """(changes, refusals, notes). Each change: dict(kind, seg, block, anchor, old, new, label)."""
    refusals, notes, changes = [], [], []
    ch = C.chapter_of(card)
    if ch is None:
        return [], ["the card names no chapter"], notes
    if ch in B.OUT_OF_WORKFLOW:
        refusals.append(f"Chapter {ch} is out of the workflow (book.toml [workflow] out_of_workflow)")
    st, row = lock_state(ch)
    if st == LOCKED:
        refusals.append(f"Chapter {ch} is locked in {C.rel(B.LOCKS)}: {row}. Unlocking it is the "
                        f"author's decision; then `tools/lock.py unlock {ch:02d}`, apply, relock.")
    para = card.get("reviewedPara") or card.get("proposedPara") or ""
    note = "" if card.get("noteless") else (card.get("reviewedNote") or card.get("proposedNote") or "").strip()
    segs = [s for s in (para.split(SEP) if para.strip() else [])]
    if note:
        segs.append(note)
    if not segs:
        return [], refusals + ["the card proposes no text"], notes
    idx = blocks.index(rebuild=True)
    chapter_blocks = sorted((b for b in idx.values() if b.chapter == f"Ch{ch:02d}"), key=lambda b: b.line)
    if not chapter_blocks:
        refusals.append(f"Chapter {ch} has no block ids. Run tools/blockid.py first; "
                        f"blockedit writes only to a line that holds its id.")
        return [], refusals, notes
    current = [c for c in (card.get("current") or []) if isinstance(c, dict)]

    def target(cur, k):
        """The block current[k] names, checked against the disk. A block that
        already holds the card's text for it counts as applied, never as drift:
        a second run of an applied card changes nothing and refuses nothing."""
        w = cur.get("where", "") or ""
        seg = segs[k] if k < len(segs) and not INSERT.search(w) else None
        ids = BID.findall(w)
        if ids:
            b = idx.get(ids[0])
            if b is None:
                refusals.append(f"current[{k}] names block {ids[0]}, which is in no chapter now")
                return None
        else:
            hits = [b for b in chapter_blocks if b.text == norm(cur.get("text"))]
            if not hits and seg is not None:
                hits = [b for b in chapter_blocks if b.text == norm(seg)]
            if len(hits) != 1:
                refusals.append(f"current[{k}] ({w or 'no where'}): {len(hits)} lines in Chapter {ch} "
                                f"hold its text; exactly one must. The chapter changed under the card, "
                                f"or the card quotes it wrong.")
                return None
            b = hits[0]
        if b.chapter != f"Ch{ch:02d}":
            refusals.append(f"current[{k}] names {b.coord}, outside Chapter {ch}")
            return None
        if b.text != norm(cur.get("text")) and not (seg is not None and b.text == norm(seg)):
            refusals.append(f"current[{k}] differs from the chapter on disk at {b.coord} (block {b.id}).\n"
                            f"      THE CARD SAYS:  {norm(cur.get('text'))}\n"
                            f"      THE CHAPTER SAYS: {b.text}")
            return None
        return b

    resolved = [target(c, k) for k, c in enumerate(current)]
    for k, seg in enumerate(segs):
        if k < len(current):
            cur, b = current[k], resolved[k]
            if b is None:
                continue
            if INSERT.search(cur.get("where", "") or ""):
                changes.append({"kind": "insert", "seg": k, "anchor": b, "old": "", "new": seg.strip(),
                                "label": f"a new line after {b.coord} (block {b.id})"})
            elif norm(seg) == b.text:
                notes.append(f"segment {k + 1}: {b.coord} is already this text; nothing to change")
            else:
                changes.append({"kind": "replace", "seg": k, "block": b, "old": b.text, "new": seg.strip(),
                                "label": f"{b.coord} (block {b.id})"})
            continue
        m = NOTEDEF.match(seg)
        if not m:
            refusals.append(f"segment {k + 1} has no current[] entry and is not a footnote definition; "
                            f"which line it changes is not a guess")
            continue
        slug = m.group(1)
        defs = [b for b in chapter_blocks if NOTEDEF.match(b.text) and NOTEDEF.match(b.text).group(1) == slug]
        if len(defs) > 1:
            refusals.append(f"[^{slug}] is defined {len(defs)} times in Chapter {ch}")
        elif defs:
            b = defs[0]
            if norm(seg) == b.text:
                notes.append(f"segment {k + 1}: [^{slug}] at {b.coord} is already this text")
            else:
                changes.append({"kind": "replace", "seg": k, "block": b, "old": b.text, "new": seg.strip(),
                                "label": f"{b.coord} (block {b.id}), the note [^{slug}]"})
        else:
            notedefs = [b for b in chapter_blocks if NOTEDEF.match(b.text)]
            a = (notedefs or chapter_blocks)[-1]
            changes.append({"kind": "insert", "seg": k, "anchor": a, "old": "", "new": seg.strip(),
                            "label": f"the new note [^{slug}], after {a.coord} (block {a.id})"})
    return changes, refusals, notes


def ledger_entry(cid, card, taken, done, day):
    page = "the Source Rulings page" + (f" ({B.PAGE_URL})" if B.PAGE_URL else "")
    src = (f"read from the page snapshot taken {taken.isoformat(timespec='minutes')}" if taken
           else "read from a card file")
    approved = (f"The author approved it {card['approvedAt']}." if card.get("approvedAt")
                else "No approval time is recorded on the card.")
    lines = [f"## {day} — card {cid} applied: {C.norm(card.get('title')) or cid}", "",
             f"Applied by `{TOOL}` from {page}, card `{cid}`, {src}. {approved}", ""]
    for c in done:
        if c["kind"] == "replace":
            lines += [f"- Replaced {c['label']}.", f"  - Before: {c['old']}", f"  - After: {norm(c['new'])}"]
        else:
            nid = c.get("new_id") or "(id minted on write)"
            lines += [f"- Added {c['label']}, block {nid}.", f"  - New: {norm(c['new'])}"]
    rl = C.CARDS / f"{cid}.reads.json"
    if rl.exists():
        try:
            reads = json.loads(rl.read_text(encoding="utf-8")).get("reads") or []
        except json.JSONDecodeError:
            reads = []
        if reads:
            lines.append(f"- Sources the card names (`{C.rel(rl)}`):")
            for r in reads:
                lines.append(f"  - {C.norm(r.get('author'))}, *{C.norm(r.get('title'))}* — "
                             f"{C.norm(r.get('location'))}. For {C.norm(r.get('ref'))}.")
    return "\n".join(lines) + "\n"


def show(changes):
    for i, c in enumerate(changes, 1):
        print("=" * 72)
        if c["kind"] == "replace":
            print(f"[{i}] REPLACE {c['label']}\n")
            print(f"  CURRENT\n  {'-' * 68}\n  {c['old']}\n")
            print(f"  PROPOSED\n  {'-' * 68}\n  {norm(c['new'])}\n")
        else:
            print(f"[{i}] INSERT {c['label']}\n")
            print(f"  AFTER THIS LINE (current)\n  {'-' * 68}\n  {c['anchor'].text}\n")
            print(f"  NEW LINE (proposed)\n  {'-' * 68}\n  {norm(c['new'])}\n")


def main(argv):
    write = "--write" in argv
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        return 2
    cid, card, taken = load(args[0])
    title = C.norm(card.get("title")) or cid
    status = card.get("status", "")
    print(f"CARD {cid} — {title}  [status: {status or 'none'}]")
    if taken:
        age = (datetime.datetime.now(datetime.timezone.utc) - taken).total_seconds() / 3600
        print(f"Page snapshot taken {taken.isoformat(timespec='minutes')}, {age:.1f} hours ago.")
    if status == "applied":
        print("\nREFUSED: this card is already applied. Nothing written.")
        return 1
    changes, refusals, notes = plan(cid, card)
    hold = []
    if status != "approved":
        hold.append(f"the card's status is {status or 'none'}; --write applies only a card the "
                    f"author approved on the page")
    if card.get("reviewedPara") is not None and card.get("proposedPara") is not None \
            and card.get("reviewedPara") != card.get("proposedPara"):
        hold.append("the text in the card's box differs from the text Claude checked "
                    "(proposedPara is not reviewedPara)")
    if not card.get("noteless") and (card.get("reviewedNote") or "") != (card.get("proposedNote") or "") \
            and card.get("reviewedNote") is not None:
        hold.append("the footnote in the card's box differs from the note Claude checked")
    if taken and (datetime.datetime.now(datetime.timezone.utc) - taken).total_seconds() / 3600 > MAX_AGE_H:
        hold.append(f"the snapshot is over {MAX_AGE_H} hours old; the author may have withdrawn the "
                    f"approval since. Read the page again into {C.rel(C.SNAPSHOT)}/")
    ch = C.chapter_of(card)
    ledger = None
    try:
        ledger = C.ledger_file(ch) if ch is not None else None
    except SystemExit as e:
        hold.append(f"the apply entry has nowhere to go: {e}")
    for n in notes:
        print(f"  {n}")
    if refusals:
        print("\nREFUSED, nothing written:")
        for r in refusals:
            print(f"  - {r}")
        return 1
    if not changes:
        print("\nNothing to change: the chapter already holds this card's text.")
        return 0
    print()
    show(changes)
    day = C.today_utc()
    entry = ledger_entry(cid, card, taken, changes, day)
    print("=" * 72)
    print(f"LEDGER ENTRY, appended to {C.rel(ledger) if ledger else '(no ledger)'}\n")
    print("\n".join("  " + l for l in entry.splitlines()))
    print("=" * 72)
    if not write:
        if hold:
            print("\n--write would refuse:\n" + "\n".join(f"  - {h}" for h in hold))
        print(f"\nDRY RUN: {len(changes)} change(s) shown in full; nothing written. "
              f"--write applies them.")
        return 0
    if hold:
        print("\nREFUSED, nothing written:\n" + "\n".join(f"  - {h}" for h in hold))
        return 1

    import blockedit
    import vaultlog
    why = (f'Source Rulings card {cid} "{title}", approved by the author '
           f'{card.get("approvedAt") or ""}; applied by {TOOL}').strip()
    done, last_after = [], {}
    try:
        for c in [x for x in changes if x["kind"] == "replace"]:
            blockedit.replace(c["block"].id, c["new"], why=why, actor=B.AUTHOR_ACTOR,
                              sheet="Source Rulings", item=cid)
            done.append(c)
            print(f"CHANGED  {c['label']}")
        for c in [x for x in changes if x["kind"] == "insert"]:
            after = last_after.get(c["anchor"].id, c["anchor"].id)
            rec = blockedit.insert_after(after, c["new"], why=why, actor=B.AUTHOR_ACTOR,
                                         sheet="Source Rulings", item=cid)
            c["new_id"] = rec.get("block_id", "")
            last_after[c["anchor"].id] = c["new_id"] or after
            done.append(c)
            print(f"ADDED    {c['label']}, block {c['new_id']}")
    except blockedit.Refused as e:
        print(f"\nSTOPPED: blockedit refused a write: {e}")
        print(f"Written before the stop: {len(done)} of {len(changes)}. Each is in the event log "
              f"with its before and after, and the chapter was copied aside before each write.")
        return 1
    entry = ledger_entry(cid, card, taken, done, day)
    before = ledger.read_text(encoding="utf-8")
    sep = "" if before.endswith("\n\n") else ("\n" if before.endswith("\n") else "\n\n")
    vaultlog.write_file(ledger, before + sep + entry, tool=TOOL, why=f"apply entry for card {cid}")
    # Read back: a write is not proof.
    idx = blocks.index(rebuild=True)
    bad = []
    for c in done:
        bid = c["block"].id if c["kind"] == "replace" else c.get("new_id")
        b = idx.get(bid)
        if b is None:
            bad.append(f"block {bid} is not in the chapter after the write")
        elif b.text != norm(c["new"]):
            bad.append(f"{b.coord} (block {bid}) does not hold the proposed text after the write")
    if f"card {cid} applied" not in ledger.read_text(encoding="utf-8"):
        bad.append("the ledger has no apply entry after the write")
    if bad:
        print("\nWRITTEN, BUT THE READ-BACK FAILED:\n  " + "\n  ".join(bad))
        return 1
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    patch = {"status": "applied", "appliedAt": now,
             "appliedNote": f"Applied by {TOOL}; ledger entry in {C.rel(ledger)}."}
    print(f"\nApplied and read back: {len(done)} change(s); ledger entry in {C.rel(ledger)}.")
    print(f"Next: update proposals/{cid} on the page with ArtifactData (action update), data:")
    print(json.dumps(patch, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

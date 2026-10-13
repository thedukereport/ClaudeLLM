#!/usr/bin/env python3
"""card-log.py — put the sources a card names on record, in the turn the card is written.

    tools/card-log.py CARD.reads.json [CARD.reads.json ...]           # sample: writes nothing
    tools/card-log.py --write CARD.reads.json [...]                   # writes

    CARD.reads.json lives in Handoffs/editor-tools/cards/ (book.toml
    [paths] card_reads) and is named for the card's id on the Source Rulings
    page. Its shape is in tools/cardlib.py.

WHAT IT WRITES, FOR EACH READ THE CARD NAMES

    1. A row in `Fact Check/Claims/Ch NN.jsonl`, unless a row with the same
       author, title, location and ref is already there (exact match; the rule
       is stated in cardlib.py). An existing row is never changed.
    2. One section per card in the chapter's ledger, headed with the card id,
       listing each read with its Claims line. Not written twice for one card.
    3. A `source.read` event in `Fact Check/events/`, naming the card id.
       Not written twice for one read of one card.

    Files are written through `vaultlog.write_file`, which logs a
    `file.written` event and copies the old file aside first.

WHY

    The Source Rulings page lies outside every gate a script can run. The
    author's rule: "Every read, every zero, every correction, to Fact
    Check/Claims/Ch NN.jsonl and source.read in the event log. A read that is
    not logged did not happen." In the system this kit comes from, cards that
    said their reads were logged had them in Claims and in neither the ledger
    nor the event log.

THE GATE

    Without --write it prints every change it would make, whole, and writes
    nothing. With --write it refuses more than five changes until
    `Methodology/UAT Log.md` records the author accepting a sample of this
    tool (`uat.py`; "Nothing writes at scale until the author has accepted a
    sample"). Run it twice: the second run must find nothing to do.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cardlib as C  # noqa: E402

TOOL = "tools/card-log.py"


def plan(card: dict, events: list, day: str, pending: dict):
    """The changes this card needs: (claims_rows_to_add, ledger_text_or_None,
    events_to_add, report_lines).

    `pending` holds, per chapter, the rows earlier cards in this same run will
    add, as {key: line}, so two cards in one run never number the same new
    line twice or add one read twice."""
    ch = int(card["chapter"])
    pend = pending.setdefault(ch, {})
    rows, new_rows, report = [], [], []
    for read in card["reads"]:
        hit = C.find_row(ch, read)
        if not hit and C.key(read) in pend:
            hit = (pend[C.key(read)], read)
        rows.append((read, hit[0] if hit else None))
        if hit:
            report.append(f"  already in Claims, line {hit[0]}: "
                          f"{C.norm(read['author'])}, {C.norm(read['title'])}")
        else:
            new_rows.append(read)
            report.append(f"  NEW Claims row: {C.norm(read['author'])}, "
                          f"{C.norm(read['title'])}")
    ledger = None
    have = C.ledger_has_card(ch, card["card"])
    if have:
        report.append(f"  ledger already has: {have}")
    else:
        # A new row's line number is the one it WILL have once appended.
        n = (len(C.claims_file(ch).read_text(encoding="utf-8").splitlines())
             if C.claims_file(ch).exists() else 0) + len(pend)
        numbered = []
        for read, ln in rows:
            if ln is None:
                n += 1
                pend[C.key(read)] = n
                numbered.append((read, n, True))
            else:
                numbered.append((read, ln, False))
        ledger = C.ledger_section(card, day, numbered, card.get("_source", ""))
        report.append(f"  ledger section to add: {C.heading(card, day)}")
    new_events = []
    for read in card["reads"]:
        if C.event_for(events, card["card"], read):
            report.append(f"  event already logged: {C.norm(read['author'])}")
        else:
            new_events.append(read)
    return new_rows, ledger, new_events, report


def claims_row(card: dict, read: dict, day: str) -> dict:
    row = {k: v for k, v in read.items() if not k.startswith("_")}
    row.setdefault("type", "source_states")
    row.setdefault("date_read", day)
    row.setdefault("reader", f"Claude, the Editor, for card {card['card']}")
    row["run_id"] = row.get("run_id") or f"card-{card['card']}"
    row["card"] = card["card"]
    return row


def event_payload(card: dict, read: dict) -> dict:
    p = {k: C.norm(read.get(k)) for k in ("author", "title", "location", "ref")}
    p["card"] = card["card"]
    p["drive_path"] = C.norm(read.get("drive_path"))
    p["why"] = (f"named on card \"{C.norm(card['title'])}\", Source Rulings page; "
                f"logged by {TOOL}")
    return p


def main(argv):
    write = "--write" in argv
    paths = [Path(a) for a in argv if not a.startswith("--")]
    if not paths:
        print(__doc__)
        return 2
    day = C.today_utc()
    events = C.source_read_events()
    cards = [C.load_card(p) for p in paths]

    changes = []          # (where, before, after) for the sample
    work = []
    pending = {}
    for card in cards:
        ch = int(card["chapter"])
        new_rows, ledger, new_events, report = plan(card, events, day, pending)
        print(f"\nCARD {card['card']} — {C.norm(card['title'])}  (Ch{ch:02d})")
        print("\n".join(report))
        work.append((card, new_rows, ledger, new_events))
        for r in new_rows:
            changes.append((f"{C.rel(C.claims_file(ch))} — a new last line",
                            "(nothing; the file ends at its current last line)",
                            json.dumps(claims_row(card, r, day), ensure_ascii=False,
                                       indent=1)))
        if ledger:
            lf = C.ledger_file(ch)
            last = [l for l in lf.read_text(encoding="utf-8").splitlines() if l.strip()]
            changes.append((f"{C.rel(lf)} — appended at the end",
                            "the ledger ends with this line:\n" + (last[-1] if last else ""),
                            ledger))
        for r in new_events:
            changes.append((f"{C.rel(C.EVENTS)}/ — a new source.read event",
                            "(nothing)", json.dumps(event_payload(card, r),
                                                    ensure_ascii=False, indent=1)))

    n = len(changes)
    if not write:
        import uat
        uat.show_sample(changes, n=max(n, 1))     # every change, whole
        return 0
    if n == 0:
        print("\nNothing to write. Every read these cards name is already on record.")
        return 0

    import uat
    import vaultlog
    uat.require_acceptance(TOOL, n, sample_flag="(no flag)")
    for card, new_rows, ledger, new_events in work:
        ch = int(card["chapter"])
        if new_rows:
            p = C.claims_file(ch)
            before = p.read_text(encoding="utf-8") if p.exists() else ""
            if before and not before.endswith("\n"):
                before_fixed = before + "\n"
            else:
                before_fixed = before
            after = before_fixed + "".join(
                json.dumps(claims_row(card, r, day), ensure_ascii=False) + "\n"
                for r in new_rows)
            vaultlog.write_file(p, after, tool=TOOL,
                                why=f"reads named on card {card['card']}")
        if ledger:
            lf = C.ledger_file(ch)
            before = lf.read_text(encoding="utf-8")
            sep = "" if before.endswith("\n\n") else ("\n" if before.endswith("\n") else "\n\n")
            vaultlog.write_file(lf, before + sep + ledger, tool=TOOL,
                                why=f"ledger section for card {card['card']}")
        for r in new_events:
            vaultlog.append("source.read", actor="claude", **event_payload(card, r))
    # Read back what was written: a write is not proof.
    events = C.source_read_events()
    bad = []
    for card, *_ in work:
        ch = int(card["chapter"])
        for r in card["reads"]:
            if not C.find_row(ch, r):
                bad.append(f"{card['card']}: no Claims row for {C.norm(r['author'])}")
            if not C.event_for(events, card["card"], r):
                bad.append(f"{card['card']}: no event for {C.norm(r['author'])}")
        if not C.ledger_has_card(ch, card["card"]):
            bad.append(f"{card['card']}: no ledger section")
    if bad:
        print("\nWRITTEN, BUT THE READ-BACK FAILED:\n  " + "\n  ".join(bad))
        return 1
    print(f"\nWritten and read back: {n} changes across {len(work)} card(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

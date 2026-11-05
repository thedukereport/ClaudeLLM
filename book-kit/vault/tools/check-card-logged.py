#!/usr/bin/env python3
"""check-card-logged.py — no card reaches the author naming a read that is not on record.

    tools/check-card-logged.py            # report; exit 1 on any fault
    tools/check-card-logged.py --json     # one object per finding

WHAT IT CHECKS

    Each card in the card store (`Fact Check/Cards/cards.jsonl`, read through
    `tools/cards.py` with the author's presses folded in) whose status is
    yours, submitted or approved. For each one:

      NO READ LIST   no `<card reads folder>/<card id>.reads.json`
      NO CLAIMS ROW  a read in the list has no row in `Fact Check/Claims/Ch NN.jsonl`
      NO LEDGER      the chapter's ledger has no section for the card
      NO EVENT       a read has no `source.read` event naming the card id
      OWED           the card is in `card-log-backlog.txt` (beside the card
                     reads folder) and has no read list yet: reported, never failed

    Fix any of the first four with `tools/card-log.py`. "Already logged" is
    decided in `tools/cardlib.py` and nowhere else.

WHAT IT LEAVES OUT

    Applied cards are not checked. Their reads belong to the ledger's apply
    entry, which `tools/apply-card.py` writes.

WHY

    A read that is not logged did not happen, because the next pass will do
    it again. The backlog file is work owed, never permission: a card not on it fails the
    day it appears.
"""
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cardlib as C  # noqa: E402



def main(argv):
    as_json = "--json" in argv
    out = []
    cards = C.store_cards()
    header = f"{len(cards)} cards in {C.rel(C.B.CARD_STORE)}."
    owed = C.backlog()
    events = C.source_read_events()
    checked = applied = 0
    for card in cards:
        status = card.get("status", "")
        cid = card["id"]
        title = C.norm(card.get("title")) or cid
        if status not in C.CHECKED_STATUSES:
            applied += status == "applied"
            continue
        checked += 1
        where = C.norm(card.get("where")) or card.get("chapter", "—")
        rl = C.CARDS / f"{cid}.reads.json"
        if not rl.exists():
            out.append({"check": "check-card-logged",
                        "kind": "OWED" if cid in owed else "NO READ LIST",
                        "where": where, "card": cid, "title": title,
                        "detail": f"no {C.rel(rl)}"})
            continue
        try:
            rc = C.load_card(rl)
        except SystemExit as e:
            out.append({"check": "check-card-logged", "kind": "BAD READ LIST",
                        "where": where, "card": cid, "title": title,
                        "detail": str(e)})
            continue
        ch = int(rc["chapter"])
        try:
            led = C.ledger_file(ch)
            has = C.ledger_has_card(ch, cid)
        except SystemExit as e:          # no ledger, or more than one
            led, has = None, ""
            out.append({"check": "check-card-logged", "kind": "NO LEDGER",
                        "where": where, "card": cid, "title": title, "detail": str(e)})
        if led and not has:
            out.append({"check": "check-card-logged", "kind": "NO LEDGER",
                        "where": where, "card": cid, "title": title,
                        "detail": f"no section for {cid} in {C.rel(led)}"})
        for r in rc["reads"]:
            rw = C.norm(r.get("ref")) or where
            who = f"{C.norm(r['author'])}, {C.norm(r['title'])}"
            if not C.find_row(ch, r):
                out.append({"check": "check-card-logged", "kind": "NO CLAIMS ROW",
                            "where": rw, "card": cid, "title": title,
                            "detail": f"{who} — not in {C.rel(C.claims_file(ch))}"})
            if not C.event_for(events, cid, r):
                out.append({"check": "check-card-logged", "kind": "NO EVENT",
                            "where": rw, "card": cid, "title": title,
                            "detail": f"{who} — no source.read event for this card"})
    header += f" Checked {checked} (yours, submitted, approved); {applied} applied, not checked."
    return finish(out, as_json, header)


def finish(out, as_json, header):
    faults = [o for o in out if o["kind"] != "OWED"]
    if as_json:
        for o in out:
            print(json.dumps(o, ensure_ascii=False))
    else:
        print(header)
        kinds = {}
        for o in out:
            kinds.setdefault(o["kind"], []).append(o)
        for k in ("BAD READ LIST", "NO READ LIST",
                  "NO CLAIMS ROW", "NO LEDGER", "NO EVENT", "OWED"):
            rows = kinds.get(k, [])
            if not rows:
                continue
            print(f"\n{k} — {len(rows)}")
            for o in rows:
                t = f"  {o.get('title', '')}" if o.get("title") else ""
                print(f"  {o['where']:<28} {o['card']:<22}{t}\n      {o['detail']}")
        print(f"\n{len(faults)} fault(s); "
              f"{sum(1 for o in out if o['kind'] == 'OWED')} card(s) owed from the backlog.")
    return 1 if faults else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

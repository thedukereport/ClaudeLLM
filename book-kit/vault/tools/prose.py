#!/usr/bin/env python3
"""prose.py — records that the neurolinguistic-prose skill ran on a card's exact text, and lists the open cards without that record.

WHY THIS EXISTS

    The author's rule: "All proposals need to have been run through the
    neurolinguistic prose skill before they get to me." The author caught a
    card that had skipped the skill from one phrase in it. The skill was
    there the whole time; what did not exist was a record of whether it had
    run on a given card. So "I ran it" was a claim with nothing behind it,
    and the author could check it only by reading the prose and catching the
    miss.

WHAT IS RECORDED, AND WHY IT IS HASHED

    A `prose.audited` event names the card (sheet "Source Rulings", item =
    card id), **the hash of the exact text that was audited**, and the
    findings for each of the skill's fourteen principles. Rewrite the card
    and its audit goes stale by itself, because the audit was of the old
    words. The hash ignores whitespace: reflowing a paragraph is not a
    rewrite.

WHAT THIS FILE DOES NOT DO

    It does not run the audit. Reading the card under
    `Skills/neurolinguistic-prose` is the audit; this file records that it
    happened and against which words. A gate that could certify its own
    output would say the skill had run whenever the code said so.

THE TEXT AUDITED

    The text the author would approve: the paragraph box (`reviewedPara`,
    else `proposedPara`), then the footnote box (`reviewedNote`, else
    `proposedNote`), unless the card is marked noteless.

USE

    tools/prose.py [--from DIR] [--json] [--patch-dir D]
        every open card on the page snapshot (or the card files in DIR):
        audited, stale or unrun. Exit 1 if any card lacks an audit of its
        current text. --patch-dir writes D/<card id>.json =
        {"proseCheck": {...}} to merge into the card on the page.
    tools/prose.py --card F.json [--patch-dir D]
        one card document, before it is written to the page. Exit 1 if its
        text has no audit.
    tools/prose.py --record-card F.json --findings G.json [--patch-dir D]
        record the audit of that card's text. G holds the findings for all
        fourteen principles; an audit that names fewer is refused.

    The page holds a card under "With Claude", with no Approve button, until
    its `proseCheck` says ok for the exact text the author would approve
    (page function `proseHeld()`). A card written without this step does not
    reach the author.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402

#: The fourteen principles, by the name the skill gives each. An audit that
#: records findings for fewer than all fourteen is a partial audit and is
#: refused: the skill's "Common Misses" section names principles that get
#: skipped whenever the output does not name them.
PRINCIPLES = (
    "agent-visibility", "verb-priority", "negation", "quantifier", "modal",
    "comparison", "emergence", "complex-equivalence", "mind-reading",
    "flourish", "telegraphing", "epistemic", "actor-verb-headings",
    "invented-person",
)

PAGE_SHEET = "Source Rulings"
CLOSED = ("approved", "applied")


def text_sha(text: str) -> str:
    """The identity of a card's prose, whitespace ignored."""
    return hashlib.sha256(re.sub(r"\s+", " ", (text or "")).strip().encode("utf-8")).hexdigest()[:16]


def record(sheet: str, item: str, text: str, findings: dict, actor: str = "claude", why: str = "") -> dict:
    """Record that the skill ran on THIS text, with THESE findings. Refuses a partial audit or empty text."""
    if not (text or "").strip():
        raise ValueError("there is no text to audit")
    missing = [p for p in PRINCIPLES if p not in findings]
    if missing:
        raise ValueError(
            f"this audit records {len(findings)} of {len(PRINCIPLES)} principles; missing "
            f"{', '.join(missing)}. The skill's Common Misses section names principles that get "
            f"skipped whenever the output does not name them, so a partial tally is not an audit.")
    import vaultlog
    return vaultlog.append("prose.audited", actor=actor, sheet=sheet, item=str(item),
                           text_sha=text_sha(text), findings=findings,
                           why=why or "neurolinguistic-prose, before this card reaches the author")


def audits() -> dict:
    """{(sheet, item): {text_sha: event}} for every audit on record, retracted ones left out."""
    import vaultlog
    gone = vaultlog.retracted_hashes()
    out: dict = {}
    for e in vaultlog.fold("prose.audited"):
        if e.get("hash") in gone:
            continue
        out.setdefault((e.get("sheet"), str(e.get("item"))), {})[e.get("text_sha")] = e
    return out


def card_text(card: dict) -> str:
    """The prose the author would approve: the paragraph box, then the footnote box."""
    para = card.get("reviewedPara") or card.get("proposedPara") or ""
    note = "" if card.get("noteless") else (card.get("reviewedNote") or card.get("proposedNote") or "")
    return para + ("\n\n" + note if note.strip() else "")


def card_state(card_id: str, card: dict, known: dict | None = None) -> str:
    """"audited", "stale" or "unrun" for the card's current text."""
    text = card_text(card)
    if not text.strip():
        return "audited"            # nothing to audit is not an omission
    got = (known if known is not None else audits()).get((PAGE_SHEET, str(card_id)))
    if not got:
        return "unrun"
    return "audited" if text_sha(text) in got else "stale"


def record_card(card_id: str, card: dict, findings: dict, actor: str = "claude", why: str = "") -> dict:
    return record(PAGE_SHEET, card_id, card_text(card), findings, actor=actor,
                  why=why or "neurolinguistic-prose on the card's text, before it reaches the author")


def prose_check(card_id: str, card: dict, known: dict | None = None) -> dict:
    """The proseCheck the page reads: ok only for an audit of this exact text."""
    known = known if known is not None else audits()
    text = card_text(card)
    got = known.get((PAGE_SHEET, str(card_id)), {}).get(text_sha(text))
    return {"ok": bool(got) or not text.strip(), "state": card_state(card_id, card, known), "text": text,
            "sha": text_sha(text), "audit": (got or {}).get("hash", ""),
            "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "tool": "prose.py"}


def _chapter(card: dict):
    m = re.search(r"\d+", str(card.get("chapter", "")))
    return int(m.group(0)) if m else None


def _load_card(path: Path) -> tuple:
    d = json.loads(path.read_text(encoding="utf-8"))
    d = dict(d.get("data", d))
    return d.get("id") or path.stem.split(".")[0], d


def page_cards(src: Path | None = None) -> list[tuple]:
    """(card id, card) for every open card: not approved or applied, not out of the workflow."""
    if src:
        cards = [_load_card(p) for p in sorted(Path(src).glob("*.json"))]
    else:
        import cardlib
        _when, snap = cardlib.snapshot_cards()
        cards = [(c["id"], c) for c in snap]
    return [(i, c) for i, c in cards
            if c.get("status") not in CLOSED and _chapter(c) not in B.OUT_OF_WORKFLOW]


def _patch(dirpath, card_id, check):
    d = Path(dirpath)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{card_id}.json").write_text(json.dumps({"proseCheck": check}, ensure_ascii=False, indent=1),
                                       encoding="utf-8")


def main(argv) -> int:
    patch = argv[argv.index("--patch-dir") + 1] if "--patch-dir" in argv else None
    if "--record-card" in argv:
        cid, card = _load_card(Path(argv[argv.index("--record-card") + 1]))
        if "--findings" not in argv:
            print("--record-card needs --findings G.json (the fourteen principles' findings)")
            return 2
        findings = json.loads(Path(argv[argv.index("--findings") + 1]).read_text(encoding="utf-8"))
        try:
            ev = record_card(cid, card, findings)
        except ValueError as exc:
            print(f"NOT RECORDED: {exc}")
            return 2
        print(f"recorded prose.audited {ev['hash']} for {cid}, text {ev['text_sha']}")
        cards = [(cid, card)]
    elif "--card" in argv:
        cards = [_load_card(Path(argv[argv.index("--card") + 1]))]
    else:
        src = Path(argv[argv.index("--from") + 1]) if "--from" in argv else None
        try:
            cards = page_cards(src)
        except Exception as exc:                              # noqa: BLE001
            print(f"NOT RUN: {exc}. Pass --from DIR, or save a page snapshot first.")
            return 2
    known = audits()
    bad = 0
    for cid, card in sorted(cards, key=lambda x: str(x[1].get("title", ""))):
        chk = prose_check(cid, card, known)
        if patch:
            _patch(patch, cid, chk)
        bad += not chk["ok"]
        if "--json" in argv:
            print(json.dumps({"check": "prose.py", "card": cid, "title": card.get("title", ""),
                              "status": card.get("status", ""), "state": chk["state"],
                              "words": len(chk["text"].split())}, ensure_ascii=False))
        else:
            mark = {"audited": "ok   ", "stale": "STALE", "unrun": "UNRUN"}[chk["state"]]
            print(f"  {mark}  [{card.get('status', '')}] {str(card.get('title', ''))[:110]}  "
                  f"({len(chk['text'].split())} words)")
    if "--json" not in argv:
        print(f"\n  {len(cards)} open card(s); {bad} without a prose audit of the text the author would approve.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

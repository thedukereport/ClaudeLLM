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

    A `prose.audited` event names the card (sheet "Source Rulings", the key
    the review page used and the card desk keeps; item = card id), **the hash of the exact text that was audited**, the
    findings for each of the skill's fifteen principles, the verdict (ok, or
    finding: a fault the writer must fix), and the session that recorded it. Rewrite the card
    and its audit goes stale by itself, because the audit was of the old
    words. The hash ignores whitespace: reflowing a paragraph is not a
    rewrite.

WHAT THIS FILE DOES NOT DO

    It does not run the audit. Reading the card under
    `Skills/neurolinguistic-prose` is the audit; this file records that it
    happened and against which words. A gate that could certify its own
    output would say the skill had run whenever the code said so.

A SECOND SESSION AUDITS EACH CARD

    The session that wrote a card also graded it, and its own faults passed.
    The author's rule since: each card's prose audit is done by a session other
    than the one that wrote the card. An audit counts toward the gate only when
    its session wrote no version of the card with that text (the card store
    records each version's session; `vaultlog.session_id()` gives the
    session). book.toml [gates] "card_cross_audit": "warn" shows a
    self-audited card as such; "refuse" holds it. An audit whose verdict is
    "finding" keeps the card held until a new version is written and audited.

THE TEXT AUDITED

    The text the author would approve: the paragraph box (`reviewedPara`,
    else `proposedPara`), then the footnote box (`reviewedNote`, else
    `proposedNote`), unless the card is marked noteless.

USE

    tools/prose.py [--from DIR] [--json] [--patch-dir D]
        every open card in the card store (or the card files in DIR):
        audited, stale or unrun. Exit 1 if any card lacks an audit of its
        current text. --patch-dir writes D/<card id>.json =
        {"proseCheck": {...}}.
    tools/prose.py --card F.json [--patch-dir D]
        one card document, before it goes into the store. Exit 1 if its
        text has no audit.
    tools/prose.py --record-card F.json --findings G.json --verdict ok|finding
        record the audit of that card's text (F: a card file, or a card id in
        the store). G holds the findings for all fifteen principles; an audit
        that names fewer is refused.

    The card desk holds a card under "With Claude", with no Approve button,
    until `prose_check` says ok for the exact text the author would approve.
    A card written without this step does not reach the author.
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

#: The fifteen principles, by the name the skill gives each. An audit that
#: records findings for fewer than all fifteen is a partial audit and is
#: refused: the skill's "Common Misses" section names principles that get
#: skipped whenever the output does not name them.
PRINCIPLES = (
    "agent-visibility", "verb-priority", "negation", "quantifier", "modal",
    "comparison", "emergence", "complex-equivalence", "mind-reading",
    "flourish", "telegraphing", "epistemic", "actor-verb-headings",
    "invented-person",
    # Principle 15: an unspecified verb ("addresses", "deals with", "handles", "engages") says
    # that something was done and not what. Added in the system this kit comes from when the
    # author asked whether the check covered "invented people, unspecified verbs, abstract nouns,
    # and nominalizations", and three of the four had no line in the audit.
    "unspecified-verbs",
)

PAGE_SHEET = "Source Rulings"
CLOSED = ("approved", "applied")


def text_sha(text: str) -> str:
    """The identity of a card's prose, whitespace ignored."""
    return hashlib.sha256(re.sub(r"\s+", " ", (text or "")).strip().encode("utf-8")).hexdigest()[:16]


def record(sheet: str, item: str, text: str, findings: dict, actor: str = "claude", why: str = "",
           verdict: str = "ok") -> dict:
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
    if verdict not in ("ok", "finding"):
        raise ValueError('an audit gives its verdict: ok (no fault) or finding (a fault the writer must fix)')
    return vaultlog.append("prose.audited", actor=actor, sheet=sheet, item=str(item),
                           text_sha=text_sha(text), findings=findings, verdict=verdict,
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


def record_card(card_id: str, card: dict, findings: dict, actor: str = "claude", why: str = "",
                verdict: str = "ok") -> dict:
    return record(PAGE_SHEET, card_id, card_text(card), findings, actor=actor,
                  why=why or "neurolinguistic-prose on the card's text, before it reaches the author",
                  verdict=verdict)


def writer_sessions(card_id: str, sha: str) -> set:
    """The sessions that wrote a version of this card whose text is `sha`."""
    try:
        import cards
        return {l.get("session") for l in cards.versions(card_id)
                if l.get("session") and text_sha(card_text(l.get("card") or {})) == sha}
    except Exception:  # noqa: BLE001
        return set()


def other_audit(card_id: str, sha: str, known_rows=None):
    """The newest audit of this text by a session that wrote no version of it, or None. An audit with no
    session on record is not counted as the writer's."""
    import vaultlog
    writers = writer_sessions(card_id, sha)
    gone = vaultlog.retracted_hashes()
    last = None
    for e in vaultlog.fold("prose.audited"):
        if e.get("hash") in gone or e.get("sheet") != PAGE_SHEET or str(e.get("item")) != str(card_id) \
                or e.get("text_sha") != sha:
            continue
        if not e.get("session") or e.get("session") not in writers:
            last = e
    return last


def prose_check(card_id: str, card: dict, known: dict | None = None) -> dict:
    """ok only for an audit of this exact text, by a session other than the card's writer when
    book.toml [gates] "card_cross_audit" is "refuse", and never while that audit's verdict is "finding"."""
    known = known if known is not None else audits()
    text = card_text(card)
    sha = text_sha(text)
    got = known.get((PAGE_SHEET, str(card_id)), {}).get(sha)
    other = other_audit(card_id, sha) if got else None
    self_only = bool(got) and other is None
    if self_only and B.gate_mode("card_cross_audit") == "refuse":
        got = None
    found = (other or got or {}).get("verdict") == "finding"
    if found:
        got = None
    state = "finding" if found else ("self-audited" if self_only else ("audited" if got
                                                                       else card_state(card_id, card, known)))
    return {"ok": bool(got) or not text.strip(), "state": state, "selfAudited": self_only, "text": text,
            "sha": sha, "audit": (got or {}).get("hash", ""),
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
        arg = argv[argv.index("--record-card") + 1]
        if Path(arg).suffix == ".json" and Path(arg).exists():
            cid, card = _load_card(Path(arg))
        else:
            import cards
            card = cards.fold().get(arg)
            if card is None:
                print(f"no card file and no card {arg!r} in the store")
                return 2
            cid = arg
        if "--findings" not in argv:
            print("--record-card needs --findings G.json (the fifteen principles' findings)")
            return 2
        verdict = argv[argv.index("--verdict") + 1] if "--verdict" in argv else ""
        findings = json.loads(Path(argv[argv.index("--findings") + 1]).read_text(encoding="utf-8"))
        try:
            ev = record_card(cid, card, findings, verdict=verdict)
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
            print(f"NOT RUN: {exc}. Pass --from DIR.")
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
            mark = {"audited": "ok   ", "stale": "STALE", "unrun": "UNRUN", "self-audited": "SELF ",
                    "finding": "FOUND"}[chk["state"]]
            print(f"  {mark}  [{card.get('status', '')}] {str(card.get('title', ''))[:110]}  "
                  f"({len(chk['text'].split())} words)")
    if "--json" not in argv:
        print(f"\n  {len(cards)} open card(s); {bad} without a prose audit of the text the author would approve.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

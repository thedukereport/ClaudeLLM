#!/usr/bin/env python3
"""card_desk_test.py — the card store, its gates, the card desk's presses and the refresh after an apply.

On a copy of the sample vault. Requires:
  1. `cards.py add` refuses a card with no proposed text, and writes nothing;
  2. with card_words = "warn" a card with a banned word goes in and the writer is told;
     with "refuse" it is refused and nothing is written;
  3. the read gate lists the quotation on card (d) until its read is logged, then nothing;
  4. the desk holds card (d) under With Claude until a second session audits its prose,
     then puts it in Waiting for you; card (c), on the applied card's line, goes to Reopen?;
  5. an Approve press on the version on screen is recorded and the card reads approved;
     a press on an older version is refused and leaves a press.refused event;
     "Send my edits" with the text unchanged is refused;
  6. hold takes a waiting card off the desk; release puts it back;
  7. after card (d) is applied, card (b), whose note (d) changed, is reported "back";
     with card_refresh = "write" it is held and the Editor's Inbox gets one item;
  8. a POST from another page is refused with 403 and recorded nowhere.
"""
import importlib.util
import json
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cardtest as T  # noqa: E402

FIFTEEN = ("agent-visibility", "verb-priority", "negation", "quantifier", "modal", "comparison",
           "emergence", "complex-equivalence", "mind-reading", "flourish", "telegraphing",
           "epistemic", "actor-verb-headings", "invented-person", "unspecified-verbs")
bad = []


def events(v, kind):
    return [json.loads(l) for f in (v / "Fact Check" / "events").glob("*.jsonl")
            for l in f.read_text(encoding="utf-8").splitlines() if f'"{kind}"' in l]


def desk(v, code):
    """Run `code` against the card desk module inside the copy; returns its stdout."""
    prog = ("import sys, json, importlib.util; sys.path.insert(0, sys.argv[1]); "
            "s = importlib.util.spec_from_file_location('d', sys.argv[1] + '/card-desk.py'); "
            "d = importlib.util.module_from_spec(s); s.loader.exec_module(d)\n" + code)
    import os
    import subprocess
    r = subprocess.run([sys.executable, "-c", prog, str(T.TOOLS)], cwd=v, capture_output=True, text=True,
                       env=dict(os.environ, BOOK_VAULT=str(v), BOOK_SESSION="test-desk", BOOK_APPROVE_WAIT="0"), timeout=150)
    if r.returncode:
        bad.append("the desk code failed: " + r.stderr[-800:])
    return r.stdout


def lanes(v):
    out = desk(v, "g = d.Gates()\nfor lane, cid, c, why in d.ordered(g): print(json.dumps([lane, cid, why]))")
    return {x[1]: (x[0], x[2]) for x in map(json.loads, filter(None, out.splitlines()))}


with T.sample_copy() as v:
    toml = v / "book.toml"
    base = toml.read_text(encoding="utf-8")
    wl = v / "Methodology" / "Word Lists.md"
    wl.parent.mkdir(parents=True, exist_ok=True)
    wl.write_text("# Word Lists\n\n<!-- BANNED-WORDS-MACHINE-LIST:BEGIN -->\n```\n"
                  "\\bcarr(y|ies|ied|ying)\\b ;; literal physical carrying; quoted\n"
                  "```\n<!-- BANNED-WORDS-MACHINE-LIST:END -->\n", encoding="utf-8")
    store = v / T.STORE_REL
    new = v / "new.json"
    card = {"id": "t-new", "title": "Ch 01 · test", "chapter": "Ch 01", "where": "Ch01/L5", "status": "yours",
            "current": [{"where": "Ch01/L5", "text": "x"}], "proposedPara": ""}

    # 1
    new.write_text(json.dumps(card), encoding="utf-8")
    before = store.read_bytes()
    r = T.run(v, "cards.py", "add", new, "--why", "test")
    if r.returncode != 1 or "REFUSED" not in r.stdout or store.read_bytes() != before:
        bad.append("a card with no proposed text went in: " + r.stdout[-300:])

    # 2
    new.write_text(json.dumps(dict(card, proposedPara="The pamphlet carries the frame.")), encoding="utf-8")
    r = T.run(v, "cards.py", "add", new, "--why", "test")
    if r.returncode != 0 or "banned word" not in r.stderr or b"t-new" not in store.read_bytes():
        bad.append("warn mode: the card did not go in with the writer told: " + r.stdout[-200:] + r.stderr[-300:])
    toml.write_text(base.replace('card_words = "warn"', 'card_words = "refuse"'), encoding="utf-8")
    before = store.read_bytes()
    r = T.run(v, "cards.py", "add", new, "--why", "test")
    if r.returncode != 1 or store.read_bytes() != before:
        bad.append("refuse mode: a card with a banned word went in: " + r.stdout[-300:])
    toml.write_text(base, encoding="utf-8")

    # 3
    r = T.run(v, "card_reads.py", "--card", T.CHOICE)
    if "quotation" not in r.stdout:
        bad.append("the read gate did not list card (d)'s quotation: " + r.stdout[-300:])
    T.run(v, "card-log.py", "--write", v / "Handoffs/editor-tools/cards/ch02-reflection-choice.reads.json")
    r = T.run(v, "card_reads.py", "--card", T.CHOICE)
    if "0 of 1 facts" not in r.stdout:
        bad.append("the logged read did not clear the quotation: " + r.stdout[-300:])

    # 4
    got = lanes(v)
    if got.get(T.CHOICE, ("",))[0] != "claude" or not any("prose" in w for w in got[T.CHOICE][1]):
        bad.append(f"card (d) was not held for its prose audit: {got.get(T.CHOICE)}")
    full = v / "full.json"
    full.write_text(json.dumps({k: "none" for k in FIFTEEN}), encoding="utf-8")
    T.run(v, "prose.py", "--record-card", T.CHOICE, "--findings", full, "--verdict", "ok", session="test-qa")
    got = lanes(v)
    if got.get(T.CHOICE, ("",))[0] != "yours":
        bad.append(f"card (d) did not reach Waiting for you once audited: {got.get(T.CHOICE)}")
    if got.get(T.ON_CLOSED, ("",))[0] not in ("reopen", "claude"):
        bad.append(f"card (c) on an approved line reached the author's queue: {got.get(T.ON_CLOSED)}")

    # 5
    out = desk(v, "print(json.dumps(d.record_press({'card': ['ch02-reflection-choice'], 'version': ['1'], "
                  "'kind': ['edit'], 'text': [d.cards.card('ch02-reflection-choice')['proposedPara']]})))")
    if '"REFUSED' not in out and "REFUSED" not in out:
        bad.append("an edit with the text unchanged was recorded: " + out)
    out = desk(v, "print(json.dumps(d.record_press({'card': ['ch02-reflection-choice'], 'version': ['1'], "
                  "'kind': ['approve'], 'text': ['']})))")
    if "Recorded" not in out:
        bad.append("the Approve press was not recorded: " + out)
    if '"status": "approved"' not in T.run(v, "cards.py", "show", T.CHOICE).stdout:
        bad.append("card (d) does not read approved after the press")
    n0 = len(events(v, "press.refused"))
    out = desk(v, "print(json.dumps(d.record_press({'card': ['ch02-fed1-note-interpretation'], 'version': ['9'], "
                  "'kind': ['approve'], 'text': ['']})))")
    if "REFUSED" not in out or len(events(v, "press.refused")) != n0 + 1:
        bad.append("a press on a version the store does not hold was not refused and recorded: " + out)

    # 6
    r = T.run(v, "cards.py", "hold", T.NOTE_ARGUES, "--by", "Editor", "--reason", "not ready")
    if r.returncode != 0 or lanes(v).get(T.NOTE_ARGUES, ("",))[0] != "claude":
        bad.append("a held card was not off the author's desk: " + r.stdout[-200:])
    r = T.run(v, "cards.py", "release", T.NOTE_ARGUES, "--by", "Editor")
    if r.returncode != 0 or '"status": "yours"' not in T.run(v, "cards.py", "show", T.NOTE_ARGUES).stdout:
        bad.append("release did not put the card back: " + r.stdout[-200:])

    # 7
    T.ledger(v, 2, "Reflection and Choice")
    r = T.run(v, "apply-card.py", T.CHOICE, "--write")
    if r.returncode != 0:
        bad.append("apply of card (d) failed: " + (r.stdout + r.stderr)[-500:])
    if f"{T.NOTE_ARGUES} v" not in r.stderr or "back" not in r.stderr:
        bad.append("the refresh after the apply did not report card (b): " + r.stderr[-400:])
    toml.write_text(base.replace('card_refresh = "report"', 'card_refresh = "write"'), encoding="utf-8")
    r = T.run(v, "card_refresh.py", "--chapter", "2", "--write")
    inbox = (v / "Handoffs" / "Editor.md").read_text(encoding="utf-8")
    if '"status": "held"' not in T.run(v, "cards.py", "show", T.NOTE_ARGUES).stdout or inbox.count(T.NOTE_ARGUES) != 1:
        bad.append("write mode did not hold card (b) and tell its owner once: " + r.stdout[-300:])
    toml.write_text(base, encoding="utf-8")

    # 8
    import os
    os.environ["BOOK_VAULT"] = str(v)
    spec = importlib.util.spec_from_file_location("d", T.TOOLS / "card-desk.py")
    d = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(d)
    srv = d.ThreadingHTTPServer(("127.0.0.1", 0), d.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    n0 = len(events(v, "decision.recorded")) + len(events(v, "press.refused"))
    req = urllib.request.Request(url + "/press", data=urllib.parse.urlencode(
        {"card": T.NOTE_ARGUES, "version": "1", "kind": "card-note", "text": "x"}).encode(),
        headers={"Origin": "http://elsewhere.example"})
    try:
        urllib.request.urlopen(req)
        bad.append("a press from another page was accepted")
    except urllib.error.HTTPError as e:
        if e.code != 403:
            bad.append(f"a press from another page got {e.code}, not 403")
    if len(events(v, "decision.recorded")) + len(events(v, "press.refused")) != n0:
        bad.append("a press from another page was recorded")
    for path in ("/", "/all", "/asks", "/sources", f"/card/{T.APPLIED}"):
        if urllib.request.urlopen(url + path).status != 200:
            bad.append(f"{path} did not answer 200")
    srv.shutdown()

T.finish("card-desk", bad,
         "card desk: the store refuses a card without its words; the word and read gates warn or refuse; "
         "the desk holds a card until a second session audits it and sends a closed line to Reopen?; presses "
         "are recorded, a stale one is refused and logged; hold and release work; an apply refreshes or sends "
         "back the chapter's other cards; a press from another page is refused")

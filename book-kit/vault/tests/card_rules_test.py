#!/usr/bin/env python3
"""card_rules_test.py — the card rules ported on 2026-11-11: the shape gates, the five-minute Undo, choices, the
three-version stop, the writer's own doors (withdraw, hold), the fresh reviewer at release, queued cards, and the
store split by day.

On a copy of the sample vault. Requires:
   1. a card pointing to "Chapter 3" is refused with card_pointer = "refuse";
   2. a new card on card (d)'s paragraph is refused with card_overlap = "refuse", and with `queuedBehind` it goes
      in held; after (d) is approved and applied, it is released;
   3. a card that only changes punctuation is refused for the desk with card_format_only = "refuse", and goes in
      written at "approved" with reopenedBy "format-only";
   4. a card with no tldr, recommendation, subject or reasons is refused with card_summary = "refuse";
   5. two choices with no option for each are refused with card_choices = "refuse"; with options the desk draws
      "Approve choice 1" and "Approve choice 2", and a press of choice 2 records the paragraph choice 2 writes;
   6. Approve waits: the card reads "approving", Production's apply is refused, and "Undo my approval" puts it back;
   7. "Keep it the way it is" closes a card unapplied;
   8. after the author's directive, a fourth version that changes the book's words is refused with
      card_three_versions = "refuse", the card sits in Questions for you, and his "Bring it back to me" lets it in;
   9. withdraw: only the writer closes its held card; the desk lists it "Withdrawn by its writer";
  10. a version written to a held card goes in held;
  11. release with card_review = "refuse" needs a reviewer's PASS on the version, or a fix list after a FAIL;
  12. split-by-day --write makes day files and every card folds as before; a new line goes to today's file;
  13. the desk's card page shows no asterisk outside the edit boxes; /chapter/2 answers; --show prints text;
  14. the read gate: a quoted title is a "title" fact, a spelled-out name in parentheses a "full name", a quotation
      past 600 characters is one quotation, and a Claims row that records a failed search covers nothing;
  15. the note check applies the footnote protocol: a URL, a pointer to another chapter, a judgement of a source, a
      retelling and two works in one note are reported; with card_notes_protocol = "refuse" they hold the card.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cardtest as T  # noqa: E402

bad = []
GATES = ("card_pointer", "card_overlap", "card_format_only", "card_summary", "card_choices", "card_three_versions",
         "card_review", "card_cross_audit", "card_reads", "card_words", "card_answer", "card_own_words",
         "card_notes_protocol")
L3 = ("Alexander Hamilton addressed the first *Federalist* paper \"To the People of the State of New York,\" and the "
      "Project Gutenberg text heads it \"For the Independent Journal.\"[^fed1_heading]")
FULL = {"tldr": "The card adds one sentence. It changes nothing else.", "recommendation": "Approve it.",
        "subject": "Hamilton's address to the people."}


def gates(v, **modes):
    toml = v / "book.toml"
    t = toml.read_text(encoding="utf-8")
    if "[gates]" not in t:
        t += "\n[gates]\n"
    lines = [l for l in t.splitlines() if not any(l.startswith(g + " ") for g in GATES)]
    i = lines.index("[gates]") + 1
    for g in GATES:
        lines.insert(i, f'{g} = "{modes.get(g, "warn")}"')
    toml.write_text("\n".join(lines) + "\n", encoding="utf-8")


def add(v, rec, by="Editor", session="test-writer"):
    p = v / "tmp-card.json"
    p.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    return T.run(v, "cards.py", "add", p, "--why", "test", "--by", by, session=session)


def card(cid, para, **more):
    rec = {"id": cid, "title": f"Ch 02 · {cid}", "chapter": "Ch 02", "where": "Ch02/L3 (block 0bdbc7)",
           "status": "yours", "current": [{"where": "Ch02/L3 (block 0bdbc7)", "text": L3}], "proposedPara": para}
    rec.update(more)
    return rec


def show(v, cid):
    return json.loads(T.run(v, "cards.py", "show", cid).stdout or "{}")


def desk(v, code, wait="0"):
    prog = ("import sys, json, importlib.util; sys.path.insert(0, sys.argv[1]); "
            "s = importlib.util.spec_from_file_location('d', sys.argv[1] + '/card-desk.py'); "
            "d = importlib.util.module_from_spec(s); s.loader.exec_module(d)\n" + code)
    r = subprocess.run([sys.executable, "-c", prog, str(T.TOOLS)], cwd=v, capture_output=True, text=True,
                       env=dict(os.environ, BOOK_VAULT=str(v), BOOK_SESSION="test-desk", BOOK_APPROVE_WAIT=wait),
                       timeout=150)
    if r.returncode:
        bad.append("the desk code failed: " + r.stderr[-800:])
    return r.stdout


def lane(v, cid, wait="0"):
    out = desk(v, f"g = d.Gates(); print(json.dumps(g.lane({cid!r}, g.folded[{cid!r}])))", wait)
    try:
        return json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return ["", []]


def press(v, cid, kind, text="", wait="0"):
    c = show(v, cid)
    return desk(v, f"print(d.record_press({{'card': [{cid!r}], 'version': ['{c.get('_version')}'], "
                   f"'kind': [{kind!r}], 'text': [{text!r}]}})[1])", wait)


with T.sample_copy() as v:
    gates(v)
    # 1
    gates(v, card_pointer="refuse")
    r = add(v, card("t-ptr", L3 + " As we will see in Chapter 3, he answered it."))
    if r.returncode != 1 or "another part of this book" not in r.stdout:
        bad.append("1: a pointer to Chapter 3 went in: " + r.stdout[-300:])
    gates(v)

    # 2
    dup = {"id": "t-dup", "title": "Ch 02 · second card on the paragraph", "chapter": "Ch 02",
           "where": "Ch02/L5 (block 3204ff)", "status": "yours",
           "current": [T.newest(v, T.CHOICE)["current"][0]],
           "proposedPara": T.newest(v, T.CHOICE)["current"][0]["text"].replace("a test", "a trial")}
    gates(v, card_overlap="refuse")
    r = add(v, dup)
    if r.returncode != 1 or T.CHOICE not in r.stdout:
        bad.append("2: a second open card on one paragraph went in: " + r.stdout[-300:])
    r = add(v, dict(dup, queuedBehind=T.CHOICE))
    if r.returncode != 0 or show(v, "t-dup").get("status") != "held":
        bad.append("2: a queued card did not go in held: " + r.stdout[-300:] + r.stderr[-300:])
    gates(v)

    # 3
    fmt = card("t-fmt", L3.replace("Journal.", "Journal"))
    gates(v, card_format_only="refuse")
    r = add(v, fmt)
    if r.returncode != 1 or "formatting change" not in r.stdout:
        bad.append("3: a punctuation-only card went to the desk: " + r.stdout[-300:])
    r = add(v, dict(fmt, status="approved", reopenedBy="format-only"))
    if r.returncode != 0:
        bad.append("3: a format-only card written approved was refused: " + r.stdout[-300:])
    gates(v)

    # 4
    gates(v, card_summary="refuse")
    para4 = L3 + " Hamilton signed it Publius."
    r = add(v, card("t-sum", para4))
    if r.returncode != 1 or "tldr" not in r.stdout:
        bad.append("4: a card with no TLDR went in: " + r.stdout[-300:])
    ok4 = card("t-sum", para4, changeList=[{"before": "", "after": "Hamilton signed it Publius.",
                                            "why": "The paragraph names the signature the paper carries."}], **FULL)
    r = add(v, ok4)
    if r.returncode != 0:
        bad.append("4: a card with its TLDR and reasons was refused: " + r.stdout[-300:])
    gates(v)

    # 5
    one, two = "Hamilton signed the paper Publius.", "Hamilton signed the paper with a Roman name."
    ch = card("t-ch", L3 + " " + one, choices=[{"label": "Name the signature", "text": L3 + " " + one},
                                                 {"label": "Describe the signature", "text": L3 + " " + two}], **FULL)
    gates(v, card_choices="refuse")
    r = add(v, dict(ch, changeList=[{"after": one, "why": "The paper carries it."}]))
    if r.returncode != 1 or "choices" not in r.stdout:
        bad.append("5: two choices with one proposed text went in: " + r.stdout[-300:])
    ch["changeList"] = [{"before": "", "after": one, "why": "The paper carries the signature.",
                         "choices": [{"label": "Name it", "after": one}, {"label": "Describe it", "after": two}]}]
    r = add(v, ch)
    if r.returncode != 0:
        bad.append("5: a choice card with an option for each was refused: " + r.stdout[-300:])
    gates(v)
    T.run(v, "card-log.py", "--write", v / "Handoffs/editor-tools/cards/ch02-reflection-choice.reads.json")
    page = desk(v, "g = d.Gates(); r = [x for x in d.ordered(g) if x[1] == 't-ch'][0]; print(d.show_card('t-ch', r[2], 'yours', []))")
    if "Approve choice 1" not in page or "Approve choice 2" not in page:
        bad.append("5: the desk did not draw a button for each choice")
    desk(v, "c = d.cards.fold()['t-ch']; d.Gates.lane = lambda self, cid, c: ('yours', []); "
            "print(d.record_press({'card': ['t-ch'], 'version': [str(c['_version'])], 'kind': ['approve#2'], 'text': ['']}))")
    c5 = show(v, "t-ch")
    if c5.get("approvedChoice") != 2 or two not in (c5.get("approvedText") or ""):
        bad.append(f"5: the choice press did not record choice 2's text: {c5.get('approvedChoice')} {c5.get('approvedText')!r}")

    # 6
    desk(v, "d.Gates.lane = lambda self, cid, c: ('yours', []); "
            f"print(d.record_press({{'card': ['t-sum'], 'version': ['{show(v, 't-sum')['_version']}'], 'kind': ['approve'], 'text': ['']}}))",
         wait="300")
    if lane(v, "t-sum", wait="300")[0] != "approving":
        bad.append(f"6: an approve inside the wait did not read approving: {lane(v, 't-sum', wait='300')}")
    r = subprocess.run([sys.executable, str(T.TOOLS / "cards.py"), "applied", "t-sum", "--version",
                        str(show(v, "t-sum")["_version"]), "--edit-event", "x"], cwd=v, capture_output=True, text=True,
                       env=dict(os.environ, BOOK_VAULT=str(v), BOOK_APPROVE_WAIT="300", BOOK_SESSION="t"))
    if r.returncode != 1 or "undo" not in r.stdout:
        bad.append("6: Production applied a card inside the wait: " + r.stdout[-300:])
    out = press(v, "t-sum", "undo", wait="300")
    if "Recorded" not in out or show(v, "t-sum").get("status") != "yours":
        bad.append("6: Undo did not put the card back: " + out[-300:])

    # 7
    add(v, card("t-keep", L3.replace("first", "opening"), **FULL,
                changeList=[{"before": "first", "after": "opening", "why": "test"}]))
    desk(v, "d.Gates.lane = lambda self, cid, c: ('yours', []); "
            f"print(d.record_press({{'card': ['t-keep'], 'version': ['{show(v, 't-keep')['_version']}'], 'kind': ['leave'], 'text': ['']}}))")
    if show(v, "t-keep").get("status") != "superseded" or lane(v, "t-keep")[0] != "closed":
        bad.append(f"7: Keep it the way it is left the card open: {show(v, 't-keep').get('status')}")

    # 8
    base = card("t-stop", L3 + " Version zero.", **FULL, changeList=[{"after": "x", "why": "test"}])
    add(v, base)
    T.press(v, "t-stop", "directive", "Say who signed it.")
    time.sleep(1.1)            # the store and the log keep whole seconds
    for i in range(1, 4):
        add(v, dict(base, proposedPara=L3 + f" Version {i}.", status="held", heldBy="Editor", heldReason="test"))
    gates(v, card_three_versions="refuse")
    r = add(v, dict(base, proposedPara=L3 + " Version 4."))
    if r.returncode != 1 or "Managing Editor" not in r.stdout:
        bad.append("8: a fourth version after the directive went in: " + r.stdout[-300:])
    if lane(v, "t-stop")[0] != "question":
        bad.append(f"8: the stopped card is not in Questions for you: {lane(v, 't-stop')}")
    out = press(v, "t-stop", "bring", "Bring it back.")
    time.sleep(1.1)
    r = add(v, dict(base, proposedPara=L3 + " Version 4."))
    if r.returncode != 0:
        bad.append("8: after Bring it back to me the version was still refused: " + out[-200:] + r.stdout[-300:])
    gates(v)

    # 9 and 10
    add(v, card("t-w", L3.replace("first", "earliest"), **FULL, changeList=[{"after": "x", "why": "test"}]))
    T.run(v, "cards.py", "hold", "t-w", "--by", "Editor", "--reason", "not ready")
    r = add(v, card("t-w", L3.replace("first", "first numbered"), **FULL, changeList=[{"after": "x", "why": "t"}]))
    if show(v, "t-w").get("status") != "held":
        bad.append("10: a version written to a held card went to the desk: " + r.stderr[-300:])
    r = T.run(v, "cards.py", "withdraw", "t-w", "--by", "QA", "--reason", "repeat")
    if r.returncode != 1:
        bad.append("9: a role that did not hold the card withdrew it: " + r.stdout[-300:])
    r = T.run(v, "cards.py", "withdraw", "t-w", "--by", "Editor", "--reason", "a repeat of another telling")
    got = lane(v, "t-w")
    if r.returncode != 0 or got[0] != "closed" or "Withdrawn by its writer" not in " ".join(got[1]):
        bad.append(f"9: withdraw by its writer did not close it: {r.stdout[-200:]} {got}")

    # 11
    add(v, card("t-rev", L3.replace("first", "first numbered"), **FULL, changeList=[{"after": "x", "why": "t"}]))
    T.run(v, "cards.py", "hold", "t-rev", "--by", "Editor", "--reason", "for review")
    gates(v, card_review="refuse")
    r = T.run(v, "cards.py", "release", "t-rev", "--by", "Editor")
    if r.returncode != 1 or "reviewer" not in r.stdout:
        bad.append("11: release without a reviewer's verdict went through: " + r.stdout[-300:])
    n = show(v, "t-rev")["_version"]
    T.run(v, "cards.py", "review-pass", "t-rev", "--version", n, "--by", "Reviewer", "--verdict", "FAIL",
          "--note", "one fault", "--finding", "say the paper's number")
    add(v, card("t-rev", L3.replace("first", "first numbered (No. 1)"), **FULL, changeList=[{"after": "x", "why": "t"}]))
    r = T.run(v, "cards.py", "review-fix", "t-rev", "--by", "Editor", "--fix", "1=(No. 1)")
    r2 = T.run(v, "cards.py", "release", "t-rev", "--by", "Editor")
    if r.returncode != 0 or r2.returncode != 0:
        bad.append("11: the fix list after a FAIL did not release the card: " + r.stdout[-200:] + r2.stdout[-300:])
    gates(v)

    # 13 (before the split, on the store as it is)
    page = desk(v, f"g = d.Gates(); r = [x for x in d.ordered(g) if x[1] == {T.CHOICE!r}][0]; "
                   f"print(d.show_card(r[1], r[2], r[0], r[3]))")
    import re
    vis = re.sub(r"<textarea.*?</textarea>|<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    if "*" in re.sub(r"<[^>]+>", "", vis):
        bad.append("13: the card page shows an asterisk outside the edit boxes")
    if "<i>Federalist</i>" not in page:
        bad.append("13: the card page did not draw the book's italics")
    if "200" not in desk(v, "print(d.route('/chapter/2', {})[0][:0] or 200)"):
        bad.append("13: /chapter/2 did not answer")
    r = T.run(v, "desk_audit.py", "--card", T.CHOICE)
    if r.returncode != 0:
        bad.append("13: the desk audit found faults on card (d)'s page: " + r.stdout[-400:])
    T.put_card(v, "t-aud", card("t-aud", L3, title="Ch 02 · the Editor's fix, see tools/cards.py", **FULL,
                                 changeList=[{"after": "x", "why": "t"}]))
    r = T.run(v, "desk_audit.py", "--card", "t-aud")
    if r.returncode != 1 or "role" not in r.stdout or "path" not in r.stdout:
        bad.append("13: the desk audit did not catch a role name and a path in a card's title: " + r.stdout[-300:])
    r = T.run(v, "card-desk.py", "--show", T.CHOICE)
    if r.returncode != 0 or "Proposed, as it would read" not in r.stdout or "<" in r.stdout.replace("<i>", ""):
        bad.append("13: --show did not print the card as text: " + r.stdout[:300])

    # 14
    claims = v / "Fact Check" / "Claims" / "Ch 02.jsonl"
    claims.parent.mkdir(parents=True, exist_ok=True)
    with claims.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"reader": "Fact-checker", "drive_path": "library/x.pdf", "type": "search_negative",
                            "states": "No source gives 14 March 1788."}) + "\n")
    code = ("import sys, json; sys.path.insert(0, sys.argv[1]); import card_reads as R; "
            "long = 'He said ' + chr(34) + ' '.join(['word'] * 130) + chr(34) + ' and left.'; "
            "print(json.dumps([R.facts('Alan Smith, ' + chr(34) + 'The Red Pill,' + chr(34) + ' in his book.'), "
            "R.facts('The firm Satys (Société d' + chr(39) + 'Application des Techniques) bid.'), "
            "[k for k, _ in R.facts(long)], R.covered('date', '14 March 1788', R.opened_rows())]))")
    r = subprocess.run([sys.executable, "-c", code, str(T.TOOLS)], cwd=v, capture_output=True, text=True,
                       env=dict(os.environ, BOOK_VAULT=str(v)))
    try:
        t14, f14, q14, neg = json.loads(r.stdout)
    except ValueError:
        t14 = f14 = q14 = neg = None
        bad.append("14: the read gate check did not run: " + r.stderr[-400:])
    if t14 is not None:
        if ["title", "The Red Pill"] not in t14:
            bad.append(f"14: a quoted title is not a title fact: {t14}")
        if not any(k == "full name" for k, _ in f14):
            bad.append(f"14: a spelled-out name in parentheses is not a fact: {f14}")
        if q14.count("quotation") != 1:
            bad.append(f"14: a long quotation did not read as one quotation: {q14}")
        if neg:
            bad.append("14: a failed-search row covered the date it says no source gives")

    # 15
    code = ("import sys, json, importlib.util as u; sys.path.insert(0, sys.argv[1]); "
            "s = u.spec_from_file_location('n', sys.argv[1] + '/check-card-notes.py'); m = u.module_from_spec(s); "
            "s.loader.exec_module(m); print(json.dumps([[r for r, _w, _s in m.protocol_findings(t)] for t in sys.argv[2:]]))")
    notes = ["See https://example.org/a.", "As discussed in Chapter 4, Hamilton wrote it.",
             "The standard reference is Jones, *A History*.", "Smith documents the whole affair, pp. 3–9.",
             "Hamilton, *Federalist* No. 1; Paine, *Common Sense*, 3.", "Hamilton, *Federalist* No. 1, \"General Introduction.\""]
    r = subprocess.run([sys.executable, "-c", code, str(T.TOOLS), *notes], cwd=v, capture_output=True, text=True,
                       env=dict(os.environ, BOOK_VAULT=str(v)))
    try:
        got = json.loads(r.stdout)
    except ValueError:
        got = None
        bad.append("15: the note protocol did not run: " + r.stderr[-300:])
    if got is not None and got != [["URL"], ["BOOK POINTER"], ["JUDGES"], ["RETELLS"], ["ONE WORK"], []]:
        bad.append(f"15: the footnote protocol read the six notes as {got}")
    nc = card("t-note", L3, proposedPara=L3 + "\n\n⁂\n\n[^fed1_heading]: The standard reference is Hamilton, "
              "*The Federalist* No. 1.", **FULL, changeList=[{"after": "x", "why": "t"}])
    T.put_card(v, "t-note", nc)
    gates(v, card_notes_protocol="refuse")
    if not any("JUDGES" in w for w in lane(v, "t-note")[1]):
        bad.append(f"15: refuse mode did not hold the card whose note judges its source: {lane(v, 't-note')}")
    gates(v)

    # 2, continued: the queued card is released when the card ahead is applied
    T.edit_card(v, T.CHOICE, status="approved")
    T.ledger(v, 2, "Reflection and Choice")
    r = T.run(v, "apply-card.py", T.CHOICE, "--write")
    if "t-dup" not in r.stderr or show(v, "t-dup").get("queuedBehind"):
        bad.append("2: the card queued behind (d) was not released when (d) was applied: " + r.stderr[-400:])

    # 12
    before = T.run(v, "cards.py", "list").stdout
    r = T.run(v, "cards.py", "split-by-day", "--write")
    days = sorted((v / "Fact Check" / "Cards").glob("cards-*.jsonl"))
    if r.returncode != 0 or not days or (v / T.STORE_REL).exists() or T.run(v, "cards.py", "list").stdout != before:
        bad.append("12: split-by-day did not keep every card: " + r.stdout[-300:])
    add(v, card("t-after", L3.replace("first", "opening"), **FULL, changeList=[{"after": "x", "why": "t"}]))
    if show(v, "t-after").get("_version") != 1 or (v / T.STORE_REL).exists():
        bad.append("12: a card written after the split did not go to a day file")

T.finish("card-rules", bad,
         "card rules: pointer, overlap, format-only, summary and choice gates warn or refuse; Approve waits with Undo; "
         "choices record their own text; Keep it the way it is closes; three versions stop and Bring it back lifts; "
         "only the writer withdraws; a hold survives a version; release takes a PASS or a fix list; a queued card "
         "goes up when the card ahead is in; the store splits by day; the desk draws italics and a chapter page")

#!/usr/bin/env python3
"""card_closed_test.py — tools/check-card-closed.py holds a card on a line the author approved, and passes the rest.

On a copy of the sample vault and its page snapshot. Requires:
  1. card (c), on the Chapter 1 paragraph the applied card (a) changed, is
     held, and the finding names card (a) by its title;
  2. cards (b) and (d), on lines nobody approved, pass;
  3. a saved Approve press on card (d) holds it (a later version written over
     an approval), and a later saved "reopen" press lifts it;
  4. an edit.applied event by the author on card (d)'s line holds (d), and
     --page-only does not see that event;
  5. the author's decision.recorded named in reopenedBy, dated after the
     closing, lets (d) through;
  6. a chapter in book.toml [workflow] out_of_workflow is skipped;
  7. --card checks one card file against the snapshot.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cardtest as T  # noqa: E402

bad = []


def results(v, *args):
    r = T.run(v, "check-card-closed.py", "--json", *args)
    if "Traceback" in r.stderr:
        bad.append("check-card-closed crashed:\n" + r.stderr[-800:])
    return r.returncode, {x["card"]: x for x in T.rows(r)}


def log(v, code):
    r = subprocess.run([sys.executable, "-c", "import sys, json; sys.path.insert(0, sys.argv[1]); "
                        "import vaultlog, bookconfig as B; " + code, str(T.TOOLS)],
                       env=dict(os.environ, BOOK_VAULT=str(v)), capture_output=True, text=True, check=True)
    return r.stdout.strip()


with T.sample_copy() as v:
    rc, got = results(v)
    c = got.get(T.ON_CLOSED)
    if not c or c["ok"]:
        bad.append(f"card (c) was not held: {c}")
    elif not any("Paine's two words: cite the section" in x["said"]
                 for f in c["findings"] for x in f["closedBy"]):
        bad.append(f"card (c) was held without naming the applied card (a): {c['findings']}")
    for cid in (T.NOTE_ARGUES, T.CHOICE):
        if not got.get(cid, {}).get("ok"):
            bad.append(f"{cid} was held: {got.get(cid)}")
    if T.APPLIED in got:
        bad.append("the applied card was checked as an open card")
    if rc != 1:
        bad.append(f"exit {rc} with a held card, expected 1")

    # 7. --card
    r = T.run(v, "check-card-closed.py", "--card", T.card_path(v, T.ON_CLOSED), "--json")
    if r.returncode != 1 or len(T.rows(r)) != 1:
        bad.append(f"--card on card (c) did not hold exactly that card: {r.stdout[-300:]}")

    # 3. presses
    presses = v / T.SNAP_REL / "presses"

    def press(action, at):
        (presses / f"{at.replace(':', '-')}_{T.CHOICE}_{action}.json").write_text(json.dumps(
            {"card": T.CHOICE, "title": "t", "button": action, "action": action, "at": at,
             "result": "saved", "reason": ""}), encoding="utf-8")
    press("approve", "2026-10-13T16:00:00.000Z")
    _, got = results(v)
    if got.get(T.CHOICE, {}).get("ok", True):
        bad.append("a saved Approve press on card (d) did not hold it")
    press("reopen", "2026-10-13T16:05:00.000Z")
    _, got = results(v)
    if not got.get(T.CHOICE, {}).get("ok"):
        bad.append(f"a later saved reopen press did not lift the hold: {got.get(T.CHOICE)}")

    # 4. an edit.applied by the author on (d)'s paragraph
    log(v, "vaultlog.append('edit.applied', actor=B.AUTHOR_ACTOR, block_id='3204ff', "
           "coord='Ch02/L5', sheet='', item='', old='', new='', why='the author ruled: use my words')")
    _, got = results(v)
    d = got.get(T.CHOICE, {})
    if d.get("ok", True):
        bad.append("an edit.applied ruling of the author's on (d)'s line did not hold (d)")
    _, got = results(v, "--page-only")
    if not got.get(T.CHOICE, {}).get("ok"):
        bad.append("--page-only saw an event-log closing")

    # 5. reopenedBy. Event times are to the second, and a reopening must come
    # after the closing it lifts.
    import time
    time.sleep(1.1)
    h = log(v, "e = vaultlog.append('decision.recorded', actor=B.AUTHOR_ACTOR, sheet='Source Rulings', "
               "item='ch02-reflection-choice', text='reopen this line'); print(e['hash'])")
    T.edit_card(v, T.CHOICE, reopenedBy=h)
    _, got = results(v)
    if not got.get(T.CHOICE, {}).get("ok"):
        bad.append(f"the author's reopening in reopenedBy did not let (d) through: {got.get(T.CHOICE)}")

    # 6. out of workflow
    toml = v / "book.toml"
    toml.write_text(toml.read_text(encoding="utf-8").replace("out_of_workflow = []", "out_of_workflow = [1]"),
                    encoding="utf-8")
    _, got = results(v)
    if T.ON_CLOSED in got:
        bad.append("a card in an out-of-workflow chapter was checked")

T.finish("check-card-closed", bad,
         "closed lines: the card on the applied paragraph is held and names the applied card; open lines pass; "
         "presses, the author's edits and reopenings, and out-of-workflow chapters behave")

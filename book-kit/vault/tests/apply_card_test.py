#!/usr/bin/env python3
"""apply_card_test.py — tools/apply-card.py applies one approved card, on a copy of the sample vault.

Card (d) corrects "reflection and design" to "reflection and choice" in
Chapter 2 and trims [^fed1_test] to its citation. Requires:
  1. the dry run prints the whole Current and Proposed of both lines and
     changes no file;
  2. --write refuses while the card is not approved, and changes no file;
  3. --write refuses a chapter locked in Fact Check/Locks.md;
  4. --write refuses when a `current` text differs from the chapter on disk;
  5. once approved, --write changes both lines, keeps their block ids, logs
     edit.applied events naming the card, and writes the ledger's apply entry;
  6. a second --write finds nothing to change.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cardtest as T  # noqa: E402

DESIGN = "establishing good government from reflection and design"
CHOICE = "establishing good government from reflection and choice"

bad = []
with T.sample_copy() as v:
    ch2 = next((v / "Chapters").glob("Chapter 02 *.md"))
    text0 = ch2.read_text(encoding="utf-8")
    ids0 = re.findall(r"<!-- b:([0-9a-f]{6}) -->", text0)
    L5 = text0.split("\n")[4]
    bid5 = re.search(r"b:([0-9a-f]{6})", L5).group(1)
    T.ledger(v, 2, "Reflection and Choice")

    # 1
    before = T.files(v)
    r = T.run(v, "apply-card.py", T.CHOICE)
    out = r.stdout
    if r.returncode != 0 or "Traceback" in r.stderr:
        bad.append("the dry run failed: " + (out + r.stderr)[-500:])
    if out.count("CURRENT") != 2 or out.count("PROPOSED") != 2 or DESIGN not in out or CHOICE not in out:
        bad.append("the dry run did not print both lines' Current and Proposed in full:\n" + out[-800:])
    if "This shows that the founders" not in out or '[^fed1_test]: Hamilton, *Federalist* No. 1, "General Introduction."' not in out:
        bad.append("the dry run did not show the note's Current and Proposed")
    if "--write would refuse" not in out or "status is yours" not in out:
        bad.append("the dry run of an unapproved card did not say --write would refuse it")
    if before != T.files(v):
        bad.append("THE DRY RUN WROTE TO DISK")

    # 2
    r = T.run(v, "apply-card.py", T.CHOICE, "--write")
    if r.returncode != 1 or before != T.files(v):
        bad.append("--write applied a card the author has not approved")

    T.edit_card(v, T.CHOICE, status="approved", approvedAt="2026-10-13T15:30:00Z")
    # 3
    locks = v / "Fact Check" / "Locks.md"
    locks.write_text("# Locks\n\n| chapter | state | date | by | note |\n|---|---|---|---|---|\n"
                     "| 2 | 🔒 | 2026-10-13 | production | test |\n", encoding="utf-8")
    before = T.files(v)
    r = T.run(v, "apply-card.py", T.CHOICE, "--write")
    if r.returncode != 1 or "locked" not in r.stdout or before != T.files(v):
        bad.append("--write applied a card to a locked chapter: " + r.stdout[-300:])
    locks.write_text(locks.read_text(encoding="utf-8").replace("| 2 | 🔒 |", "| 2 | 🔓 |"), encoding="utf-8")

    # 4
    card = json.loads(T.card_path(v, T.CHOICE).read_text(encoding="utf-8"))
    stale = [dict(card["current"][0], text=card["current"][0]["text"].replace("accident and force", "accident and chance")),
             card["current"][1]]
    T.edit_card(v, T.CHOICE, current=stale)
    before = T.files(v)
    r = T.run(v, "apply-card.py", T.CHOICE, "--write")
    if r.returncode != 1 or "differs from the chapter on disk" not in r.stdout or before != T.files(v):
        bad.append("--write applied a card whose current text differs from the chapter: " + r.stdout[-300:])
    T.edit_card(v, T.CHOICE, current=card["current"])

    # 5
    r = T.run(v, "apply-card.py", T.CHOICE, "--write")
    if r.returncode != 0:
        bad.append("--write failed on the approved card: " + (r.stdout + r.stderr)[-800:])
    text1 = ch2.read_text(encoding="utf-8")
    lines = text1.split("\n")
    if CHOICE not in lines[4] or f"<!-- b:{bid5} -->" not in lines[4]:
        bad.append(f"the paragraph was not changed with its block id kept: {lines[4]}")
    if DESIGN in text1 or "This shows that" in text1:
        bad.append("the old words are still in the chapter")
    if re.findall(r"<!-- b:([0-9a-f]{6}) -->", text1) != ids0:
        bad.append("the chapter's block ids changed")
    ev = [json.loads(l) for f in (v / "Fact Check" / "events").glob("*.jsonl")
          for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    applied = [e for e in ev if e.get("kind") == "edit.applied" and e.get("item") == T.CHOICE]
    if len(applied) != 2:
        bad.append(f"expected 2 edit.applied events naming the card, got {len(applied)}")
    led = T.ledger(v, 2, "Reflection and Choice").read_text(encoding="utf-8")
    if f"card {T.CHOICE} applied" not in led or CHOICE not in led:
        bad.append("the ledger has no apply entry for the card")
    if '"status": "applied"' not in r.stdout:
        bad.append("the run did not print the page patch")

    # 6
    before = T.files(v)
    r = T.run(v, "apply-card.py", T.CHOICE, "--write")
    if r.returncode != 0 or "Nothing to change" not in r.stdout or before != T.files(v):
        bad.append("a second --write changed something: " + r.stdout[-300:])

T.finish("apply-card", bad,
         "apply-card: the dry run shows Current and Proposed whole and writes nothing; unapproved, locked "
         "and stale cards are refused; the approved card changes both lines, keeps the block ids, logs and "
         "writes the ledger entry; a second run changes nothing")

#!/usr/bin/env python3
"""card_log_test.py — tools/card-log.py on a copy of the sample vault, run twice, and check-card-logged.py after it.

Requires, each a way this tool could go wrong:
  1. The sample mode writes nothing.
  2. A read already in Claims gets no second row; a new read gets exactly one,
     at the line number the ledger section says.
  3. Two cards in one run naming the same new read add ONE row.
  4. Each card gets one ledger section and one event per read.
  5. A second --write run finds nothing to do.
  6. check-card-logged.py passes the logged cards and fails an unlogged one.
  7. More than five changes are refused with no UAT acceptance line.
The two cards are the sample snapshot's Chapter 2 cards (b) and (d); card (c)
in Chapter 1 has no read list.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cardtest as T  # noqa: E402

bad = []
with T.sample_copy() as v:
    T.ledger(v, 2, "Reflection and Choice")
    claims = v / "Fact Check" / "Claims" / "Ch 02.jsonl"
    old = {"author": "Alexander Hamilton", "title": "The Federalist Papers",
           "location": "No. 1, \"General Introduction,\" paragraph 1", "ref": "Ch02/L3",
           "drive_path": "PDF/Hamilton Madison Jay - The Federalist Papers.txt",
           "states": "The paper is addressed \"To the People of the State of New York\".",
           "reader": "Claude, the Fact-checker", "date_read": "2026-10-01"}
    claims.write_text(json.dumps(old) + "\n", encoding="utf-8")
    new = dict(old, location="No. 1, \"General Introduction,\" paragraph 1, the question of reflection and choice",
               ref="Ch02/L5", states="\"from reflection and choice\"")
    new.pop("reader"), new.pop("date_read")
    cards = v / "Handoffs" / "editor-tools" / "cards"
    cards.mkdir(parents=True, exist_ok=True)
    (cards / f"{T.CHOICE}.reads.json").write_text(json.dumps(
        {"card": T.CHOICE, "title": "Ch 02 · Hamilton wrote \"reflection and choice\"", "chapter": 2,
         "reads": [old, new]}), encoding="utf-8")
    (cards / f"{T.NOTE_ARGUES}.reads.json").write_text(json.dumps(
        {"card": T.NOTE_ARGUES, "title": "Ch 02 · [^fed1_test]", "chapter": 2,
         "reads": [new]}), encoding="utf-8")
    args = [cards / f"{T.CHOICE}.reads.json", cards / f"{T.NOTE_ARGUES}.reads.json"]
    n0 = 1

    # 1. the sample writes nothing
    before = T.files(v)
    r = T.run(v, "card-log.py", *args)
    if r.returncode != 0:
        bad.append("sample run failed: " + (r.stderr or r.stdout)[-400:])
    if before != T.files(v):
        bad.append("THE SAMPLE MODE WROTE TO DISK")

    # 7. 1 row + 2 ledger sections + 3 events = 6 changes, refused without acceptance
    r = T.run(v, "card-log.py", "--write", *args)
    if r.returncode == 0 or "REFUSING" not in (r.stdout + r.stderr):
        bad.append("a write of more than five changes ran with no UAT acceptance")
    if len(claims.read_text(encoding="utf-8").splitlines()) != n0:
        bad.append("the refused run still wrote a Claims row")

    (v / "Methodology").mkdir(exist_ok=True)
    (v / "Methodology" / "UAT Log.md").write_text(
        "| date | tool | what | verdict |\n|---|---|---|---|\n"
        "| 2026-01-01 | `tools/card-log.py` | test | ACCEPTED |\n", encoding="utf-8")
    r = T.run(v, "card-log.py", "--write", *args)
    if r.returncode != 0:
        bad.append("write run failed: " + (r.stdout + r.stderr)[-600:])
    lines = claims.read_text(encoding="utf-8").splitlines()
    # 2 and 3
    if len(lines) != n0 + 1:
        bad.append(f"expected exactly one new Claims row, got {len(lines) - n0}")
    elif json.loads(lines[-1]).get("ref") != "Ch02/L5":
        bad.append("the new row is not the new read")
    led = T.ledger(v, 2, "Reflection and Choice").read_text(encoding="utf-8")
    for cid in (T.CHOICE, T.NOTE_ARGUES):
        c = led.count(f"the sources named on card {cid}:")
        if c != 1:
            bad.append(f"card {cid}: {c} ledger sections, expected 1")
    if f"Ch 02.jsonl` line {n0 + 1}, new row" not in led:
        bad.append("the ledger does not give the new row's real line number")
    if "line 1, already there" not in led:
        bad.append("the ledger does not point at the existing row 1")
    # 4
    ev = [json.loads(l) for f in (v / "Fact Check" / "events").glob("*.jsonl")
          for l in f.read_text(encoding="utf-8").splitlines() if '"source.read"' in l]
    if len(ev) != 3:
        bad.append(f"expected 3 source.read events (2 for card d, 1 for card b), got {len(ev)}")
    # 5
    before = T.files(v)
    r = T.run(v, "card-log.py", "--write", *args)
    if "Nothing to write" not in r.stdout or before != T.files(v):
        bad.append("A SECOND RUN CHANGED SOMETHING — the tool cannot be run twice")
    # 6
    r = T.run(v, "check-card-logged.py", "--json")
    kinds = {(o["card"], o["kind"]) for o in T.rows(r)}
    if (T.ON_CLOSED, "NO READ LIST") not in kinds:
        bad.append(f"check-card-logged did not fail the card with no read list: {kinds}")
    if any(c in (T.CHOICE, T.NOTE_ARGUES) for c, _ in kinds):
        bad.append(f"check-card-logged failed a card that is logged: {kinds}")
    if any(c == T.APPLIED for c, _ in kinds):
        bad.append("check-card-logged checked the applied card")
    if r.returncode == 0:
        bad.append("check-card-logged exited 0 with a fault present")

T.finish("card-log", bad,
         "card-log: sample writes nothing, bulk refused without acceptance, one row per read, "
         "one section per card, a second run changes nothing, and the check tells logged from unlogged")

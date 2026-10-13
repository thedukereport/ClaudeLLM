#!/usr/bin/env python3
"""card_notes_test.py — tools/check-card-notes.py refuses a note that argues, and passes a citation.

On a copy of the sample vault and its page snapshot. Requires:
  1. card (b), which proposes [^fed1_test] with its sentence of interpretation
     and changes no paragraph, is refused, and the finding names that sentence;
  2. card (d), whose note is citation only, passes;
  3. a card that proposes prose for a note the author ruled citations only
     (a note.ruled event in the copy's log) is refused, citing the ruling;
  4. --patch-dir writes a noteCheck for each card that proposes a note, and
     changes nothing else;
  5. the applied card (a) and card (c), which proposes no note, are not checked.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cardtest as T  # noqa: E402

bad = []
with T.sample_copy() as v:
    r = T.run(v, "check-card-notes.py", "--json")
    if "Traceback" in r.stderr:
        bad.append("check-card-notes crashed:\n" + r.stderr[-800:])
    got = {x["card"]: x for x in T.rows(r)}
    b = got.get(T.NOTE_ARGUES)
    if not b or b["ok"]:
        bad.append(f"card (b) was not refused: {b}")
    elif not any("This shows that the founders" in f["clause"] for f in b["findings"]):
        bad.append(f"card (b) was refused without naming the interpretation sentence: {b['findings']}")
    d = got.get(T.CHOICE)
    if not d or not d["ok"]:
        bad.append(f"card (d), citation only, was refused: {d}")
    if T.APPLIED in got or T.ON_CLOSED in got:
        bad.append("an applied card, or a card with no note, was checked")
    if r.returncode != 1:
        bad.append(f"exit {r.returncode} with a refused card, expected 1")

    # 3. a ruling the card contradicts
    subprocess.run([sys.executable, "-c",
                    "import sys; sys.path.insert(0, sys.argv[1]); import vaultlog, bookconfig as B; "
                    "vaultlog.append('note.ruled', actor=B.AUTHOR_ACTOR, chapter=2, slug='fed1_heading', "
                    "note_kind='citations_only', text='citations only')", str(T.TOOLS)],
                   env=dict(os.environ, BOOK_VAULT=str(v)), check=True)
    card = {"title": "Ch 02 · test card", "chapter": "Ch 02", "status": "yours", "noteless": True,
            "reviewedPara": "[^fed1_heading]: Hamilton wrote the paper to win New York, and every reader since has taken it at his word.",
            "proposedPara": ""}
    p = v / "ruled.json"
    p.write_text(json.dumps(card), encoding="utf-8")
    r = T.run(v, "check-card-notes.py", "--card", p, "--json")
    rr = T.rows(r)
    if r.returncode != 1 or not rr or not any(f["pile"] == "RULING" and "citations only" in f["why"]
                                                for f in rr[0]["findings"]):
        bad.append(f"a card against the citations-only ruling passed: {rr} {r.stderr[-300:]}")

    # 4. --patch-dir
    before = T.files(v)
    pd = v.parent / "patches"
    T.run(v, "check-card-notes.py", "--patch-dir", pd)
    if T.files(v) != before:
        bad.append("--patch-dir changed a file in the vault")
    names = sorted(x.stem for x in pd.glob("*.json"))
    if names != sorted([T.NOTE_ARGUES, T.CHOICE]):
        bad.append(f"--patch-dir wrote {names}")
    else:
        nc = json.loads((pd / f"{T.NOTE_ARGUES}.json").read_text())["noteCheck"]
        if nc["ok"] or not nc["text"].startswith("[^fed1_test]:"):
            bad.append(f"the noteCheck for card (b) is wrong: {nc}")

T.finish("check-card-notes", bad,
         "card notes: the note that argues is refused and named; the citation-only note passes; "
         "a card against a ruling is refused; --patch-dir writes only patches")

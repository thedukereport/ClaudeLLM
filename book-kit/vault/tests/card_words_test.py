#!/usr/bin/env python3
"""card_words_test.py — the banned-word check on card text, on a copy of the sample vault.

Replaces the copy's page snapshot with six made-up cards and writes the
copy a one-word list (the `carry` family, as the starter list has it), so the
test measures the card check and not the list's contents. Requires:
  1. a banned word in the card's own proposed text is reported;
  2. the same word inside double quotation marks is not;
  3. a word the card copies word for word from the chapter text (`current`)
     is not reported, and is counted as the chapter's;
  4. a word in the author's own submitted text is not;
  5. an applied card is not read at all;
  6. the reviewed text is read in place of the proposed text when set;
  7. with no word list the check says it did not run (exit 2).
And on the sample snapshot itself: card (c) removes "carries" and offers no
banned word, and the applied card (a), whose text holds "carries", is not read.
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cardtest as T  # noqa: E402

S = "The essay carried the claim forward to the court."
CARDS = {
    "c1": {"status": "yours", "proposedPara": S, "current": []},
    "c2": {"status": "yours", "proposedPara": 'He wrote that "the river carried the dead" in 1851.',
           "current": []},
    "c3": {"status": "yours", "proposedPara": S + " A new sentence follows.",
           "current": [{"where": "Ch01/L1", "text": S}]},
    "c4": {"status": "submitted", "proposedPara": S, "submittedPara": S, "current": []},
    "c5": {"status": "applied", "proposedPara": S, "current": []},
    "c6": {"status": "approved", "proposedPara": "Clean text.", "reviewedPara": S,
           "current": []},
}

bad = []
with T.sample_copy() as v:
    wl = v / "Methodology" / "Word Lists.md"
    wl.parent.mkdir(parents=True, exist_ok=True)
    wl.write_text("# Word Lists\n\n<!-- BANNED-WORDS-MACHINE-LIST:BEGIN -->\n```\n"
                  "\\bcarr(y|ies|ied|ying)\\b ;; literal physical carrying; quoted\n"
                  "```\n<!-- BANNED-WORDS-MACHINE-LIST:END -->\n", encoding="utf-8")

    r = T.run(v, "check-card-words.py", "--json")
    if "Traceback" in r.stderr:
        bad.append("check-card-words crashed on the sample snapshot:\n" + r.stderr[-800:])
    hits = {x["card"] for x in T.rows(r)}
    if hits:
        bad.append(f"the sample snapshot's cards were reported: {sorted(hits)}")

    props = v / T.SNAP_REL / "proposals"
    shutil.rmtree(props)
    props.mkdir()
    for cid, d in CARDS.items():
        d = dict(d, title=f"Ch 01 · test {cid}", where="Ch01/L1", chapter="Ch 01")
        (props / f"{cid}.json").write_text(json.dumps(d), encoding="utf-8")
    r = T.run(v, "check-card-words.py", "--json")
    if "Traceback" in r.stderr:
        bad.append("check-card-words crashed:\n" + r.stderr[-800:])
    got = {x["card"] for x in T.rows(r)}
    r2 = T.run(v, "check-card-words.py")
    if got != {"c1", "c6"}:
        bad.append(f"reported cards {sorted(got)}, expected ['c1', 'c6']")
    if r.returncode != 1:
        bad.append(f"exit {r.returncode} with hits present, expected 1")
    if "1 more stand word for word in the chapter" not in r2.stdout:
        bad.append("the word copied from the chapter was not counted as the chapter's:\n"
                   + r2.stdout[-300:])

    wl.unlink()
    r = T.run(v, "check-card-words.py")
    if r.returncode != 2 or "NOT RUN" not in r.stdout:
        bad.append(f"with no word list the check did not say it did not run: {r.returncode} {r.stdout[-200:]}")

T.finish("check-card-words", bad,
         "card words: the card's own banned word is caught; quoted, chapter, the author's own "
         "and applied text are not; reviewed text is read; no word list means NOT RUN")

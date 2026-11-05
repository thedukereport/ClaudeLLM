# Practise on the sample book

`book-kit/sample/` is a two-chapter book about Paine's *Common Sense* and *Federalist* No. 1, with its own library (`sample/library/PDF/`) and four faults planted on purpose. Run every command here from the `book-kit` folder on a copy, so the sample stays as it is:

```
cp -r sample /tmp/practice
export BOOK_VAULT=/tmp/practice          # Windows PowerShell: $env:BOOK_VAULT="C:\temp\practice"
T=vault/tools
```

## Fault 4: a read nobody logged (the Fact-checker)

```
python3 $T/check-read.sh
```
Each cited work is UNREAD: it is in the library and no Claims row names a reader. The Fact-checker opens the source and reads the passage whole:
```
python3 $T/have.sh "The Federalist Papers"
python3 $T/find-source.sh "reflection and choice"
```
`find-source` prints Hamilton's sentence: "…establishing good government from reflection and choice…". The Fact-checker writes what it read as a Claims row (`Fact Check/Claims/README.md` has the fields), a section in the chapter's ledger and a `source.read` event, in the same turn.

## Fault 1: a quotation that differs from its source (Fact-checker, then Editor)

Chapter 2 quotes Hamilton as writing "from reflection and design". The source says "reflection and choice". The Fact-checker records what the source says, and hands the finding to the Editor in `Handoffs/Editor.md`. The Editor builds a card. The sample's card store already holds one, `ch02-reflection-choice`:
```
python3 $T/cards.py list
python3 $T/cards.py show ch02-reflection-choice
```
Open the card desk on the copy and look at it:
```
python3 $T/card-desk.py --port 8767        # then open http://127.0.0.1:8767 ; Ctrl-C stops it
```
The card waits under **With Claude**, with two reasons: the quotation on it has no logged read, and no second session has audited its prose. You see only cards that are ready. The Editor logs the card's reads:
```
python3 $T/card-log.py         /tmp/practice/Handoffs/editor-tools/cards/ch02-reflection-choice.reads.json   # shows
python3 $T/card-log.py --write /tmp/practice/Handoffs/editor-tools/cards/ch02-reflection-choice.reads.json
python3 $T/card_reads.py --card ch02-reflection-choice                                                        # 0 unread
```
The sample already holds the card's reads file: the card's id, title and chapter, and each read with the same fields as a Claims row (`tools/cardlib.py` has the shape). For your own cards the Editor writes it. The first run shows what it would write; the second writes it; run it a third time and it finds nothing to do.

Then a second session audits the card's prose under the neurolinguistic-prose skill and records it. In practice you can play both sessions by naming them (`BOOK_SESSION`); make `f.json` with each of the fifteen principles from `tools/prose.py` (`PRINCIPLES`) as a key and its finding as the value:
```
BOOK_SESSION=sample-editor python3 $T/prose.py --record-card ch02-reflection-choice --findings f.json --verdict ok
python3 $T/prose.py            # SELF: the session that wrote the card audited it
BOOK_SESSION=qa python3 $T/prose.py --record-card ch02-reflection-choice --findings f.json --verdict ok
python3 $T/prose.py            # ok: a second session audited it
```
(The sample card was written by a session named `sample-editor`. In your own sessions Claude Code gives each one its id, and `tools/prose.py` reads it.) Reload the desk: the card is under **Waiting for you**.

## You approve; Production applies

On the desk, press **Approve for the chapter**. The press is one `decision.recorded` event in `Fact Check/events/`; `tools/cards.py list` now shows the card `approved`. Then Production:
```
python3 $T/apply-card.py ch02-reflection-choice            # Current and Proposed in full, nothing written
python3 $T/apply-card.py ch02-reflection-choice --write    # applies, keeps the block ids, writes the ledger entry
```
It marks the card applied in the store, and then looks at the chapter's other open cards. The card `ch02-fed1-note-interpretation` proposes a new text for the note this card just changed, so it no longer reads as the chapter does: the refresh reports it "back", and the desk holds it under With Claude. That is a collision caught (`tools/card_refresh.py --chapter 2`).

## Fault 2: a footnote that holds an argument (the Editor)

```
python3 $T/check-note-content.py
python3 $T/assess-notes.py
```
`[^fed1_test]` ends "This shows that the founders saw the Constitution as a philosophical experiment…": a claim, in a note whose job is to say where the words are. The card above already cuts the note to its citation. The store's other card on that note, `ch02-fed1-note-interpretation`, proposes the argument again; `check-card-notes.py` refuses it, and the desk holds it.

## Fault 3: a banned word (the Editor)

```
python3 $T/check-banned-words.sh
```
Chapter 1, line 5: "The sentence carries the whole pamphlet's frame." The word list is `Methodology/Word Lists.md`. The fix is a card; so is a ruling to keep the word (`Fact Check/Banned-Word Rulings.md`).

## A line you approved

```
python3 $T/check-card-closed.py
```
The card `ch01-carries-sentence` is held: it changes Chapter 1's paragraph, which the applied card `ch01-paine-society-cite` already changed. Once its gates pass, the desk shows it in the **Reopen?** lane, whole, with "Reopen this line" and "Keep it closed". A line you approved does not come back for a better word; it comes back there when a reading shows it wrong.

## Locking

```
python3 $T/preflight.sh 2
python3 $T/check-lock-ready.sh 2
python3 $T/lock.py status
```
`check-lock-ready` lists what blocks the lock: open cards, unread works, banned words, footnote faults. When it passes, `python3 $T/lock.py lock 2 --by production` locks the chapter in `Fact Check/Locks.md`.

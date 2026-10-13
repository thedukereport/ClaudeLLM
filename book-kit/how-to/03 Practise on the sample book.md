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

Chapter 2 quotes Hamilton as writing "from reflection and design". The source says "reflection and choice". The Fact-checker records what the source says, and hands the finding to the Editor in `Handoffs/Editor.md`. The Editor builds a card. The sample snapshot already holds one: `ch02-reflection-choice`. The Editor lists the card's reads and logs them:
```
python3 $T/card-log.py        /tmp/practice/Handoffs/editor-tools/cards/ch02-reflection-choice.reads.json   # shows
python3 $T/card-log.py --write /tmp/practice/Handoffs/editor-tools/cards/ch02-reflection-choice.reads.json
```
The sample already holds the card's reads file, `ch02-reflection-choice.reads.json`: the card's id, title and chapter, and each read with the same fields as a Claims row (`tools/cardlib.py` has the shape). For your own cards the Editor writes it. The first run shows what it would write; the second writes it; run it a third time and it finds nothing to do. Then the two gates every card passes before it goes on the page:
```
python3 $T/check-card-notes.py  --card /tmp/practice/Handoffs/editor-tools/page-snapshot/proposals/ch02-reflection-choice.json
python3 $T/check-card-closed.py --card /tmp/practice/Handoffs/editor-tools/page-snapshot/proposals/ch02-reflection-choice.json
```

## You approve; Production applies

On the real page you press Approve. To practise, mark the card approved in the snapshot copy (set `"status": "approved"` in its JSON) and refresh the snapshot time (`date -u +%Y-%m-%dT%H:%M:%S+00:00 > /tmp/practice/Handoffs/editor-tools/page-snapshot/TAKEN`). Then Production:
```
python3 $T/apply-card.py ch02-reflection-choice            # Current and Proposed in full, nothing written
python3 $T/apply-card.py ch02-reflection-choice --write    # applies, keeps the block ids, writes the ledger entry
```
It prints the update for the card on the page (`status: applied`).

## Fault 2: a footnote that holds an argument (the Editor)

```
python3 $T/check-note-content.py
python3 $T/assess-notes.py
```
`[^fed1_test]` ends "This shows that the founders saw the Constitution as a philosophical experiment…": a claim, in a note whose job is to say where the words are. The card above already cuts the note to its citation. The snapshot's other card on that note, `ch02-fed1-note-interpretation`, proposes the argument again; `check-card-notes.py` refuses it.

## Fault 3: a banned word (the Editor)

```
python3 $T/check-banned-words.sh
```
Chapter 1, line 5: "The sentence carries the whole pamphlet's frame." The word list is `Methodology/Word Lists.md`. The fix is a card; so is a ruling to keep the word (`Fact Check/Banned-Word Rulings.md`).

## Closed is closed

```
python3 $T/check-card-closed.py --page-only
```
The card `ch01-carries-sentence` is held: it changes Chapter 1's paragraph, which the applied card `ch01-paine-society-cite` already changed. The page hides it from every view except All. A line you approved does not come back to you.

## Locking

```
python3 $T/preflight.sh 2
python3 $T/check-lock-ready.sh 2
python3 $T/lock.py status
```
`check-lock-ready` lists what blocks the lock: open cards, unread works, banned words, footnote faults. When it passes, `python3 $T/lock.py lock 2 --by production` locks the chapter in `Fact Check/Locks.md`.

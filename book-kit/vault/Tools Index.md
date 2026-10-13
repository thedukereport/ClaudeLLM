# Tools Index

Each script in `tools/`, in its own words (its first docstring line), with who runs it. Run any tool from the vault folder, for example `python3 tools/have.sh "Common Sense"` or `tools/check-read.sh 2`. Every tool reads its paths from `book.toml` through `tools/bookconfig.py`. Add a row here when you add a script.

## Settings and the record

| Script | What it does | Run by |
|---|---|---|
| `bookconfig.py` | the one place every tool learns where the book lives | every tool; run it alone to print your settings |
| `vaultlog.py` | the append-only, hash-chained event log that every tool writes to | every writing tool; `--verify` checks the chain |
| `witness.py` | lists files that changed with no logged event saying why | Systems, the Watcher; `--seal` once on a clean vault |
| `uat.py` | nothing writes at scale until the author has accepted a sample | every tool that writes more than five things |
| `smoke-test.sh` | run every tool in its safe mode, then every test, and report what broke | Systems, before every hand-back |

## The chapters' text

| Script | What it does | Run by |
|---|---|---|
| `blockid.py` | gives every block in a chapter a block id that survives editing | once after chapters are added; again for new text |
| `blocks.py` | finds where a block of chapter text is now, by its block id | the card tools |
| `blockedit.py` | the only way a chapter line is rewritten; it owns the block id | Production, through `apply-card.py` |
| `apply-card.py` | Production applies one approved card from the page snapshot to its chapter | Production |
| `show.sh` | print a manuscript line inside its context, before proposing any change | Editor, Production |

## The library and the reads

| Script | What it does | Run by |
|---|---|---|
| `have.sh` | the one search that answers "is this work in the library?" | Fact-checker, Editor |
| `find-source.sh` | look for a passage or a book across the whole library | Fact-checker |
| `find-page.sh` | what page is this passage on, in the print edition? | Fact-checker |
| `check-read.sh` | every work the chapters cite, and whether anyone opened it | Fact-checker; the lock check |
| `check-drive-path.sh` | every drive_path recorded in Claims opens, or the run fails | Fact-checker, Systems |
| `resolve-sources.sh` | find the file in the library for each work the book cites | Fact-checker |
| `citedworks.py` | the works the chapters cite, and the Claims records about them | imported by the read tools |
| `preflight.sh` | print the sources in front of Claude before a chapter is touched | each role, before a chapter |

## Language and footnotes

| Script | What it does | Run by |
|---|---|---|
| `check-banned-words.sh` | report banned-word hits in the chapters, for reading | Editor; the lock check |
| `check-epistemics.sh` | flag borrowed authority, pre-emptive retreat and their kin, for reading | Editor; the lock check |
| `wordlists.py` | the one loader for the machine lists in `Methodology/Word Lists.md` | imported by the word checks |
| `rulings.py` | one place where "the author already ruled on this" is decided | imported by the word checks |
| `check-footnotes.sh` | check footnote structure: orphans, unanchored or doubled notes, self-talk, verdicts, length | Editor; the lock check |
| `check-footnote-length.sh` | report footnotes over the word cap, once each | Editor; the lock check |
| `check-anchors.sh` | check that each footnote gives a reader a way to find the passage it cites | Editor, Fact-checker |
| `check-note-content.py` | find footnote sentences that hold body content instead of a citation | Editor |
| `assess-notes.py` | split every footnote into sentences and sort each one into six piles | Editor |
| `notelib.py` | small helpers the footnote checks share | imported |
| `check-ellipsis.sh` | print the words an ellipsis took out of a quotation, when the source is in the library | Fact-checker |
| `check-crossrefs.sh` | check that each "Chapter N" cross-reference points at the right chapter | Editor; the lock check |
| `check-glossary.sh` | check that each term of art is glossed where the reader first meets it | Editor |

## Cards and the Source Rulings page

| Script | What it does | Run by |
|---|---|---|
| `cardlib.py` | the one place that says whether a card's reads are on record | imported by the card tools |
| `card-log.py` | put the sources a card names on record, in the turn the card is written | Editor, per card |
| `check-card-logged.py` | no card reaches the author naming a read that is not on record | Editor; smoke test |
| `check-card-words.py` | never offer the author a banned word on a card | Editor; smoke test |
| `check-card-notes.py` | no card reaches the author with a footnote the author's rules send back | Editor, per card (`--card`) |
| `check-card-closed.py` | no card reaches the author on a line or note the author has already approved | Editor, per card (`--card`) |
| `dashboard-sync.py` | loads the Asks and Back-fill views of the page, and reads the author's presses back | Systems |

## Locks and output

| Script | What it does | Run by |
|---|---|---|
| `lock.py` | lock and unlock chapters; the one writer of `Fact Check/Locks.md` | Production |
| `check-lock-ready.sh` | say whether a chapter may be locked, and what blocks it | Production; `lock.py lock` runs it |
| `backup-to-github.sh` | push the chapters and the working files to the author's own GitHub repository | the author (pushing is the author's) |
| `snapshot-vault.sh` | copy the whole vault to another disk, then verify the copy | Systems, the author |
| `publish-pdfs.sh` | make a PDF of each chapter and appendix | Production, after a lock |

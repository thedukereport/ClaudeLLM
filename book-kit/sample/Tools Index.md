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
| `apply-card.py` | Production applies one approved card from the card store to its chapter, and marks it applied | Production |
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

## Cards and the card desk

| Script | What it does | Run by |
|---|---|---|
| `cards.py` | the cards (`Fact Check/Cards/`, one file, or one a day after `split-by-day --write`), and the one way a card goes in: `list`, `show`, `counts`, `add` (with every gate in `book.toml` `[gates]`), `applied` (refused inside the author's five-minute Undo; releases the cards queued behind), `hold`, `rehold`, `release` (the gates again, the second session's audit, the desk audit and the reviewer's verdict), `withdraw`, `supersede`, `review-pass`, `review-fix`, `lift-stop`, `desk-why` | Editor, QA, Production, Managing Editor |
| `card_shape.py` | the shape gates `cards.py` runs on each version: a pointer to another part of the book, a second open card on one paragraph, a formatting-only change, the TLDR, recommendation and reasons, choices that are one decision each, the answer to the author's directive. `card_shape.py <id>` lists them for one card | Editor, QA; `cards.py` |
| `review_pipeline.py` | six fresh reviewers read a card once before release: `packet` writes their prompts, `record` each verdict, `status` | Editor, QA |
| `desk_audit.py` | every page the author rules from, drawn with the desk's code and read for asterisks, role names, paths, codes and gate names; `--card <id>` for one card; `cards.py release` runs it | Systems, Editor; `cards.py` |
| `card-desk.py` | the one place the author rules: a server on http://127.0.0.1:8766 that shows Questions for you, then one card at a time (its answer, TLDR and recommendation first, each choice with its own Approve, What changed and why), runs every gate on it, and records each press in the event log; a chapter page (`/chapter/N`); also the Asks and Sources views. `--check` draws every page once; `--show <id>` prints a card as the author reads it | the author; smoke test; reviewers |
| `card_reads.py` | no card reaches the author with an unread fact in it: the names, numbers, dates and quotations in a card's passage that no opened read in `Fact Check/Claims/` holds | Editor, QA, Fact-checker; `cards.py` and the desk |
| `card_refresh.py` | after an apply, each other open card of the chapter gets its neighbours as on disk, or goes back to its owner (`book.toml` `[gates] card_refresh`) | `cards.py applied`; Systems |
| `cardlib.py` | the one place that says whether a card's reads are on record | imported by the card tools |
| `card-log.py` | put the sources a card names on record, in the turn the card is written | Editor, per card |
| `check-card-logged.py` | no card reaches the author naming a read that is not on record | Editor; smoke test |
| `check-card-words.py` | never offer the author a banned word on a card | Editor; smoke test |
| `check-card-notes.py` | no card reaches the author with a footnote the author's rules send back | Editor, per card (`--card`) |
| `check-card-closed.py` | no card reaches the author on a line or note the author has already approved, except through the desk's Reopen? lane | Editor, per card (`--card`); the desk |
| `prose.py` | records that the neurolinguistic-prose skill ran on a card's exact text, by which session and with what verdict, and lists the open cards without an audit by a second session | QA and Editor, on each other's cards (`--record-card`) |
| `dashboard-sync.py` | builds the card desk's Asks and Sources views, writes the author's presses there back into `Fact Check/Asks.md` and the Back-fill Queue, and writes the Fact-checker's reading queue (`queue`) | Systems; Fact-checker (`queue`) |

## Locks and output

| Script | What it does | Run by |
|---|---|---|
| `lock.py` | lock and unlock chapters; the one writer of `Fact Check/Locks.md` | Production |
| `check-lock-ready.sh` | say whether a chapter may be locked, and what blocks it | Production; `lock.py lock` runs it |
| `backup-to-github.sh` | push the chapters and the working files to the author's own GitHub repository | the author (pushing is the author's) |
| `snapshot-vault.sh` | copy the whole vault to another disk, then verify the copy | Systems, the author |
| `publish-pdfs.sh` | make a PDF of each chapter and appendix | Production, after a lock |

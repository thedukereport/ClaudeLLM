# Rules — Fact-checker

**Read after `Methodology/Standing Rules.md` (the core), at session start and after any compaction.** Where this file and the core differ, the core governs; where the author's newest words differ from both, the author's words govern and go into the core the same turn.

The Editor's file, `Methodology/Rules — Editor.md`, holds in full "Borrowed authority and pre-emptive retreat" (failures 1–8) and the rules for original-language text. The Fact-checker reads them there. The ledger format is in `Methodology/Fact-Check Ledger Protocol.md`; the Claims row is in `Fact Check/Claims/README.md`.

---

## Nothing is cited that nobody has opened

**The rule.** A citation is a statement that someone here opened that source and read the page. Writing a citation from a search result, a catalogue entry, a cover scan, or another book's footnote is forbidden, however right the resulting reference may turn out to be.

## One search answers "is it in the library" — and a name search is unfinished

**The rule.** `tools/have.sh "<title>"` is the only search that answers this, and each tool and each agent uses it. It covers each shelf under the library roots set in `book.toml` (`[library] roots`), and the library index (`[library] index_file`), which names works no filename reveals.

## Prior work — the read-back receipt

**`tools/preflight.sh NN` is done when Claude has said out loud what it printed.** Running it is the first half. The reason: in the original system a chat spent hours redrafting a section from a summary of a working file, and repeated wrong turns the file had recorded so they would not be repeated. It had read a description of the file in place of the file.

## Source hierarchy — read the PDF before the EPUB

The author: *"I … prefer the PDFs, as I do quality control on those files."*

The checked shelf (`[library] checked_shelf` in `book.toml`) is the one the author checks by hand. Other shelves are unchecked. **So: look for the PDF on the checked shelf first, each time.** Open an EPUB only when no PDF of that title exists anywhere in the library, and say in chat that the copy read was an EPUB. Never take an edition from an EPUB's file metadata.

## An unreadable source is raised, never skipped

**The author is the only person who can fix it.** The author owns the library, buys the books and runs the scanner. Claude cannot. So a source Claude could not open is a request, and it goes to the author (`Fact Check/Asks.md`, kind ONLY YOU CAN).

## A cited book has its path in the library

**The rule.** Each work the book cites has a record in `Fact Check/Claims/`, and that record's `drive_path` field names the file that was opened. The file — never the title, never the folder. `tools/check-drive-path.sh` fails any `drive_path` that does not open.

## A work inside a book has no filename

**The rule.** An essay, chapter, paper, lecture or document that was published INSIDE another book is never reported absent on the strength of a title search. `tools/have.sh` reads filenames and index titles. A work inside a volume has neither. Before writing that such a work is not here:

1. `tools/have.sh` on the ANTHOLOGY, the collection, the editor, the series — the container, never the piece.
2. `tools/find-source.sh` on a phrase from the work. A full-text search reads contents, which filenames cannot show.
3. `tools/find-source.sh` on the author's name with a subject term, because a contributor is findable by what he or she argues.

Only after all three may a record say the work is not here.

## Start from "we have it and I lost the reference"

**The rule.** Each source in this book was opened by somebody while the book was being written. So a search that comes back empty has found a lost REFERENCE. The default conclusion is "the pointer is broken"; "the source does not exist" is never the default.

## The local surfaces first, and the web only when they have failed

**The rule.** Before any web fetch or web search, the local surfaces are asked (core §6), and the reply says which were asked and what they returned.

## AN ERROR IS FACT-CHECKED AND LOGGED BEFORE IT REACHES THE AUTHOR

**The rule.** A suspected error in the book is never an ask on its own. Before it is put to the author it is checked, in this order — the library, the checked shelf, any local servers — by reading the sources whole, and each read is logged (`Fact Check/Claims/Ch NN.jsonl`, the chapter ledger, `source.read`). What reaches the author is what the sources say, on a card. An ask is filed only when the whole search is exhausted and the surfaces are stated. This is THE SIX DIRECTIVES, A and B, restated by the author as a standing rule after an unchecked ask reached the author.

## Rules from the table "Voice and framing rules"

- **Page numbers do not travel between editions.** A page number that does not match the copy in the library is the normal condition, never a finding. Cite by structure (chapter, section) where the copy's pages differ from print.
- **A failed lookup is a fact about the query.** Before writing that a source is unread or unreachable, search the library by author and by title, retry the reference in the format the tool expects, and account for how the text was extracted (a bad scan defeats a phrase search on a page that holds the phrase; read the page).
- **No source-negative from a window.** "The source does not say X" requires reading the whole section, and the finding states what was read — "read chapter 21 entire" — never "searched and found nothing."
- **An author's own summary is a different text from the source.** Previews, abstracts, chapter summaries and back-matter recaps are the author's abridgement of himself or herself. Verify against body text.
- **A broken citation is a research task, never grounds for deletion.** When a locator is wrong, missing, or points at an edition nobody holds, find the right one. Do not propose cutting a sentence that serves the reader because its citation is inconvenient to repair.
- **Verify rather than ask.** When a claim needs checking, Claude checks it.
- **State the search surface before the negative.** A negative result is reported with its coverage attached: which files, how many of how many, which search terms, which method, and what was not searched. The coverage comes before the conclusion, and before anyone challenges it.
- **A ruling is made once and logged.** Any recurring check that surfaces a passage for the author's judgement writes the author's ruling to a file, keyed to the text, and reads that file before reporting again. `tools/rulings.py` holds the mechanism: a ruling is keyed to a fingerprint of the text, so a rewritten passage needs ruling again.
- **Two verdicts per claim row.** A ledger row answers QUOTE (is the quoted matter faithful?) and CLAIM (does the body sentence characterise the source correctly?). A row with one verdict does not stop a re-search. (`Methodology/Fact-Check Ledger Protocol.md`.)

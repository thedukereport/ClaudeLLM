# Standing Rules — the core

**How to use this file.** Each chat reads this core and its own role's file (`Methodology/Rules — <Role>.md`) at session start and after any compaction, before touching prose; `Methodology/Roles.md` says which role a chat has. The lists the tools read (banned words and their carve-outs, epistemic triggers, attribution classes) are in `Methodology/Word Lists.md`; the book's terms of art are in `Methodology/Glossary Terms.md`. Where this core and a role file seem to disagree, Claude follows this core. Where the author's newest words differ from both, Claude follows the author's words and writes them into this file the same turn, quoted, with the date.

Each rule below came from a failure in the system this kit comes from. The reason stays with the rule so that a reader can tell when the rule applies. The author of this book may strike or amend any rule; the amendment is recorded here.

---

## 1. Read the text. A search locates; only reading decides.

The author: **"READ DON'T GREP IS THE WHOLE OF THE LAW."** Where another rule seems to disagree with this one, Claude follows this one.

- A search hit gives a place to read. It is never a finding, a verification, or the ground of a proposal. A zero count is a fact about the query. The author: *"a failed grep does not mean something does not exist, it simply means that the grep failed, and needs to be backed up by reading or other means."* Before Claude writes that anything is missing, Claude backs a zero from grep, a library search or a server search with a read or a different search, and states both.
- Claude reads a file whole, in the session, from disk, before changing it: chapters, ledgers, scripts, protocols, this file.
- Claude reads a chapter end to end in the session before proposing anything for it, and reads the paragraphs around a destination before proposing text for that place.
- Claude makes a claim about a source only from the structural unit read whole — heading to heading, section to section. For a negative ("the source does not say X") Claude reads the whole unit and states what was read.
- When something will not come clear, Claude opens the text again. Claude's own notes, cards and ledger rows are copies; re-reading them produces no fact about the book or a source.
- Slow and correct is the settled trade. The author: *"Slow and correct beats fast and wrong, EVERY TIME."* Claude never offers a faster path that skips a read.

## 2. Roles, files and queues

- `Methodology/Roles.md` assigns each file one writer. A chat writes only the files its role owns, plus the shared, append-only places Roles.md lists (hand-off inboxes, `Fact Check/Asks.md`, the event log, the field-level shares).
- **One queue.** The author: *"We need to have a single queue."* The author rules on the Source Rulings page and nowhere else; its Asks tab shows `Fact Check/Asks.md`. Claude brings work to the author through that page and through no other channel.
- Chats pass work to each other through `Handoffs/`. The author relays nothing between chats.
- **Chapters out of the workflow.** `book.toml` lists them under `[workflow] out_of_workflow`. No card, triage row, fact-check, audit, sweep, routed item or tool write touches such a chapter until the author takes it off the list. Claude leaves anything found in it exactly as it is and raises none of it. Tests never write to `Chapters/`.
- The first line of each role's hand-off file says `WORKING: <task> — <time>` or `WORKING: nothing`. One task per session; a session ends when its task ends.

## 3. Talking to the author

- **Plain language.** Claude applies each rule for the book's prose to chat as well. Name the actor, the act and the number. The author: *"I'm directing you to use plain language with me."*
- **Full paths.** A file or folder is given to the author by its full path on the author's computer. Paths inside vault files and scripts stay vault-relative.
- **Ch##/L##.** Each place in the manuscript is written `Ch##/L##`, two digits, with the line numbers re-derived after any edit. Claude gives the coordinate in place of a section label or a description of the passage. A coordinate is printed for the author to navigate by; the tools store block ids (Rules — Systems).
- **The stored thing by its path.** Claude writes the file's path in place of "the ledger", "the register", "the log" or "the record".
- **What the author can see.** Claude refers to cards by the title on the page and to asks by the number the author rules by, never by internal ids.
- **"ok" is the word.** It approves a card, releases a sample and agrees in chat. Claude writes whatever log line a tool needs; the author learns no word invented for a tool.
- **Say you are stuck, in those words.** "I cannot find X. Can you get it?" goes to the author in one line before Claude draws any conclusion from the absence.
- **A number is a claim.** Claude writes "many" or "several" wherever the argument works without a count, re-measures any figure in the turn it is quoted, and hand-checks three rows before quoting a total.
- **Never write "You're right."** Nor "correct", "good catch", nor the author's point restated back before it is answered. Open with the substance or the correction. The author: *"Nothing makes me angrier or more frustrated than 'You're Right!'"*

## 4. The author's words

- **Read all of the answer.** An agreement word followed by anything is an instruction, and the words after it are the work. A bare "no" means the book stays as it is; a "no" with words after it is work.
- **The author's prose goes in verbatim.** When the author writes the sentence, that sentence goes into the chapter. Any change to it goes back to the author first.
- **The author's question is answered before the item closes.**
- **An instruction starts the turn it is read** and finishes before the next chapter opens.
- **Each comment of the author's that asks for work is a directive** and gets a row in `Fact Check/Directive Register.md` the turn it is given.
- **A rule the author states goes into this file the same turn**, with the author's words quoted, and a `rule.stated` event goes to the log.
- **A ruling the author gives in conversation goes to the event log as the author's**: `decision.recorded`, with the actor named in `book.toml` (`author_actor`), the words verbatim.
- **Settled prose is settled. Closed is closed.** Once the author approves a passage, Claude reopens it in no later pass for a better word or a tighter version. The author: *"If something has been 1) read, 2) fact-checked, 3) approved, and 4) logged in the fact-checking documentation, DO NOT OPEN IT AGAIN, EVER."* A fact found after approval goes to the chapter's ledger and `Fact Check/Back-fill Queue.md`; it reaches the author only if the author reopens the line. The reason: in the original system an exception for "a factual error of record" was used five times in one evening to put new versions on lines the author had approved. The author: *"I need to know that when I've made a decision that it will never come back to me."* The author looks at a card before any check takes it off the queue.
- **What the author says the author was told is enough.** A sentence resting on what someone told the author stands on the author's authority and gets no card. The author: *"If there is an actual cited event and the facts are wrong, or a quote that is truncated or wrong, that needs to be fixed."* A card is for a cited event whose facts are wrong, or a quotation that is truncated or wrong.
- **A check that leaves the text alone does not come back to the author.** When Claude's check changes a card's text, the card goes back on the page as a revised card, version line first.

## 5. Showing a change

- **Current, then Proposed, in full, both times.** The text on disk now, read in the same turn, then the replacement, each under its own heading; the reasons follow. Claude never puts a description, a word count, an ellipsis or `[unchanged]` in place of text. Long notes break into paragraphs so the author can see the parts.
- **Context.** The paragraph above and below a changed body line, and the notes the line anchors.
- **The whole paragraph** once two of its sentences are under revision.
- **One change at a time.** Approving a sweep approves none of its output; each candidate is shown and ruled on its own.
- **A card shows the words.** Each card gives the sentences that would go into the book if the author says yes. A card that asks the author to choose without text is unfinished.
- **A fault on a line the author approved comes to the author as a full card.** The author: *"I don't know, because this view does not show me the full context."* A finding on a closed line reaches the author as a card with the current and proposed text and their surrounding paragraphs, in the page's "Reopen?" view, where the author's press reopens the line or keeps it closed. It never reaches the author as a bare "say 'reopen X'" ask.
- **One proposal per target, one ask per card.** A new version replaces the old one in the open part, and the old one goes into the card's `removed` list, whole, version line first. A matter the proposal leaves open becomes a lettered choice above the proposal or a card of its own.
- **Before a proposal reaches the author** Claude takes it through the six directives in order: A, the ledger and `Fact Check/Claims/Ch NN.jsonl` first; B, the source, with the search surface stated; C, what belongs in the body; D, redundancy before and after; E, the neurolinguistic-prose skill on each word the author will read, recorded with `tools/prose.py` (the page holds a card with no record for its exact text); F, each read logged, including what was not found. (Rules — Editor, "The six directives".)

## 6. Sources and claims

- **Each claim and each citation is checked, cited and logged.** The author: *"EVERY claim or citation must be checked, cited, and logged in a fact-checking file to facilitate future queries (and prevent redundant searches)."* Claude reads the source, cites it, and writes the read to `Fact Check/Claims/Ch NN.jsonl`, the chapter's ledger and the event log (`source.read`) in the same turn: the reader, the date, the `drive_path` of the file opened, where in it, and the words found (`Fact Check/Claims/README.md`). Each quote, in the book or on a card, is checked against the source word for word for accuracy, and for completeness, so that a cut or an ellipsis changes nothing the person said. The author: *"Quote = Words claimed that a person said or wrote."* A search that finds nothing is logged the same way, with its coverage: which surfaces, which terms, what went unsearched. For any later query Claude opens that file first and repeats no search it records.
- **No citation without a source opened and read, unless the author approves it.** The author: *"There should be no citations in the book that have not been sourced and read, unless specifically approved by me."* An approved exception is recorded as the author's ruling (`decision.recorded`) and in the Claims row; no other exception exists.
- **Gaps are back-filled; nothing is removed without the author's approval.** The author: *"I don't want anything removed that I have not approved."* A citation or claim already in the book with no logged read stays in place and goes on the Fact-checker's reading queue, where it is read and logged. Claude removes nothing from the book, a card or a ledger without the author's approval.
- **Reading needs no permission; unread citations get read.** The author: *"You don't need to ask me to read the books; that is the entire point of the exercise."* And: *"The point of scanning the footnote for unread citations IS TO READ THEM, NOT TO TELL ME THEY HAVE NOT BEEN READ."* So:
  - Claude reads, whole and logged, any work the book cites and any work in the library that bears on a cited claim, with no ask. The author's permission covers only adding a new work to the book's text.
  - `tools/check-read.sh`, the page's Back-fill view and any other scan for unread citations feed the Fact-checker's reading queue, `Fact Check/Reading Queue.md` (`tools/dashboard-sync.py queue`). Nothing from them reaches the author except "I cannot find X. Can you get it?" for a work the library cannot produce.
  - For each unread citation, the reader also records the write that put it in the book: the date, the session or tool, and the reason it gave. The queue names the first one the event log or git records.
  - Where two sources differ, the record sets them side by side (who said what, when and where) and rules on neither.
- **Claude asks the author for a source before using it.** The author: *"If you need a source, you have to ask me for it before using it, including the author's name, title, and (if available) the URL."* The ask goes in `Fact Check/Asks.md` with the author, the title, the URL where one exists, and whether the source is in the author's draft or new. "Using" means opening it for the book, citing it, or putting it on a card; a source the chapter already cites needs no ask.
- **Local first, and the web never for what is held locally.** The author: *"I don't want to go searching for something on the Internet that we have curated locally."* Claude asks the local surfaces first, in this order: `tools/have.sh` (is the work in the library?), the checked shelf named in `book.toml` (`[library] checked_shelf`), `tools/find-source.sh` (a passage or a book across the whole library), then any local reference servers the author has connected, then the vault's own notes. A search locates; before Claude opens a source the chapter does not already cite, the ask goes to the author with what the search found. Claude goes to the web only after each of these comes back empty, and asks the author before the fetch, with the URL and the local surfaces already asked.
- **A suspected error is fact-checked before it reaches the author**, on those same surfaces, read whole and logged; the author receives what the sources say, on a card. The author: *"if there is an error, 1. it needs to be fact-checked … and logged, BEFORE being presented to me as an issue."*
- **Who said what, when and where.** Claude records what each source says and never rules one source right and another wrong. Claude reports what a source says and what its words do to a reader's belief, and offers no verdict on whether a claim is true; Claude asks before treating any request as a request for one. The author: *"When I analyze language, I'm not usually trying to establish veracity; I am trying to measure impact on belief."* Claude puts a source's credentials nowhere in the book as a reason to believe it.
- **An empty search means a broken pointer.** Start from "we have it and I lost the reference." Claude states the coverage of a negative — which files, how many of how many, which terms, what went unsearched — and writes no record calling a work absent on the strength of a search.
- **The PDF before the EPUB.** The checked shelf (`[library] checked_shelf` in `book.toml`) is the one the author checks by hand; Claude says so whenever an EPUB was the copy read.
- **A source Claude cannot find or cannot read goes to the author** as a request, in one line, and the author's sentence stays as written. Claude never cuts or softens a claim to fit what Claude found.

## 7. Write it down the turn it happens

- **A finding** goes into the file Roles.md assigns — a card, `Fact Check/Findings Register.md`, a ledger — in the turn it is found, before the reply is written.
- **An overturned ledger row** is marked as overturned the turn a later read overturns it (the reads themselves: §6).
- **An ask** goes into `Fact Check/Asks.md` with its kind (DECIDE, REVIEW, ONLY YOU CAN) and what silence means. Asks are batched for a checkpoint and asked once.
- **An anomaly** gets an entry in `Methodology/Anomalies and Contingencies.md` the turn it is met: the signal, the case, the contingency.
- **Something Claude told the author that proves false** goes to the event log as `claim.corrected`.

## 8. Tools and bulk changes

- **A sample before any bulk write.** Before a tool writes more than five things, Claude shows the author the whole before and after of a few of its changes and records the author's "ok" in `Methodology/UAT Log.md`. A count is no sample. `tools/uat.py` refuses a bulk write for a tool with no ACCEPTED line.
- **A repair a command can decide is no question.** When a test decides the case for each row — a path opens or it does not — Claude repairs what the test verifies, lists what it cannot, and reports afterwards. Choosing a word, a source or a book is judgment, and judgment goes to the author.
- **Copy the file before a scripted change** that rewrites it whole. When a file's format is awkward for a tool, Claude changes the tool; the file is the author's.
- **A check that did not finish found nothing.** Claude reports it as not done.
- **Nothing under the author's name is written by a test.**

## 9. The words Claude writes

Claude applies these to its own prose — in the book, on cards and in chat. The author's own words and first-person passages are the author's.

- **No invented people as examples.** The author: *"No invented people as examples."* A point is illustrated with named people, dated events and documents somebody can open, or it stays unillustrated and the search goes on the Punch List. Claude never puts a made-up person, scene or transaction in place of a real case. "A man who…" and each disguise of it ("a reader who", "a voter who", "whoever") are banned.
- **People act.** A person, or a body with documented members, is the subject of an active verb. Peoples, nations, eras, documents, chapters and concepts take no verbs of intent or action.
- **What a reader can check.** Claude states what the record shows, cites it, and stops. A claim no document could break is a story: a source's story is attributed and left there; where the book gives its own account of such a matter, Claude writes "may", never "probably". Claude assigns nobody a motive, intention or feeling without a document.
- **No borrowed authority, no pre-emptive retreat.** A list of names settles nothing; Claude cuts a hedge that discounts the evidence just given.
- **Quote a primary source; paraphrase none.**
- **A paragraph ends on its last fact.** No aphorism after it, no caption after a quotation saying what the quotation showed, no announcement of what a chapter will do or has done.
- **The plain word, and the word already on the page.** No synonym for variety. Write the thought in full; terse is a different thing from plain. Repair a fault by naming the actor and adding context, and keep the author's hedges.
- **Banned words.** The list and its carve-outs are in `Methodology/Word Lists.md`, between its machine-list markers; `tools/check-banned-words.sh` reads it there and nowhere else. To add or amend a banned word, edit that block and nothing else.
- **Canonical terms.** The book's terms of art are listed in `Methodology/Glossary Terms.md`. Claude uses them as written and substitutes nothing for them.
- **Never offer the author a banned word** in a proposal, a card or a reply. `tools/check-card-words.py` checks each card.

## 10. Pushing

Pushing to GitHub is the author's. No chat pushes. After each commit Production gives the author the line to type, from the vault folder:

```
./tools/backup-to-github.sh -m "<commit message>"
```

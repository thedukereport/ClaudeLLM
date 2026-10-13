# Chapter Close-Out Procedure

The order a chapter is closed in, and **the classes of defect each step catches that the step before it missed.** The order matters because each step depends on the one above it being finished. Production runs the lock steps; the Editor and Fact-checker run the reading steps.

---

## The governing rule

**Open blocks.** The author: *"If it is open it is blocking. That is the rule."* There is no minor open item, no deferred open item, and no open item that leaves a lock alone. An item closes one of two ways: verified, or **closed by decision and recorded as such** — the author rules that a claim stays out of the body, and the ledger says so.

## One lock source

**`Fact Check/Locks.md` is the only record of whether a chapter is locked.** It is a table — chapter | state (🔒 or 🔓) | date | by | note — with one row per lock or unlock, newest last; the last row for a chapter is its state, and the event log records each change as well. The file is changed only by:

```
tools/lock.py unlock NN --by production --note "<the author's ruling and the reason>"
tools/lock.py lock NN --by production      # refuses unless tools/check-lock-ready.sh NN passes
tools/lock.py status                       # each chapter and its state
```

Never edit `Locks.md` by hand, and never write a lock stamp anywhere else — in the chapter, `Book Structure.md`, `Punch List.md` or `Project State.md`. Those files may say "see `Fact Check/Locks.md`".

**Why one source.** In the original system the lock lived in four or five places (the chapter's stamp, the Punch List's lock table, the Book Structure heading, Project State, the ledger), and each unlock or relock had to change all of them in one turn. Claude unlocked a chapter in three of four places and stopped, minutes after writing the step that said to change all of them; the gate reported OUT OF SYNC. A parser read the first lock word in a bullet instead of the last, so a line narrating "unlocked, edited and re-locked" reported the chapter unlocked. Several copies of one fact disagree; one copy cannot.

**Why the lock matters beyond bookkeeping.** The lock is what the Watcher, the fact-check agent and `tools/check-lock-ready.sh` read. A chapter edited while marked 🔒 reports itself as verified and finished to each tool that asks, and the edits inherit a verification they never had.

---

## The order of steps

### −1. UNLOCK BEFORE THE FIRST EDIT

In the original system a day of edits went into three locked chapters without one being unlocked. The procedure described how to close a chapter and never described how to open one, so the omission was invisible until the author named it: *"you are also missing the unlock edit relock push context."*

**A chapter marked 🔒 is closed. Before touching one word of it:**

1. **Say why, in chat, and get the ruling.** A lock is a statement that the chapter is finished. Reopening one is the author's decision, never a consequence of finding something.
2. **Unlock it:** `tools/lock.py unlock NN --by production --note "<the author's ruling and the reason>"`. The reason goes into `Fact Check/Locks.md` with the date, and the change into the event log.
3. **Record the reason in the chapter's fact-check ledger**, dated.
4. Then edit — showing each change first, per `Methodology/Rules — Production.md`, "Showing changes."
5. Then **relock** at step 8, and **push** at step 10.

**Unlock, edit, relock, push.** Four steps, and the first and third are the ones that get skipped, because only the middle one feels like work.

### 0. Never reason over truncated output

**Precondition on each step below.** `head`, `cut -c`, `fold -w`, `%.Ns`, `| head -N` and width-limited `grep -o` all drop content without saying so. Use them to find *where* to look. The moment the work turns from locating to judging, **re-read the line in full.**

The question is binary and answerable before speaking: *did I see the whole thing?*

The worked failure in the original system: a line was read through a 150-character display limit, which ended mid-number. Claude reported a sentence breaking off mid-line, wrote it onto the Punch List as a defect, and a chapter locked for months was unlocked over it. The line was intact. The same day, a slug pattern that matched only `[a-z0-9_]` hid footnotes and produced a false count of broken anchors, and a width limit hid the lock table, producing a flatly wrong answer about whether a chapter was locked.

Quoting a line to the author means the quote came from an untruncated read, or Claude says plainly that it did not.

### 1. Mechanical detection first, judgment second

Search for candidates; never let a search return a verdict. Run `tools/check-banned-words.sh NN`, `tools/check-epistemics.sh NN`, `tools/check-ellipsis.sh NN`, `tools/check-glossary.sh NN`, and the neurolinguistic-prose skill's checks (nominalization, modals, quantifiers, negation-first constructions, paragraph openers, heading form).

**Apply carve-outs before counting.** In the original system fifteen hits on one banned word produced **one** real violation; the rest were financial holdings, legal holdings, physical grips and a capitalised term of art. A candidate dump without verdicts is no audit, and its totals will be misread as violations.

**The parser lied.** A first anchor count reported fewer anchors than definitions and Claude announced a break. The slug pattern had silently dropped each note whose name held another character; the true count matched. **Fix the parser, never the chapter, and never report a count you have not sanity-checked.**

### 2. Read each sentence

The author: **"no I like eyeballing."** Automated extraction flagged a handful of sentences; the reading pass found defects in classes no regex can express:

- a **plural pronoun orphaned** when its antecedent sentence was cut an hour earlier
- an **arithmetic error** inside prose that scans perfectly (a year plus "one hundred years later" giving the wrong year)
- a **conceptual duplicate** sharing almost no vocabulary with its twin
- a sentence whose **object never arrives**
- a **false etymology** that no source in the chapter supports

Shingle-matching finds the *verbal* duplicates. Only reading finds the rest.

### 3. Citation audit — and check the library before the web

The author: **"You had all of the sources locally. Check [the library] to find the source, and then cite the primary sources."**

**Read the secondary source's own notes.** That is where the primary lives. Where a scan runs several notes together and the mapping cannot be recovered, **say so in the footnote** rather than guessing which citation supports which figure. Run the citation-audit skill (`Skills/`) for the chapter.

### 4. Go to the original, even when the second-hand quotation looks fine

In the original system a pin cite taken through a secondary source proved correct, and reading the original still paid twice: it produced a stronger sentence for the body, and it showed that the original writer reached his conclusion by setting aside the explanation the chapter argued — a seam a hostile reader would have found first. Going to the original also caught a misquotation in the secondary source.

### 5. Audit footnotes as prose addressed to a reader

The test is **who is the sentence talking to.** In the original system a sweep for meta-language reported the notes clean, and its pattern list did not contain the name of the author's library. Nine notes were citing storage locations. A reader has no library folder, no server and no vault; each such phrase is addressed to Claude and printed in a book. Run `tools/check-footnotes.sh NN`, `tools/check-anchors.sh NN` and `tools/check-note-content.py`, and read each hit.

**The provenance those phrases recorded is real and belongs in the fact-check ledger** — it records that a quotation came from a text actually opened. Move it; do not delete it.

### 6. Write the ledger *as you go*

The author: *"Write all the fact-checking to the fact checking document, so you don't need to look from scratch again. (You're supposed to do that by default.)"*

**Negative results are the expensive ones.** A statistic that took three lookups to disprove, and a source not in the library, were not recorded, so the next session would have paid for both again. **A claim is unchecked until the check is on disk.**

Record: verified-at-source, errors found and corrected, dead ends, still-open, and the files confirmed present in the library (`Methodology/Fact-Check Ledger Protocol.md`).

### 7. Cross-reference sweep — after all prose edits, never before

Editing shifts line numbers. Prefer **section-name references over line numbers** where the target has stable headings. Run `tools/check-crossrefs.sh NN`.

This sweep also reads the *target*: verifying a pointer can find unrelated scaffolding at the place it points to, which goes on that chapter's Punch List.

### 7¼. Put the author's answers in the chapter, and mark the card

Each step above this one finds work and puts it on a card. Each step below locks the chapter. In the original system nothing in between moved the author's answer into the manuscript: hundreds of answered items never reached a chapter file, and over a hundred more reached the file with nobody marking them applied.

**Before the gate,** Production applies each approved card for the chapter with `tools/apply-card.py`, which reads the card from the page snapshot and writes through `tools/blockedit.py`, and marks it applied on the page with an apply entry in the ledger. A card the author answered with words after "ok" is work, and it goes back to the Editor for a new version; it is never applied as it stands.

**The mark is the point.** A card with status `applied` is what takes it off both queues, and what `tools/check-lock-ready.sh` reads. An edit made without the mark looks exactly like work nobody did.

### 7½. THE GATE — run `tools/check-lock-ready.sh NN` before locking

**Mandatory. Nothing below happens until it returns PASS.** `tools/lock.py lock NN` runs it again and refuses on a failure.

```
tools/check-lock-ready.sh NN
```

It looks at:

- **open Punch List items** naming the chapter (`Punch List.md`)
- **open cards** for the chapter on the page snapshot (`Handoffs/editor-tools/page-snapshot/`): any card not `applied`
- **the read check**, `tools/check-read.sh NN --strict`: a chapter citing a work nobody opened does not lock
- **banned words** (`tools/check-banned-words.sh NN`)
- **epistemics** (`tools/check-epistemics.sh NN`)
- **footnote length** (`tools/check-footnote-length.sh NN`)
- **cross-references** (`tools/check-crossrefs.sh NN`)
- **that `tools/preflight.sh NN` ran** for this chapter: its receipt, `.preflight/chNN.stamp`

Exit 1 means do not lock. It prints each blocking item with the file and heading it was found under.

**Why the gate exists.** In the original system Claude declared a chapter lock-ready on "zero open items" — meaning zero on the fact-check ledger, a file Claude had written and curated. The Punch List held the chapter's open items, and Claude never queried it. The cause is general: **Claude builds the check out of its own model of the system instead of out of the system.** Care does not fix that. A gate that runs the system's own code does.

**Why the read check blocks.** A rule — "there should not be one source in this book that you have not opened" — was written down and a check was built that measured it, but the check was wired to nothing that could refuse. A citation for a book nobody had could be written, reviewed, ruled on and locked. **A rule that nothing can refuse is a hope.** The gate is the place in the vault that refuses, so a rule that matters is wired to it.

### 8. Then the lock

```
tools/lock.py lock NN --by production
```

One file changes: `Fact Check/Locks.md`. **Check the lock state before claiming to change it** — `tools/lock.py status NN`.

### 9. Then the PDFs — delete the prior file first

`tools/publish-pdfs.sh` for the chapter, after removing the existing PDF, so a failed render cannot leave a stale file looking current. Spot-check the rendered text for the change you made; an HTML comment will not appear, and a missing glyph fails silently.

### 10. Then the GitHub push — each time, without waiting to be reminded

Production commits and prints the line the author types from the vault folder:

```
./tools/backup-to-github.sh -m "<what changed>"
```

The author: "GitHub push needs to be an always thing from now on."

The repository is the copy of the manuscript that is off the author's computer. A chapter locked and rendered but not pushed exists in one place, and a close-out is hours of work. Claude cannot push: `backup-to-github.sh` handles no credentials, and pushing is the author's (Standing Rules §10). **So the obligation is to print the command with a written commit message at the end of each session that touched `Chapters/` or `Appendices/`** — without asking whether a push is wanted. If the session ends without the push line, the close-out is incomplete.

The script's allowlist decides what goes up. Files outside it stay local, which means **the ledger entries written during close-out may not be backed up by this step**; `tools/snapshot-vault.sh` copies the whole vault to the folder set in `book.toml` (`[output] snapshot_dir`).

---

## Related

`Methodology/Standing Rules.md` · `Methodology/Rules — Production.md` · the citation-audit and neurolinguistic-prose skills in `Skills/` · `Methodology/Fact-Check Ledger Protocol.md` · `Methodology/Anomalies and Contingencies.md`.

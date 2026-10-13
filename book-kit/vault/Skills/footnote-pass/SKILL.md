---
name: footnote-pass
description: "The citation-only footnote pass for your book. Use when the user says \"footnote pass on chapter X,\" \"trim the footnotes,\" \"fix the footnotes in X,\" \"footnotes are too long,\" \"the apparatus is bigger than the chapter,\" or asks about footnote length, footnote structure, orphaned or unanchored notes, footnote cross-references, or the book-wide footnote ratio. Also use when tools/check-footnotes.sh output needs adjudicating. Asks first what job the PARAGRAPH does in the chapter's argument, because a note whose source does not bear on that job has a placement fault no trim can fix. Holds every note to navigation, not evaluation: a note says where the thing is, never how much to believe it, never asserts a source's authority, and NEVER says what the book is about. Asks whether anything in the note belongs in the BODY. Shows every proposal as full Current and full Proposed text. Do NOT use for whether a note has the right source or page — that is citation-audit."
---

# Footnote Pass

The vault's footnotes belong to this skill. This file is what to do when the author says "footnote pass on 04."

**The boundary with `citation-audit`, stated once:**

> `citation-audit` decides what a note must contain. This skill decides how long it may be.

A note missing a page number is a citation-audit finding. A note that is 400 words long is this one's. Never file both about the same note in the same pass.

---

## Before anything else — three questions, in this order

### 1. Read the chapter, end to end, from disk, in this session

Not the spans the script prints. Not a grep window. Not a ledger row describing a past edit. The author: *"You grep, you fail. every time,"* and *"over dozens of chats, the false economy of grep has failed hundreds of times."* A chapter of about 9,000 words is one read. In the original project, reading one chapter end to end once turned up a doubled comma around an anchor, a footnote slug printed inside body prose, two broken sentences, two names spelled two ways, and an edit the ledger recorded as applied that was not in the file. **No script found any of them.**

**A standing constraint: `grep` is forbidden for locating content in a source.** The author: *"you may not grep. You may read, but you may not grep."* A badly formed regex — one requiring 70 characters of context on either side of a name — reported that a person was never introduced in a chapter. He was introduced in a line that began with a bold label, with too few characters before the name to match. The finding was fabricated by the tool and reported to the author as fact. Locate by reading a table of contents and then reading the unit.

### 2. Say what job the paragraph does — from the chapter, not from the note

The author: *"What job is the paragraph doing?"*

**This is not the question `tools/check-footnotes.sh` asks.** The script looks *down* from a note to the sentence that anchors it — the original author's ruling that "the job of a footnote is fixed by the sentence that anchors it, and by nothing else." This question looks *up*, from the paragraph to what the chapter is arguing.

**If the note's source does not bear on that job, the fault is placement, and no amount of trimming fixes it.**

**The recorded case.** A 224-word note tripped only the length class. Its paragraph was one step in a pattern the chapter stated two paragraphs later, and the anchoring sentence claimed one specific thing about a person's ideas. The cited book argued where those ideas came from, and no sentence in the chapter made that claim. The note had been answering an unasked question since it was written. **The length check could never have caught it** — note and anchor sentence were about the same person, so nothing tripped. The note came out whole; the anchor sentence was re-sourced to a writer already cited two sentences above.

### 3. Read for promises — the paragraph may not have done its job at all

**"Names the actors" is a promise. Keep it on the page.** When a sentence says a source names, traces, identifies or documents specific people, the specific people appear in that paragraph. The author: *"If the job of the paragraph is not complete, maybe there needs to be a second look at the source."*

**No trim reaches this fault. Open the source and finish the paragraph.**

**A sample-book case.** *Common Sense*, "Of the Origin and Design of Government in General," opens "Some writers have so confounded society with government" and later says "Some writers have explained the English constitution thus." Paine names no writer in that section. A chapter sentence saying "Paine names the writers who confused society with government" makes a promise the source does not keep, and the sentence changes to what Paine wrote.

**The recorded case.** A line closed by saying a writer names the people responsible, and named nobody, inside a five-example series whose whole shape set an account that omits the actors against an account that names them. The cited book's chapter named them in its closing sentence. The names, offices and years went into the body; the note shrank from 202 words to 58 **as a byproduct.** Across that one series the promise was made five times and kept once.

**Read each paragraph for two things:** a promise sentence with no names after it, and a paragraph citing several works where each work must be checked for a contribution. The second exists because one recorded paragraph cited two volumes by the same author, named eight people, and drew every one from the later volume. **The promise was kept and a cited source had still been erased.**

---

## The standard

From `Methodology/Standing Rules.md`, "A footnote is a citation, not an essay." A footnote holds three things and stops:

1. **Who said it and where** — author, title, edition, page or section.
2. **The words the body relies on**, if the body has not already printed them.
3. **One clause where a reader following the citation would otherwise land in the wrong place or read the wrong words** — a misprinted title, a stale edition, a variant text, an unclosed chain, a locator the source itself gets wrong.

### Navigation, not evaluation

A note says where the thing is, and warns about anything that would send a reader to the wrong place or the wrong words. **It never says how much to believe it.**

The author: *"AGAIN, let's reserve footnotes for references unless you can come up with a better heuristic."*

Passes, in the shapes recorded: a writer misprints a document's title by one word, so a reader searching the wrong word finds nothing; one writer's reproduction of a document differs from the released copy in three places; a writer says "some" of a group, not all. In the sample book: "The Bradford title page calls this printing 'A new edition, with several additions in the body of the work.'"

Fails, in the shapes recorded: one writer's account of why another changed his mind; a sentence declaring a book well supported by evidence; a sentence calling a writer a partisan source whose conclusions the chapter does not endorse — a verdict, and a pre-emptive retreat to a critic who has not appeared; a sentence calling a writer partisan and not neutral — same fault. In the sample book: Chapter 2's `[^fed1_test]`, which adds "This shows that the founders saw the Constitution as a philosophical experiment in human nature."

### The warrant rule — a badge is not evidence

**A note never asserts a source's authority or access.** A chair, a doctorate, a decoration, a directorship — **none of it enters the book as support.** No accreditation makes a claim true. Paine put it in his own postscript: "Who the Author of this Production is, is wholly unnecessary to the Public, as the Object for Attention is the Doctrine itself, not the Man."

**What a writer read is different, and it is part of who said it.** That a writer had a sealed correspondence in front of him says which documents he was looking at; that he directed the archive that held it asks a reader to defer. **The first goes in the body. The second goes nowhere.**

*(The original author corrected this rule once. It was first written as "a reason the body's claim stands," which is the accreditation move in different clothes.)*

**Do not widen this rule into one the author never gave.** It was once stated back to the original author as "you told me not to put credentials in the book," and he corrected it: *"Never said this… I did say this: A job title does not make a claim true."* The rule forbids a credential **working as support**. Whether a credential appears at all is the author's call, not a rule to invoke against him.

### Unfalsifiability is the boundary

The author: *"The question isn't whether or not something is true, verified, or from a so-called authoritative source; the question is: a) who said it and b) what meaning they are conveying. In my frame, unfalsifiability is the boundary between what is real and what is a story/opinion, and no amount of accreditation can change that."*

**A sentence no document could break is a story, whoever wrote it.** A source's unfalsifiable claim is **attributed and nothing more** — "Hamilton writes," "Paine says." The book's own is **replaced by the actions**, not hedged and not marked. And where the book offers its own account of an unfalsifiable matter, the marker is **"may," never "probably"** — a likelihood estimate needs something to ground it.

**A sample-book case.** Hamilton draws the line himself in *Federalist* No. 1: "My motives must remain in the depository of my own breast. My arguments will be open to all, and may be judged of by all." A note or sentence assigning Hamilton a motive states something no document could break. Even his stated conviction — "I am convinced that this is the safest course for your liberty, your dignity, and your happiness" — enters the book as his account: Hamilton writes that he is convinced.

**The recorded case.** A historian's sentence assigning a motive to a medieval group was about to be promoted into a chapter's body as the source for the chapter's own claim. Checking the page showed the motive sentence had no note of its own — the historian's notes sat on the sentences before and after it. **The citation was never the point.** A motive assigned to people centuries dead cannot be broken by any document the historian could have cited, and reporting "he cites nothing" is still grading his standing. Withdrawn before it was applied.

### Account is the word

An **account** of what a source concludes, and why, is evaluation and belongs in the body. The watchlisted "interpretation" is out, and so is "reading." The author: *"Account is a great word."*

A footnote does not hold the argument for the claim, the counter-argument, comparisons between sources, statutory or documentary text at length, research history, a source's motive, a source's credentials or access, an account of what a source concludes, or any sentence telling a reader how much weight a claim deserves.

### A note never says what the book is about

The author: *"These all need to go, in the whole book, and this has to be part of the footnote agent sweep. I don't know how many times I need to repeat this."*

**This is not the evaluation fault, and that is why it survived.** A note saying how much to believe a source trips class J. A note saying what a source *argues* has no verdict language at all — it reads as a helpful précis, and in the original project nothing flagged it for a month. **Class K exists for it.**

**Why these notes outlive every pass.** They are short, under the word cap. The passes open the long notes and leave the short ones closed. In the original project one such note had been in the vault since its first commit, and a later footnote pass edited the body line directly above it without opening it.

**The shape of the recorded failure:** a 62-word note summarizing what a writer's history traces and what it calls the model for later states, then telling the reader to cross-reference a second writer on the same material. Not one word said where anything was. What it became, in 34 words: author, title, year, the chapter title for the quoted phrase and the event, and the second writer's title and page for the one fact the two agree on. A second recorded note went from 78 words to 14 by the same test.

**THE TEST.** Cover the citation and read what is left. If what remains is a sentence *about the work* rather than a pointer to a page, chapter or section, it goes.

**The carve-out.** A locator that happens to use one of these verbs stays: "[Author] gives the figures in ch. 17," "[Author] documents the pipeline at pp. 43–44." Those route a reader to a page. The tell of a class K hit is a sentence about the work **with no page, chapter or section in it.**

**A second pattern surfaced by the same sweep, and it may be worse.** Notes that explain what the *chapter* is doing with a source — "is the chapter's diagnostic point," "the chapter's preferred anchor," "the chapter's synthesis," "the chapter's working claims." **A chapter makes its argument in the body.** Treat these as class K and cut them.

### A note that names an author may be quoting the foreword

**Check who wrote the sentence before attributing it to the author on the cover.** In the recorded case a note credited a book's author with a sentence about where certain objects were placed. The author's own sentence, in the body of the book, placed them somewhere else. The sentence the note quoted belonged to the foreword writer, and it described where two of the objects survive today, which is a different claim from where they were first put. The note had held a misattribution and dropped the foreword's qualifiers for as long as it existed, and **only a full read of the book caught it.**

**The test: read it aloud. If it needs a breath in the middle, it is an essay.**

The cap is 150 words, and the cap is a trigger to read the note, never a verdict on it.

### A trim has THREE outcomes: cut it, keep it, or PROMOTE IT TO THE BODY

The author: *"My continuing question when I see a huge footnote is there anything in the note, which should be in the body? We need to address that every time."* And: *"You're constantly over-compressing key ideas and context."*

`tools/check-footnotes.sh` prints candidates under **BELONGS IN THE BODY?** — material absent from the whole chapter — and under **ALREADY IN THE BODY**, with line numbers, where the chapter prints it elsewhere. **That second block exists because of a failure:** a promotion was proposed into one line when the chapter already printed that exact sentence twenty-four lines further on. The check had been comparing the note against its **anchor sentence** when the question is whether the material appears anywhere in the chapter. **A script's silence is not a finding.** `tools/check-note-content.py` and `tools/assess-notes.py` look for the same fault sentence by sentence; they find candidates and do not read.

**And a promotion proposed from memory is the same failure again.** In the original project, material was offered for promotion out of a note when the chapter already printed it twenty lines above the note's anchor. Check the body before offering.

Recorded promotions, by shape: a note held a writer's own definition of his term while the body merely charged that such terms cover tracks (253 → 19 words); a note held the permission a writer had to see the documents — the warrant (298 → 26); a note held the names a writer gave while the body said "[the writer] names the actors" and named nobody (147 → 39); a note held a witness's **first-person account** while the body **paraphrased** him — a primary source, and the standing rules forbid paraphrasing one (261 → 61).

**The sharpest rule inside the rule: a quotation in a note whose body sentence paraphrases it is a rule violation, not a style choice. It moves.**

**And when the promoted material will not fit, the paragraph splits.** The author: *"If it needs a new paragraph or sentence, it needs a new paragraph or sentence."* In the recorded case, proposing to drop two named institutions for sentence length would have made the book erase named agents inside a paragraph accusing others of erasing them. The example became two paragraphs.

**Where the displaced material goes:** the chapter's ledger in `Fact Check/`, cumulative, which no reader meets. A trim whose substance has not been written to the ledger in the same turn is a deletion wearing a different name.

---

## Order of operations

### 1. Keep the current state first, always

Commit the vault (`tools/backup-to-github.sh`) or run `tools/snapshot-vault.sh` before the first edit, and run `python3 tools/witness.py` so every later change is accounted for. **No note is edited in a chapter whose current state has not been kept.**

### 2. Read the prior work

`tools/preflight.sh NN`, and post a **PRIOR WORK** block from its output. A chapter has several fact-check records plus its open Punch List items. In the original project, a reading of one chapter produced six findings presented as new; the open-items list already held two, and one of those named five sites where the read had found one.

### 3. Detect

```
tools/check-footnotes.sh NN          # env FOOTNOTE_CAP to override the 150 default
tools/check-footnote-length.sh NN
tools/check-anchors.sh NN            # can a reader holding the cited edition find the passage
```

Then read every paragraph for promises (question 3 above) — no script does that.

Eleven classes: **A ORPHAN** and **G NO-DEF / NO-ANCHOR** block a lock. **B UNMARKED** quotation with no reference. **C LENGTH** over cap. **D SELF-TALK** the note discussing its own making, or a vault path. **E XREF** a note pointing at another note. **F FULL-CITE** the same source in full twice. **H DUPLICATE** the note repeats its own anchor sentence. **I WARRANT** the note asserts authority or access. **J VERDICT** the note says how much to believe it. **K THESIS** the note says what the book is about.

### 4. Apply the mechanical classes — E, F, D

**Apply the mechanical, propose the judgment.**

**E XREF is a rendering defect.** Tested against pandoc: a reference inside a definition is neither resolved nor stripped — **the literal characters print in the finished book.** Delete the pointer; restate in words. **The same defect appears in body prose and appendices, where no class looks for it.** In the original project a chapter printed "the earlier `[^slug]` footnote already identified" inside a body sentence, and two appendices printed six more. Slugs never appear in the finished apparatus — pandoc prints numbers — so a reader meets a token that resolves to nothing. Replace with the source's name.

**F FULL-CITE.** Full Chicago once per chapter, short form after. Never a bare "Ibid." **Check the dependency before cutting a full citation:** in the recorded case one note held the only full citation of a writer in the chapter and four later notes short-formed him.

**D SELF-TALK.** Vault vocabulary, session process, status fields, drive paths, and any sentence addressed to whoever is editing. **Vault-relative paths count and were invisible for weeks** — the class matched only absolute drive paths, so a note saying transcripts were "in the vault at" a folder passed every run. Three more turned up in other chapters once the class was widened.

**The one carve-out on D, and it is the author's.** A stated limit on the evidence is a fact about the evidence and belongs. What went was the label in front of it — `Open:`, a status field borrowed from `Fact Check/`. **The leak was the vocabulary, not the disclosure.**

**URLs are not navigation.** The author: *"I just want to cite the speech without all the URL garbage,"* and, of a recorded interview, *"We know he said it."* Cite the work — speaker, occasion, place, date; author, title, edition, page.

### 5. Rule on I, J and K

Coordinates, not verdicts — the script cannot tell "[A] writes that [B] concluded" from "[A]'s account is convincing." But once the note is open the ruling is short: **a warrant moves to the body or goes; a verdict goes; a thesis summary goes; an account goes to the body if the chapter's argument uses it and to `Fact Check/` if it does not.**

### 6. Propose the length trims — C

Sort the note's contents into three piles, in writing, before showing anything: **citation** (stays), **load-bearing fact the reader needs at the moment of the claim** (goes to the body), **everything else** (goes to `Fact Check/`).

**Check every locator before it prints.** In the original project a proposed trim gave "Part 1" where the PDF puts the sentence in chapter 1 under its own title, and another proposed trim had no section at all until the book was opened.

### 7. Show everything, formatted to be read

The author, in four messages about one footnote: *"I cannot tell what you are suggesting,"* then *"SHOW ME,"* then *"FORMAT IT SO I CAN READ IT,"* then *"when you take shortcuts, you cost time. YOU NEED TO SHOW ME EVERYTHING, FROM NOW ON."*

1. `tools/show.sh NN L` output, pasted, above everything.
2. The body sentence or sentences the note serves, quoted in full.
3. `## Current — N words`, the note's full text as prose, **broken into paragraphs** if long. A 291-word wall is not a showing.
4. `## Proposed — N words`, full text.
5. What comes out, and why, item by item.

**Label every proposal with the word PROPOSAL.** The author: *"I don't see a proposal. Maybe you need to start labeling proposals as such."* A paragraph of reasoning that happens to contain replacement wording is not a proposal a reader can find.

**Show the whole thing, in context, every time — including for a footnote.** In the original project a note was proposed four times in a row without the body sentence it anchors and without the current note text, and the author's answer was *"Apply what?"* A footnote shown alone is not shown.

**Never:** a description of the change in place of the change; a word count standing in for the text; `[unchanged]` or an ellipsis; the proposal folded into reasoning; wrapped monospace with pipe gutters.

**And never describe the file's future state in the present tense.** A proposal once said a name "is now in the body" about a change the author had not yet approved, to justify a second change that depended on it. Check the file and paste the check.

### 8. Verify

Re-run the detection scripts. Then check the **body word count**. If nothing was promoted it must be unchanged. **If something was promoted the count goes UP, and by how much must be stated.**

---

## Book-wide state

Keep the book-wide numbers in `Project State.md` and update them after each pass: words of notes against words of body, per chapter and in total; notes over the cap; longest note; mean note length. The original project started at 58 per cent notes to body, with nine chapters between 73 and 116 per cent, and brought its first worked chapters down to roughly half their note words.

Three lessons from that record hold for any book:

- **Short notes survive passes.** In one re-pass, six duplicates (class H), two thesis summaries (class K) and one warrant (class I) were cleared from a chapter already worked once — each had survived because it was under the cap.
- **The opposite fault exists.** A long chapter with two notes, or an appendix with none, wants a read for unsourced hinges, not a trim.
- **Definitions never anchored block a lock.** Class G: a chapter cannot lock until each unanchored definition is anchored or cut (`tools/check-lock-ready.sh` checks this).

---

## Rules that govern every step

- **Never work a locked chapter without saying so — and a lock is never a reason to leave an error standing.** The author: *"they will need to be unlocked edited and relocked, so stop asking me about locked chapters."* Check `Fact Check/Locks.md`; report the unlock and relock (`tools/lock.py`) as part of the work, not as a question.
- **Read the file before you touch it.** Any file being changed gets read in full, from disk, this session. Sources get read a whole structural unit at a time, heading to heading.
- **No false economy — the cheap check locates, the expensive one decides.** In the original project a backup script was found to overwrite its own snapshot on a second same-day run by testing it, after reading it had passed it. **Run it; do not read it and report.**
- **Slow and correct beats fast and wrong, every time.** The author's rule. Never weigh speed against accuracy in a proposal, never flag reading time as a cost.
- **Identify the book before quoting it.** Cached text files may be named by hash; read the first lines first. **And filenames lie:** in the original library one EPUB filed under one author's name and title held a different author's book.
- **A failed lookup is a fact about the query.** A case-sensitive search reported zero hits for a law firm a source names twice, and a body change was proposed on the strength of the false negative.
- **A hit is a coordinate, not a verdict — and a non-hit is not a finding.**
- **Never write "You're right."** Open with the substance or the correction.
- **Never reason over truncated output.**
- **One note at a time.** The author: *"Let me see them one at a time with context."*
- **Plain language in chat, not only in the book.** Complete sentences with a subject that is a person, place or thing; a verb that says what it does; a complete thought. **Two compressed phrases — a verb given a preposition it does not take, and "kept what he was after" — both reached a proposal and both were caught by the author.** The author quoted the rule back at chat prose: *"WHAT ARE YOU SAYING IN PLAIN LANGUAGE… No abstract nouns, unspecified verbs, or nominalizations."*
- **Ask questions the author can answer.** *"How would I know?"* was the reply to "which of these three should we do next." Recommend, give the reason, and propose.
- **Reference notation is `ChNN/LNN`,** two-digit chapter, always.

---

## Open items

Footnote findings that are not settled in the pass go on `Punch List.md` under the chapter's heading, tagged by check type: `FN-LENGTH`, `FN-UNMARKED`, `FN-ORPHAN`, `FN-PARITY`, `FN-WARRANT`, `FN-VERDICT`, `FN-THESIS`, `FN-PLACEMENT`, `FN-PROMISE`.

Applied changes are recorded **after** the edit in the chapter's ledger as `FN-APPLIED` rows with the before and after text. A record, not a request.

---

## Related

`Methodology/Standing Rules.md` · `citation-audit` and `neurolinguistic-prose` skills · `tools/check-footnotes.sh` · `tools/check-footnote-length.sh` · `tools/check-anchors.sh` · `tools/check-note-content.py` · `tools/assess-notes.py` · `tools/rulings.py`

# Rules — Editor

**Read after `Methodology/Standing Rules.md` (the core), at session start and after any compaction.** Where this file and the core differ, the core governs; where the author's newest words differ from both, the author's words govern and go into the core the same turn.

The Production file, `Methodology/Rules — Production.md`, holds the rules for applying a change (`tools/show.sh`, `tools/preflight.sh`, no renumbering); the Editor reads the ones that touch prose there. How a card is laid out is in `Methodology/How a Card Is Built.md`; the footnote rubric is in `Methodology/Footnote Plan.md`.

---

## A proposal without the current text is no proposal

**The rule.** Each item that proposes a change shows, before the proposal:

- **NOW** — the line or the note **as it stands on disk**, verbatim, in full
- the paragraph above and below, where a body line is in play

## Each author gets a gloss at first mention

**The rule.** The first time the body names a person the reader is expected to weigh, the sentence says who they are. Give what they did, or what the named work is. Leave out rank: the standing rules put a warrant in the body or nowhere, and "the definitive scholar of X" rates a source. The shape: "<name>, whose <work> is <what it is>"; "<name>, <subject>'s biographer".

## Borrowed authority and pre-emptive retreat — what the fact-check agent flags

These are failures of method, and the reason is the book's own argument: a book that asks readers to check claims for themselves cannot settle questions by naming interpreters, and cannot flinch in its own footnotes. The triggers the tools look for are in `Methodology/Word Lists.md`; `tools/check-epistemics.sh` reads them.

### 1. Borrowed authority

Settling a question by reporting who holds the position, in place of giving the reader something to check.

### 2. Pre-emptive retreat

Conceding to an imagined critic before one appears — hedging that discounts the writer's own evidence in the same breath as presenting it.

### 3. Sense substitution inside the book's own prose

Using a word in the sense a lexicon lists first, where the passage's own context calls for a different one.

### 4. Over-reaching a source

Stating a source's narrow claim as a broad one.

### 5. Claims that were true when written

Present-tense assertions about offices, roles and holdings that a later event falsifies without touching the text.

### 6. Draft history printed for a reader

Editorial notes addressed to us, left in the book.

### 7. Unsourced hinges

A load-bearing claim stated flatly with no footnote, usually because it reads as common knowledge.

### 8. Attribution drift — the quotation is faithful and the sentence is wrong about it

The body's attribution verb claims a stronger act than the note's source supports. The classes, by shape:

- the body says a person *testified* or made *a sworn statement*; the note says the words were *summarized in a statute* that followed
- the body says *the court held*; the note cites a *dissent*
- the body says a named person *said*; the note says the words are *quoted in another writer*

The worked failure in the original system: a ledger row checked the quotation, found the words identical, recorded that they were the statute's words, and passed the claim. The check asked whether the quotation was faithful. It never asked whether the sentence characterised the source correctly. A legislature's drafting is a different act from a person's words under oath.

## Original-language text

For a book that quotes another language or script:

| Rule | Statement |
|---|---|
| Transcription gate | Text in another script enters the manuscript only as copy-paste from a source the tool output shows first; a `[<LANGUAGE>: ref — FETCH]` placeholder otherwise |
| Search never quotes | A search locates; a source addressed by reference quotes |
| The original before the translation | A primary text in the original language, read from a local source, ranks above an English translation |
| Gloss at first use | A foreign term is glossed inline at its first use in each chapter |

## Abstraction by omission — name the thing, or point at where it was named

**The rule.** Each sentence that uses a concept either names the thing or points at where it was named. A pointer counts only if a reader can follow it — "as Chapter 9 establishes" — and "the book that names him" is a riddle.

## One proposal per item. A second version never stands beside the first.

The author: *"I want to see one proposal per item … You keep amending new proposals … and I have no idea what I am supposed to rule on."*

**So, when a proposal changes:**

1. The new version REPLACES the old one in the open part. It never joins it.
2. The old version goes into the card's `removed` list, whole, with its version line first. Nothing is deleted.
3. The version note — what changed and why — goes with the old version, never above the question.
4. The open part holds the heading, the question, the references and carve-outs, one NOW per target, one PROPOSED per target, and a short why. Nothing else.

## An item holds one ask. A matter it does not settle is a choice or a new item, never a paragraph.

The author: *"There is a proposed new paragraph/note … and then THREE THINGS THIS DOES NOT SETTLE. This format does not present me with a good way to manage all of the issues."*

**Three kinds of text get written into one item, and only one of them is an ask.**

| | | |
|---|---|---|
| **THE ASK** | the question, the text as it stands, the replacement | the author answers this — it stays at the top |
| **THE REASONING** | why the proposal says what it says, what was opened, what was found | it goes in the card's `review` |
| **THE RESIDUE** | what the proposal did not settle | it is one of the two things below, and never prose |

**A FORK is residue that changes the text the author is ruling on.** When a proposal drops a detail because nothing in the library gives it, that drop is part of the ask. It goes above the proposal as a lettered choice the author can answer in one line — and one of the letters is always *I am stuck and I am asking*, naming the document that would settle it.

**A STRAY is a finding about somewhere else in the book.** It gets its own card on the chapter it concerns. **A finding with no card is a finding nobody will ever rule on.**

## Each acronym is glossed at first use

The author: *"acronyms should always be glossed, at least the first time they are used."*

**The first time the body prints an acronym it prints what the letters stand for** — "the International Committee of the Red Cross (ICRC)" — and uses the short form after. This is the author-gloss rule applied to initialisms: a reader meeting a bare acronym has the same two choices as a reader meeting a bare surname, take it on trust or stop and search.

**Where it does not fire:** an acronym inside a quotation; one the chapter has already expanded; a form that has replaced its expansion in ordinary use and whose letters answer nothing (laser, radar, NATO on second reference).

## A NOTE NEVER EXPLAINS WHAT THE COPY IN THE LIBRARY IS

**No note says that a file is reflowed, unpaginated, an EPUB, a digital edition, or that a reader "lands by chapter."** The book's appendix on sources says that once, for the whole book. A note that cannot give a page gives a chapter, a section or a heading **and says nothing about why**. Which printing Claude read belongs in the edition statement.

## THE SIX DIRECTIVES — the gate each proposal passes before the author sees it

The author, after two cards reached the queue in a state the author had to diagnose:

> **"These are directives: A) Did you check the Fact-Checking Log? B) Did you research it and find the actual source? (Starting with [the local library] or local MCP Servers?) C) Did you make a recommendation that makes the body more relevant/contextual? D) Did you check before and after for redundancy? E) Did you run the neurolinguistic skill against any and all proposed copy? F) Did you log any fact-checking that you did?"**

### A — The ledger first. Always. Before any search.

`Fact Check/Claims/Ch NN.jsonl` and the chapter's ledger, `Fact Check/Ch. NN — <title>.md`. **Both**: the two have been found disagreeing, so a row in one is no reading of the other.

### B — Then the source, and name the surface you searched.

The local library first (`tools/have.sh`, the checked shelf, `tools/find-source.sh`), then any local servers. Say which ones ran and what they returned, **including zero**. A negative is a fact about the query until the query is stated: "0 hits" means nothing without the file, the character count and the spelling searched.

### C — Ask what belongs in the BODY before touching the note.

This is the question the note pass exists to ask, and it is asked **first**, before any trim. The author: *"your first example is going in the exact opposite direction, making the note bigger, instead of determining if there is content/context that should be promoted to the body."*

### D — Redundancy, twice: before the proposal and after it.

**Before**, because the thing you are about to promote may already be two paragraphs up. **After**, because compression introduces repetition of its own; the neurolinguistic-prose skill treats each revised passage as unaudited new draft.

### E — The neurolinguistic-prose skill, on each word the author will read.

All of its principles, named, with the subject-scan table produced before any prose-change edit. The audit is recorded as a `prose.audited` event hashed to the exact text, so a rewrite makes its own audit stale.

### F — Log it, including what you did not find.

Each read, each zero, each correction, to `Fact Check/Claims/Ch NN.jsonl` and `source.read` in the event log (`tools/card-log.py` does this for a card's sources). A read that is not logged did not happen, because the next pass will do it again — which is how A gets violated.

### What a finished proposal looks like

Six answers in the card's `review`, in the author's order, each with evidence. **A proposal that cannot answer all six is unfinished, and does not go in the author's queue.**

## SETTLED PROSE IS SETTLED

**When the author has approved a passage, it is closed.** The author: *"If something has been 1) read, 2) fact-checked, 3) approved, and 4) logged in the fact-checking documentation, DO NOT OPEN IT AGAIN, EVER."* And what the author says the author was told is enough — a card is for a cited event whose facts are wrong or a quotation that is truncated or wrong, nothing else (core §4). A later pass does not reopen it to propose a better word, a corrected count, or a tighter version — on the card, in a comment, or as "an option if you want it." `tools/check-card-closed.py` holds any card on a line an approved or applied card changed.

## THE CAPTION AFTER THE EVIDENCE

**After quoted evidence, write no sentence that says what the quotation showed.** The quotation is the demonstration. A sentence summarising it adds nothing a reader needed and, far more often than it looks, adds a claim the evidence does not support.

## A CHAPTER THAT TEACHES A PATTERN QUOTES IT. A SWEEP MUST NOT "CORRECT" IT.

Where a chapter names a pattern, quotes it and takes it apart, the pattern on the page is a MENTION. Under the neurolinguistic-prose skill's Sweep Scope rule a pattern that is named, taught, quoted-to-deconstruct, or listed as an example never counts — so an editing pass that "fixes" such a chapter's examples deletes the lesson. Mark such chapters in `Book Structure.md`.

## Rules from the table "Voice and framing rules"

- **No elegant variation — the plain word, and the word already on the page.** Never swap in a synonym because the obvious word appeared recently or because a longer one sounds more considered.
- **Full citation once, short form after.** A source gets its full Chicago citation at its first appearance in a chapter and a shortened form at each appearance after — author surname, short title, locator. Never a bare "Ibid."
- **No self-talk in the book.** A footnote never discusses its own making, and never defends the chapter against claims the chapter does not make.
- **A footnote is a citation, not an essay.** A footnote holds three things and stops: who said it and where (author, title, edition, page or section); the words the body relies on, if the body has not already printed them; and one clause where a reader following the citation would otherwise land in the wrong place or read the wrong words — a misprinted title, a stale edition, a variant text, an unclosed chain, a locator the source itself gets wrong. (`Methodology/Footnote Plan.md`.)
- **A promotion is read, not matched, and checked for redundancy first.** When the author rules "promote the content to the body" on a note, the proposal that comes back is written after reading the WHOLE CHAPTER from disk in that session, and after checking whether the chapter already says it somewhere else.
- **A note holding body content never reaches the author's queue.** `tools/check-note-content.py` reads each sentence of each note and reports any sentence that is neither a pointer to a place in a work nor a warning that another edition prints something different; `tools/check-card-notes.py` holds a card whose note fails.
- **A footnote holds what a reader checking the claim needs**, and nothing else.
- **Explain the mechanism before editing it.** Before proposing prose for any passage that describes how something works, write the mechanism out in chat as a numbered chain — actor, action, consequence, one link per line — name each distinct class of person in it, attach a source to each disputable link and read that source in the same turn, and get the chain confirmed. Only then propose prose.
- **"Names the actors" is a promise — keep it on the page.** When a sentence says a source names, traces, identifies or documents specific people, the specific people appear in that paragraph.
- **Say what job the paragraph does, before you read the note.** Before trimming, re-anchoring or cutting any footnote, state in one sentence what job its paragraph does in the section's argument — taken from the chapter, never from the note.
- **Unchanged is not checked.** A sentence reproduced inside a proposal as surrounding context has not been audited, and marking it unchanged does not clear it. An audit of a passage is an audit of each sentence in it.
- **No epigram at the close.** A paragraph ends on its last fact, never on an aphorism about the fact.
- **No universals or modals unless requisite.** No every/all/always/never or must/should/have-to unless literally defensible.
- **Audiences don't act.** "Audience" takes no active verb.
- **Phases don't act.** Phases, eras, populations and movements take no active verbs.
- **Chapters don't pick.** The chapter or the book as agent is forbidden.
- **No recapitulation.** Sections never restate what a prior section established.
- **Don't telegraph.** No forward or retrospective structure announcements; cross-references for the team go in HTML comments.
- **No reader-questions at chapter ends.** Closing paragraphs don't prompt the reader with questions.
- **First-person memoirist protection.** The author's first-person witness passages are the author's voice — never edited or flagged as violations.
- **Author-voice carve-out.** Banned-word rules bind Claude's prose, never the author's own word choices. Record each such choice as a carve-out in `Methodology/Word Lists.md`.
- **Directives are no content.** The author's working principles, and any conceit the author states in conversation, direct how Claude writes; they never appear as statements, themes or clever echoes inside the manuscript.
- **No blocks of foreign script in the body.** Sentences and clauses in another script do not appear in body prose; single words and short technical terms do.
- **Thaw nouns; add missing context. Never cut to fix.** A violation gets repaired by naming the actor or unfreezing the verb, and the words around it stay.
- **Rewrite the passage, never patch the clause.** When any finding lands in a passage, rewrite the whole passage from scratch.
- **Do not compress the idea out of the sentence.** Write the thought in full. Terse is a different thing from plain.
- **No talking to ourselves in the book.** Commentary about the book's own drafting never appears in the book.
- **Read the rulings page before every reply.** The Source Rulings page cannot notify any chat. At the start of each reply, the Editor (and any other role whose task touches cards) reads the page's `proposals` collection first and reports, at the top of the reply, each card sent, approved, edited, reopened or withdrawn since the last read — one line per card, by its title, with the time — and deals with each before anything else. It also reads the page's `presses` collection, the page's log of each button press, saved, refused or failed, and reports each press since the last read by the card's title as the page shows it, never by its internal code. When it has checked text the author sent, it sets `reviewedAt` after the author's `submittedAt`, which brings back the Approve button (in the original system, sent cards waited with no Approve button because the chat left them marked "sent for checking"). It then sets `claudeReadAt` on each card it has read, which clears the page's "Not yet read by Claude" row.
- **Footnote length is a trigger.** A footnote definition over the cap set in `tools/check-footnote-length.sh` gets read, never cut for its length.
- **Thesis first only when the evidence needs a frame.** State the thesis before the evidence when the evidence is long, heterogeneous, or unreadable without knowing what to watch for. Let the evidence come first when it supplies its own frame.

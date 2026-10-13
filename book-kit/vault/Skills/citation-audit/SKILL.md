---
name: citation-audit
description: "Three-phase chapter audit for your book. Phase 1: Continuity — check that the opening lands on what the prior chapter handed off and the closing sets up the next. Phase 2: Citation Audit — extract every disputable claim, check it against primary sources (the library, its checked shelf first, then the web, then direct reading), flag errors, produce Chicago-style footnotes holding what a reader checking the claim needs. Phase 3: Fact-Check Ledger — check the chapter's ledger before searching; write all results, including negative ones, to Fact Check/ as the final step. Use whenever the user asks to \"fact-check,\" \"verify,\" \"audit citations,\" \"source-check,\" \"verify claims,\" \"check the handoffs,\" \"run the audit on chapter X,\" \"check this against the library,\" \"add footnotes,\" \"add citations,\" or \"source this chapter.\" If the user asks to audit or check a chapter in any way, this skill applies."
---

# Citation Audit

You are auditing a book chapter for two things: continuity with adjacent chapters, and factual accuracy. Run both phases in order, then write the ledger. The chapter lives inside a book with a chapter map or outline and adjacent chapter files in `Chapters/`.

Before Phase 1, run `tools/preflight.sh NN` and read what it prints: the chapter's ledger, its Claims rows and any earlier audit reports. Work already done is not redone.

---

## Phase 1: Chapter Continuity

Before checking facts, check flow. A chapter that fact-checks perfectly and doesn't connect to its neighbors breaks the reader's experience.

### Step 1: Read the Adjacent Chapters

Read three files:
1. The chapter being audited
2. The preceding chapter (last two paragraphs + closing lines)
3. The following chapter (opening paragraphs through first argument beat)

If the chapter is the first, skip the preceding check. If it's the last, skip the following check.

Also read the relevant entries in the book's chapter map or outline — the entries for all three chapters — to understand what each chapter is supposed to set up and hand off.

### Step 2: Check the Setup

The chapter's opening should land on ground the preceding chapter prepared. Check:

- **Conceptual continuity.** Does the opening reference, build on, or assume concepts the preceding chapter established? If the chapter opens with a term, framework, or argument, has the reader encountered it before arriving here?
- **Tone and register continuity.** Does the chapter open at the same energy level the preceding chapter ended? A chapter that ends on a quiet reflective note shouldn't be followed by one that opens with a loud declarative.
- **Forward-reference payoff.** If the preceding chapter teased something ("We'll come back to that," "Chapter N unpacks this"), does this chapter deliver on the tease? If the tease pointed here, it had better land here.

### Step 3: Check the Handoff

The chapter's closing should set up the next chapter. Check:

- **Thread seeding.** Does the closing plant a question, concept, or tension that the next chapter picks up? The reader should feel pulled forward.
- **No orphaned promises.** If the chapter closes with a forward reference ("Chapter N shows..."), check that the referenced chapter covers the referenced material. `tools/check-crossrefs.sh` lists the cross-references; read each target.
- **No premature closure.** The chapter shouldn't fully resolve its argument if a later chapter depends on unresolved tension from it. Check whether the chapter map expects the argument to stay open.

### Step 4: Report Continuity Issues

Produce a brief continuity report:

```markdown
## Continuity Check: Chapter [N]

### Setup (from Ch. [N-1])
- **Status:** CLEAN / ISSUE
- [describe what the preceding chapter handed off and whether this chapter picks it up]
- [flag any concepts used in the opening that haven't been established yet]

### Handoff (to Ch. [N+1])
- **Status:** CLEAN / ISSUE
- [describe what this chapter hands off and whether the next chapter picks it up]
- [flag any orphaned promises or premature closures]
```

---

## Phase 2: Citation Audit

With continuity checked, audit the chapter's factual claims.

### Step 1: Extract Claims

Read the document paragraph by paragraph. For each paragraph, extract every disputable factual claim. A claim is disputable if a skeptical, informed reader could reasonably ask "is that true?" or "where does that come from?"

**What counts as a claim:**
- Named people doing specific things ("Hamilton addressed the first *Federalist* paper to the people of the State of New York")
- Dates and sequences ("the Bradford printing of *Common Sense* is dated February 14, 1776")
- Institutional relationships ("the printers who issued the pamphlet also sold it")
- Quantitative assertions (how many, how much, how often)
- Direct quotes attributed to specific people
- Causal assertions (one group's act produced a named result)
- Structural/pattern arguments (the same arrangement found at a different scale)

**What does NOT count:**
- The author's own analytical framework or coined terminology (these are arguments, not facts)
- Rhetorical framing, metaphors, and analogies
- Forward/backward references to other chapters
- Statements explicitly marked as the author's thesis or interpretation

Organize claims by paragraph. Number them for tracking.

### Step 2: Triage Claims by Verification Need

Not every claim needs the same level of sourcing. Triage into three tiers:

**Tier 1 — Consensus facts.** Widely documented, uncontested. A single reliable source confirms. Examples: "Paine published *Common Sense* in Philadelphia in 1776," "Hamilton wrote *Federalist* No. 1." These need a footnote pointing to the standard source, but don't need three-source cross-reference.

**Tier 2 — Contested or counter-narrative claims.** Assertions that challenge mainstream accounts, allege coordination, or attribute specific actions to specific people in ways that aren't part of the standard historical record. These need three independent sources minimum.

**Tier 3 — Structural/interpretive claims.** The author's own framework applied to evidence. These don't need citation — they need the underlying evidence to be solid (which means the Tier 1 and Tier 2 claims they rest on need to check out). Flag if the underlying evidence is missing.

### Step 3: Search for Sources

For each Tier 1 and Tier 2 claim, search in this order:

0. **Check the chapter's fact-check ledger first** (`Fact Check/Ch. NN — Title.md`) and its Claims file (`Fact Check/Claims/Ch NN.jsonl`). A prior VERIFIED row with source and page short-circuits the search — cite it and move on. A prior negative result ("checked pp. 145–152, nothing relevant") rules out that source without re-reading it. Re-checking ledgered claims is the failure mode this step exists to prevent: in the original project, context compression once destroyed a session's checking work and half the next session went to re-reading pages the ledger would have answered.

1. **Check existing footnotes.** The document may already cite a source. Read the footnote. Does it support the specific claim, or just gesture at the general topic? A footnote citing "Paine, *Common Sense*" is useful only if Paine states the specific thing the text claims, in the section the note names. Note whether the footnote needs to be checked, expanded, or corrected.

2. **Search the library.** `tools/have.sh` says whether a work is in the library; `tools/find-source.sh` searches for a passage across it; `tools/find-page.sh` locates the page or section. Read the `checked_shelf` copy first — it is the shelf the author checked by hand — before any EPUB, and never take an edition from EPUB file metadata. Use specific, targeted queries — not "Federalist" but "reflection and choice accident and force." Search returns passages, not books. Read the returned passages carefully. Does the passage confirm the specific claim, or just discuss the general topic?

3. **Web search.** For claims the library doesn't cover, or to cross-reference library findings. Prefer primary sources (the original paper, the original speech, the government document) over secondary commentary. When a web source contradicts a library source, flag the discrepancy.

4. **Direct source reading.** When the library or web search returns a promising book or document, read the specific pages. Search excerpts can mislead out of context — a paragraph that appears to confirm a claim may be followed by a qualification that reverses its meaning. **A search hit is a coordinate, not a reading.** Grep and library search both return windows, and reading a window feels like reading the source. When a query lands, print from the nearest heading above the hit to the next heading below and read that; never quote from, or rule on, the matched line and its neighbours. **No source-negative from a window** — "the source does not say X" requires reading the whole section, and the finding states what was read ("read 'Of the Origin and Design of Government in General' entire"), never "searched and found nothing." A negative needs more reading than a positive: finding a quotation proves it exists, and failing to find it in forty lines proves nothing. **An author's own summary is not the source** — previews, abstracts, chapter summaries and back-matter recaps are the author abridging himself; check against body text. **Two recorded failures:** three library searches reported a pamphlet's date unfindable, and plain text extraction of the same volume had the date one line above the excerpt's start, with the endnote naming its source. Later, with the file open, a search of another book landed in the author's chapter summary, and the audit reported that the author never made an attribution he makes fifty lines above — in a book whose front matter announces that every chapter has a preview and a summary, so search hits land in them constantly.

When you have read a work, record the read in `Fact Check/Claims/Ch NN.jsonl` (who read it, what was read, when). `tools/check-read.sh` lists every work the chapter cites with no record of anyone opening it; a citation written from a search result nobody opened is the failure it catches.

**The three-source rule for Tier 2 claims:** Three independent sources means three sources that arrived at the same conclusion through different research paths. Three articles all citing the same original study count as one source, not three. Wikipedia plus two articles that Wikipedia sourced count as one. Trace back to originals.

### Step 4: Flag Issues

For each claim, assign a status:

- **VERIFIED** — Source(s) confirm the specific claim as stated. Note the source(s).
- **VERIFIED WITH CORRECTION** — The claim is substantially correct but contains a factual error in the details (wrong date, wrong name, wrong number, a word changed inside a quotation). State what's wrong and what the source says. This is the most valuable finding — it catches errors before publication.
- **PARTIALLY VERIFIED** — Part of the claim checks out, part doesn't. Specify which part.
- **UNVERIFIED** — Couldn't find sources confirming or denying. The claim may be true but isn't currently sourced. Flag for the author's attention.
- **CONTRADICTED** — Source(s) directly contradict the claim. Quote the contradicting source. This is urgent — the author needs to know immediately.
- **NEEDS SOURCING** — The claim is plausible and may well be true, but the existing footnote is insufficient (too vague, wrong source, doesn't say what the text claims it says).

### Step 5: Produce Footnotes

For Tier 2 claims, footnotes should show their work. The reader who wants to check should be able to follow the footnote to the source and find the specific passage that supports the claim.

**Chicago-style format.** Author, *Title* (Place: Publisher, Year), page(s). For articles: Author, "Title," *Journal* Volume, no. Issue (Year): pages.

**Full citation once per chapter, short form after.** A source gets its full citation at its first appearance *in that chapter* and a shortened form every time after — author surname, short title, locator: "Paine, *Common Sense*, 'Of the Origin and Design of Government in General.'" **Never bare "Ibid."** It depends on the note above it staying the note above it; insert one footnote between them or move a paragraph and it points silently at the wrong book. Chicago moved away from it for that reason. First appearance means first in the chapter, not first in the book — a reader who opens at a late chapter has not seen an early chapter's full citation.

**Quote key passages** when the source directly confirms a counter-narrative claim. A footnote that says "See Paine, *Common Sense*" is weaker than one that gives the section and the sentence the body relies on. The quoted passage lets the reader judge the source's strength without tracking down the book.

**A footnote holds what a reader checking the claim needs, and nothing else.** The author: *"What a reader checking the claim actually needs, needs to be the book's standard."* Test the note sentence by sentence — does this help the reader find the source, or judge whether the source supports the body's claim? If neither, cut it. **Passes:** author, title, edition, page; the exact words the body relies on; the chain when the cited source is itself quoting another; a defect in the source that bears on the claim, such as a stale edition, a variant text, a publisher's disclaimer, or a failed prediction that undercuts its authority. **Fails:** further facts about the subject the body does not claim; the source's other interesting statements; the audit's own reasoning about how the finding was reached; readings considered and rejected; anything beginning "note also." **The recorded scale of the fault:** a note establishing one pamphlet's title and year ran to 180 words and came down to 75 — title, year, the person's role, the chain of who quoted whom, a second printing, and one clause on what one printing gives that the others do not. **Carve-out:** notes whose subject matter *is* the provenance dispute, where the chain and its defects are the claim.

**The sample book has this fault on purpose.** Chapter 2's `[^fed1_test]` cites *Federalist* No. 1 and then adds "This shows that the founders saw the Constitution as a philosophical experiment in human nature." That sentence neither helps a reader find the passage nor judge whether it supports the body. It is argument, and it leaves the note.

**No self-talk, ever.** A footnote never discusses its own making, and never defends the chapter against claims the chapter does not make. The author: *"I do not want any of that self-talk in this book… terminate all of it with extreme prejudice. There is no place for it in this book. If they are not claims the chapter makes, why are they here?"* **Forbidden shapes:** the note describing its own editorial choices ("The fuller text is used here," "this note gives only the register," "it appears here as a remark she reports"); the note reporting what the author has and has not done ("I have not established the year," "Until the newspaper issue is examined"); the note addressing a future editor ("recorded here so it is not offered again"); ledger vocabulary ("wants corroboration," "**Open:**," "PENDING," "before lock"); file and drive paths; and **a block of claims checked and rejected that the chapter never asserted.** That last is the largest: one recorded note spent 170 words refuting three writers on three claims, none of which the chapter mentions. **Where it goes instead:** the chapter's ledger in `Fact Check/`, so the search is not repeated and the reader never meets it. **What survives:** a defect in the source that bears on the claim, stated as a fact about the source rather than as a report on the audit — "The Bradford title page calls this printing 'A new edition, with several additions in the body of the work,'" not "so the edition wants checking." **Carve-outs:** a first-person statement separating the author's judgement from a quoted source's, and a note explaining why a quotation differs from the edition the reader will open.

**The 150-word cap is a trigger, not a limit.** Any footnote definition running past 150 words gets read, not cut. The original cap was 250; the author lowered it to 150: *"I want footnotes to be footnotes, not a monograph."* **And the count is the whole definition line, quotations included** — `tools/check-footnotes.sh` and `tools/check-footnote-length.sh` both count it raw, because quotations are on the page. The author: *"a word-count pass is not a licence to cut evidence."* A note that runs long because it holds a source chain defending a corrected claim is doing its job. A note that runs long because nobody stopped writing is not. `tools/check-footnote-length.sh` reports the count; the ruling happens with the note open, against the reader-checking test above. A 300-word note can pass that test and a 90-word note can fail it.

**The exceptions, worked.** A long note passes when it holds:

- **a source chain** — the primary, the secondary it was reached through, and what each supports
- **a contested-source caveat** — where a figure is one person's uncorroborated research, or a quotation reaches us through a partisan secondary
- **quoted primary text** the body cannot fit, per the no-paraphrasing rule
- **statutory or documentary text** quoted section by section

A long note fails when it holds draft history, notes addressed to the editors, a second essay on the topic, the same point restated, or rejected claims the chapter never made.

**When ruling, weigh the editorial prose.** The scripts count everything, so a note full of quoted statute trips the cap. With the note open, the quotation the body relies on is evidence; the question is what the framing prose around it does. A note that is 400 words of quoted statute and 60 words of framing is ruled as a 60-word note.

**Rulings are logged and never re-raised.** The author's verdicts on footnote length are recorded with `tools/rulings.py`, keyed by a SHA-1 fingerprint of the note text. The fingerprint breaks deliberately when the note is rewritten — a note that grew by two hundred words is a new note and gets a fresh ruling.

**Note discrepancies** between sources in the footnote when they exist. If two sources agree on the event but disagree on the date, say so. The footnote's job is to give the reader an honest picture of the sourcing, not to cherry-pick the most convenient version.

**Cite one edition per source per chapter.** Two notes citing the same book from different editions send a reader to a page that may not hold what the note promises. When the chapter quotes a source, cite the edition actually read — normally the copy in the library.

---

## Output Format

Produce a structured audit report as a markdown file. Combine both phases:

```markdown
# Citation Audit: [Chapter Title]

**Date:** [date]
**Chapter:** [number and title]
**Claims extracted:** [count]
**Verified:** [count] | **Corrected:** [count] | **Unverified:** [count] | **Contradicted:** [count]

---

## Phase 1: Continuity

### Setup (from Ch. [N-1])
- **Status:** CLEAN / ISSUE
- [findings]

### Handoff (to Ch. [N+1])
- **Status:** CLEAN / ISSUE
- [findings]

---

## Phase 2: Citation Audit

### Paragraph [N] — [first few words for identification]

#### Claim [N.1]: [the claim as stated in the text]
- **Tier:** [1/2/3]
- **Status:** [VERIFIED / VERIFIED WITH CORRECTION / PARTIALLY VERIFIED / UNVERIFIED / CONTRADICTED / NEEDS SOURCING]
- **Existing footnote:** [footnote reference if any, or "none"]
- **Sources found:**
  - [Source 1 with specific page/passage]
  - [Source 2]
  - [Source 3 if Tier 2]
- **Notes:** [any discrepancies, corrections, or context]
- **Recommended footnote:** [Chicago-style footnote text, or "existing footnote sufficient"]

[repeat for each claim in paragraph]

---

[repeat for each paragraph]

## Summary

### Continuity Issues
[list any setup/handoff problems requiring attention]

### Errors Found
[list any VERIFIED WITH CORRECTION or CONTRADICTED items — these need immediate author attention]

### Sourcing Gaps
[list UNVERIFIED and NEEDS SOURCING items — these need author decision on whether to source, soften the claim, or remove]

### Footnotes to Add or Revise
[list recommended footnote changes]
```

---

## Working Principles

**Check the specific claim, not the general topic.** "Hamilton wrote about the new Constitution" does not check a sentence saying Hamilton framed the question as "reflection and choice" against "accident and force." Finding those words in *Federalist* No. 1 does.

**Read the passage, not just the title.** Search returns passages. A passage mentioning a person does not check a specific claim about what that person did — read the passage to see if it confirms the specific detail.

**Attribution errors are the most common catch.** People get confused — mixing up two people with the same first name, blending two events that happened in the same year, attributing a quote to the wrong speech. These are the errors that damage credibility most, and they're the ones the audit is most likely to catch.

**A broken citation is a research task, not grounds for deletion.** When a locator is wrong, missing, or names an edition nobody holds, find the right one. Do not propose cutting a sentence that serves the reader because its citation is inconvenient to repair. The author: *"Why suggest cutting [the] sentence instead of just finding the correct reference? The sentences have a purpose."* **The recorded case:** a note closed with "for corroborating treatment, see" two books, with no chapters given and one edition not in the library. The proposal was to cut the sentence; reading both books instead produced a chapter locator for each. Sentence kept, both locators added. Cutting solves the auditor's problem, not the reader's. Carve-out: a sentence that fails the reader-checking test on its own merits, independent of its citation.

**Don't hallucinate sources.** If you can't find a source, say so. "UNVERIFIED — no source found in the library or web search" is more valuable than a plausible-sounding citation that turns out not to exist. The user can find the source themselves — they can't un-publish a fabricated footnote.

**A quotation's frame is part of the claim.** Faithful quotation inside an unfaithful sentence is the commonest failure this audit catches, and quotation marks do not excuse it. Four shapes: a sequence the source does not establish (a sentence making a document a reply to an event it is not dated against); a source's own overstatement borrowed to hold up an argument; an ellipsis that removes the qualifier (`tools/check-ellipsis.sh` prints the words each ellipsis took out of the source); and **stopping one sentence short of the answer the source gives.** The recorded case of the last: a chapter quoted a witness up to a sentence denying a purpose, then supplied a motive of its own, while the witness's next sentence supplied his. Check the sentence around every quotation, and read to the end of the source's thought. **The sample book shows the frame shape.** *Federalist* No. 1 introduces "reflection and choice" with "It has been frequently remarked that it seems to have been reserved to the people of this country" and follows it with "If there be any truth in the remark." A sentence presenting the question as Hamilton's own flat assertion drops both.

**Counter-narrative claims get extra scrutiny, not less.** The instinct is to go easier on claims that align with the author's thesis. Resist it. The author's credibility depends on every claim being solid, and the claims that critics will attack first are the counter-narrative ones. Source them harder.

**Quotes must be exact.** When the text quotes someone, check the exact wording against the original source. Paraphrases presented as direct quotes are a common error. If the original says something slightly different, flag it — the author can decide whether to correct the quote or switch to paraphrase. The sample book plants this fault: Chapter 2 quotes Hamilton as writing "from reflection and design"; the source reads "from reflection and choice."

**Check for recent developments.** After checking the historical accuracy of a claim, run a quick web search for recent news that might change the picture. A claim about an "unresolved" question may have been resolved last month. A person described as holding a position may have left it. Institutional positions shift. The audit should reflect the state of the world at publication time. Flag any recent developments that the author should consider, even if the original claim remains technically accurate.

**Cache the report immediately.** After producing the audit report, save it to `Fact Check/` before doing anything else. Context compression can destroy work that exists only in the conversation window. File naming: `Citation Audit — Ch. NN Short Title.md`.

**The Original-Language Transcription Gate — transcribe, never generate.** Greek (and any other original-language text the book quotes) enters or changes in the manuscript ONLY as a copy-paste from a same-session lookup against the local source servers from this repository, with the tool output shown in chat before the Edit is applied. Pin one edition per corpus and record the pin in `Methodology/Standing Rules.md`; the original author pinned the New Testament to the Byzantine text because model memory defaults to the modern critical text — that is the documented drift direction. Never quote original-language text from a search excerpt — search locates passages; only the reference-addressed server supplies quotable text. If the server is unreachable, insert `[GREEK: ref — FETCH]` and put it on the Punch List; a from-memory approximation is forbidden even as scaffolding. Recorded failures: a Greek word quoted from a verse where no edition prints it, and critical-text readings quoted where the pinned edition was required.

**Park unresolved claims in the ledger, not with the author.** When a fan-out search fails to check a claim, record in the ledger what was searched (queries, sources, pages) and what's still needed, under Open Questions. Ask the author only after the ledger row shows the search was exhausted.

---

## Phase 3: Fact-Check Ledger (mandatory final step)

After Phases 1 and 2, update the chapter's persistent ledger at `Fact Check/Ch. NN — Title.md`, and the read records in `Fact Check/Claims/Ch NN.jsonl`. The audit is incomplete until the ledger is written. The core requirements:

1. **Claims Register:** every disputable claim gets a row — claim, tier, status, source with page, footnote ref, notes, date — whether or not it became a footnote.
2. **Source Pages Consulted:** every book/page range actually read, with results, **including negative results**. Format-tag each source (`PDF-scan`, `EPUB`, `EPUB-to-PDF`, `TXT`, `Web`, `Print`, `Audio`); footnotes cite structural anchors (chapter, section, heading), never page numbers, for reflowed formats. A page-number mismatch between a citation and a different printing is the normal condition; cite by structure.
3. **Original-Language Verification Log:** any claimed Greek word in a quoted passage gets a checked yes/no row. False Greek claims were the largest fabrication category in the original author's audits. **Run the mechanical audit first:** `python3 servers/greek/greek_audit.py "<chapter file>"` from this repository — it extracts every Greek run, checks quotes against the pinned New Testament and Septuagint texts by exact comparison, and emits a MATCH/MISMATCH table. Paste the table's problem rows into the ledger; hand-check only the NO-REF rows (classical and other authors without a reference) and MISMATCH findings.
4. **Editorial Decisions:** changes made and why, dated — prevents re-insertion of deliberately removed material.
5. **Rejected claims:** anything checked and found unsupported that the chapter does not assert. This is where such material lives — never in a footnote.
6. **Open Questions:** unresolved claims with the exhausted search trail (see Working Principles above).

**Cumulative, never overwritten.** Each audit adds rows and updates statuses with dates; prior entries stay. One file per chapter, the single source of truth for what has been checked there.
